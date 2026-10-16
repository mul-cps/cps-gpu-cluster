#!/usr/bin/env python3
"""Inert CPU-only Root transport for one freshly attributed QA GPU descriptor."""
import argparse,array,ctypes as C,hashlib,json,os,platform,re,socket,struct,sys,time,uuid
from pathlib import Path

def require(value,message):
    if not value:raise ValueError(message)

def canonical_uuid(value):
    require(isinstance(value,str) and str(uuid.UUID(value))==value and uuid.UUID(value).int!=0,'Canonical nonzero UUID required')

def process_proof(expected,trial):
    require(isinstance(expected,dict) and expected.get('kind')=='root-read-only-importer-attribution'
        and expected.get('trial_id')==trial,'Fresh trusted process attribution required')
    pid=expected['host_pid'];require(type(pid) is int and pid==expected['host_tgid'] and pid>1,'Exact host thread-group required')
    require(0<=time.time_ns()-expected['observed_time_ns']<=20_000_000_000,'Process attribution expired')
    canonical_uuid(expected['pod_uid']);canonical_uuid(expected['driver_generation'])
    require(expected['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Actual boot changed')
    p=Path('/proc')/str(pid);start=lambda:int((p/'stat').read_text().rsplit(') ',1)[1].split()[19])
    require(start()==expected['pid_start_ticks'],'Original process lifetime changed')
    status=dict(line.split(':',1) for line in (p/'status').read_text().splitlines() if ':' in line)
    require([int(v) for v in status['Uid'].split()]==[1000]*4 and [int(v) for v in status['Gid'].split()]==[100]*4,
            'Only ordinary notebook UID1000/GID100 processes allowed')
    require([int(v) for v in status['NSpid'].split()]==expected['nspid'] and expected['nspid'][-1]==expected['namespace_pid'],
            'Actual namespace PID changed')
    require(hashlib.sha256((p/'cmdline').read_bytes()).hexdigest()==expected['cmdline_sha256'],'Endpoint command changed')
    relative=(p/'cgroup').read_text().strip().split('::',1)[1]
    require(relative==expected['process_cgroup_relative'] and '..' not in relative.split('/'),'Actual cgroup changed')
    token='pod'+expected['pod_uid'].replace('-','_')+'.slice';parts=relative.split('/')
    parents=[i for i,v in enumerate(parts) if v.endswith(token)];require(len(parents)==1,'Exact Pod parent required')
    parent=Path('/sys/fs/cgroup')/('/'.join(parts[:parents[0]+1]).lstrip('/'))
    st=parent.stat();require(st.st_ino==expected['pod_cgroup_inode'],'Actual Pod parent inode changed')
    record=Path('/run/cps-native-gpu/journal')/(expected['pod_uid']+'.json')
    fd=os.open(record,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd);require(info.st_uid==0 and info.st_mode&0o777==0o600 and info.st_nlink==1,'Original protected journal required')
        raw=os.read(fd,1048577);require(len(raw)==info.st_size and len(raw)<=1048576,'Bounded complete journal required');value=json.loads(raw)
    finally:os.close(fd)
    require(value['state']=='sealed' and value['intent']['pod_uid']==expected['pod_uid']
        and value['identity']['cgroup_inode']==st.st_ino and value['identity']['cgroup_device']==st.st_dev
        and value['identity']['driver_generation']==expected['driver_generation']
        and value['intent']['gpu_uuid']==expected['gpu_uuid'],'Sealed native parent changed')
    require(start()==expected['pid_start_ticks'],'Process changed during attribution verification')
    return p

def relay(request):
    require(os.geteuid()==0 and platform.machine()=='x86_64','Explicit trusted x86_64 Root worker required')
    require(isinstance(request,dict) and set(request)=={'trial_id','exporter','importer','export_fd','fd_stat'},'Closed descriptor request required')
    trial=request['trial_id'];canonical_uuid(trial);source=request['exporter'];target=request['importer']
    process_proof(source,trial);target_path=process_proof(target,trial)
    require(source['host_pid']!=target['host_pid'] and source['gpu_uuid']==target['gpu_uuid']
        and source['driver_generation']==target['driver_generation'],'Distinct same-GPU/epoch endpoint processes required')
    require(type(request['export_fd']) is int and 2<request['export_fd']<4096,'Bounded explicit exported descriptor required')
    pfd=netfd=copied=None
    try:
        pfd=os.pidfd_open(source['host_pid'],0);netfd=os.open(target_path/'ns/net',os.O_RDONLY)
        net_inode=os.fstat(netfd).st_ino;require(net_inode==(target_path/'ns/net').stat().st_ino,'Target network namespace changed')
        process_proof(source,trial);process_proof(target,trial)
        libc=C.CDLL(None,use_errno=True);libc.syscall.restype=C.c_long
        copied=libc.syscall(C.c_long(438),C.c_int(pfd),C.c_int(request['export_fd']),C.c_uint(0))
        if copied<0:raise OSError(C.get_errno(),'Exact exporter descriptor duplication failed')
        st=os.fstat(copied);require({k:getattr(st,'st_'+k) for k in ('dev','ino','mode','rdev')}==request['fd_stat'],'Exported descriptor identity changed')
        process_proof(source,trial);process_proof(target,trial)
        libc.setns.argtypes=[C.c_int,C.c_int];libc.setns.restype=C.c_int
        if libc.setns(netfd,0)!=0:raise OSError(C.get_errno(),'Target network namespace unavailable')
        os.setgroups([]);os.setgid(100);os.setuid(1000)
        require(os.getresuid()==(1000,1000,1000) and os.getresgid()==(100,100,100),'Permanent ordinary identity drop required')
        with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as connection:
            connection.settimeout(5);connection.connect('\0cps-qa-vmm-'+trial)
            pid,uid,gid=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            require((pid,uid,gid)==(target['host_pid'],1000,100),'Exact attributed importer socket peer required')
            header=json.dumps(dict(trial_id=trial,exporter_pod_uid=source['pod_uid'],bytes=67108864),separators=(',',':')).encode()
            require(connection.sendmsg([header],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[copied]))])==len(header),
                    'Complete single descriptor delivery required')
        return dict(state='descriptor-delivered',trial_id=trial,exporter_host_pid=source['host_pid'],importer_host_pid=target['host_pid'],
                    importer_network_inode=net_inode,uid=1000,gid=100,gpu_calls=False,mount_changes=False)
    finally:
        for fd in (copied,netfd,pfd):
            if fd is not None and fd>=0:os.close(fd)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if not args.execute:print(json.dumps(dict(state='inert',gpu_calls=False,fd_copies=False)));return
    raw=sys.stdin.buffer.read(65537);require(len(raw)<=65536,'Bounded Root request required')
    print(json.dumps(relay(json.loads(raw))))

if __name__=='__main__':main()

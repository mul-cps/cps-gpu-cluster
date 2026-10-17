#!/usr/bin/env python3
"""Root-only bounded one-FD VMM bridge; default inert, no CUDA/cap calls."""
import argparse,array,select,socket,sys,types,threading
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import uuid

BOOT = '209f8bc9-a478-48e4-925a-6e07ffa56f7a'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'

def require(ok, message):
    if not ok: raise ValueError(message)

def parse_start(value, host_pid):
    prefix, suffix = value.rsplit(')', 1)
    require(prefix.split('(', 1)[0].strip() == str(host_pid), 'Actual host PID stat required')
    fields = suffix.split(); require(len(fields) >= 20 and fields[19].isdecimal(), 'Readable actual PID start ticks required')
    return int(fields[19])

def status_fields(value):
    fields = {}
    for line in value.splitlines():
        key, separator, rest = line.partition(':')
        if separator:
            require(key not in fields, 'Duplicate process status field')
            fields[key] = rest.strip()
    return fields

def normalized_cgroup(value):
    lines = value.splitlines(); require(len(lines) == 1 and lines[0].startswith('0::/'), 'Exact default unified cgroup required')
    path = lines[0][3:]
    require('..' not in path.split('/') and '//' not in path, 'Canonical process cgroup required'); return path

def observe(request, proc=Path('/proc'), cgroup=Path('/sys/fs/cgroup')):
    require(set(request) == {'trial_id','namespace_pid','identity','role','expect','source_sha256'}, 'Closed read-only attribution request required')
    trial, namespace_pid, identity = request['trial_id'], request['namespace_pid'], request['identity']
    require(str(uuid.UUID(trial)) == trial and uuid.UUID(trial).int != 0 and type(namespace_pid) is int and namespace_pid > 0,
        'Canonical current trial and actual namespace PID required')
    relative = identity['cgroup_relative']
    require(isinstance(relative, str) and relative.startswith('/kubepods.slice/') and '..' not in relative.split('/')
        and identity['cgroup_path'] == '/sys/fs/cgroup' + relative and identity['boot_id'] == BOOT
        and identity['gpu_uuid'] == GPU, 'Exact preflight sealed Pod authority required')
    parent = cgroup / relative.lstrip('/'); before = parent.stat(follow_symlinks=False)
    require(stat.S_ISDIR(before.st_mode) and (before.st_dev, before.st_ino) == (identity['cgroup_device'], identity['cgroup_inode']),
        'Actual finite parent inode required')
    matches = []
    deadline = time.monotonic() + 8
    for item in proc.iterdir():
        require(time.monotonic() < deadline, 'Bounded process observation exceeded')
        if not item.name.isdecimal(): continue
        host_pid = int(item.name)
        try:
            current = normalized_cgroup((item / 'cgroup').read_text())
            if current != relative and not current.startswith(relative + '/'): continue
            status = status_fields((item / 'status').read_text())
            nspids = status.get('NSpid', '').split()
            require(nspids and all(p.isdecimal() for p in nspids) and int(nspids[0]) == host_pid, 'Actual host namespace PID chain required')
            if int(nspids[-1]) != namespace_pid: continue
            require(status.get('Uid', '').split() == ['1000'] * 4 and status.get('Gid', '').split() == ['100'] * 4,
                'Actual notebook process UID/GID required')
            require(status.get('Tgid') == item.name, 'Importing process must be the actual thread-group leader')
            cmdline = (item / 'cmdline').read_bytes()
            require(len(cmdline) <= 100000, 'Bounded probe argv required')
            argv = cmdline.rstrip(b'\0').split(b'\0')
            for flag, value in ((b'--trial-id',trial.encode()),(b'--role',request['role'].encode()),(b'--gpu-uuid',GPU.encode()),(b'--expect',request['expect'].encode()),(b'--source-sha256',request['source_sha256'].encode()),(b'--expected-pod-uid',identity['pod_uid'].encode())):
                require(argv.count(flag) == 1 and argv.index(flag) + 1 < len(argv) and argv[argv.index(flag) + 1] == value,
                    'Actual trusted importer argv must match current trial')
            source_path=Path('/tmp')/('cpv-'+uuid.UUID(trial).hex[:16]+'-'+request['role']+'-src')/'vmm_endpoint.py'
            actual_source=item/'root'/str(source_path).lstrip('/');info=actual_source.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_uid==1000 and info.st_nlink==1 and stat.S_IMODE(info.st_mode)==0o600
                and hashlib.sha256(actual_source.read_bytes()).hexdigest()==request['source_sha256'], 'Actual mapped source bytes required')
            source_after=actual_source.lstat()
            require(all(getattr(info,k)==getattr(source_after,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'Mapped source replaced while hashing')
            source_parent=actual_source.parent.lstat()
            require(stat.S_ISDIR(source_parent.st_mode) and source_parent.st_uid==1000 and stat.S_IMODE(source_parent.st_mode)==0o700,'Fresh private source directory required')
            require(argv.count(str(source_path).encode())==1,'Actual staged source executable path required')
            start = parse_start((item / 'stat').read_text(), host_pid)
            pidns = (item / 'ns/pid').stat()
            # Read status independently again; no PID-reuse inference from stale text.
            status_after = status_fields((item / 'status').read_text())
            require(status_after.get('NSpid') == status.get('NSpid') and status_after.get('Tgid') == status.get('Tgid')
                and status_after.get('Uid') == status.get('Uid') and status_after.get('Gid') == status.get('Gid')
                and normalized_cgroup((item / 'cgroup').read_text()) == current
                and parse_start((item / 'stat').read_text(), host_pid) == start
                and (item / 'ns/pid').stat().st_ino == pidns.st_ino, 'Live process identity changed during observation')
            matches.append({'host_pid': host_pid, 'host_tgid': host_pid, 'pid_start_ticks': start,
                'namespace_pid': namespace_pid, 'nspid': [int(v) for v in nspids], 'pid_namespace_inode': pidns.st_ino,
                'process_cgroup_relative': current, 'pod_cgroup_inode': before.st_ino,
                'cmdline_sha256':hashlib.sha256(cmdline).hexdigest(),'network_namespace_inode':(item/'ns/net').stat().st_ino,'source_sha256':request['source_sha256']})
        except FileNotFoundError:
            # Other processes may naturally exit; the held importer must be found uniquely.
            continue
    after = parent.stat(follow_symlinks=False)
    require(len(matches) == 1 and stat.S_ISDIR(after.st_mode) and (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino),
        'One unchanged actual importing process required')
    inventory_raw = (proc / 'driver/nvidia/gpus/0000:06:10.0/cps_native_caps').read_bytes()
    require(len(inventory_raw) <= 262144, 'Bounded native inventory required')
    inventory = json.loads(inventory_raw)
    require(isinstance(inventory, dict) and set(inventory) == {'version','backend','gpu_uuid','gpu_id','entries'}
        and type(inventory['version']) is int and inventory['version'] == 1 and inventory['backend'] == 'misc-fallback'
        and inventory['gpu_uuid'] == GPU and type(inventory['gpu_id']) is int and 0 <= inventory['gpu_id'] < 2**32
        and isinstance(inventory['entries'], list) and len(inventory['entries']) <= 256,
        'Actual GPU ID for kernel denial attribution required')
    require(inventory['gpu_id']==1552,'Current selected GPU1552 kernel identity required')
    rows = {}
    for row in inventory['entries']:
        require(isinstance(row, dict) and set(row) == {'cgroup_id','kernfs_id','inode','offline','pinned','default_hierarchy','soft','hard','used'}
            and all(type(row[k]) is int and 0 <= row[k] < 2**64 for k in ('cgroup_id','kernfs_id','inode','soft','hard','used'))
            and all(type(row[k]) is bool for k in ('offline','pinned','default_hierarchy'))
            and row['cgroup_id'] == row['kernfs_id'] == row['inode'] > 0 and row['inode'] not in rows,
            'Closed unique actual native cap rows required')
        rows[row['inode']] = row
    actual = rows.get(identity['cgroup_inode'])
    require(actual is not None and actual['offline'] is False and actual['pinned'] is True
        and actual['default_hierarchy'] is True and actual['soft'] == actual['hard'] == 5368709120
        and actual['used'] <= 5368709120, 'Importing parent must still have an active finite5GiB cap')
    return {'kind': 'root-read-only-importer-attribution', 'trial_id': trial, 'boot_id': BOOT, 'gpu_uuid': GPU,
        'gpu_id': inventory['gpu_id'], 'pod_uid': identity['pod_uid'], 'driver_generation': identity['driver_generation'],
        'observed_time_ns': time.time_ns(), 'observed_monotonic_ns': time.monotonic_ns(), **matches[0], 'gpu_calls': False}

ROOT=Path('/run/cps-native-gpu/operator/native-vmm-distinct-process-20261017')
GENERATION='b10498fc-9153-4394-875a-ea7cfb498625'
PODS=frozenset()  # Filled only from separately hash-pinned Root0400 target manifest.

def validate_request(r):
    require(isinstance(r,dict) and set(r)=={'trial_id','transfer','exporter','importer'} and str(uuid.UUID(r['trial_id']))==r['trial_id'] and uuid.UUID(r['trial_id']).int,
        'Closed canonical bridge request required')
    require(r['transfer'] in ('positive','cross'),'Only current positive/cross transfer allowed')
    for key,role,expect in [('exporter','exporter','allow'),('importer','positive' if r['transfer']=='positive' else 'importer','allow' if r['transfer']=='positive' else 'deny')]:
        endpoint=r[key]
        require(isinstance(endpoint,dict) and set(endpoint)=={'role','expect','namespace_pid','identity'} and endpoint['role']==role and endpoint['expect']==expect
            and type(endpoint['namespace_pid'])is int and endpoint['namespace_pid']>0 and endpoint['identity']['pod_uid'] in PODS
            and endpoint['identity']['driver_generation']==GENERATION,'Exact current source-owned endpoint required')
    require((r['exporter']['identity']['pod_uid']==r['importer']['identity']['pod_uid'])==(r['transfer']=='positive'),
        'Positive must share the actual parent; cross must have distinct actual parents')

def verify_peer(sock,a):
    pid,uid,gid=array.array('i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
    require((pid,uid,gid)==(a['host_tgid'],1000,100),'Socket peer must be exact actual ordinary endpoint')

def forward(e,exporter,importer,trial,transfer,source):
    descriptor=None
    try:
        e.send_frame(exporter,{'op':'export','trial_id':trial,'transfer':transfer,'source_sha256':source})
        value,descriptor=e.receive_frame(exporter,want_fd=True)
        require(set(value)=={'phase','trial_id','transfer','backing_bytes','fd_identity'} and value['phase']=='exported-fd'
            and value['trial_id']==trial and value['transfer']==transfer and type(value['backing_bytes'])is int and value['backing_bytes']==67108864
            and value['fd_identity']==e.fd_identity(descriptor),'Exact one received64MiB backing descriptor required')
        e.valid_fd_identity(value['fd_identity']);e.send_frame(importer,value,descriptor)
        ack,_=e.receive_frame(importer)
        require(ack=={'phase':'fd-received','trial_id':trial,'transfer':transfer,'fd_identity':value['fd_identity']},'Exact forwarded descriptor acknowledgement required')
        e.send_frame(exporter,{'op':'forwarded','trial_id':trial,'transfer':transfer})
        return value['fd_identity']
    finally:
        if descriptor is not None:os.close(descriptor)

def protected(path,digest):
    parent=path.parent.lstat();require(stat.S_ISDIR(parent.st_mode) and parent.st_uid==parent.st_gid==0 and stat.S_IMODE(parent.st_mode)==0o700,'Root700 source directory required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd);raw=os.read(fd,100001);after=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==info.st_gid==0 and info.st_nlink==1 and stat.S_IMODE(info.st_mode)==0o400
          and 0<len(raw)<=100000 and all(getattr(info,k)==getattr(after,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
          and hashlib.sha256(raw).hexdigest()==digest,'Exact immutable Root400 source pin required');return raw
    finally:os.close(fd)

def connect_endpoint(e,trial,request,a):
    path=Path('/proc')/str(a['host_tgid'])/'root'/str(e.socket_path(trial,request['role'])).lstrip('/')
    require(len(str(path).encode())<108,'Bounded actual pathname Unix address required')
    parent=path.parent.lstat();before=path.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid==1000 and stat.S_IMODE(parent.st_mode)==0o700
        and stat.S_ISSOCK(before.st_mode) and before.st_uid==1000 and stat.S_IMODE(before.st_mode)==0o600,'Exact private endpoint socket inode required')
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET);sock.settimeout(10)
    try:
        sock.connect(str(path));verify_peer(sock,a);after=path.lstat()
        require((before.st_dev,before.st_ino)==(after.st_dev,after.st_ino),'Socket path replaced during connection')
        return sock,{'path':str(path),'device':before.st_dev,'inode':before.st_ino,'host_tgid':a['host_tgid'],'uid':1000,'gid':100}
    except BaseException:sock.close();raise

def store(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    with os.fdopen(fd,'w') as f:json.dump(value,f,sort_keys=True,separators=(',',':'),allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(parent)
    finally:os.close(parent)

def main(argv=None):
    p=argparse.ArgumentParser(description='Qualification-only Root one-FD bridge; inert default')
    p.add_argument('--execute',action='store_true');p.add_argument('--qualification',action='store_true');p.add_argument('--source-sha256');p.add_argument('--endpoint-source-sha256');p.add_argument('--targets-sha256')
    args=p.parse_args(argv)
    if not args.execute:print(json.dumps({'state':'inert','gpu_calls':False,'proc_reads':False,'host_writes':False}));return
    require(args.qualification and os.getuid()==os.geteuid()==os.getgid()==os.getegid()==0 and Path(__file__)==ROOT/'vmm_bridge.py'
        and socket.gethostname()=='k3s-wk-gpu2' and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'Exact qualification Root host bridge required')
    global PODS
    targets=json.loads(protected(ROOT/'targets.json',args.targets_sha256))
    require(type(targets)is dict and set(targets)=={'pods','node','observer'} and set(targets['pods'])=={'a','b'},'Closed Root target manifest required')
    PODS=frozenset(row['uid']for row in targets['pods'].values())
    require(len(PODS)==2 and all(str(uuid.UUID(uid))==uid and uuid.UUID(uid).int for uid in PODS),'Two exact manifest Pod UIDs required')
    protected(ROOT/'vmm_bridge.py',args.source_sha256);raw=protected(ROOT/'vmm_endpoint.py',args.endpoint_source_sha256)
    e=types.ModuleType('root_vmm_protocol');e.__file__=str(ROOT/'vmm_endpoint.py');exec(compile(raw,e.__file__,'exec'),e.__dict__)
    packet=bytearray();deadline=time.monotonic()+15
    while not packet.endswith(b'\n'):
        require(time.monotonic()<deadline and select.select([0],[],[],max(0,deadline-time.monotonic()))[0],'Bounded bridge request required')
        piece=os.read(0,65537-len(packet));require(piece and len(packet)+len(piece)<=65536,'Complete bounded bridge request required');packet.extend(piece)
    require(packet.count(b'\n')==1,'One complete bridge request required');r=e.parse(packet);validate_request(r)
    session=ROOT/'bridge-sessions';info=session.lstat();require(stat.S_ISDIR(info.st_mode) and info.st_uid==info.st_gid==0 and stat.S_IMODE(info.st_mode)==0o700,'Root700 bridge sessions required')
    directory=session/(r['trial_id']+'-'+r['transfer']);directory.mkdir(mode=0o700)
    parent=os.open(session,os.O_RDONLY|os.O_DIRECTORY);os.fsync(parent);os.close(parent)
    sockets=[];pidfds=[];timer=threading.Timer(40,lambda:os._exit(124));timer.daemon=True;timer.start()
    try:
        attrs={};requests={};socket_proofs={};stage='attribution'
        for key in ('exporter','importer'):
            request={'trial_id':r['trial_id'],**r[key],'source_sha256':args.endpoint_source_sha256};requests[key]=request
            stage=key+'-attribution';a=observe(request);attrs[key]=a;pidfd=os.pidfd_open(a['host_tgid']);pidfds.append(pidfd)
            require(not select.select([pidfd],[],[],0)[0],'Original endpoint already exited')
            stage=key+'-socket';conn,proof=connect_endpoint(e,r['trial_id'],r[key],a);sockets.append(conn);socket_proofs[key]=proof
        stage='one-fd-forward';fd=forward(e,sockets[0],sockets[1],r['trial_id'],r['transfer'],args.endpoint_source_sha256)
        for key,pidfd in zip(('exporter','importer'),pidfds):
            require(not select.select([pidfd],[],[],0)[0],'Endpoint exited during bridge')
            stage=key+'-identity-recheck';fresh=observe(requests[key]);require(all(fresh[k]==attrs[key][k]for k in ('host_tgid','pid_start_ticks','pod_uid','pod_cgroup_inode','process_cgroup_relative','cmdline_sha256','pid_namespace_inode','network_namespace_inode','source_sha256','gpu_id')),'Actual endpoint identity changed during FD bridge')
        proof={'state':'one-bounded-vmm-descriptor-forwarded','trial_id':r['trial_id'],'transfer':r['transfer'],'bridge_source_sha256':args.source_sha256,
            'endpoint_source_sha256':args.endpoint_source_sha256,'descriptor_count':1,'backing_bytes':67108864,'fd_identity':fd,
            'exporter_attribution':attrs['exporter'],'importer_attribution':attrs['importer'],'socket_proofs':socket_proofs,
            'network_namespace_entered':False,'gpu_calls':False,'production_qualified':False}
        store(directory/'proof.json',proof);print(json.dumps(proof,sort_keys=True,allow_nan=False),flush=True)
    except BaseException as error:
        store(directory/'error.json',{'error_type':type(error).__name__,'error_message':str(error).replace('\x00','?')[:512],
            'stage':stage,'trial_id':r['trial_id'],'transfer':r['transfer'],'production_qualified':False});raise
    finally:
        for s in sockets:s.close()
        for fd in pidfds:os.close(fd)
        timer.cancel()
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Default-inert, read-only observation of the actual sealed QA cohort on GPU2."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

CONTROLLER_SHA256='b4e93ae91fb61572e6be4637cebbd9a3ed31ded0a5e2e21e79971ea363f4df80'
IMAGE='ghcr.io/mul-cps/cps-jupyter-notebook@sha256:5427088986bc06ad0713875d1aa2f31439f0bd1fbe6099d4669570fcf3e85be4'

def require(value,message):
    if not value:raise ValueError(message)

def controller(path):
    raw=Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest()==CONTROLLER_SHA256,'Reviewed controller source required')
    module=types.ModuleType('qa_controller');module.__file__=str(path)
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module

def protected_bytes(path,uid):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==uid and stat.S_IMODE(before.st_mode)==0o600
                and before.st_nlink==1 and before.st_size<=32768,'Protected original QA record required')
        raw=os.read(fd,32769);after=os.fstat(fd)
        require(len(raw)<=32768 and all(getattr(before,k)==getattr(after,k) for k in
            ('st_dev','st_ino','st_uid','st_gid','st_mode','st_size','st_mtime_ns','st_ctime_ns')),
            'QA record changed while reading')
        return raw
    finally:os.close(fd)

def sealed_record(backend,journal,intent):
    record=journal.read(intent.pod_uid)
    require(record is not None and record.intent==intent and record.state=='sealed'
            and record.readback==record.limit and record.limit.soft==record.limit.hard==intent.cap_bytes,
            'Exact original sealed QA ownership required')
    owner=backend.check_owner(record.identity)
    require(owner.epoch==record.identity.epoch and owner.healthy is True and owner.cgroup_exists is True
            and owner.pod_uid==intent.pod_uid and owner.spec_sha256==intent.spec_sha256
            and owner.cgroup_device==record.identity.cgroup_device
            and owner.cgroup_inode==record.identity.cgroup_inode and owner.descendants_unlimited is True,
            'Fresh exact live owner/epoch/parent proof required')
    require(backend.read_limit_readonly(record.identity)==record.limit
            and backend.read_gate(record.identity)==record.receipt(),'Exact native limit and original seal required')
    jraw=protected_bytes(journal.path(intent.pod_uid),backend.uid)
    graw=protected_bytes(backend.state/'receipts'/(intent.pod_uid+'.json'),backend.uid)
    require(backend.m.CapRecord.from_dict(json.loads(jraw))==record and json.loads(graw)==record.receipt(),
            'Protected receipt/journal changed during observation')
    limit=backend._raw(record.identity)
    require(type(limit) is dict and set(limit)=={'soft','hard','used'}
            and limit['soft']==limit['hard']==intent.cap_bytes
            and type(limit['used']) is int and 0<=limit['used']<=intent.cap_bytes,
            'Fresh exact bounded native readback required')
    return {'pod_uid':intent.pod_uid,'intent':intent.to_dict(),'identity':record.identity.to_dict(),
            'seal_id':record.seal_id,'journal_sha256':hashlib.sha256(jraw).hexdigest(),
            'gate_sha256':hashlib.sha256(graw).hexdigest(),
            'limit':limit}

def checked_pod(pod,intent):
    require(pod['metadata']['uid']==intent.pod_uid and pod['metadata']['namespace']==intent.namespace
            and pod['metadata']['name']==intent.name and not pod['metadata'].get('deletionTimestamp')
            and pod['spec']['nodeName']==intent.node and pod['status']['phase']=='Running',
            'Actual live exact QA Pod required')
    spec=[c for c in pod['spec']['containers'] if c['name']=='notebook']
    statuses=[c for c in pod['status']['containerStatuses'] if c['name']=='notebook']
    require(len(spec)==len(statuses)==1 and spec[0]['image']==IMAGE,'Exact notebook542 runtime required')
    status=statuses[0]
    require(status['ready'] is True and status['restartCount']==0 and 'running' in status['state']
            and status['imageID'].split('@')[-1]==IMAGE.split('@')[-1],
            'Ready un-restarted actual notebook image required')
    return {'uid':intent.pod_uid,'spec':pod['spec'],'status':status}

def process(backend,intent,record,reader):
    cri=reader(intent);status=cri['status'];cid=status['id'];pid=cri['info']['pid']
    require(status['state']=='CONTAINER_RUNNING' and type(pid) is int and pid>0
            and all(status['labels'].get(k)==v for k,v in {
                'io.kubernetes.pod.uid':intent.pod_uid,'io.kubernetes.pod.namespace':intent.namespace,
                'io.kubernetes.pod.name':intent.name,'io.kubernetes.container.name':'notebook'}.items()),
            'Actual notebook CRI identity required')
    root=backend.proc/str(pid)
    start=int((root/'stat').read_text().rsplit(') ',1)[1].split()[19])
    groups=(root/'cgroup').read_text().splitlines()
    require(len(groups)==1 and groups[0].startswith('0::/'),'Actual unified notebook process required')
    leaf=groups[0][3:]
    require(Path(leaf).name=='cri-containerd-'+cid+'.scope'
            and str(Path(leaf).parent)==record.identity.cgroup_relative,'Exact sealed Pod-parent process required')
    backend.manual.safe_path(backend.cg,leaf)
    return {'container_id':cid,'host_pid':pid,'pid_start_ticks':start,'cgroup_relative':leaf}

def readonly(event,args):
    if event=='open':
        mode=args[1];flags=args[2]
        require(not (isinstance(mode,str) and any(c in mode for c in 'wax+'))
                and not (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)),
                'Read-only observer forbids writes')
    require(event not in {'os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink',
        'os.chmod','os.chown','os.truncate','os.utime'},'Read-only observer forbids mutation')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true');p.add_argument('--controller',type=Path)
    p.add_argument('--bundle',type=Path);p.add_argument('--intent-a',type=Path);p.add_argument('--intent-a-sha256')
    p.add_argument('--intent-b',type=Path);p.add_argument('--intent-b-sha256');p.add_argument('--crictl',type=Path)
    p.add_argument('--cri-socket',default='unix:///run/k3s/containerd/containerd.sock')
    p.add_argument('--service-account',type=Path)
    p.add_argument('--cohort-uid');p.add_argument('--retirement',type=Path);p.add_argument('--retirement-sha256')
    args=p.parse_args(argv)
    if not args.execute:print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False}));return
    require(os.geteuid()==0 and all((args.controller,args.bundle,args.intent_a,args.intent_a_sha256,
        args.intent_b,args.intent_b_sha256,args.crictl,args.service_account)),'Explicit Root readonly QA inputs required')
    c=controller(args.controller);modules=c.load_bundle(args.bundle)
    m,b,ident,nvml,tr,health=[modules[name] for name in ('native_gpu_controller.py','native_node/backend.py',
        'native_node/identity.py','native_node/nvml.py','native_node/transport.py','native_gpu_health.py')]
    intents=[]
    for path,pin in ((args.intent_a,args.intent_a_sha256),(args.intent_b,args.intent_b_sha256)):
        raw=path.read_bytes();require(hashlib.sha256(raw).hexdigest()==pin,'Actual bound intent raw hash changed')
        intent=m.CapIntent(**c.document(raw))
        require(intent.namespace==c.NS and intent.node==c.NODE and intent.node_uid==c.NODE_UID
                and intent.gpu_uuid==c.GPU and intent.cap_mib==5120,'Exact current QA cohort required')
        intents.append(intent)
    state=c.cohort_state(args.cohort_uid)
    suffix='-'+args.cohort_uid[:8] if args.cohort_uid else ''
    require({i.name for i in intents}=={'native-qa147-a'+suffix,'native-qa147-b'+suffix}
            and len({i.pod_uid for i in intents})==2,'Two distinct actual QA Pods required')
    sys.addaudithook(readonly)
    kube=tr.Kubernetes(args.service_account)
    ns=kube.call('GET','/api/v1/namespaces/'+c.NS)
    require(ns['metadata']['uid']==c.NS_UID and not ns['metadata'].get('deletionTimestamp'),'Actual namespace UID changed')
    node=kube.node(c.NODE)
    require(node['metadata']['uid']==c.NODE_UID and node['status']['nodeInfo']['bootID']==c.BOOT,'Actual Node/boot changed')
    def healthy():
        require(health.validate_native_driver_health(authority_directory=c.AUTHORITY,boot_id=c.BOOT)==c.GENERATION,
                'Exact guarded147 current driver health required');return True
    driver=nvml.Nvml()
    try:
        require(driver.version=='615.71.09','Exact loaded NVML driver required')
        reader=tr.cri_reader(args.crictl,args.cri_socket,gate_name='notebook')
        def make_backend(enrolled,root):
            return b.QualificationNodeBackend(m,ident,intents=enrolled,driver=driver,get_pod=kube.pod,
                get_node=kube.node,get_cri=reader,delete_pod=lambda _:require(False,'Readonly observer cannot delete'),
                gpu_clients=lambda _:require(False,'Readonly observer never cleans'),health=healthy,state_root=Path(root))
        backend=make_backend(intents,state)
        retired=c.retirement_inputs(args,m,b,make_backend,state)
        journal=m.PrivateJournal.__new__(m.PrivateJournal);journal.directory=Path(state)/'journal'
        require({r.intent.pod_uid for r in journal.records()}=={i.pod_uid for i in intents},'Complete exact QA journal required')
        before=[checked_pod(kube.pod(i),i) for i in intents]
        records=[journal.read(i.pod_uid) for i in intents]
        processes=[process(backend,i,r,reader) for i,r in zip(intents,records)]
        rows=[sealed_record(backend,journal,i) for i in intents]
        actual=backend._inventory(records[0].identity)
        normalized=deepcopy(actual)
        for row in normalized['entries']:
            require(type(row.get('used')) is int and 0<=row['used']<=5120*1048576
                    and row.get('soft')==row.get('hard')==5120*1048576,'Exact live bounded native accounting required')
            row['used']=0  # Reuse original closed-shape/ownership validation; retain actual charge below.
        c.inventory(normalized,{r.identity.cgroup_inode for r in records},retired=retired)
        require(len(actual['entries'])==2+len(retired),'Exactly current and independently proven retired QA caps required')
        require(processes==[process(backend,i,r,reader) for i,r in zip(intents,records)]
                and before==[checked_pod(kube.pod(i),i) for i in intents],'Process/Pod changed across fresh host proof')
        healthy()
        require(c.retirement_inputs(args,m,b,make_backend,state)==retired,'Original retired entries changed during proof')
        print(json.dumps({'version':1,'observed_monotonic_ns':time.monotonic_ns(),'pods':before,
            'processes':processes,'targets':rows,'inventory':actual,'hardware_qualified':False,
            'production_qualified':False},sort_keys=True),flush=True)
    finally:driver.close()

if __name__=='__main__':main()

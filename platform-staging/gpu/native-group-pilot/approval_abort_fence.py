"""Default-inert, read-only Root observer holding all existing native locks.

Run only in the reviewed maintenance copy of the node Pod, after Root stops the
actual node writer and excludes new Starts. No driver, cap, Pod, enrollment or
ledger writes occur here. Capture derives all proof fields from actual reads;
execute holds the same locks across each live publisher verify RPC.
"""
import argparse
import base64
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime,timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
import time
from types import SimpleNamespace

import abort_before_gate as old
import approval_before_gate as publisher
import native_approval_revision as approval

require,closed=old.require,old.closed


def protected(path,*,uid=0,modes=(0o400,0o600),limit=1048576):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==uid and stat.S_IMODE(info.st_mode) in modes
            and info.st_nlink==1 and info.st_size<=limit,'Protected bounded original file required')
        raw=os.read(fd,limit+1);require(len(raw)<=limit,'Oversized protected file')
        return raw
    finally:os.close(fd)


def directory(path,*,uid=0):
    info=Path(path).lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid==uid and stat.S_IMODE(info.st_mode)==0o700,
        'Existing protected root0700 directory required')
    return info


def acquire_lock(path,*,uid=0):
    fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        verify_lock(path,fd,uid=uid);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);return fd
    except BaseException:os.close(fd);raise


def verify_lock(path,fd,*,uid=0):
    actual=os.fstat(fd);current=Path(path).lstat()
    require(stat.S_ISREG(actual.st_mode) and actual.st_uid==uid and stat.S_IMODE(actual.st_mode)==0o600
        and actual.st_nlink==1 and (actual.st_dev,actual.st_ino)==(current.st_dev,current.st_ino),
        'Original protected native lock inode must remain held')


def capture_journals(root,target,*,uid=0):
    directory(root,uid=uid);paths=sorted(Path(root).glob('*.json'))
    require(1<=len(paths)<=256,'Complete bounded existing retired journal required')
    result=[]
    for path in paths:
        require(old.valid_uuid(path.stem) and path.stem!=target,'Target UID has a transaction; never-gated recovery denied')
        raw=protected(path,uid=uid,modes=(0o600,),limit=65536)
        result.append(dict(pod_uid=path.stem,raw_base64=base64.b64encode(raw).decode(),
            raw_sha256='sha256:'+hashlib.sha256(raw).hexdigest()))
    return result


def target_tasks(root,target,*,limit=8192):
    root=Path(root);require(root.is_dir() and not root.is_symlink(),'Actual host cgroup hierarchy required')
    count=0;tasks=set();deadline=time.monotonic()+10
    def failed(error):raise error
    for folder,dirs,files in os.walk(root,onerror=failed,followlinks=False):
        count+=1;require(count<=limit and time.monotonic()<deadline,'Complete cgroup walk bound exceeded')
        require(all(not (Path(folder)/name).is_symlink() for name in dirs),'Symlink in cgroup walk denied')
        if target in folder or target.replace('-','_') in folder:
            require('cgroup.procs' in files,'Exact target cgroup tasks must be observable')
            text=(Path(folder)/'cgroup.procs').read_text()
            require(len(text)<=65536,'Bounded exact cgroup tasks required')
            for value in text.split():
                require(value.isdecimal() and int(value)>0,'Typed positive actual runtime PID required');tasks.add(int(value))
    return len(tasks)


def process_counts(proc=Path('/proc'),dev=Path('/dev')):
    devices=set()
    for path in [*dev.glob('nvidia*'),*dev.joinpath('nvidia-caps').glob('*')]:
        info=path.stat()
        if stat.S_ISCHR(info.st_mode):devices.add(info.st_rdev)
    require(devices,'Actual NVIDIA device identity inventory required')
    clients=set();writers=set();count=0;deadline=time.monotonic()+10
    names={'node_agent.py','poll.py','pod_cap.py','driver_loader.py'}
    for path in proc.iterdir():
        if not path.name.isdecimal() or int(path.name)==os.getpid():continue
        count+=1;require(count<=65536 and time.monotonic()<deadline,'Complete host process scan bound exceeded')
        try:
            raw=(path/'cmdline').read_bytes();require(len(raw)<=65536,'Bounded actual process argv required')
            if any(Path(arg.decode()).name in names for arg in raw.split(b'\0') if arg):writers.add(int(path.name))
            for fd in path.joinpath('fd').iterdir():
                try:
                    info=fd.stat()
                    if stat.S_ISCHR(info.st_mode) and info.st_rdev in devices:clients.add(int(path.name))
                except (FileNotFoundError,ProcessLookupError):pass
        except (FileNotFoundError,ProcessLookupError):pass
    return not writers,len(clients)


def validate_request(value):
    closed(value,('version','qualification_only','binding_id','attempt','enrollment_uid','approval_ref'),
        'Closed explicit actual failed-enrollment request required')
    require(type(value['version']) is int and value['version']==1 and value['qualification_only'] is True,
        'Explicit controlled qualification request required')
    require(isinstance(value['binding_id'],str) and len(value['binding_id'])==60
        and all(c in '0123456789abcdef' for c in value['binding_id']) and old.valid_uuid(value['enrollment_uid'])
        and isinstance(value['attempt'],str) and 0<len(value['attempt'])<=128,'Actual binding/attempt/enrollment UID required')
    require(approval.reference(value['approval_ref'])['namespace']==old.NAMESPACE,'Exact node approval reference required')


class HostProbe:
    def __init__(self,args,agent,request):
        self.args,self.agent,self.request=args,agent,request
        validate_request(request)
        self.config=agent.read_config(Path(args.config));self.bundle=agent.load_bundle(Path(args.bundle))
        self.adapter,self.qualification,self.modules=self.bundle
        self.state=Path(args.state);directory(self.state)
        self.kube=agent.api_class(self.qualification)(args.service_account)
        self.ref=approval.read_private(Path(args.reference));self.template=approval.read_private(Path(args.template))
        require(self.ref==request['approval_ref'],'Current mounted node approval reference must match request')
        self.consumer=approval.ApprovalConsumer(agent,self.config,self.template,self.ref,self.kube.configmap)
        self.consumer.current();self.locks={}

    def acquire(self,stack):
        for relative in ('.node-agent.lock','journal/.writer.lock','authority/.driver-loader.lock'):
            fd=acquire_lock(self.state/relative);stack.callback(os.close,fd);self.locks[relative]=fd

    def query(self,args):
        result=subprocess.run(['/usr/local/bin/nvidia-smi',*args],env=dict(os.environ),
            capture_output=True,text=True,timeout=15,check=True)
        return result.stdout.strip()

    def capture(self):
        require(len(self.locks)==3,'All actual native writer locks must remain held')
        for relative,fd in self.locks.items():verify_lock(self.state/relative,fd)
        require(approval.read_private(Path(self.args.reference))==self.ref
            and approval.read_private(Path(self.args.template))==self.template,'Mounted current approval context changed')
        cm=self.kube.configmap(old.NAMESPACE,'cps-native-enrollment-'+self.request['binding_id'][:40])
        require(cm is not None and cm.get('metadata',{}).get('uid')==self.request['enrollment_uid'],
            'Actual original immutable enrollment UID required')
        doc=self.consumer.current();envelope=self.consumer._envelope(cm,self.modules['models'],doc,self.ref)
        body=envelope['enrollment'];target=body['intent']['pod_uid']
        require(body['source']=='cps' and body['workspace']=='native-group-b' and body['profile']=='interactive-shared-5'
            and body['cap_mib']==5120 and body['attempt']==self.request['attempt']
            and body['binding_id']==self.request['binding_id'] and body['approval_ref']==self.ref,
            'Only original current controlled CPS5 enrollment supported')
        for folder in ('enrollments','intents','approval-references'):
            directory(self.state/folder)
        expected_ref=dict(version=1,approval_ref=self.ref,enrollment_uid=envelope['configmap_uid'],
            enrollment_sha256=approval.digest(body))
        require(old.parse(protected(self.state/'enrollments'/(target+'.json'),modes=(0o600,)))==envelope
            and old.parse(protected(self.state/'intents'/(target+'.json'),modes=(0o600,)))==body['intent']
            and old.parse(protected(self.state/'approval-references'/(target+'.json'),modes=(0o600,)))==expected_ref,
            'Original protected enrollment/intent/reference must precede terminal recovery')
        journals=capture_journals(self.state/'journal',target)
        for folder in ('receipts','bootstrap'):
            directory(self.state/folder)
            require(not (self.state/folder/(target+'.json')).exists()
                and not (self.state/folder/(target+'.json')).is_symlink(),'A target native gate/bootstrap exists')
        require(self.kube.pod(self.modules['models'].CapIntent(**body['intent'])) is None,
            'Existing or replacement actual Pod blocks never-gated recovery')
        driver=self.modules['manual'].Nvml()
        try:
            driver_version=driver.version
            epoch=self.agent.abort_current_epoch(self.config,self.state,driver,self.modules['health'],self.modules['models'])
            self.agent.validate_pool_epoch(self.config,epoch)
        finally:driver.close()
        # Reuse the exact reviewed backend's read-only inventory method. Its
        # constructor only validates existing private state and binds callbacks.
        backend=self.adapter.QualificationNodeBackend(self.modules['models'],self.modules['manual'],
            intents=[],driver=SimpleNamespace(version=driver_version),get_pod=self.kube.pod,get_node=self.kube.node,
            get_cri=None,delete_pod=None,gpu_clients=None,health=None,state_root=self.state)
        physical=backend._inventory(SimpleNamespace(gpu_uuid=old.GPU))
        closed(physical,('version','backend','gpu_uuid','gpu_id','entries'),'Full exact physical inventory required')
        require(type(physical['version']) is int and physical['version']==1 and physical['backend']=='misc-fallback'
            and physical['gpu_uuid']==old.GPU and type(physical['gpu_id']) is int,
            'Current exact physical GPU inventory required')
        rows=physical['entries'];quiet,clients=process_counts()
        gpu=self.query(['--id='+old.GPU,'--query-gpu=uuid,memory.used,memory.total,driver_version','--format=csv,noheader,nounits'])
        fields=[v.strip() for v in gpu.split(',')]
        require(len(fields)==4 and fields[0]==old.GPU and fields[1].isdecimal() and fields[2]=='40960'
            and fields[3]=='615.71.09','Actual exact40GiB GPU/current driver measurement required')
        apps=self.query(['--id='+old.GPU,'--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'])
        original=self.modules['models'].CapRecord.from_dict(old.parse(base64.b64decode(journals[0]['raw_base64'],validate=True)))
        backend._retired_mount(original.identity)
        task_count=target_tasks(Path('/sys/fs/cgroup'),target)
        info=directory(self.state/'journal')
        proof=dict(node_epoch=asdict(epoch),journal_device=info.st_dev,journal_inode=info.st_ino,
            journal_protected=True,target_journal_absent=True,gate_receipts_absent=True,
            native_writers_quiesced=quiet,exclusive_lock=True,driver_healthy=True,approval_current=True,
            approval_ref=self.ref,retired_history_sha256=old.sha256(journals),physical_rows_sha256=old.sha256(rows),
            global_gpu_memory_mib=int(fields[1]),global_gpu_clients=clients,
            global_compute_apps=len(apps.splitlines()) if apps else 0,pod_runtime_tasks=task_count)
        materials=dict(proof=proof,retired_journals=journals,physical_rows=rows)
        publisher.validate_proof(proof,dict(materials,approval_ref=self.ref));publisher.validate_history(materials,self.modules['models'])
        return materials


def read_rpc():
    require(select.select([sys.stdin.buffer],[],[],120)[0],'Root publisher RPC timed out')
    raw=sys.stdin.buffer.readline(8193);require(raw and len(raw)<=8192,'Bounded live Root RPC required')
    return old.parse(raw)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group();action.add_argument('--capture',action='store_true');action.add_argument('--execute',action='store_true')
    parser.add_argument('--qualification-only',action='store_true')
    for flag in ('request','request-sha256','agent-source-sha256','self-sha256','evidence','output'):
        parser.add_argument('--'+flag)
    for flag,default in [('agent','/opt/native/node_agent.py'),('bundle','/opt/native'),('config','/config/config.json'),
        ('state','/run/cps-native-gpu'),('reference','/var/run/cps-native-approvals/reference.json'),
        ('template','/var/run/cps-native-approvals/template.json'),('service-account','/var/run/secrets/kubernetes.io/serviceaccount')]:
        parser.add_argument('--'+flag,default=default)
    args=parser.parse_args(argv)
    if not args.capture and not args.execute:
        print(old.canonical(dict(state='inert',api_calls=False,device_calls=False)));return
    require(os.geteuid()==0 and args.qualification_only and args.request and args.request_sha256
        and args.agent_source_sha256 and args.self_sha256,'Explicit Root/pinned source/qualification request required')
    require('sha256:'+hashlib.sha256(protected(Path(__file__))).hexdigest()==args.self_sha256,'Protected exact Root fence source required')
    request=old.parse(protected(args.request));require(old.sha256(request)==args.request_sha256,'Exact reviewed request hash required')
    raw=protected(args.agent);require('sha256:'+hashlib.sha256(raw).hexdigest()==args.agent_source_sha256,'Exact reviewed actual node source required')
    spec=importlib.util.spec_from_file_location('_approved_abort_actual_node',args.agent)
    agent=importlib.util.module_from_spec(spec);sys.modules[spec.name]=agent
    exec(compile(raw,args.agent,'exec'),agent.__dict__)
    probe=HostProbe(args,agent,request)
    with ExitStack() as stack:
        probe.acquire(stack);actual=probe.capture()
        if args.capture:
            require(args.output,'New private actual capture output required');old.private_output(args.output,actual)
            print(old.canonical(dict(state='captured',sha256=old.sha256(actual),live_writes=False)));return
        require(args.evidence,'Reviewed complete publisher evidence required')
        evidence=old.parse(protected(args.evidence))
        publisher.validate_evidence(evidence,old.sha256(evidence),probe.consumer,probe.modules['models'])
        require(all(actual[key]==evidence[key] for key in actual),'Fresh complete Root observations differ from reviewed evidence')
        def emit(event):
            value=probe.capture();require(value==actual,'Current full actual observation changed while fenced')
            print(old.canonical(dict(event=event,observed_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),proof=value['proof'])),flush=True)
        emit('fence-acquired')
        while True:
            request=read_rpc()
            if request=={'op':'verify'}:emit('fence-verified')
            else:
                require(request=={'op':'release'},'Closed ordered Root fence RPC required');break


if __name__=='__main__':main()

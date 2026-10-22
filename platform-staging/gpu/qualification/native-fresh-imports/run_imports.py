#!/usr/bin/env python3
"""Default-inert fresh QA same-parent import measurement, with original trusted engines."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import types
import uuid

BINARY_SHA='0e19d4ec396dd64cabe364607fee151c001821cdcb2da5e5b181d7f902a76f69'
HELPER_SHA='d8cdbf06d93a0f46e0fc122f5f547ff121d0728b7d99b55f1ca8345c574e4f6c'
ENGINE_SHA='dc6103ae49c8b91dab546f62fa67515a1fecd3caa3964cb220bda7d1c5aa9e58'
PEER_RUNNER_SHA='1e8a0d398672842bd124a3bbe3fbde50817b76c5394714dfbd374695d220653a'
PREFLIGHT_SHA='07137f623f1a0c383597c90fbf485f4ea95597a553b433ffc388dcedcbd70d58'
PEER_SHA='ea49812f2f68371a27f63e709534f08aa1b23028395c4b76b2efc07b88d86834'

def require(value,message):
    if not value:raise ValueError(message)

def checked_bytes(path,pin):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);raw=os.read(fd,1024*1024+1);after=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1
                and not before.st_mode&0o022 and 0<len(raw)<=1024*1024
                and all(getattr(before,k)==getattr(after,k) for k in
                    ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'Stable owned reviewed artifact required')
        require(hashlib.sha256(raw).hexdigest()==pin,'Exact reviewed artifact hash required: '+Path(path).name)
        return raw
    finally:os.close(fd)

def load(name,path,raw):
    result=types.ModuleType(name);result.__file__=str(path)
    exec(compile(raw,str(path),'exec'),result.__dict__);return result

def write(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(value,stream,sort_keys=True,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())

def unchanged(before,after):
    require(before['pods']==after['pods'],'Actual Pod/container/restart changed')
    require(before['host']['processes']==after['host']['processes'],'Actual notebook PID/CID/start changed')
    require(len(before['host']['targets'])==len(after['host']['targets']),'Protected QA target count changed')
    for old,new in zip(before['host']['targets'],after['host']['targets']):
        require({k:v for k,v in old.items() if k!='limit'}=={k:v for k,v in new.items() if k!='limit'},
                'Original protected seal/journal/identity changed')
        require(old['limit']['soft']==new['limit']['soft'] and old['limit']['hard']==new['limit']['hard']
                and new['limit']['used']<=old['limit']['used'],'Original cap or recovered charge changed')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true');p.add_argument('--manifest');p.add_argument('--manifest-sha256')
    p.add_argument('--binary',type=Path);p.add_argument('--binary-sha256');p.add_argument('--runner-sha256')
    p.add_argument('--side',choices=('a','b'),default='a');p.add_argument('--mode',choices=('vmm-direct','ipc','vmm'),default='vmm-direct')
    p.add_argument('--output',type=Path);a=p.parse_args(argv)
    if not a.execute:print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False,'production_qualified':False}));return
    require(all((a.manifest,a.manifest_sha256,a.binary,a.binary_sha256,a.runner_sha256,a.output))
            and a.binary_sha256==BINARY_SHA,'Reviewed actual cohort, binary, runner and fresh output required')
    here=Path(__file__).resolve().parent;common=here.parent/'native-fresh-domain'
    # Authenticate every source/binary before executing any dependency or contacting an API.
    checked_bytes(Path(__file__),a.runner_sha256)
    binary=checked_bytes(a.binary,BINARY_SHA)
    engine_raw=checked_bytes(here/'same_parent_engine.py',ENGINE_SHA)
    helper=checked_bytes(here/'same_pod_imports.py',HELPER_SHA)
    peer_runner_raw=checked_bytes(common/'run_peer_oom.py',PEER_RUNNER_SHA)
    preflight_raw=checked_bytes(common/'fresh_preflight.py',PREFLIGHT_SHA)
    peer_source=checked_bytes(common/'peer_probe.py',PEER_SHA)
    engine=load('qa_same_parent_engine',here/'same_parent_engine.py',engine_raw)
    transport=load('qa_peer_transport',common/'run_peer_oom.py',peer_runner_raw)
    current=load('qa_fresh_preflight',common/'fresh_preflight.py',preflight_raw)
    targets=current.read_targets(a.manifest,a.manifest_sha256)
    a.output.mkdir(mode=0o700)
    peer=None
    result={'state':'inconclusive','mode':a.mode,'side':a.side,'production_qualified':False,
        'cross_parent_isolation_qualified':False,'binary_sha256':BINARY_SHA,'helper_sha256':HELPER_SHA,
        'engine_sha256':ENGINE_SHA,'fresh_preflight_sha256':PREFLIGHT_SHA,'peer_source_sha256':PEER_SHA,
        'manifest_sha256':a.manifest_sha256}
    try:
        before=current.preflight({'manifest':targets});write(a.output/'before.json',before)
        other='b' if a.side=='a' else 'a'
        peer=transport.ProbeRun(targets['pods'][other],'peer',115,peer_source,a.output)
        peer.wait(lambda events:sum(e.get('phase')=='peer_tick' for e in events)>=2,30)
        source=engine.bundle(binary,helper,a.mode,str(uuid.uuid4()))
        result['streamed_source_sha256']=hashlib.sha256(source).hexdigest()
        target=targets['pods'][a.side]
        response=subprocess.run(['kubectl','-n',target['namespace'],'exec','-i',target['name'],'-c','notebook',
            '--','python','-I','-u','-'],input=source,capture_output=True,timeout=105)
        require(response.returncode==0 and len(response.stdout)<=2*1024*1024 and len(response.stderr)<=1024*1024,
                'Successful bounded native helper transport required')
        packet=json.loads(response.stdout);write(a.output/'native-events.json',packet)
        events=peer.complete();write(a.output/'peer-events.json',events)
        result.update(engine.assess(packet,events,a.mode))
        after=current.preflight({'manifest':targets});write(a.output/'after.json',after);unchanged(before,after)
        result.update(state='bounded-same-parent-imports-with-peer-observed',unchanged_native_authorities=True)
    except Exception as error:
        result['error_type']=type(error).__name__
    finally:
        try:transport.abandon(peer)
        except Exception as error:
            result.update(state='inconclusive',transport_cleanup_error=type(error).__name__)
        write(a.output/'receipt.json',result)
    print(json.dumps({'state':result['state'],'receipt':str(a.output/'receipt.json'),'production_qualified':False}))
    if result['state']=='inconclusive':raise SystemExit(1)

if __name__=='__main__':main()

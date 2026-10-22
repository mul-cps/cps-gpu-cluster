#!/usr/bin/env python3
"""Default-inert exact-preimage Source332 A5-to-B10 IPC preparation; no live calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types

HERE=Path(__file__).resolve().parent
PRODUCER_SHA='a35c0778bba76b0ca840216d585ef850cefb2313af7d1ca2ad6fb3c2688a019b'
IMPORTS_SHA='5ad010a9823f8c02276eebb99779071b98d81bb45561ba7f9383e9b9bfedb802'
POLICY='sha256:332d14fb9e510b9810feffb8d40b408743f9679ebd13ca1ba0e1077d666e9281'
OLD='6ba3353d-bf13-4cad-9c35-3119dd279a67'
COHORT='a9fc091b-f388-4f21-8771-b6ae7b4734dc'
PINS={'run_cross_pod.py':'db60d19fe64e6414c8229c4622c63bf4df310affb1ea8863429618c36022e833',
 'ipc_engine.py':'a4478f7d2bfeb0e85e826f26ac1c30800800e0910db0df10e4d5cc67c2423ce3',
 'ipc_endpoint.py':'20b36695ae6b5a9a6d3807ff4646c2928d0ba72017aa2fec4c20cb1fdcd4712b',
 'ipc_host_pid.py':'d3f43d1d5fb02a4f83aac8a1360bffb673e7f3d77f58669cf1f789a569499f95',
 'kernel_witness_collector.py':'78d0db27fe46ee28ee7cb6d01d2eb6f123596038e0f94c183dd7d0fd9621b1bf',
 'kernel_witness_validator.py':'030f5faec77d1db819944f85ec09bb0117480c6f3b2ce85915830c793f9cb795',
 'kernel_witness_transport.py':'ce703a63de29c8d6e9447c2c92bd08bbbddd77d757b2789c21b9b3fc86167850'}

def require(ok,message):
    if not ok:raise ValueError(message)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def replace(source,old,new,count=1):
    require(source.count(old)==count,'Exact reviewed IPC adaptation span changed')
    return source.replace(old,new)

def load(name,raw):
    m=types.ModuleType('prepared_'+name);m.__file__=str(HERE/name)
    exec(compile(raw,m.__file__,'exec'),m.__dict__);return m

def unique(pairs):
    out={}
    for k,v in pairs:
        require(k not in out,'Duplicate JSON key');out[k]=v
    return out

def build_sources(manifest,manifest_sha256):
    require(type(manifest_sha256)is str and re.fullmatch('[a-f0-9]{64}',manifest_sha256),'Independent actual manifest raw SHA required')
    raw={name:(HERE.parent/'native-fresh-ipc'/name).read_bytes() for name in PINS}
    producer=(HERE/'prepare.py').read_bytes()
    helper=(HERE.parent/'native-fresh-imports/run_imports.py').read_bytes()
    require(sha(producer)==PRODUCER_SHA and sha(helper)==IMPORTS_SHA
            and all(sha(raw[n])==pin for n,pin in PINS.items()),'All exact reviewed IPC preimages required before execution')
    generated=load('prepare.py',producer).build_sources('5-10')
    current=load('fresh_preflight.py',generated['fresh_preflight.py']);current.validate_targets(manifest)
    require(manifest['cohort_uid']==COHORT,'Exact actual Source332 cohort required')
    out=dict(raw)
    out['fresh_preflight.py']=generated['fresh_preflight.py']
    out['retained_import_proof.py']=helper
    endpoint=raw['ipc_endpoint.py'].decode()
    out['ipc_endpoint_b.py']=replace(endpoint,'CAP = 5368709120','CAP = 10737418240').replace('finite5GiB','finite10GiB').encode()
    host=raw['ipc_host_pid.py'].decode()
    host=replace(host,"    relative = identity['cgroup_relative']", "    require(type(identity)is dict and identity.get('pod_uid')=="+repr(manifest['pods']['b']['uid'])+", 'Exact actual10GiB importer UID required')\n    relative = identity['cgroup_relative']")
    host=replace(host,'5368709120','10737418240',2).replace('finite5GiB','finite10GiB');out['ipc_host_pid.py']=host.encode()
    for name in ('kernel_witness_collector.py','kernel_witness_transport.py'):
        out[name]=replace(raw[name].decode(),OLD,COHORT).encode()
    runner=raw['run_cross_pod.py'].decode()
    runner=replace(runner,OLD,COHORT)
    for name in PINS:
        if name!='run_cross_pod.py' and sha(out[name])!=PINS[name]:runner=replace(runner,PINS[name],sha(out[name]))
    runner=replace(runner,"PREFLIGHT_SHA='07137f623f1a0c383597c90fbf485f4ea95597a553b433ffc388dcedcbd70d58'", "PREFLIGHT_SHA='"+sha(out['fresh_preflight.py'])+"'")
    runner=replace(runner,"IMPORTS_SHA='"+IMPORTS_SHA+"'", "IMPORTS_SHA='"+IMPORTS_SHA+"'\nENDPOINT_B_SHA='"+sha(out['ipc_endpoint_b.py'])+"'")
    runner=replace(runner,"choices=('a-to-b','b-to-a')","choices=('a-to-b',)")
    runner=replace(runner,"common=here.parent/'native-fresh-domain';imports=here.parent/'native-fresh-imports'","common=here;imports=here")
    runner=replace(runner,"    preflight=checked(common/'fresh_preflight.py',PREFLIGHT_SHA)","    raw['ipc_endpoint_b.py']=checked(here/'ipc_endpoint_b.py',ENDPOINT_B_SHA)\n    require(a.manifest_sha256=="+repr(manifest_sha256)+",'Exact prepared actual manifest raw SHA required')\n    preflight=checked(common/'fresh_preflight.py',PREFLIGHT_SHA)")
    runner=replace(runner,"imports/'run_imports.py'","imports/'retained_import_proof.py'",2)
    runner=replace(runner,"raw['ipc_endpoint.py'],'cross-pod-importer'","raw['ipc_endpoint_b.py'],'cross-pod-importer'")
    runner=replace(runner,"before=current.preflight({'manifest':target});retained.write(a.output/'before.json',before)","before=current.preflight({'manifest':target})\n        require(len(before['host']['targets'])==2 and all(t['intent']['policy_hash']=="+repr(POLICY)+" for t in before['host']['targets']),'Actual sealed Source332 intent required')\n        retained.write(a.output/'before.json',before)")
    out['run_cross_pod.py']=runner.encode()
    for name,data in out.items():compile(data,name,'exec')
    return out

def read_manifest(path,pin):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);raw=os.read(fd,65537);after=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1
                and stat.S_IMODE(before.st_mode)==0o600 and 0<len(raw)<=65536
                and all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
                and sha(raw)==pin,'Exact protected reviewed manifest required')
        return json.loads(raw,object_pairs_hook=unique)
    finally:os.close(fd)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    p.add_argument('--manifest',type=Path);p.add_argument('--manifest-sha256');p.add_argument('--output',type=Path);a=p.parse_args(argv)
    if not a.prepare:print('{"state":"inert","api_calls":false,"gpu_calls":false}');return
    require(a.manifest and a.manifest_sha256 and a.output,'Reviewed actual manifest and exclusive output required')
    sources=build_sources(read_manifest(a.manifest,a.manifest_sha256),a.manifest_sha256);a.output.mkdir(mode=0o700)
    for name,raw in sources.items():
        fd=os.open(a.output/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    print(json.dumps({'state':'prepared','sources':{n:sha(v) for n,v in sources.items()},'manifest_sha256':a.manifest_sha256,'production_qualified':False},sort_keys=True))

if __name__=='__main__':main()

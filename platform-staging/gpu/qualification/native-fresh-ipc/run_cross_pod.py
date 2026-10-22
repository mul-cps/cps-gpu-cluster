#!/usr/bin/env python3
"""Default-inert fresh QA IPC denial with original endpoints and mandatory Root kernel witness."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import types
import uuid

BOOT='a464df41-e391-4443-b8e8-ad7ecd052318'
GENERATION='4ebffc96-e25e-4583-a3b8-0d853fd90efd'
ROOT='/var/lib/cps-native-gpu/qualification/1f7d941a-872d-4453-a1ba-fd489d8aff14/cohorts/6ba3353d-bf13-4cad-9c35-3119dd279a67/ipc-kmsg-witness'
PINS={'ipc_engine.py':'a4478f7d2bfeb0e85e826f26ac1c30800800e0910db0df10e4d5cc67c2423ce3',
 'ipc_endpoint.py':'20b36695ae6b5a9a6d3807ff4646c2928d0ba72017aa2fec4c20cb1fdcd4712b',
 'ipc_host_pid.py':'d3f43d1d5fb02a4f83aac8a1360bffb673e7f3d77f58669cf1f789a569499f95',
 'kernel_witness_collector.py':'78d0db27fe46ee28ee7cb6d01d2eb6f123596038e0f94c183dd7d0fd9621b1bf',
 'kernel_witness_validator.py':'030f5faec77d1db819944f85ec09bb0117480c6f3b2ce85915830c793f9cb795',
 'kernel_witness_transport.py':'ce703a63de29c8d6e9447c2c92bd08bbbddd77d757b2789c21b9b3fc86167850'}
PREFLIGHT_SHA='07137f623f1a0c383597c90fbf485f4ea95597a553b433ffc388dcedcbd70d58'
IMPORTS_SHA='5ad010a9823f8c02276eebb99779071b98d81bb45561ba7f9383e9b9bfedb802'

def require(value,message):
    if not value:raise ValueError(message)

def checked(path,pin):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);raw=os.read(fd,1024*1024+1);after=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1
                and not before.st_mode&0o022 and 0<len(raw)<=1024*1024
                and all(getattr(before,k)==getattr(after,k) for k in
                    ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'Stable owned reviewed input required')
        require(hashlib.sha256(raw).hexdigest()==pin,'Reviewed input hash mismatch: '+Path(path).name)
        return raw
    finally:os.close(fd)

def load(name,path,raw):
    m=types.ModuleType(name);m.__file__=str(path);exec(compile(raw,str(path),'exec'),m.__dict__);return m

def transports(value):
    require(type(value) is dict and set(value)=={'version','attribution_argv','witness_argv'}
            and type(value['version']) is int and value['version']==1,'Closed reviewed Root IPC transport required')
    for key,script in (('attribution_argv','ipc_host_pid.py'),('witness_argv','kernel_witness_collector.py')):
        argv=value[key]
        require(type(argv) is list and 3<=len(argv)<=128 and all(type(s) is str and 0<len(s)<=4096
                and not any(c in s for c in '\x00\r\n') for s in argv)
                and Path(argv[0]).name=='ssh' and '--execute' in argv and ROOT+'/'+script in argv,
                'Independently reviewed exact Root SSH transport required')
    require('--request' not in value['attribution_argv'],'Wrapper supplies the exact current request only')
    argv=value['witness_argv']
    require('--qualification' in argv,'Explicit Root qualification markers required')
    for flag,pin in (('--source-sha256',PINS['kernel_witness_collector.py']),
                     ('--validator-sha256',PINS['kernel_witness_validator.py'])):
        require(argv.count(flag)==1 and argv.index(flag)+1<len(argv) and argv[argv.index(flag)+1]==pin,
                'Root collector/validator source bindings changed')
    return value

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--manifest');p.add_argument('--manifest-sha256');p.add_argument('--transports',type=Path)
    p.add_argument('--transports-sha256');p.add_argument('--runner-sha256');p.add_argument('--output',type=Path)
    p.add_argument('--direction',choices=('a-to-b','b-to-a'),default='a-to-b');a=p.parse_args(argv)
    if not a.execute:print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False}));return
    require(all((a.manifest,a.manifest_sha256,a.transports,a.transports_sha256,a.runner_sha256,a.output)),
            'Reviewed actual cohort, Root transports, source and fresh output required')
    here=Path(__file__).resolve().parent;common=here.parent/'native-fresh-domain';imports=here.parent/'native-fresh-imports'
    checked(Path(__file__),a.runner_sha256)
    raw={name:checked(here/name,pin) for name,pin in PINS.items()}
    preflight=checked(common/'fresh_preflight.py',PREFLIGHT_SHA)
    helper=checked(imports/'run_imports.py',IMPORTS_SHA)
    transport_raw=checked(a.transports,a.transports_sha256)
    # Nothing below executes a dependency or contacts a process before all bytes are authenticated.
    engine=load('fresh_ipc_engine',here/'ipc_engine.py',raw['ipc_engine.py'])
    current=load('fresh_qa_preflight',common/'fresh_preflight.py',preflight)
    retained=load('fresh_import_proof',imports/'run_imports.py',helper)
    witness_module=load('fresh_kernel_transport',here/'kernel_witness_transport.py',raw['kernel_witness_transport.py'])
    target=current.read_targets(a.manifest,a.manifest_sha256)
    routes=transports(json.loads(transport_raw,object_pairs_hook=current.unique))
    a.output.mkdir(mode=0o700);sessions=[];witness=None;trial=str(uuid.uuid4())
    receipt={'state':'inconclusive','trial_id':trial,'direction':a.direction,'source_sha256':PINS,
             'manifest_sha256':a.manifest_sha256,'transports_sha256':a.transports_sha256,
             'production_qualified':False,'cross_parent_isolation_qualified':False}
    try:
        before=current.preflight({'manifest':target});retained.write(a.output/'before.json',before)
        exporter_key,importer_key=('a','b') if a.direction=='a-to-b' else ('b','a')
        exporter_target,importer_target=target['pods'][exporter_key],target['pods'][importer_key]
        base=['--execute','--gpu-uuid',current.GPU,'--trial-id',trial]
        exporter=engine.Session(exporter_target,[*base,'--role','exporter'],raw['ipc_endpoint.py'],'exporter',a.output)
        sessions.append(exporter);handle=exporter.wait('handle-ready');exporter.wait('exporter-tick')
        positive=engine.Session(exporter_target,[*base,'--role','importer','--wait-for-root','--expect','allow',
            '--handle-b64',handle['handle_b64']],raw['ipc_endpoint.py'],'same-pod-positive',a.output)
        sessions.append(positive);positive.wait('importer-ready');positive.send('open',trial);positive_events=positive.complete()
        denied=engine.Session(importer_target,[*base,'--role','importer','--wait-for-root','--expect','deny',
            '--handle-b64',handle['handle_b64']],raw['ipc_endpoint.py'],'cross-pod-importer',a.output)
        sessions.append(denied);ready=denied.wait('importer-ready')
        identity=next(row['identity'] for row in before['host']['targets'] if row['pod_uid']==importer_target['uid'])
        request={'trial_id':trial,'namespace_pid':ready['namespace_pid'],'identity':identity}
        # SSH concatenates its remote argv through a shell: quote the single canonical JSON argument.
        response=subprocess.run([*routes['attribution_argv'],'--request',shlex.quote(json.dumps(request,sort_keys=True,separators=(',',':')))],
            capture_output=True,text=True,timeout=10)
        require(response.returncode==0 and len(response.stdout)<=131072,'Actual bounded Root PID attribution failed')
        attribution=json.loads(response.stdout,object_pairs_hook=current.unique)
        require(attribution['trial_id']==trial and attribution['namespace_pid']==ready['namespace_pid']
                and attribution['pod_uid']==importer_target['uid'] and attribution['boot_id']==BOOT
                and attribution['driver_generation']==GENERATION,'Exact actual importer lifetime required')
        retained.write(a.output/'importer-host-attribution.json',attribution)
        witness=witness_module.KernelWitness(routes['witness_argv'],a.output,
            collector_sha256=PINS['kernel_witness_collector.py'],validator_sha256=PINS['kernel_witness_validator.py'])
        denied_events,kernel=engine.open_denied(denied,trial,attribution,witness)
        call=[event for event in denied_events if event.get('phase')=='import-result']
        require(len(call)==1 and type(call[0]['call_ended_monotonic_ns']) is int,'Actual exact denied call window required')
        exporter.send('recover',trial);exporter.wait('exporter-recovery')
        exporter.wait_matching(lambda e:e.get('phase')=='exporter-tick' and type(e.get('tick')) is int and e['tick']>=2
            and type(e.get('monotonic_ns')) is int and e['monotonic_ns']>call[0]['call_ended_monotonic_ns'])
        exporter.send('finish',trial);exporter_events=exporter.complete()
        measured=engine.assess_endpoint_events(exporter_events,positive_events,denied_events,trial)
        capture,correlation=kernel
        retained.write(a.output/'kernel-witness-capture.json',capture)
        retained.write(a.output/'kernel-witness-correlation.json',correlation)
        after=current.preflight({'manifest':target});retained.write(a.output/'after.json',after);retained.unchanged(before,after)
        receipt.update(measured,state='bounded-cross-parent-kernel-denial-measured',kernel_witness_correlated=True,
                       kernel_witness_correlation=correlation,unchanged_native_authorities=True)
    except Exception as error:receipt.update(state='inconclusive',error_type=type(error).__name__)
    finally:
        if witness is not None:
            try:witness.close()
            except Exception as error:receipt.update(state='inconclusive',kernel_cleanup_error=type(error).__name__)
        for session in reversed(sessions):
            try:session.abandon()
            except Exception as error:receipt.update(state='inconclusive',transport_cleanup_error=type(error).__name__)
        retained.write(a.output/'receipt.json',receipt)
    print(json.dumps({'state':receipt['state'],'receipt':str(a.output/'receipt.json'),'production_qualified':False}))
    if receipt['state']=='inconclusive':raise SystemExit(1)

if __name__=='__main__':main()

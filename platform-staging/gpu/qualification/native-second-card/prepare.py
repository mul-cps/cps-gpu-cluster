#!/usr/bin/env python3
"""Closed second GPU2 5/10 QA source preparation. Offline and default inert."""
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import types
import uuid

HERE = Path(__file__).resolve().parent
SECOND_GPU = 'GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6'
CDI_KIND = 'k8s.device-plugin.nvidia.com/gpu'
CDI_DEVICE = CDI_KIND + '=' + SECOND_GPU
CDI_PATH = '/var/run/cdi/k8s.device-plugin.nvidia.com-gpu.json'
CDI_SHA = 'b940041ddae78f5570f05ede8347b4eb366892342a581cc01fac2edacf4cd087'
NODE_UID = '3336cdd5-d245-436e-b57c-2f66c6dcaa41'
FIRST_GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
OLD_NS = 'cps-native-qa147-20261022'
OLD_NS_UID = '1f7d941a-872d-4453-a1ba-fd489d8aff14'
OLD_COHORT = 'a9fc091b-f388-4f21-8771-b6ae7b4734dc'
OLD_BOOT = 'a464df41-e391-4443-b8e8-ad7ecd052318'
OLD_GEN = '4ebffc96-e25e-4583-a3b8-0d853fd90efd'
COLLECTOR = Path('/tmp/cps-mujoco-reviewed-sdk-installed-20261027/cps_compute/personal_qualification_collect.py')
COLLECTOR_SHA = '190b6ada40b7162891d4a150779eae5cfe94b622cf3d796d90231f5064f36edf'
PINS = {
 'native-fresh-unequal/prepare.py':'a35c0778bba76b0ca840216d585ef850cefb2313af7d1ca2ad6fb3c2688a019b',
 'native-fresh-unequal/prepare_imports.py':'0c7f619f6f1da98d6f82022a2e9b4096dff9c3500370aa93a518872c3b96aa72',
 'native-fresh-unequal/prepare_mps.py':'e42280e049cdfac2eca3625cf7de139b6dc81303719363abf68e385d40354f57',
 'native-fresh-unequal/fresh_import_closure.py':'544629a0b4aa781dcfb9ef7cf84c700085559c2c27484c12b2370a4d2b1afb18',
 'native-fresh-domain/physical_samples.py':'78f730f66c0c84198737715c06601eb4e5dabef68d88644d616b0123351ad35a',
}


def require(ok, message):
    if not ok: raise ValueError(message)


def sha(raw): return hashlib.sha256(raw).hexdigest()
def source_path(name): return HERE.parent / name


def checked_source(name, raw=None):
    raw = source_path(name).read_bytes() if raw is None else raw
    require(sha(raw) == PINS[name], 'Exact reviewed preimage changed: ' + name)
    return raw


def load(name, raw, path):
    m = types.ModuleType(name); m.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), m.__dict__)
    return m


def canonical(v): return json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def identifier(v):
    require(type(v) is str and str(uuid.UUID(v)) == v and uuid.UUID(v).int > 0,
            'Canonical nonzero actual UUID observation required')
    return v


def context(value):
    require(type(value) is dict and set(value) == {'node','namespace','guard','device','cohort_uid','policy_hash','cdi'},
            'Closed independent capture sections required')
    node, ns, guard, device = [value[k] for k in ('node','namespace','guard','device')]
    require(node['metadata']['name'] == 'k3s-wk-gpu2' and node['metadata']['uid'] == NODE_UID,
            'Only closed second-card GPU2 Node allowed')
    boot = identifier(node['status']['nodeInfo']['bootID'])
    require(guard['node_uid'] == device['node_uid'] == NODE_UID
            and guard['boot_id'] == device['boot_id'] == boot
            and device['gpu_uuid'] == SECOND_GPU and guard['driver_version'] == '615.71.09',
            'Independent second-card device/guard/Node observations must agree')
    require(not node['metadata'].get('deletionTimestamp') and not ns['metadata'].get('deletionTimestamp'),
            'Deleting Node/namespace refused')
    name = ns['metadata']['name']; ns_uid = identifier(ns['metadata']['uid'])
    require(re.fullmatch(r'cps-native-second-card-[a-z0-9-]{1,35}', name or '')
            and ns_uid != OLD_NS_UID, 'Fresh dedicated second-card QA namespace required')
    cdi=value['cdi']
    require(type(cdi)is dict and set(cdi)=={'path','sha256','raw'}
            and cdi['path']==CDI_PATH and cdi['sha256']==CDI_SHA
            and type(cdi['raw'])is str and len(cdi['raw'])<=1048576 and sha(cdi['raw'].encode())==CDI_SHA,
            'Exact independently observed CDI provider path/bytes/hash required')
    provider=json.loads(cdi['raw'])
    require(provider.get('containerEdits',{}).get('env',[]).count('NVIDIA_VISIBLE_DEVICES=void')==1,
            'Exact authenticated CDI runtime environment edit required')
    require(provider.get('kind')==CDI_KIND and type(provider.get('devices'))is list,'Exact installed CDI kind required')
    selected=[d for d in provider['devices']if d.get('name')==SECOND_GPU]
    require(len(selected)==1 and selected[0].get('containerEdits',{}).get('deviceNodes')==
            [{'path':'/dev/nvidia1','hostPath':'/run/nvidia/driver/dev/nvidia1'}],
            'Exact observed CDI second UUID/minor1 mapping required')
    cohort = identifier(value['cohort_uid'])
    require(cohort not in (OLD_COHORT,'3b217fe8-5750-4ead-954a-09286afd7d3f'), 'Historical cohort reuse denied')
    require(re.fullmatch(r'sha256:[a-f0-9]{64}',value['policy_hash']) and value['policy_hash']!='sha256:'+'0'*64,'Exact reviewed QA policy hash required')
    return {'policy_hash':value['policy_hash'],'namespace':name,'namespace_uid':ns_uid,'cohort':cohort,'boot':boot,
            'generation':identifier(guard['driver_generation'])}


def substitutions(source, ctx):
    # Only authenticated exact source bytes enter here. Hardware target is fixed,
    # not accepted as a CLI or request UUID. Every old literal is closed below.
    for old, new in ((FIRST_GPU,SECOND_GPU),(OLD_NS,ctx['namespace']),
                     (OLD_NS_UID,ctx['namespace_uid']),(OLD_COHORT,ctx['cohort']),
                     (OLD_BOOT,ctx['boot']),(OLD_GEN,ctx['generation']),
                     ('native-qa147-','native-second-card-'),
                     ('sha256:332d14fb9e510b9810feffb8d40b408743f9679ebd13ca1ba0e1077d666e9281',ctx['policy_hash'])):
        source = source.replace(old,new)
    return source


def replace_pin(source, old, new):
    require(old in source, 'Dependent reviewed source pin missing: ' + old)
    return source.replace(old,new)


def build_sources(observations):
    ctx = context(observations)
    checked = {n:checked_source(n) for n in PINS}  # Before executing ANY producer.
    producer = load('second_unequal', checked['native-fresh-unequal/prepare.py'], source_path('native-fresh-unequal/prepare.py'))
    original = producer.build_sources('5-10')
    files = {n:substitutions(r.decode(),ctx).encode() for n,r in original.items()}
    physical=substitutions(checked['native-fresh-domain/physical_samples.py'].decode(),ctx)
    require(physical.count('total>0')==1,'Exact physical capacity span required')
    files['physical_samples.py']=physical.replace('total>0','total==40960').encode()
    renderer=files['render_fixture.py'].decode()
    require(renderer.count("'restartPolicy': 'Never'")==1,'Exact QA base Pod restart policy span required')
    renderer=renderer.replace("'restartPolicy': 'Never'","'restartPolicy': 'Always'")
    injection="        for container in [*pod['spec']['initContainers'], *pod['spec']['containers']]:\n            container['imagePullPolicy'] = 'Never'"
    require(renderer.count(injection)==1,'Exact compiler-owned GPU environment adaptation span required')
    renderer=renderer.replace(injection,injection+"\n            for entry in container.get('env',[]):\n                if entry.get('name')=='NVIDIA_VISIBLE_DEVICES' and entry.get('value')==GPU:\n                    entry['value']="+repr(CDI_DEVICE))
    files['render_fixture.py']=renderer.encode()
    closure_pins={**PINS,**producer.PINS,'observed-cdi-provider':CDI_SHA}
    # Reuse reviewed exact-fd host loader, not bare SONAME or container-only env.
    collector = COLLECTOR.read_bytes()
    require(sha(collector) == COLLECTOR_SHA, 'Exact reviewed host loader preimage required')
    tree = ast.parse(collector)
    fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='trusted_nvml')
    assignment = next(n for n in tree.body if isinstance(n,ast.Assign)
                      and any(isinstance(t,ast.Name) and t.id=='HOST_NVML_LIBRARY' for t in n.targets))
    loader = ast.get_source_segment(collector.decode(),assignment)+'\n\n'+ast.get_source_segment(collector.decode(),fn)+'\n'
    c = files['controller.py'].decode()
    # Read exact original six-module SDK bundle with unchanged original checks.
    controller = load('second_bundle_contract', original['controller.py'], source_path('native-fresh-domain/controller.py'))
    bundle = {}
    for name,pin in controller.PINS.items():
        raw = (controller.SDK/'cps_compute'/name).read_bytes()
        require(sha(raw)==pin,'Exact six-module SDK bundle preimage required')
        bundle[name]=raw
    nvml = bundle['native_node/nvml.py'].decode()
    require(nvml.count("C.CDLL('libnvidia-ml.so.1')") == 1,'Exact original NVML loader seam changed')
    nvml = nvml.replace('import ctypes as C','import ctypes as C\nimport os,stat,hashlib')
    nvml = nvml.replace("C.CDLL('libnvidia-ml.so.1')",'trusted_nvml()')+'\n'+loader
    old_nvml = controller.PINS['native_node/nvml.py']; bundle['native_node/nvml.py']=nvml.encode()
    c=replace_pin(c,old_nvml,sha(bundle['native_node/nvml.py']))
    old_sdk="SDK = Path('/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023/src')"
    require(c.count(old_sdk)==1,'Exact controller bundle source root required')
    c=c.replace(old_sdk,"SDK = Path(__file__).resolve().parent / 'bundle'")
    retired_guard='record.intent.gpu_uuid==GPU and record.intent.cap_mib==5120'
    require(c.count(retired_guard)==1,'Exact prior-cohort retirement cap guard required')
    c=c.replace(retired_guard,'record.intent.gpu_uuid==GPU and record.intent.cap_mib==retired_expected_cap(record.intent.name,old)')
    helper='''def retired_expected_cap(name,state):
    prefix=ROOT+'/cohorts/'
    require(type(state)is str and state.startswith(prefix) and state.endswith('/state'),
            'Exact original namespace/cohort retirement state required')
    cohort=state[len(prefix):-len('/state')]
    require(str(uuid.UUID(cohort))==cohort and uuid.UUID(cohort).int>0
            and cohort_state(cohort)==state, 'Canonical exact original retirement cohort required')
    names={'native-second-card-a-'+cohort[:8]:5120,'native-second-card-b-'+cohort[:8]:10240}
    require(name in names,'Exact original cohort A/B retirement name required')
    return names[name]

'''
    require(c.count('def retirement_inputs(')==1,'Exact existing retirement parser seam required')
    c=c.replace('def retirement_inputs(',helper+'def retirement_inputs(')
    files['controller.py']=c.encode()
    o=files['observe.py'].decode()
    o=replace_pin(o,sha(original['controller.py']),sha(files['controller.py']))
    files['observe.py']=o.encode()
    for n,r in bundle.items():files['bundle/cps_compute/'+n]=r
    # Existing import/MPS adapters authenticate their complete engine closures.
    family_files={}
    for label,adapter in (('imports','prepare_imports.py'),('mps','prepare_mps.py')):
        module=load('second_'+label,checked['native-fresh-unequal/'+adapter],source_path('native-fresh-unequal/'+adapter))
        generated=module.build_sources()
        closure_pins.update({('native-fresh-imports/' if label=='imports' else 'native-fresh-mps/')+n:p for n,p in module.PINS.items()})
        transformed={n:substitutions(r.decode(),ctx) for n,r in generated.items()}
        if label=='mps':
            guard="os.environ.get('CUDA_VISIBLE_DEVICES') == '0' and os.environ.get('NVIDIA_VISIBLE_DEVICES') == GPU"
            probe=transformed['mps_probe.py']
            require(probe.count(guard)==1 and probe.count('def preflight(')==1,'Exact MPS environment assertion required')
            helper="""def compiler_environment():
    # CDI edits initial OCI env; CRI exec carries the configured selector.
    # Read only these two initial-process facts, never emit its environment.
    with Path('/proc/1/environ').open('rb') as stream:
        raw = stream.read(262145)
    if len(raw) > 262144:
        return False
    entries = raw.split(b'\\0')
    return (os.environ.get('CUDA_VISIBLE_DEVICES') == '0'
        and os.environ.get('NVIDIA_VISIBLE_DEVICES') == SELECTOR
        and entries.count(b'CUDA_VISIBLE_DEVICES=0') == 1
        and entries.count(b'NVIDIA_VISIBLE_DEVICES=void') == 1
        and sum(e.startswith(b'CUDA_VISIBLE_DEVICES=') for e in entries) == 1
        and sum(e.startswith(b'NVIDIA_VISIBLE_DEVICES=') for e in entries) == 1)

""".replace('SELECTOR',repr(CDI_DEVICE))
            transformed['mps_probe.py']=probe.replace(guard,'compiler_environment()').replace('def preflight(',helper+'def preflight(')
        # Both original adapters intentionally bind protected policy. Keep binding
        # exact; caller may not pass a replacement policy or synthesize authority.
        for name in ('fresh_preflight.py','peer_probe.py','run_peer_oom.py'):
            transformed[name]=files[name].decode()
        # Topological repin: helper -> engine -> runner plus shared peer closure.
        for dep in ('same_pod_imports.py','same_parent_engine.py','mps_probe.py','mapper.py','engine.py',
                    'fresh_preflight.py','peer_probe.py','run_peer_oom.py'):
            if dep not in generated:continue
            old,new=sha(generated[dep]),sha(transformed[dep].encode())
            if old != new:
                for n,s in transformed.items():
                    if n!=dep: transformed[n]=s.replace(old,new)
        for n,s in transformed.items():family_files[label+'/'+n]=s.encode()
    files.update(family_files)
    # Full original managed/VMM closure requires admitted actual Pod UIDs; keep
    # the exact-source adapter available for the post-finalize stage, never fake.
    closure=substitutions(checked['native-fresh-unequal/fresh_import_closure.py'].decode(),ctx)
    closure=closure.replace('3b217fe8-5750-4ead-954a-09286afd7d3f',ctx['cohort'])
    closure=closure.replace('Source332','QA-policy-bound')
    require(closure.count(' for name,s in text.items():')==1,'Exact import closure loop required')
    native_guards=(
        ('vmm-cross-parent/vmm_bridge.py',"inventory['gpu_id']==1552","inventory['gpu_id']==1553"),
        ('vmm-cross-parent/kernel_witness_validator.py',"a['gpu_id']==1552","a['gpu_id']==1553"),
        ('vmm-owner-exit/host_owner_observer.py','driver/nvidia/gpus/0000:06:10.0/cps_native_caps','driver/nvidia/gpus/0000:06:11.0/cps_native_caps'),
        ('vmm-cross-parent/vmm_bridge.py','driver/nvidia/gpus/0000:06:10.0/cps_native_caps','driver/nvidia/gpus/0000:06:11.0/cps_native_caps'))
    guard_adapter=''
    for name,old,new in native_guards:
        guard_adapter+=' text['+repr(name)+']=replace(text['+repr(name)+'],'+repr(old)+','+repr(new)+')\n'
    closure=closure.replace(' for name,s in text.items():',guard_adapter+' for name,s in text.items():\n  s=s.replace('+repr(FIRST_GPU)+','+repr(SECOND_GPU)+')')
    closure=replace_pin(closure,'5ce86051f1a9bd435abc14a8633f273e03e1af086658de7fad8b8d5dcceb3cc0',sha(files['fresh_preflight.py']))
    files['prepare_import_closure.py']=closure.encode()
    historical=load('second_historical_inventory',checked['native-fresh-unequal/fresh_import_closure.py'],source_path('native-fresh-unequal/fresh_import_closure.py'))
    for n,pin in historical.PINS.items():
        require(sha((historical.OLD/n).read_bytes())==pin,'Complete historical gate source preimage required')
        closure_pins['historical-group-probes/'+n]=pin
    for n,pin in controller.PINS.items():closure_pins['sdk/cps_compute/'+n]=pin
    restart=files['fresh_preflight.py'].decode()
    require(restart.count("current['restartCount']==0")==1,'Exact initial restart guard span required')
    restart=restart.replace("current['restartCount']==0","current['restartCount']==(1 if row['name']=="+repr('native-second-card-a-'+ctx['cohort'][:8])+" else 0)")
    files['restart/fresh_preflight.py']=restart.encode()
    observed=files['observe.py'].decode()
    require(observed.count("status['restartCount']==0")==1,'Exact Root notebook restart assertion required')
    names=('native-second-card-a-'+ctx['cohort'][:8],'native-second-card-b-'+ctx['cohort'][:8])
    observed=observed.replace("status['restartCount']==0","intent.name in "+repr(names)+" and status['restartCount']==(1 if intent.name=="+repr(names[0])+" else 0)")
    arg="p.add_argument('--execute',action='store_true');p.add_argument('--controller',type=Path)"
    require(observed.count(arg)==1 and observed.count('    c=controller(args.controller);')==1,'Exact Root observer admission seam required')
    observed=observed.replace(arg,arg+";p.add_argument('--source-sha256')")
    pincheck="""    fd=os.open(__file__,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);raw=os.read(fd,262145);after=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==before.st_gid==0
                and before.st_nlink==1 and stat.S_IMODE(before.st_mode)==0o400
                and len(raw)<=262144 and hashlib.sha256(raw).hexdigest()==args.source_sha256
                and all(getattr(before,k)==getattr(after,k) for k in
                        ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),
                'Exact protected restart observer source pin required')
    finally:os.close(fd)
"""
    observed=observed.replace('    c=controller(args.controller);',pincheck+'    c=controller(args.controller);')
    files['restart/observe.py']=observed.encode()
    for name in ('run_peer_oom.py','peer_probe.py'):
        files['restart/'+name]=files[name]
    for name,raw in files.items():
        if name.endswith('.py'):compile(raw,name,'exec')
    families={name:{'state':'unrun','receipts':[]} for name in
              ('cap-assignment','oom-peer','aggregate','memory-import','restart-cleanup','mps','capacity')}
    for name,paths in {'cap-assignment':['controller.py','observe.py'],'oom-peer':['run_peer_oom.py'],'aggregate':['run_aggregate.py'],'memory-import':['imports/run_imports.py','prepare_import_closure.py'],'restart-cleanup':['restart/run_peer_oom.py','controller.py'],'mps':['mps/run_mps.py'],'capacity':['physical_samples.py']}.items():families[name]['entrypoints']=paths
    return {'files':files,'families':families,'context':ctx,
            'source_sha256':{**closure_pins,'reviewed-host-loader':COLLECTOR_SHA},
            'hardware_qualified':False,'production_qualified':False}



def finalize_import_sources(observations, manifest_raw, manifest_sha, host_argv):
    """Offline second phase: actual finalized manifest, no invented Pod identity."""
    require(sha(manifest_raw)==manifest_sha and len(manifest_raw)<=65536,
            'Exact bounded finalized manifest bytes required')
    # The independently captured native inventory is tied to the same Node/boot
    # by context(); execution still rechecks the exact current inventory/epoch.
    inventory=observations['device'].get('native_inventory')
    require(type(inventory)is dict and set(inventory)=={'version','backend','gpu_uuid','gpu_id','entries'}
            and inventory['version']==1 and inventory['backend']=='misc-fallback'
            and inventory['gpu_uuid']==SECOND_GPU and type(inventory['gpu_id'])is int
            and inventory['gpu_id']==1553 and type(inventory['entries'])is list
            and observations['device'].get('pci_bdf')=='0000:06:11.0'
            and type(observations['device'].get('minor_number'))is int
            and observations['device']['minor_number']==1,
            'Exact captured second-card native GPU identity required')
    generated=build_sources(observations)
    require(type(host_argv) is list and 3<=len(host_argv)<=128
            and all(type(v) is str and 0<len(v)<=4096 and not any(c in v for c in '\x00\r\n') for v in host_argv)
            and Path(host_argv[0]).name in ('ssh','kubectl')
            and ('sudo' in host_argv or 'nsenter' in host_argv),
            'Independently reviewed bounded Root host transport required')
    raw=generated['files']['prepare_import_closure.py'].decode()
    tree=ast.parse(raw)
    node=next(n for n in tree.body if isinstance(n,ast.Assign)
              and any(isinstance(t,ast.Name) and t.id=='HOST_ARGV' for t in n.targets))
    old=ast.get_source_segment(raw,node)
    require(raw.count(old)==1,'Exact host transport assignment required')
    raw=raw.replace(old,'HOST_ARGV='+repr(host_argv))
    module=load('second_import_closure_finalized',raw,HERE/'prepare_import_closure.py')
    files=module.build(json.loads(manifest_raw),manifest_sha,
                       generated['files']['fresh_preflight.py'],sha(generated['files']['fresh_preflight.py']))
    files['manifest.json']=manifest_raw
    files['source-preparation.py']=raw.encode()
    return files


def write_files(output, files):
    output.mkdir(mode=0o700)
    for name,data in files.items():
        path=output/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(data)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare',action='store_true');p.add_argument('--finalize-imports',action='store_true');
    p.add_argument('--manifest',type=Path);p.add_argument('--manifest-sha256');p.add_argument('--host-argv',type=Path);p.add_argument('--host-argv-sha256');p.add_argument('--observations',type=Path)
    p.add_argument('--observations-sha256');p.add_argument('--inputs',type=Path);p.add_argument('--inputs-sha256')
    p.add_argument('--output',type=Path);p.add_argument('--approve-qa-hostpaths',action='store_true')
    args=p.parse_args(argv)
    if not (args.prepare or args.finalize_imports):
        print('{"inert":true,"api_calls":false,"gpu_calls":false}');return
    if args.finalize_imports:
        require(not args.prepare and all((args.observations,args.observations_sha256,args.manifest,args.manifest_sha256,args.host_argv,args.host_argv_sha256,args.output)), 'Exclusive finalized import phase with exact pinned inputs required')
        observed=args.observations.read_bytes();host=args.host_argv.read_bytes()
        require(len(observed)<=1048576 and len(host)<=65536 and sha(observed)==args.observations_sha256 and sha(host)==args.host_argv_sha256,'Exact observation/Root transport raw pins required')
        files=finalize_import_sources(json.loads(observed),args.manifest.read_bytes(),args.manifest_sha256,json.loads(host))
        files['preparation.json']=canonical({'state':'prepared-not-executed','generated_sha256':{n:sha(v) for n,v in files.items()},'hardware_qualified':False,'production_qualified':False})+b'\n'
        write_files(args.output,files)
        print('{"prepared":true,"api_calls":false,"gpu_calls":false}');return
    require(all((args.observations,args.observations_sha256,args.inputs,args.inputs_sha256,args.output,args.approve_qa_hostpaths)),
            'Pinned observations/request/new output/explicit hostpath approval required')
    observed=args.observations.read_bytes();raw=args.inputs.read_bytes()
    require(len(observed)<=1048576 and len(raw)<=65536 and sha(observed)==args.observations_sha256
            and sha(raw)==args.inputs_sha256,'Exact bounded raw capture/request pins required')
    result=build_sources(json.loads(observed));request=json.loads(raw)
    require(request.get('pair')=='5-10' and request.get('cohort_uid')==result['context']['cohort'] and request.get('policy_hash')==result['context']['policy_hash'],
            'Closed exact fresh 5/10 cohort request required')
    renderer=load('second_renderer',result['files']['render_fixture.py'],args.output/'render_fixture.py')
    review=renderer.render(request,approve_qa_hostpaths=True)
    files=result.pop('files')
    result.update(version=1,state='offline-prepared-not-executed',observations_sha256=sha(observed),
                  request_sha256=sha(raw),generated_sha256={n:sha(r) for n,r in files.items()},
                  policy_hash=request['policy_hash'],launch_authorized=False)
    files.update({'preparation.json':canonical(result)+b'\n','observations.raw.json':observed,'inputs.json':raw,
                  'review.json':canonical(review)+b'\n','gate-source.configmap.json':canonical(review['source_configmap'])+b'\n'})
    files.update({k+'.proposed.json':canonical(v)+b'\n' for k,v in review['pods'].items()})
    write_files(args.output,files)
    print(json.dumps({'prepared':True,'api_calls':False,'gpu_calls':False,'launch_authorized':False}))

if __name__=='__main__':main()

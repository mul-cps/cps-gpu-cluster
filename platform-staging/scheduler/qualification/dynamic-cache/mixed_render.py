#!/usr/bin/env python3
"""Offline mixed 5/10/20 renderer. It creates only suspended, CPU-gated fixtures."""
import argparse
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import sys
import types
import zipfile

import render as original
import mixed_contract as contract

HERE = Path(__file__).resolve().parent
IMAGE_PULL_SECRET = 'cps-compute-image-pull'
GATE = '''import hashlib,json,os,pathlib,stat,sys,time
from mixed_contract import UID,GID,digest,validate_approval
assert (os.getuid(),os.getgid())==(UID,GID)
proof=json.loads(pathlib.Path('/probe/preflight.json').read_text())
assert set(proof['sources'])=={'mixed_probe.py','mixed_contract.py','probe_compiled.py'}
assert digest(proof['sources'])==proof['probeSha256']==sys.argv[2]
for name,digest in proof['sources'].items():
 assert hashlib.sha256(pathlib.Path('/probe',name).read_bytes()).hexdigest()==digest
cache=pathlib.Path('/cache-root/private/usage.cache').stat(follow_symlinks=False)
assert stat.S_ISREG(cache.st_mode) and (cache.st_uid,cache.st_gid)==(UID,GID)
assert stat.S_IMODE(cache.st_mode)==0o600 and cache.st_nlink==1
marker=pathlib.Path('/cache-root/operator-approved.json')
deadline=time.monotonic()+60
while time.monotonic()<deadline:
 if marker.exists():
  info=marker.stat(follow_symlinks=False)
  assert stat.S_ISREG(info.st_mode) and (info.st_uid,info.st_gid)==(UID,GID)
  assert stat.S_IMODE(info.st_mode)==0o600 and info.st_nlink==1 and info.st_size<=16384
  value=json.loads(marker.read_text())
  validate_approval(value,proof,sys.argv[1],os.environ['FIXTURE_POD_UID'])
  assert value['probeSha256']==sys.argv[2]
  print(json.dumps({'event':'mixed-cpu-gate-released','approval':value,'observedNs':time.time_ns(),
   'role':sys.argv[1],'podUid':os.environ['FIXTURE_POD_UID'],'runId':proof['runId']}),flush=True)
  sys.exit(0)
 time.sleep(0.2)
raise SystemExit('Reviewed temporary MPS cap/thread candidate was not released within 60 seconds')
'''


def compiler(wheel):
    wheel = Path(wheel)
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != contract.WHEEL_SHA:
        raise ValueError('Exact verified 40b9525 wheel required')
    with zipfile.ZipFile(wheel) as archive:
        source = archive.read('cps_compute/gpu_runtime.py')
    if hashlib.sha256(source).hexdigest() != contract.MODULE_SHA:
        raise ValueError('Verified runtime compiler module bytes required')
    name = '_mixed_packaged_gpu_runtime'
    module = types.ModuleType(name);module.__file__ = str(wheel.resolve())+'/cps_compute/gpu_runtime.py'
    sys.modules[name] = module
    exec(compile(source,module.__file__,'exec'),module.__dict__)
    return module


def compile_plan(wheel, gib):
    if type(gib) is not int or gib not in contract.QUOTAS:
        raise ValueError('Only fixed 5/10/20 GiB profiles allowed')
    module = compiler(wheel)
    settings = module.SharedGpuRuntimeSettings.from_catalog({'trusted':{'sharedGpuRuntime':{
        'initializerImage':contract.IMAGE,'approvedInitializerImages':[contract.IMAGE],
        'uid':contract.UID,'gid':contract.GID}}})
    profile = {'gpu':{'mode':'shared','nominalMemoryGiB':gib,'qualification':{
        'mechanism':'kai-hami','annotations':{'gpu-memory':str(gib*1024)},'resources':{}}}}
    return asdict(module.compile_gpu_runtime(profile,settings=settings,container_name='main'))


def render(preflight,run_id,wheel,*,now=None):
    if preflight.get('image') != contract.IMAGE:
        raise ValueError('Verified mixed qualification image required')
    proof = original.validate_preflight({**preflight,'image':original.IMAGE},now)
    proof['image'] = contract.IMAGE
    contract.validate_reference(preflight['mpsReference'],preflight,now=now)
    contract.validate_maintenance_review(preflight['mpsMaintenanceReview'],preflight['mpsReference'],preflight)
    if not re.fullmatch('[a-z0-9]{8,16}',run_id):
        raise ValueError('Run ID must be 8-16 lowercase letters/digits')
    sources = {name:(HERE/name).read_text() for name in ('mixed_probe.py','mixed_contract.py','probe_compiled.py')}
    source_hashes = {name:hashlib.sha256(source.encode()).hexdigest() for name,source in sources.items()}
    source_sha = contract.digest(source_hashes)
    proof.update(runId=run_id,mpsReference=copy.deepcopy(preflight['mpsReference']),
        mpsMaintenanceReview=copy.deepcopy(preflight['mpsMaintenanceReview']),sources=source_hashes,
        probeSha256=source_sha,runtimeIdentity={'uid':contract.UID,'gid':contract.GID},
        compiler={'sourceCommit':contract.SOURCE,'wheelSha256':contract.WHEEL_SHA,'moduleSha256':contract.MODULE_SHA,'image':contract.IMAGE},
        runtimePlans={role:compile_plan(wheel,gib) for role,gib in contract.ROLES.items()},
        nominalBudgetMiB=35*1024,simultaneousPayloadMiB=sum(sum(values) for values in contract.HOLD_ALLOCATIONS.values()),
        schedulerQuotaCandidates=copy.deepcopy(contract.QUOTAS),schedulerQuotaCandidatesLiveQualified=False,
        productionQualified=False,mpsThreeClientQualified=False)
    name = 'dynamic-mixed-'+run_id
    labels = {'compute.cps.unileoben.ac.at/qualification':'trusted-operator',
              'compute.cps.unileoben.ac.at/fixture':name,'kai.scheduler/queue':'cps-batch'}
    annotations = {'compute.cps.unileoben.ac.at/qualification-state':'disabled-manual-fixture',
        'compute.cps.unileoben.ac.at/expected-node-uid':proof['nodeUid'],
        'compute.cps.unileoben.ac.at/fixture-run-id':run_id,'compute.cps.unileoben.ac.at/probe-sha256':source_sha,
        'compute.cps.unileoben.ac.at/compiler-source':contract.SOURCE,
        'compute.cps.unileoben.ac.at/compiler-wheel-sha256':contract.WHEEL_SHA}
    items = [{'apiVersion':'v1','kind':'ConfigMap','immutable':True,'metadata':{
        'name':name,'namespace':original.NAMESPACE,'labels':labels,'annotations':annotations},
        'data':{**sources,'operator-gate.py':GATE,'preflight.json':json.dumps(proof,sort_keys=True)}}]
    for role,gib in contract.ROLES.items():
        plan = proof['runtimePlans'][role]
        security = {**plan['container_security_context'],'readOnlyRootFilesystem':True}
        env = [{'name':k,'value':v} for k,v in plan['environment'].items()]
        env.extend([{'name':'FIXTURE_POD_UID','valueFrom':{'fieldRef':{'apiVersion':'v1','fieldPath':'metadata.uid'}}},
            {'name':'FIXTURE_RUN_ID','value':run_id},{'name':'FIXTURE_UID','value':str(contract.UID)},
            {'name':'FIXTURE_GID','value':str(contract.GID)},{'name':'FIXTURE_ROLE','value':role},
            {'name':'FIXTURE_PROFILE_GIB','value':str(gib)},{'name':'EXPECTED_HAMI_LIMIT_MIB','value':str(gib*1024)},
            {'name':'EXPECTED_HAMI_SHA256','value':proof['hami']['sha256']},
            {'name':'EXPECTED_HAMI_REVISION','value':original.HAMI_REVISION},
            {'name':'EXPECTED_GPU_UUID','valueFrom':{'fieldRef':{'apiVersion':'v1','fieldPath':original.GPU_UUID_FIELD_PATH}}}])
        gate = {'name':'await-operator-runtime-review','image':contract.IMAGE,
            'command':['python','-u','/probe/operator-gate.py',role,source_sha],'securityContext':security,
            'env':[{'name':'FIXTURE_POD_UID','valueFrom':{'fieldRef':{'apiVersion':'v1','fieldPath':'metadata.uid'}}}],
            'resources':{'requests':{'cpu':'10m','memory':'32Mi'},'limits':{'cpu':'100m','memory':'64Mi'}},
            'volumeMounts':[{'name':'probe','mountPath':'/probe','readOnly':True},{'name':'cps-gpu-cache','mountPath':'/cache-root'}]}
        spec = {'schedulerName':'kai-scheduler','priorityClassName':'cps-batch','restartPolicy':'Never',
            'activeDeadlineSeconds':180,'automountServiceAccountToken':False,'imagePullSecrets':[{'name':IMAGE_PULL_SECRET}],
            'nodeSelector':{'kubernetes.io/hostname':original.NODE},'securityContext':copy.deepcopy(plan['pod_security_context']),
            'initContainers':[*copy.deepcopy(plan['init_containers']),gate],
            'containers':[{'name':'main','image':contract.IMAGE,'command':['python','-u','/probe/mixed_probe.py',role],
                'securityContext':security,'env':env,'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'cpu':'1','memory':'256Mi'}},
                'volumeMounts':[{'name':'probe','mountPath':'/probe','readOnly':True},{'name':'scratch','mountPath':'/tmp'},
                    *copy.deepcopy(plan['volume_mounts']),{'name':'cps-gpu-cache','mountPath':'/review/operator-approved.json',
                        'subPath':'operator-approved.json','readOnly':True}]}],
            'volumes':[{'name':'probe','configMap':{'name':name,'defaultMode':292}},
                       {'name':'scratch','emptyDir':{'sizeLimit':'64Mi'}},*copy.deepcopy(plan['volumes'])]}
        items.append({'apiVersion':'batch/v1','kind':'Job','metadata':{'name':name+'-'+role,
            'namespace':original.NAMESPACE,'labels':labels,'annotations':annotations},'spec':{
                'suspend':True,'backoffLimit':0,'activeDeadlineSeconds':180,'template':{
                    'metadata':{'labels':labels,'annotations':{**annotations,**plan['annotations']}},'spec':spec}}})
    return {'apiVersion':'v1','kind':'List','items':items}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('preflight','compiler-wheel','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--run-id',required=True);args=parser.parse_args()
    if args.output.resolve().is_relative_to(HERE.parents[3]):raise SystemExit('Store runtime fixtures outside Git')
    value=render(json.loads(args.preflight.read_text()),args.run_id,args.compiler_wheel)
    with args.output.open('x') as output:json.dump(value,output,indent=2);output.write('\n')
    print(json.dumps({'rendered':True,'suspendedJobs':3,'executed':False,'productionQualified':False}))

#!/usr/bin/env python3
"""Generate offline admission fixtures using the exact released SDK wheel APIs.

Compiled Argo artifacts are real compiler output. Pod materialization is an
explicit synthetic declaration, never an observed Argo-controller result.
"""
import argparse
import copy
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
import types
import uuid
import zipfile

SOURCE = '40b9525097776e0d5927242ca625a27dadbd797c'
WHEEL_SHA256 = '8321127b7db5f6554ddde60f9bb916a7414d570a3405c209632dd142210fe0f4'
IMAGE = ('ghcr.io/mul-cps/cps-compute:qualification-40b9525@sha256:'
         'b3802a7f70077ff56adbc060d1177409eeff76c8b3cf8ccf9f39047c1e6716bf')
GPU_MODULE_SHA256 = '93f4e01c3682e52192d43c130073b3daf50c59ea7bd06342971f5f4add0a2b68'
ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CATALOG = ROOT/'compute-policy/catalog.json'
DEFAULT_WHEEL = Path('/home/bjoern/cps-platform-evidence/2026-10-07/dynamic-runtime-packaging/40b9525/dist/cps_compute-0.1.0-py3-none-any.whl')
NAMESPACE = 'cps-dynamic-admission-review'
OWNER = 'offline-fixture-person'


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load_sdk(wheel):
    """Use verified zip bytes and relative imports, never an editable SDK copy."""
    path = Path(wheel).resolve();raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != WHEEL_SHA256:
        raise ValueError('Exact reviewed SDK wheel SHA256 required')
    with zipfile.ZipFile(path) as archive:
        modules = {name:archive.read(name) for name in ('cps_compute/policy.py','cps_compute/gpu_runtime.py',
                                                     'cps_compute/jobsets.py','cps_compute/hub.py')}
    if hashlib.sha256(modules['cps_compute/gpu_runtime.py']).hexdigest() != GPU_MODULE_SHA256:
        raise ValueError('Reviewed GPU runtime module bytes required')
    name = '_cps_admission_fixture_sdk_'+WHEEL_SHA256[:12]
    for key in list(sys.modules):
        if key == name or key.startswith(name+'.'):sys.modules.pop(key)
    package = types.ModuleType(name);package.__path__ = [str(path)+'/cps_compute']
    package.__package__ = name;sys.modules[name] = package
    policy = importlib.import_module(name+'.policy')
    if policy.__file__ != str(path)+'/cps_compute/policy.py':
        raise ValueError('Policy source must originate in the verified wheel')
    return policy,{module:hashlib.sha256(source).hexdigest() for module,source in modules.items()}


def fixture_catalog(base,namespace):
    """Declare local test inputs; the canonical disabled catalog is never edited."""
    if not isinstance(namespace,str) or len(namespace)>63 or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?',namespace):
        raise ValueError('Canonical isolated fixture namespace required')
    if not namespace.startswith('cps-dynamic-admission-'):
        raise ValueError('Only an isolated cps-dynamic-admission-* fixture namespace is permitted')
    catalog = copy.deepcopy(base);catalog.pop('policyHash',None)
    catalog['status'] = 'offline-admission-fixture-not-live-qualified'
    catalog['gpuQualification']['qualified'] = True
    catalog['trusted']['namespace'] = namespace
    catalog['trusted']['sharedGpuRuntime'] = {'initializerImage':IMAGE,'approvedInitializerImages':[IMAGE],
                                            'uid':1000,'gid':100}
    catalog['approvedImages'] = [IMAGE]
    for gib in (5,10,20):
        profile = catalog['profiles']['batch-shared-'+str(gib)]
        profile.update(enabled=True,images=[IMAGE],maxAgeSeconds=180)
        profile['gpu']['qualification'] = {'status':'qualified','policyVersion':catalog['version'],
            'evidence':['fixture://offline-admission-inputs-not-live-qualification'],'mechanism':'kai-hami',
            'annotations':{'gpu-memory':str(gib*1024)},'resources':{}}
    return catalog


def workflow_input(catalog,gib):
    profile = catalog['profiles']['batch-shared-'+str(gib)]
    resources = {'cpu':profile['cpu'],'memory':profile['memory']}
    return {'metadata':{'name':'offline-argo-'+str(gib)},'spec':{'entrypoint':'run','activeDeadlineSeconds':180,
        'templates':[{'name':'run','container':{'image':IMAGE,'command':['python','-c'],
            'args':['print("offline fixture only")'],'resources':{'requests':resources,'limits':copy.deepcopy(resources)}}}]}}


def declared_controller_pod(workflow):
    """Projection for CEL tests only; no controller, executor or webhook is run."""
    spec = workflow['spec'];template = spec['templates'][0]
    # UUID5 is reproducible synthetic identity, never a Kubernetes observation.
    owner_uid = str(uuid.uuid5(uuid.NAMESPACE_URL,'fixture://workflow/'+
        workflow['metadata']['namespace']+'/'+workflow['metadata']['name']))
    runtime = json.loads(template['podSpecPatch'])
    main = {'name':'main',**copy.deepcopy(template['container'])}
    main.update(copy.deepcopy(runtime['containers'][0]))
    pod_spec = {key:copy.deepcopy(value) for key,value in runtime.items() if key != 'containers'}
    pod_spec.update(json.loads(spec['podSpecPatch']))
    pod_spec.update(containers=[main],schedulerName=spec['schedulerName'],
        priorityClassName=spec['podPriorityClassName'],serviceAccountName=spec['serviceAccountName'],
        automountServiceAccountToken=spec['automountServiceAccountToken'],restartPolicy='Never',activeDeadlineSeconds=180)
    return {'apiVersion':'v1','kind':'Pod','metadata':{'name':workflow['metadata']['name']+'-declared',
        'namespace':workflow['metadata']['namespace'],**copy.deepcopy(spec['podMetadata']),
        'ownerReferences':[{'apiVersion':'argoproj.io/v1alpha1','kind':'Workflow',
            'name':workflow['metadata']['name'],'uid':owner_uid,'controller':True}]},'spec':pod_spec}


def generate(wheel=DEFAULT_WHEEL,catalog_path=DEFAULT_CATALOG,*,namespace=NAMESPACE):
    base_path = Path(catalog_path).resolve();base_bytes = base_path.read_bytes();base = json.loads(base_bytes)
    if base['gpuQualification']['qualified'] is not False or any(base['profiles']['batch-shared-'+str(g)]['enabled'] for g in (5,10,20)):
        raise ValueError('The canonical source catalog must retain disabled/unqualified GPU profiles')
    policy_module,module_hashes = load_sdk(wheel)
    catalog = fixture_catalog(base,namespace);policy = policy_module.Policy(catalog)
    fixtures = {}
    for gib in (5,10,20):
        profile = 'batch-shared-'+str(gib);request = workflow_input(catalog,gib)
        compiled = policy.validate(request,profile,OWNER)
        runtime = json.loads(compiled['spec']['templates'][0]['podSpecPatch'])
        fixtures[profile] = {'surface':'argo','evidenceStage':'compiled-pre-controller',
            'compilerAPI':'Policy.validate','profileGiB':gib,'compilerInput':request,
            'compiledWorkflow':compiled,'runtimeProjection':runtime,
            'workflowPodSpecProjection':json.loads(compiled['spec']['podSpecPatch']),
            'declaredControllerPod':{'evidenceStage':'declared-synthetic-controller-materialization',
                'object':declared_controller_pod(compiled),'actualControllerExecuted':False,
                'actualWebhookExecuted':False,'executorMaterialized':False,
                'limitations':['Argo executor init/wait/token/artifact mounts require separate observed controller evidence',
                               'No KAI injected GPU selection/quota ConfigMaps or hostPath mounts are invented']}}
    result = {'schemaVersion':1,'status':'offline-prepared-not-live-qualified',
        'provenance':{'sourceCommit':SOURCE,'wheelSha256':WHEEL_SHA256,'image':IMAGE,'moduleSha256':module_hashes,
            'baseCatalogSha256':hashlib.sha256(base_bytes).hexdigest(),'baseCatalogGpuQualified':False,
            'baseCatalogProfilesEnabled':False,'fixturePolicyHash':policy.hash,'fixturePolicyVersion':policy.version},
        'inputCatalog':catalog,'fixtures':fixtures,
        'qualification':{'liveAdmission':False,'argoControllerMaterialization':False,'gpuIsolation':False,'production':False},
        'pendingSurfaces':{
            'jobset':{'status':'pending-separate-generator-and-admission-contract',
                'reason':'JobSetLauncher uses UID1000/GID1000 and a distinct trusted controller/worker creator surface'},
            'hub':{'status':'pending-fresh-actual-KubeSpawner-manifest',
                'reason':'Hub credentials/storage/creator policy and actual KubeSpawner Pod construction require a separate fixture; no fake spawner proof'}},
        'limitations':['Fixture-only qualification flags in inputCatalog exercise the real compiler; they are not live evidence or activation',
            'The wheel APIs are executed locally; no Kubernetes, Argo controller, KAI injector, GPU or network calls occur',
            'Declared Pod projections cannot prove actual Argo-controller/webhook behavior']}
    result['manifestSha256'] = digest(result)
    return result


def verify(value,wheel=DEFAULT_WHEEL,catalog_path=DEFAULT_CATALOG,*,namespace=NAMESPACE):
    """Regenerate through pinned APIs; recomputed self-hashes cannot bless forgeries."""
    claimed = value.get('manifestSha256');unhashed = {key:entry for key,entry in value.items() if key != 'manifestSha256'}
    if claimed != digest(unhashed):raise ValueError('Fixture manifest checksum changed')
    if value['inputCatalog']['trusted']['namespace'] != namespace:
        raise ValueError('Fixture namespace differs from the independently selected isolated namespace')
    if value != generate(wheel,catalog_path,namespace=namespace):
        raise ValueError('Fixture differs from actual pinned compiler regeneration')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel',type=Path,default=DEFAULT_WHEEL)
    parser.add_argument('--catalog',type=Path,default=DEFAULT_CATALOG)
    parser.add_argument('--namespace',default=NAMESPACE)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT):raise SystemExit('Store fixtures outside Git')
    value = generate(args.wheel,args.catalog,namespace=args.namespace)
    with args.output.open('x') as output:json.dump(value,output,indent=2);output.write('\n')
    print(json.dumps({'fixtures':len(value['fixtures']),'actualCompilerAPI':True,
                      'actualControllerExecuted':False,'productionQualified':False}))

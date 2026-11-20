#!/usr/bin/env python3
"""Actual pinned notebook compiler APIs, with declared offline HTTP/S3 transports.

No controller or injector is executed. The detached executor patch is a proposed
trusted change, not part of the current compiled Workflow and not live evidence.
"""
import argparse
import asyncio
import base64
import copy
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import types
from urllib.parse import parse_qsl
import uuid
import zipfile

import compiled_fixtures as compiled

CONTROLLER_SOURCE = Path('/tmp/cps-argo-workflowpod.go')
CONTROLLER_SOURCE_SHA = '235772a6cb74cfb6a2bc508e40f43e2b36d7b33296fe3524c60c7da58c85eacd'
FIXTURE_MTIME = 1791360000
BUCKET = 'offline-notebook-fixture'
ARTIFACT_CONFIG = {'endpoint':'artifacts.fixture.invalid:443',
                   'credentialSecret':'offline-artifact-credentials', 'caSecret':'offline-artifact-ca'}
MODULES = ('submissions', 'notebooks', 'artifacts', 'argo', 'lifecycle', 'runner')


def offline_run(coroutine):
    """Bound the offline chain and keep worker completions observable here.

    Restricted hosts can suppress asyncio's socket-pair thread wakeup. A small
    timer makes the event loop poll completion callbacks without changing any
    SDK timeout, asyncio.to_thread call, or transport implementation.
    """
    loop=asyncio.new_event_loop();timer=None
    def poll():
        nonlocal timer
        timer=loop.call_later(0.01,poll)
    poll()
    try:return loop.run_until_complete(asyncio.wait_for(coroutine,120))
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor(timeout=10))
        finally:
            timer.cancel();loop.close()


def modules(wheel):
    policy, hashes = compiled.load_sdk(wheel)
    loaded = {'policy':policy}
    with zipfile.ZipFile(wheel) as archive:
        for name in MODULES:
            member = 'cps_compute/'+name+'.py'
            hashes[member] = hashlib.sha256(archive.read(member)).hexdigest()
            loaded[name] = importlib.import_module(policy.__package__+'.'+name)
            if loaded[name].__file__ != str(Path(wheel).resolve())+'/'+member:
                raise ValueError('Notebook module must originate in the reviewed wheel')
    return loaded, hashes


class StorageError(Exception):
    def __init__(self, code):
        self.response = {'Error':{'Code':code}}
        super().__init__(code)


class MemoryS3:
    """Transport-only fake: conditional immutable objects and UID metadata binding."""
    def __init__(self):
        self.objects = {}; self.calls = []

    def _get(self, bucket, key):
        try:return self.objects[(bucket,key)]
        except KeyError:raise StorageError('NoSuchKey') from None

    def put_object(self, *, Bucket, Key, Body, Metadata, Tagging, IfNoneMatch=None, **unused):
        self.calls.append({'operation':'put_object','key':Key,'condition':IfNoneMatch})
        if IfNoneMatch == '*' and (Bucket,Key) in self.objects:raise StorageError('PreconditionFailed')
        data = Body.read() if hasattr(Body,'read') else bytes(Body)
        value = {'Body':data, 'Metadata':copy.deepcopy(Metadata),
                 'ETag':'"'+hashlib.sha256(data).hexdigest()+'"','tags':dict(parse_qsl(Tagging))}
        self.objects[(Bucket,Key)] = value
        return {'ETag':value['ETag']}

    def head_object(self, *, Bucket, Key):
        self.calls.append({'operation':'head_object','key':Key})
        value = self._get(Bucket,Key)
        return {'Metadata':copy.deepcopy(value['Metadata']), 'ETag':value['ETag'], 'ContentLength':len(value['Body'])}

    def get_object(self, *, Bucket, Key):
        self.calls.append({'operation':'get_object','key':Key})
        value = self._get(Bucket,Key)
        return {'Body':io.BytesIO(value['Body']), 'Metadata':copy.deepcopy(value['Metadata']), 'ETag':value['ETag']}

    def copy_object(self, *, Bucket, Key, CopySource, CopySourceIfMatch, MetadataDirective, Metadata):
        self.calls.append({'operation':'copy_object','key':Key,'condition':CopySourceIfMatch})
        value = self._get(CopySource['Bucket'],CopySource['Key'])
        if value['ETag'] != CopySourceIfMatch:raise StorageError('PreconditionFailed')
        if MetadataDirective != 'REPLACE':raise ValueError('Only SDK metadata binding is supported')
        self.objects[(Bucket,Key)] = {**copy.deepcopy(value),'Metadata':copy.deepcopy(Metadata)}
        return {'CopyObjectResult':{'ETag':value['ETag']}}

    def get_object_tagging(self, *, Bucket, Key):
        self.calls.append({'operation':'get_object_tagging','key':Key})
        return {'TagSet':[{'Key':k,'Value':v} for k,v in self._get(Bucket,Key)['tags'].items()]}

    def put_object_tagging(self, *, Bucket, Key, Tagging):
        self.calls.append({'operation':'put_object_tagging','key':Key})
        self._get(Bucket,Key)['tags'] = {t['Key']:t['Value'] for t in Tagging['TagSet']}
        return {}


class Response:
    def __init__(self, code, body=None):self.status_code=code;self.body=copy.deepcopy(body)
    def raise_for_status(self):
        if self.status_code >= 400:raise ValueError('Offline HTTP error '+str(self.status_code))
    def json(self):return copy.deepcopy(self.body)


class MemoryArgoHTTP:
    """No controller: only explicitly synthetic name/UID API response assignment."""
    def __init__(self):self.workflows={};self.requests=[]
    async def get(self, path, **unused):
        self.requests.append({'method':'GET','path':path})
        name=path.rsplit('/',1)[-1]
        return Response(200,self.workflows[name]) if name in self.workflows else Response(404)
    async def post(self, path, *, json):
        self.requests.append({'method':'POST','path':path,'body':copy.deepcopy(json)})
        workflow=copy.deepcopy(json['workflow']);meta=workflow['metadata'];name=meta['name']
        if name in self.workflows:return Response(409)
        meta['uid']=str(uuid.uuid5(uuid.NAMESPACE_URL,'fixture://notebook-workflow/'+meta['namespace']+'/'+name))
        meta['resourceVersion']='1'
        self.workflows[name]=workflow
        return Response(200,workflow)


def request(gib):
    """Deterministic saved notebook including outputs that the SDK must strip."""
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{},'cells':[
        {'id':'parameter-cell','cell_type':'code','metadata':{'tags':['parameters']},
         'source':'count = 1\nlabel = "default"','execution_count':3,
         'outputs':[{'output_type':'stream','name':'stdout','text':'saved output'}]},
        {'id':'import-cell','cell_type':'code','metadata':{},'source':'from helper import value\nprint(value)',
         'execution_count':4,'outputs':[{'output_type':'stream','name':'stdout','text':'7'}]}]}
    encode=lambda value:base64.b64encode(value).decode('ascii')
    return {'profile':'batch-shared-'+str(gib),'walltime':180,'project':'offline-project',
            'notebook':encode(compiled.canonical(notebook)),
            'parameters':{'count':3,'label':'fixture','enabled':True,'ratio':0.25,'items':[1,None], 'options':{'x':'y'}},
            'files':{'helper.py':encode(b'value = 7\n'),'data/settings.json':encode(b'{"selected":true}\n')}}


def proposed_executor_patch(source=CONTROLLER_SOURCE):
    raw=Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTROLLER_SOURCE_SHA:
        raise ValueError('Reviewed cached Argo v3.7.18 controller source required')
    security={'runAsNonRoot':True,'runAsUser':10001,'runAsGroup':10001,'allowPrivilegeEscalation':False,
              'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']},'seccompProfile':{'type':'RuntimeDefault'}}
    patch={'volumes':[{'name':'tmp-dir-argo','emptyDir':{}}],
           'containers':[{'name':'wait','securityContext':copy.deepcopy(security)}],
           'initContainers':[{'name':'init','securityContext':copy.deepcopy(security),
              'volumeMounts':[{'name':'tmp-dir-argo','mountPath':'/tmp','subPath':'init'}]}]}
    return {'evidenceStage':'planned-trusted-workflow-podspecpatch-not-applied','patch':patch,
            'embeddedInCompiledWorkflows':False,'actualControllerExecuted':False,'qualified':False,
            'controllerSourceSha256':CONTROLLER_SOURCE_SHA,'controllerVersion':'v3.7.18',
            'sourceSpans':['workflow/controller/workflowpod.go:35-51','workflow/controller/workflowpod.go:82-105',
                           'workflow/controller/workflowpod.go:390-401','workflow/controller/workflowpod.go:617-632'],
            'limitations':['Strategic merge feasibility comes from cached controller source, not a controller execution',
                           'Init /tmp subPath ownership and artifact readability across executor UID10001 and main UID1000 are pending',
                           'Executor token/secret mounts and KAI post-webhook mutations require an observed full Pod fixture']}


class Harness:
    """Execute actual SDK chain; only storage/HTTP responses and local clock are fake."""
    def __init__(self, sdk, policy, root):
        self.sdk=sdk;self.policy=policy;self.root=Path(root);self.s3=MemoryS3();self.http=MemoryArgoHTTP()
        self.identity=types.SimpleNamespace(person=compiled.OWNER)
        self.backend=sdk['argo'].ArgoBackend(self.http,policy.catalog['trusted']['namespace'])
        self.launcher=sdk['artifacts'].S3NotebookLauncher(self.s3,BUCKET,self.root,self.backend,artifact_config=ARTIFACT_CONFIG)
        async def normalized_launch(manifest,identity,policy):
            # Archive construction is the SDK's. Normalize local file mtimes only;
            # source bytes, modes, hashes and launcher code remain unchanged.
            for path in (self.root/manifest['id']).rglob('*'):
                if path.is_file():os.utime(path,(FIXTURE_MTIME,FIXTURE_MTIME))
            return await self.launcher(manifest,identity,policy)
        self.submissions=sdk['submissions'].NotebookSubmissions(self.root,normalized_launch)

    async def submit(self, body, key):
        return await self.submissions(body,self.identity,self.policy,idempotency_key=key)

    def snapshot_receipt(self, workflow):
        identifier=workflow['metadata']['annotations']['cps.compute/notebook-id']
        directory=self.root/identifier
        files={str(p.relative_to(directory)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
               'mode':oct(stat.S_IMODE(p.stat().st_mode)),'size':p.stat().st_size} for p in sorted(directory.rglob('*')) if p.is_file()}
        object_=self.s3.objects[(BUCKET,'notebook-inputs/'+identifier+'/snapshot.tar')]
        with tarfile.open(fileobj=io.BytesIO(object_['Body']),mode='r') as tar:
            members=[{'name':m.name,'mode':oct(m.mode),'size':m.size,'uid':m.uid,'gid':m.gid,'mtime':m.mtime,
                      'sha256':hashlib.sha256(tar.extractfile(m).read()).hexdigest()} for m in tar.getmembers()]
        return {'manifest':json.loads((directory/'manifest.json').read_text()),'files':files,
                'submittedNotebook':json.loads((directory/'submitted.ipynb').read_text()),
                'parameters':json.loads((directory/'parameters.json').read_text()),
                'archive':{'sha256':hashlib.sha256(object_['Body']).hexdigest(),'members':members,
                           'metadata':copy.deepcopy(object_['Metadata']),'tags':copy.deepcopy(object_['tags'])},
                'intent':json.loads(self.s3.objects[(BUCKET,'notebook-provenance/'+identifier+'/intent.json')]['Body']),
                'binding':json.loads(self.s3.objects[(BUCKET,'notebook-provenance/'+identifier+'/binding.json')]['Body'])}


async def _generate(sdk, policy, root):
    harness=Harness(sdk,policy,root);fixtures={}
    for gib in (5,10,20):
        body=request(gib);workflow=await harness.submit(body,'offline-notebook-'+str(gib))
        before=copy.deepcopy(harness.s3.objects)
        retry=await harness.submit(body,'offline-notebook-'+str(gib))
        if retry != workflow or before != harness.s3.objects:raise ValueError('SDK idempotent retry changed immutable inputs')
        fixtures[body['profile']]={'profileGiB':gib,'surface':'notebook-argo',
            'evidenceStage':'actual-sdk-serialized-pre-controller',
            'apiChain':['NotebookSubmissions.__call__','snapshot','S3NotebookLauncher.__call__','ArgoBackend.submit'],
            'request':body,'compiledWorkflow':workflow,'snapshot':harness.snapshot_receipt(workflow),
            'runtimeProjection':json.loads(workflow['spec']['templates'][0]['podSpecPatch']),
            'workflowPodSpecProjection':json.loads(workflow['spec']['podSpecPatch']),
            'apiAssignedMetadata':{'stage':'declared-synthetic-api-response',
                'fields':['metadata.uid','metadata.resourceVersion'],'actualArgoExecuted':False},
            'idempotentRetryPreservedSnapshot':True,'actualControllerExecuted':False,'actualWebhookExecuted':False}
    return fixtures,harness


def generate(wheel=compiled.DEFAULT_WHEEL,catalog_path=compiled.DEFAULT_CATALOG,*,namespace=compiled.NAMESPACE,controller_source=CONTROLLER_SOURCE):
    base_bytes=Path(catalog_path).read_bytes();base=json.loads(base_bytes)
    if base['gpuQualification']['qualified'] is not False or any(base['profiles']['batch-shared-'+str(g)]['enabled'] for g in (5,10,20)):
        raise ValueError('Canonical GPU profiles must remain disabled/unqualified')
    sdk,hashes=modules(wheel);catalog=compiled.fixture_catalog(base,namespace);policy=sdk['policy'].Policy(catalog)
    with tempfile.TemporaryDirectory(prefix='cps-notebook-fixture-',dir='/tmp') as root:
        fixtures,harness=offline_run(_generate(sdk,policy,Path(root)/'snapshots'))
    result={'schemaVersion':1,'status':'offline-prepared-not-live-qualified',
        'provenance':{'sourceCommit':compiled.SOURCE,'wheelSha256':compiled.WHEEL_SHA256,'image':compiled.IMAGE,
            'moduleSha256':hashes,'baseCatalogSha256':hashlib.sha256(base_bytes).hexdigest(),
            'baseCatalogGpuQualified':False,'baseCatalogProfilesEnabled':False,'fixturePolicyHash':policy.hash,
            'archiveFixtureMtime':FIXTURE_MTIME,'archiveLocalUid':os.getuid(),'archiveLocalGid':os.getgid()},
        'inputCatalog':catalog,'fixtures':fixtures,'offlineTransport':{'httpRequests':harness.http.requests,'s3Calls':harness.s3.calls},
        'proposedExecutorPatch':proposed_executor_patch(controller_source),
        'qualification':{'notebookSnapshotAPI':True,'notebookLauncherAPI':True,'networkReachability':False,
            'argoControllerMaterialization':False,'executorSecurity':False,'gpuIsolation':False,'production':False},
        'limitations':['Only in-memory transport responses are synthetic; compiler, snapshot and artifact binding are actual verified wheel APIs',
            'Fake saved notebook selected files are immutable SDK snapshots; no live kernel/environment is captured',
            'Local snapshot mtimes are normalized for repeatable archives; archive ownership records the actual local fixture runner',
            'No executor, notebook kernel, Kubernetes controller, injector, GPU, S3 server or network is executed',
            'The separate executor security patch is proposed only and is not embedded in the compiled Workflows']}
    result['manifestSha256']=compiled.digest(result)
    return result


def verify(value,wheel=compiled.DEFAULT_WHEEL,catalog_path=compiled.DEFAULT_CATALOG,*,namespace=compiled.NAMESPACE,controller_source=CONTROLLER_SOURCE):
    if value.get('manifestSha256') != compiled.digest({k:v for k,v in value.items() if k != 'manifestSha256'}):
        raise ValueError('Notebook fixture checksum changed')
    if value != generate(wheel,catalog_path,namespace=namespace,controller_source=controller_source):
        raise ValueError('Notebook fixture differs from actual pinned SDK regeneration')
    return True


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel',type=Path,default=compiled.DEFAULT_WHEEL)
    parser.add_argument('--catalog',type=Path,default=compiled.DEFAULT_CATALOG)
    parser.add_argument('--namespace',default=compiled.NAMESPACE)
    parser.add_argument('--controller-source',type=Path,default=CONTROLLER_SOURCE)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.resolve().is_relative_to(compiled.ROOT):raise SystemExit('Store generated fixtures outside Git')
    value=generate(args.wheel,args.catalog,namespace=args.namespace,controller_source=args.controller_source)
    with args.output.open('x') as output:json.dump(value,output,indent=2);output.write('\n')
    print(json.dumps({'fixtures':len(value['fixtures']),'actualNotebookSDKAPIs':True,
                      'actualControllerExecuted':False,'executorPatchEmbedded':False,'productionQualified':False}))

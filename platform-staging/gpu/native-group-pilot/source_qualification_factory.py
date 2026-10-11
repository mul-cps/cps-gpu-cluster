"""Source-only Root factory; no credentials/network/provider reads by default."""
import asyncio
import hashlib
import importlib.util
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

MAX_BYTES=1048576
HANDOVER_SHA = '53c5ed41ad95729a6f4248cf9d3f384c4c5c834b0bbef92134fe25c9ede8f870'
CONTEXTS=[]


def require(value,message):
    if not value: raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def local_only_configuration(value):
    # Exact v1 disabled forms; bool/int coercion and unknown provider settings
    # are rejected before any provider constructor or credential lookup.
    minimal={'local':{'enabled':True},'moodle':{'enabled':False}}
    planned={'local':{'enabled':True},'moodle':{'enabled':False,'baseUrl':None,
        'authSecretRef':None,'syncInterval':'10m','readOnly':True}}
    try: return type(value) is dict and canonical(value) in {canonical(minimal),canonical(planned)}
    except (TypeError,ValueError): return False


def checksum(value):
    return 'sha256:'+hashlib.sha256(canonical(value).encode()).hexdigest()


def unique(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'Duplicate metadata key'); result[key]=value
    return result


def decode(raw):
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite metadata')))


def closed(value,keys,message):
    require(type(value) is dict and set(value)==set(keys),message)


def protected(path,sha256):
    require(isinstance(sha256,str) and len(sha256)==64 and all(c in '0123456789abcdef' for c in sha256),'Exact raw SHA required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        info=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==10001 and stat.S_IMODE(info.st_mode) in (0o400,0o600)
            and 0<info.st_size<=MAX_BYTES,'Protected bounded trusted operator UID10001 metadata/source required')
        raw=os.read(fd,MAX_BYTES+1)
        require(len(raw)==info.st_size and hashlib.sha256(raw).hexdigest()==sha256,'Root file pin mismatch')
        return raw
    finally: os.close(fd)


def validate_metadata(value):
    closed(value,{'version','enabled','source','workspace','handover','console','gateway','policy','qualification_config','kubernetes','freeze'},'Closed actual Root metadata required')
    require(type(value['version']) is int and value['version']==1 and value['enabled'] is True,'Explicit enabled factory metadata required')
    require(value['source']+':'+value['workspace'] in {'cps:native-group-b','cit:native-group-a'},'Exact source workspace required')
    for key in ('handover','policy','qualification_config'):
        closed(value[key],{'path','sha256'},'Pinned source/config file required')
    require(value['handover']['sha256']==HANDOVER_SHA,'Frozen helper pin mismatch')
    closed(value['console'],{'config_path','config_sha256','database_path','server_config_path','hub_api_url','compute_policy_url'},'Exact original console configuration binding required')
    closed(value['gateway'],{'namespace','pod','pod_uid','pod_spec_sha256','container','image_id','python_path','reader_path','reader_sha256','request'},'Actual gateway runtime binding required')
    closed(value['kubernetes'],{'kubeconfig','context','kubectl_path','kubectl_sha256'},'Explicit Root Kubernetes transport required')
    closed(value['freeze'],{'mode','freeze_id','operator','admins','targets','hubs','exclusion_evidence'},'Actual external freeze configuration required')
    require(value['freeze']['mode'] in ('source-writers-old-policy','network-isolation'),'Unsupported freeze mechanism')
    closed(value['freeze']['operator'],{'namespace','name','uid','spec_sha256'},'Actual operator Pod binding required')
    require(value['freeze']['operator']['namespace']=='cps-compute'
        and value['freeze']['operator']['name']=='cps-native-handover-20261009-'+value['source'],'Exact trusted source operator required')
    require(type(value['freeze']['admins']) is list and len(value['freeze']['admins'])==2
        and {x.get('source') for x in value['freeze']['admins']}=={'cps','cit'},'Both source admin writers must be frozen')
    for entry in value['freeze']['admins']:
        closed(entry,{'source','namespace','name','uid','selector'},'Exact admin deployment UID and selector required')
        require(entry['namespace']=='cps-compute','Source admin deployment namespace mismatch')
    require(type(value['freeze']['targets']) is list and type(value['freeze']['hubs']) is list,'Explicit freeze targets required')
    if value['freeze']['mode']=='network-isolation':
        require(value['freeze']['hubs']==[] and len(value['freeze']['targets'])==3
            and {x.get('purpose') for x in value['freeze']['targets']}=={'gateway-writes','cps-hub-starts','cit-hub-starts'},'All gateway and Hub start paths must be isolated')
    else:
        require(value['freeze']['targets']==[] and len(value['freeze']['hubs'])==2
            and {x.get('source') for x in value['freeze']['hubs']}=={'cps','cit'},'Both exact old-policy Hub guards required')
        for hub in value['freeze']['hubs']:
            closed(hub,{'source','namespace','pod','pod_uid','spec_sha256','image_id','container','configmap',
                'configmap_uid','configmap_data_sha256','config_volume','policy_key','old_policy_hash','hook_source_sha256'},'Exact installed Hub guard provenance required')
            require(hub['namespace']=={'cps':'jupyterhub','cit':'cit-jhub'}[hub['source']],'Hub source namespace mismatch')
    for target in value['freeze']['targets']:
        closed(target,{'purpose','namespace','selector','pod_uids','policy_name','policy_uid','port'},'Exact isolation target required')
        require(type(target['selector']) is dict and target['selector'] and type(target['pod_uids']) is list
            and target['pod_uids'] and len(target['pod_uids'])==len(set(target['pod_uids']))
            and type(target['port']) is int and 1<=target['port']<=65535,'Actual complete target Pod/port scope required')
    closed(value['freeze']['exclusion_evidence'],{'path','sha256'},'Actual Root enforcement evidence pin required')
    return value


def matches(selector,labels):
    require(type(selector) is dict and not set(selector)-{'matchLabels','matchExpressions'},'Unsupported Pod selector')
    if not all(labels.get(k)==v for k,v in selector.get('matchLabels',{}).items()): return False
    for expression in selector.get('matchExpressions',[]):
        require(type(expression) is dict and not set(expression)-{'key','operator','values'},'Unsupported selector expression')
        key=expression.get('key'); op=expression.get('operator'); values=expression.get('values',[])
        require(isinstance(key,str) and type(values) is list and all(isinstance(x,str) for x in values),'Typed selector expression required')
        require(op in ('In','NotIn','Exists','DoesNotExist'),'Unsupported selector operator')
        if op=='In' and labels.get(key) not in values: return False
        if op=='NotIn' and labels.get(key) in values: return False
        if op=='Exists' and key not in labels: return False
        if op=='DoesNotExist' and key in labels: return False
    return True


def typed_list(document,kind):
    require(type(document) is dict and document.get('kind')==kind and type(document.get('items')) is list
        and not document.get('metadata',{}).get('continue'),'Complete authenticated Kubernetes list required')
    return document['items']


def actual_pod(pod,expected):
    meta=pod.get('metadata',{}) if isinstance(pod,dict) else {}
    require(type(pod) is dict and pod.get('apiVersion')=='v1' and pod.get('kind')=='Pod'
        and meta.get('namespace')==expected['namespace'] and meta.get('name')==expected['name']
        and meta.get('uid')==expected['uid'] and not meta.get('deletionTimestamp')
        and checksum(pod.get('spec'))==expected['spec_sha256'],'Actual Pod UID/spec changed')
    return pod


class FreezeVerifier:
    def __init__(self,metadata,core,apps,networking,backend,policy_hash):
        self.metadata=metadata; self.core=core; self.apps=apps; self.networking=networking; self.backend=backend; self.policy_hash=policy_hash
    async def __call__(self):
        value=self.metadata['freeze']; operator=value['operator']; freeze_id=value['freeze_id']
        call=self.backend._call
        pod=actual_pod(await call(self.core.read_namespaced_pod,operator['name'],operator['namespace']),operator)
        spec=pod['spec']; security=spec.get('securityContext',{}); containers=spec.get('containers',[])
        require(spec.get('serviceAccountName')=='cps-native-handover-operator'
            and security.get('runAsUser')==10001 and security.get('runAsGroup')==10001
            and security.get('fsGroup')==10001 and security.get('runAsNonRoot') is True
            and security.get('seccompProfile')=={'type':'RuntimeDefault'}
            and len(containers)==1 and containers[0].get('name')=='operator'
            and not spec.get('initContainers') and not spec.get('ephemeralContainers')
            and not any(spec.get(key,False) for key in ('hostNetwork','hostPID','hostIPC')), 'Trusted restricted operator Pod required')
        container_security=containers[0].get('securityContext',{})
        require(container_security.get('runAsUser')==10001 and container_security.get('runAsGroup')==10001
            and container_security.get('runAsNonRoot') is True and container_security.get('allowPrivilegeEscalation') is False
            and container_security.get('capabilities')=={'drop':['ALL']}
            and container_security.get('privileged',False) is False,'Trusted restricted operator container required')
        marker={'cps.compute/profile-handover-operator':freeze_id}
        require(all(pod['metadata'].get('labels',{}).get(k)==v for k,v in marker.items()),'Actual Root operator marker absent')
        owners=typed_list(await call(self.core.list_namespaced_pod,operator['namespace'],label_selector='cps.compute/profile-handover-operator='+freeze_id),'PodList')
        require(len(owners)==1 and owners[0]['metadata']['uid']==operator['uid'],'Operator isolation selector is not unique')
        for admin in value['admins']:
            deploy=await call(self.apps.read_namespaced_deployment,admin['name'],admin['namespace'])
            meta=deploy.get('metadata',{})
            require(deploy.get('kind')=='Deployment' and deploy.get('apiVersion')=='apps/v1'
                and meta.get('uid')==admin['uid'] and meta.get('namespace')==admin['namespace']
                and meta.get('name')==admin['name'] and not meta.get('deletionTimestamp')
                and deploy.get('spec',{}).get('replicas')==0
                and type(deploy['spec']['replicas']) is int
                and deploy['spec'].get('selector')=={'matchLabels':admin['selector']},'Actual console writer Deployment is not quiesced')
            items=typed_list(await call(self.core.list_namespaced_pod,admin['namespace'],label_selector=','.join(k+'='+v for k,v in sorted(admin['selector'].items()))),'PodList')
            require(items==[],'Console writer/in-flight Pod still exists')
        policy_uids=[]
        for target in value['targets']:
            selected=typed_list(await call(self.core.list_namespaced_pod,target['namespace'],label_selector=','.join(k+'='+v for k,v in sorted(target['selector'].items()))),'PodList')
            require(sorted(p['metadata']['uid'] for p in selected)==sorted(target['pod_uids'])
                and all(not p['metadata'].get('deletionTimestamp') and matches({'matchLabels':target['selector']},p['metadata'].get('labels',{})) for p in selected),
                'Actual isolated target Pod set changed')
            policies=typed_list(await call(self.networking.list_namespaced_network_policy,target['namespace']),'NetworkPolicyList')
            expected_spec={'podSelector':{'matchLabels':target['selector']},'policyTypes':['Ingress'],
                'ingress':[{'from':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':operator['namespace']}},
                    'podSelector':{'matchLabels':marker}}],'ports':[{'protocol':'TCP','port':target['port']}]}]}
            own=[]
            for policy in policies:
                meta=policy.get('metadata',{}); spec=policy.get('spec',{})
                require(meta.get('namespace')==target['namespace'] and policy.get('apiVersion','networking.k8s.io/v1')=='networking.k8s.io/v1'
                    and policy.get('kind','NetworkPolicy')=='NetworkPolicy','Foreign policy/list type')
                selected_here=any(matches(spec.get('podSelector',{}),p['metadata'].get('labels',{})) for p in selected)
                if 'Ingress' not in spec.get('policyTypes',['Ingress']): continue
                if selected_here:
                    require(meta.get('name')==target['policy_name'] and meta.get('uid')==target['policy_uid']
                        and not meta.get('deletionTimestamp') and spec==expected_spec,'Additive/changed ingress policy defeats writer exclusion')
                    own.append(policy)
            require(len(own)==1,'Exact operator-only isolation policy absent')
            policy_uids.append(target['policy_uid'])
        evidence=decode(protected(value['exclusion_evidence']['path'],value['exclusion_evidence']['sha256']))
        if value['mode']=='source-writers-old-policy':
            for hub in value['hubs']:
                active=actual_pod(await call(self.core.read_namespaced_pod,hub['pod'],hub['namespace']),
                    {'namespace':hub['namespace'],'name':hub['pod'],'uid':hub['pod_uid'],'spec_sha256':hub['spec_sha256']})
                states=[s for s in active.get('status',{}).get('containerStatuses',[]) if s.get('name')==hub['container']]
                require(len(states)==1 and states[0].get('imageID')==hub['image_id'] and states[0].get('state',{}).get('running'),
                    'Installed Hub process/image changed')
                volumes=[v for v in active['spec'].get('volumes',[]) if v.get('name')==hub['config_volume']]
                require(len(volumes)==1 and volumes[0].get('configMap',{}).get('name')==hub['configmap'],'Installed Hub config binding changed')
                cm=await call(self.core.read_namespaced_config_map,hub['configmap'],hub['namespace'])
                meta=cm.get('metadata',{})
                require(cm.get('kind')=='ConfigMap' and cm.get('apiVersion')=='v1' and cm.get('immutable') is True
                    and meta.get('namespace')==hub['namespace'] and meta.get('name')==hub['configmap']
                    and meta.get('uid')==hub['configmap_uid'] and not meta.get('deletionTimestamp') and not cm.get('binaryData')
                    and checksum(cm.get('data'))==hub['configmap_data_sha256'],'Immutable installed Hub configuration changed')
                from cps_compute.policy import Policy
                old=Policy(decode(cm['data'][hub['policy_key']]))
                require(old.hash==hub['old_policy_hash'] and old.hash!=self.policy_hash,'Old-policy rejection barrier absent')
            # Core/config evidence alone cannot prove active hooks, role paths
            # or exclusive Root custody. Require a protected Root-reviewed real
            # runtime/authorization observation bound to every exact object.
            closed(evidence,{'version','protocol','freeze_id','operator_uid','hub_pod_uids','hub_old_policy_hashes',
                'gateway_new_policy_hash','hook_source_sha256','no_alternate_group_start_path',
                'source_service_token_custody','passed','observed_at'},'Actual Root start-exclusion/custody review required')
            require(evidence['protocol']=='root-operator-source-writer-start-exclusion/v1'
                and sorted(evidence['hub_pod_uids'])==sorted(h['pod_uid'] for h in value['hubs'])
                and evidence['hub_old_policy_hashes']=={h['source']:h['old_policy_hash'] for h in value['hubs']}
                and evidence['gateway_new_policy_hash']==self.policy_hash
                and evidence['hook_source_sha256']=={h['source']:h['hook_source_sha256'] for h in value['hubs']}
                and evidence['no_alternate_group_start_path'] is True
                and evidence['source_service_token_custody']=='root-exclusive-during-external-freeze',
                'Unbound active guard/role/custody observation; static config is insufficient')
        else:
            closed(evidence,{'version','protocol','freeze_id','operator_uid','policy_uids','target_pod_uids','passed','observed_at'},'Actual reviewed CNI deny/allow probe required')
            require(evidence['protocol']=='root-operator-actual-CNI-deny-probe/v1'
                and sorted(evidence['policy_uids'])==sorted(policy_uids)
                and sorted(evidence['target_pod_uids'])==sorted(u for t in value['targets'] for u in t['pod_uids']),
                'Unbound actual CNI enforcement observation')
        observed=datetime.fromisoformat(evidence['observed_at'].replace('Z','+00:00'))
        require(type(evidence['version']) is int and evidence['version']==1
            and evidence['freeze_id']==freeze_id and evidence['operator_uid']==operator['uid']
            and evidence['passed'] is True and observed.tzinfo is not None
            and 0<=(datetime.now(timezone.utc)-observed).total_seconds()<=600,'Unbound/stale or failed Root dataplane isolation evidence')
        return {'version':1,'freeze_id':freeze_id,'active':True,'sources':['cit','cps'],'writer_pods':[],
            'external_starts_excluded':True,'observed_at':datetime.now(timezone.utc).isoformat()}


async def gateway_registration(metadata,core,backend,source,workspace):
    require((source,workspace)==(metadata['source'],metadata['workspace']),'Source reader cannot choose a foreign workspace')
    binding=metadata['gateway']; expected={'namespace':binding['namespace'],'name':binding['pod'],
        'uid':binding['pod_uid'],'spec_sha256':binding['pod_spec_sha256']}
    async def check():
        pod=actual_pod(await backend._call(core.read_namespaced_pod,binding['pod'],binding['namespace']),expected)
        states=[s for s in pod.get('status',{}).get('containerStatuses',[]) if s.get('name')==binding['container']]
        require(len(states)==1 and states[0].get('imageID')==binding['image_id'] and states[0].get('state',{}).get('running'),
            'Actual gateway container/image changed')
    await check()
    request={**binding['request'],'source':source,'workspace':workspace}
    raw=protected(binding['reader_path'],binding['reader_sha256'])
    require(b'\0' not in raw,'Invalid reader source')
    code=('import sys\nsys.argv=["-",'+repr(canonical(request))+']\n').encode()+raw
    transport=metadata['kubernetes']
    # Executable argv contains only fixed selectors and paths. Full request and
    # exact source travel over stdin, avoiding ingress URI size limits.
    argv=[transport['kubectl_path'],'--kubeconfig',transport['kubeconfig'],'--context',transport['context'],
        '-n',binding['namespace'],'exec','-i',binding['pod'],'-c',binding['container'],'--',binding['python_path'],'-u','-']
    process=await asyncio.create_subprocess_exec(*argv,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:
        stdout,stderr=await asyncio.wait_for(process.communicate(code),25)
        require(process.returncode==0 and len(stdout)<=MAX_BYTES and len(stderr)<=MAX_BYTES,'Bounded actual readonly gateway exec failed')
        document=decode(stdout)
        require(type(document) is dict,'Actual full gateway registration required')
        await check()
        return document
    finally:
        if process.returncode is None:
            process.kill(); await process.wait()


async def build_from_metadata(metadata,core,apps,networking):
    validate_metadata(metadata)
    raw=protected(metadata['handover']['path'],metadata['handover']['sha256'])
    module=type(os)('root_pinned_handover')
    module.__file__=metadata['handover']['path']; exec(compile(raw,module.__file__,'exec'),module.__dict__)
    from cps_compute.policy import Policy
    from cps_compute.native_qualification import NativeGroupQualification
    from cps_compute.native_gpu_control import KubernetesNativeAuthorityBackend
    policy=Policy(decode(protected(metadata['policy']['path'],metadata['policy']['sha256'])))
    groups=NativeGroupQualification.from_config(decode(protected(metadata['qualification_config']['path'],metadata['qualification_config']['sha256'])),policy)
    require(groups is not None and groups.approval(metadata['source'],metadata['workspace']) is not None,'Actual operator qualification source approval required')
    backend=KubernetesNativeAuthorityBackend(core,groups.authority_namespace)
    freeze=FreezeVerifier(metadata,core,apps,networking,backend,policy.hash)
    await freeze()  # BEFORE opening providers or reading existing credentials
    console=metadata['console']
    # Inspect configured traits before any provider/filesystem constructor.
    # Runtime.create_runtime is deliberately never invoked: it constructs
    # Argo/artifact clients and could install background jobs.
    from e2x_course_hub.course_service.app import CourseServiceApp
    protected(console['config_path'],console['config_sha256'])
    probe=CourseServiceApp(); probe.load_config_file(console['config_path'])
    require(local_only_configuration(probe.course_providers)
        and probe.console_owner==metadata['source'],'Only actual source-owned local provider is permitted')
    protected(console['config_path'],console['config_sha256'])
    app,service=module.load_configured_service(console['config_path'],console['config_sha256'],source=metadata['source'],
        database_path=console['database_path'],server_config_path=console['server_config_path'])
    require(local_only_configuration(app.course_providers)
        and service.compute.base_url==console['compute_policy_url'].rstrip('/')
        and service.hub.hub.api_url.rstrip('/')==console['hub_api_url'].rstrip('/'),'Configured source/provider/API endpoints mismatch')
    CONTEXTS.append(app)  # retain genuine settings/provider for full operation
    async def verify_external_freeze(): return await freeze()
    async def read_registration(source,workspace):
        await freeze()
        return await gateway_registration(metadata,core,backend,source,workspace)
    return {'service':service,'policy':policy,'operator_qualification':groups,'authority_backend':backend,
        'verify_external_freeze':verify_external_freeze,'read_registration':read_registration}


async def build_context():
    # Root explicitly arms the factory in addition to the helper's --execute.
    # Absence is inert before paths, credentials, imports or API construction.
    require(os.environ.get('CPS_HANDOVER_FACTORY_EXECUTE')=='1','Factory inert: explicit Root arming required')
    require(os.geteuid()==10001,'Trusted operator UID10001 factory required')
    metadata=decode(protected(os.environ['CPS_HANDOVER_FACTORY_METADATA_PATH'],os.environ['CPS_HANDOVER_FACTORY_METADATA_SHA256']))
    validate_metadata(metadata)
    from kubernetes import client,config
    kubeconfig=metadata['kubernetes']['kubeconfig']
    info=os.lstat(kubeconfig)
    require(stat.S_ISREG(info.st_mode) and info.st_uid==10001 and stat.S_IMODE(info.st_mode) in (0o400,0o600),'Protected actual Root kubeconfig required')
    config.load_kube_config(config_file=kubeconfig,context=metadata['kubernetes']['context'])
    # Source of kubectl is pinned without treating public executable modes as
    # metadata modes. Root supplies actual binary hash and protected kubeconfig.
    executable=metadata['kubernetes']['kubectl_path']
    info=os.lstat(executable)
    require(stat.S_ISREG(info.st_mode)
        and ((info.st_uid==0 and not info.st_mode&0o022)
            or (info.st_uid==10001 and stat.S_IMODE(info.st_mode)==0o500))
        and hashlib.sha256(Path(executable).read_bytes()).hexdigest()==metadata['kubernetes']['kubectl_sha256'],'Trusted Root kubectl required')
    return await build_from_metadata(metadata,client.CoreV1Api(),client.AppsV1Api(),client.NetworkingV1Api())


if __name__=='__main__':
    print(canonical({'version':1,'state':'inert','live_execution':False}))

"""Offline, opt-in configuration for the existing TLS Gateway (no API client)."""
from copy import deepcopy
import json
import hashlib
import re

ORIGIN = 'https://compute-gateway.cps-compute.svc.cluster.local:8000'
AUDIENCE = 'cps-native-kai'
SEED = ('lease', 'compile', 'created')
BINDER = ('prepare', 'current', 'binding', 'accepted', 'close', 'hold', 'cleanup-maps', 'reservation-delete')
PRIVATE = '/kai-private'


def require(value, message):
    if not value:
        raise ValueError(message)


def obj(kind, name, namespace=None, **kwargs):
    return dict(apiVersion='rbac.authorization.k8s.io/v1' if kind in ('Role','RoleBinding','ClusterRole','ClusterRoleBinding') else 'v1',
                kind=kind, metadata=dict(name=name, **({'namespace':namespace} if namespace else {})), **kwargs)


def actor(account):
    m = account['metadata']
    require(account['kind'] == 'ServiceAccount' and account['apiVersion'] == 'v1'
            and not m.get('deletionTimestamp'), 'Current actual ServiceAccount required')
    from cps_compute.native_scheduler_coordinator_auth import canonical_uid
    canonical_uid(m['uid'])
    return 'system:serviceaccount:' + m['namespace'] + ':' + m['name']


def projected(name, audience):
    return {'name':name, 'projected':{'defaultMode':0o440, 'sources':[
        {'serviceAccountToken':{'audience':audience, 'expirationSeconds':3600, 'path':'credentials/token'}},
        {'configMap':{'name':'kube-root-ca.crt','items':[{'key':'ca.crt','path':'ca.crt'}]}}]}}


def render(context, *, gateway_account, binder_account, hub_accounts, hub_settings,
           readiness, reservation_template, api_audience, binder_pod_labels, gateway_pod_security_context, gateway_data_volume_name, queue='cps-interactive'):
    """Inputs are actual typed context and public captured objects, never tokens.

    This is an additive configuration proposal; no RBAC/deployment is applied.
    Existing Gateway authority/observer roles remain independently required.
    """
    from cps_compute.native_scheduler_group_contract import GroupPendingContext
    from cps_compute.native_scheduler_coordinator_server import ReservationTemplate
    from cps_compute.native_scheduler_coordinator_auth import ServiceRule
    require(type(context) is GroupPendingContext, 'Actual pinned current-group context required')
    require(isinstance(api_audience,str) and bool(api_audience), 'Explicit accepted API audience required')
    dep=context.deployment; namespace=dep.authority_namespace
    require(type(gateway_pod_security_context.get('fsGroup')) is int and gateway_pod_security_context['fsGroup']==10001, 'Gateway fsGroup10001 required for emptyDir materializer')
    require(isinstance(gateway_data_volume_name,str) and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',gateway_data_volume_name), 'Actual Gateway data PVC volume name required')
    gateway,binder=actor(gateway_account),actor(binder_account)
    require(binder_pod_labels and all(isinstance(k,str) and isinstance(v,str) and k and v for k,v in binder_pod_labels.items()), 'Exact dedicated binder Pod labels required')
    require(set(hub_accounts)==set(hub_settings)=={'cps','cit'}, 'Both source Hubs required')
    ReservationTemplate(reservation_template)
    settings={'authority_namespace':namespace,'binder_actor':binder,'coordinator_actor':gateway,
              'queue':queue,'fence_seconds':60,'gpu_memory_mib':dep.node_pool['total_memory_mib']}
    rules=[{'actor':binder,'uid':binder_account['metadata']['uid'],'role':'binder'}]
    hubs={}; objects=[]
    for source in ('cps','cit'):
        account=hub_accounts[source]; plain=deepcopy(hub_settings[source]); name=actor(account)
        require(plain['source']==source and plain['enabled'] is True and plain['gatewayUrl'].rstrip('/')==ORIGIN,
                'Existing authenticated source Hub/TLS origin must agree')
        require(plain.get('gatewayCAFile') and plain['groupDeployment']['policy_hash']==dep.policy_hash,
                'Existing Hub trust and measured policy required')
        rules.append({'actor':name,'uid':account['metadata']['uid'],'role':'hub','source':source,'central_actor':source})
        hubs[source]={'settings':{'enabled':True,'version':2,'groupHub':plain,'coordinator':{
            'origin':ORIGIN,'caFile':plain['gatewayCAFile'],'tokenFile':'/var/run/cps-kai-service/credentials/token','queue':queue}},
            'volumes':[projected('cps-kai-service',AUDIENCE)],
            'volumeMounts':[{'name':'cps-kai-service','mountPath':'/var/run/cps-kai-service','readOnly':True}],
            'ca_requirement':{'path':plain['gatewayCAFile'],'source_configmap':'cps-compute-gateway-ca','key':'ca.crt'}}
        role='cps-native-kai-hub-'+source
        objects.extend([obj('ClusterRole',role,rules=[{'nonResourceURLs':['/internal/native-kai/v2/'+x for x in SEED],'verbs':['post']}]),
            obj('ClusterRoleBinding',role,roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':role},
                subjects=[{'kind':'ServiceAccount','name':account['metadata']['name'],'namespace':account['metadata']['namespace']}])])
    for rule in rules: ServiceRule(**rule)
    require(readiness['enabled'] is True,'Current independent node readiness inputs required')
    declared={k:v for k,v in context._configuration.document['component_declarations']['node'].items() if k!='service_account_uid'}
    observed={k:v for k,v in readiness['processes']['node'].items() if k!='service_account_uid'}
    require(observed==declared,'Readiness node process must match exact typed NodeConfiguration declaration')
    config={'enabled':True,'version':2,'mode':'current-groups','settings':settings,'audience':AUDIENCE,
        'service_rules':rules,'api':{'origin':'https://kubernetes.default.svc','caFile':'/var/run/cps-kai-api/ca.crt',
        'tokenFile':'/var/run/cps-kai-api/credentials/token','audience':api_audience,'serviceAccountUID':gateway_account['metadata']['uid']},
        'custodyPath':'/data/native-kai-private/custody.sqlite',
        'writerLockPath':'/data/native-kai-private/writer.lock',
        'nodeConfigurationRef':context.node_configuration_ref,
        'runtime':{'writablePvcClaims':sorted({v['storage']['pvc'] for v in dep.workspaces.values()}),
                   'writableMountPaths':['/workspace'],'readonlyNfsMounts':[]},
        'epoch':{'policyPath':PRIVATE+'/config/policy.json','qualificationPath':PRIVATE+'/config/deployment.json',
                 'nodeAcknowledgment':deepcopy(readiness['acknowledgments']['node']),
                 'nodeProcess':deepcopy(observed),'ttlSeconds':readiness['ttlSeconds']},
        'reservationTemplate':deepcopy(reservation_template)}
    name='cps-native-kai-terminal'
    objects.extend([obj('ClusterRole',name,rules=[{'nonResourceURLs':['/api/native-kai/v1/'+x for x in BINDER],'verbs':['post']}]),
        obj('ClusterRoleBinding',name,roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':name},
            subjects=[{'kind':'ServiceAccount','name':binder_account['metadata']['name'],'namespace':binder_account['metadata']['namespace']}]),
        obj('ClusterRole','cps-native-kai-auth-review',rules=[{'apiGroups':['authentication.k8s.io'],'resources':['tokenreviews'],'verbs':['create']},
            {'apiGroups':['authorization.k8s.io'],'resources':['subjectaccessreviews'],'verbs':['create']}]),
        obj('ClusterRoleBinding','cps-native-kai-auth-review',roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':'cps-native-kai-auth-review'},
            subjects=[{'kind':'ServiceAccount','name':gateway_account['metadata']['name'],'namespace':gateway_account['metadata']['namespace']}])])
    subjects=[{'kind':'ServiceAccount','name':gateway_account['metadata']['name'],'namespace':gateway_account['metadata']['namespace']}]
    for account in [gateway_account,binder_account,*hub_accounts.values()]:
        m=account['metadata']; role='cps-native-kai-review-'+m['name']
        objects.extend([obj('Role',role,m['namespace'],rules=[{'apiGroups':[''],'resources':['serviceaccounts'],'resourceNames':[m['name']],'verbs':['get']}]),
            obj('RoleBinding',role,m['namespace'],roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':role},subjects=subjects)])
    # Kubernetes authorizes dryRun=All exactly like a real Pod CREATE. This
    # permission cannot be restricted to dry-run or resourceNames with RBAC.
    # Keep it namespaced to the declared Hubs and bound only to the Coordinator;
    # the compiler and admission remain responsible for trusted Pod contents.
    for namespace in sorted({a['metadata']['namespace'] for a in hub_accounts.values()}):
        role='cps-native-kai-pod-review'
        objects.extend([obj('Role',role,namespace,rules=[{'apiGroups':[''],'resources':['pods'],'verbs':['create']}]),
            obj('RoleBinding',role,namespace,roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':role},subjects=deepcopy(subjects))])
        # Coordinator.created/prepare freeze and validate KAI-owned maps;
        # abandon/cleanup use UID/RV-fenced deletion after exact contract checks.
        # KAI retains creation of maps and reservation Pods. No Secrets, exec,
        # bindings, workload ConfigMap CREATE or reservation mutation is granted.
        role='cps-native-kai-workspace-runtime'
        objects.extend([obj('Role',role,namespace,rules=[
            {'apiGroups':[''],'resources':['pods'],'verbs':['delete']},
            {'apiGroups':[''],'resources':['configmaps'],'verbs':['get','patch','delete']},
            {'apiGroups':['scheduling.run.ai'],'resources':['bindrequests'],'verbs':['get']}]),
            obj('RoleBinding',role,namespace,roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':role},subjects=deepcopy(subjects))])
    # Other ordinary API calls retain separately reviewed Gateway permissions.
    gateway_image=context._configuration.document['component_declarations']['gateway']['image']
    files={'coordinator.json':config,'policy.json':deepcopy(context._policy.catalog),'deployment.json':json.loads(dep.document)}
    data={k:json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False) for k,v in files.items()}
    seed='cps-native-kai-config-'+hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
    # Kubelet fsGroup can widen existing PVC files to0660 on remount.
    # Preserve the original lock inode; no recursive chmod or SDK relaxation.
    state_repair="""import fcntl
children=[]
try:
 names=('writer.lock','custody.sqlite','custody.sqlite-journal','custody.sqlite-wal','custody.sqlite-shm')
 present=[]
 for name in names:
  try: os.stat(name,dir_fd=fd,follow_symlinks=False)
  except FileNotFoundError: continue
  present.append(name)
 assert not present or 'writer.lock' in present, 'Existing custody requires its original writer lock'
 for name in present:
  child=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
  children.append(child)
  info=os.fstat(child)
  assert stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and info.st_nlink==1, 'Owned single-link private state inode required'
  assert stat.S_IMODE(info.st_mode) in (0o600,0o660), 'Unexpected private state permissions'
  if name=='writer.lock': fcntl.flock(child,fcntl.LOCK_EX|fcntl.LOCK_NB)
 # Normalize only fixed owned inodes after every proof, under the old lock.
 for child in children: os.fchmod(child,0o600)
finally:
 for child in reversed(children): os.close(child)
"""
    init_code=("from pathlib import Path; import os,stat; os.umask(0o077); p=Path('/kai-private/config'); p.mkdir(mode=0o700,exist_ok=True); "
               "directory=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW); "
               "assert os.fstat(directory).st_uid==os.geteuid(), 'Private config owner differs'; "
               "os.fchmod(directory,0o700); "
               "exec(\"for n in ('coordinator.json','policy.json','deployment.json'):\\n "
               "fd=os.open(n,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=directory)\\n "
               "s=os.fstat(fd)\\n "
               "assert stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid() and s.st_nlink==1 and stat.S_IMODE(s.st_mode)==0o600\\n "
               "os.ftruncate(fd,0)\\n "
               "stream=os.fdopen(fd,'wb'); stream.write(Path('/kai-seed').joinpath(n).read_bytes()); stream.flush(); os.fsync(stream.fileno()); stream.close()\"); "
               "os.close(directory); "
               "state=Path('/data/native-kai-private'); state.mkdir(mode=0o700,exist_ok=True); "
               "fd=os.open(state,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW); "
               "assert os.fstat(fd).st_uid==os.geteuid(), 'Private state owner differs'; "
               "os.fchmod(fd,0o700); "
               +"exec("+repr(state_repair)+"); os.close(fd)")
    # A fresh emptyDir, explicit UID and root-owned immutable seed avoid the
    # projected-volume symlink rejection of private_bytes without weakening it.
    flags=['--native-pending-coordinator-enabled=false','--native-coordinator-url='+ORIGIN,
           '--native-coordinator-authority-namespace='+namespace,'--native-coordinator-token-file=/var/run/cps-kai-service/credentials/token',
           '--native-coordinator-ca-file=/etc/cps-kai-trust/ca.crt',
           '--resource-reservation-pod-image='+reservation_template['image']]
    return {'binder':{'podSecurityContext':{'fsGroup':10000},'args':flags,'opt_in_args':['--native-pending-coordinator-enabled=true',*flags[1:]],
        'volumes':[projected('cps-kai-service',AUDIENCE),{'name':'cps-kai-trust','configMap':{'name':'cps-compute-gateway-ca','items':[{'key':'ca.crt','path':'ca.crt'}],'defaultMode':0o444}}],
        'volumeMounts':[{'name':'cps-kai-service','mountPath':'/var/run/cps-kai-service','readOnly':True},{'name':'cps-kai-trust','mountPath':'/etc/cps-kai-trust','readOnly':True}],
        'ca_requirement':{'namespace':binder_account['metadata']['namespace'],'configmap':'cps-compute-gateway-ca','key':'ca.crt','public_only':True}},'seed':obj('ConfigMap',seed,gateway_account['metadata']['namespace'],immutable=True,data=data),'coordinator':config,'hubs':hubs,'rbac':objects,'gateway':{
        'podSecurityContextPrerequisite':{'fsGroup':10001},
        'env':[{'name':'CPS_NATIVE_KAI_COORDINATOR_CONFIG','value':PRIVATE+'/config/coordinator.json'}],
        'volumes':[projected('cps-kai-api',api_audience),{'name':'kai-private','emptyDir':{}},{'name':'kai-seed','configMap':{'name':seed,'defaultMode':0o444}}],
        'volumeMounts':[{'name':'cps-kai-api','mountPath':'/var/run/cps-kai-api','readOnly':True},
                        {'name':'kai-private','mountPath':PRIVATE,'readOnly':True}],
        'initContainer':{'name':'native-kai-private-inputs','image':gateway_image,'command':['python','-c',init_code],
            'securityContext':{'runAsUser':10001,'runAsGroup':10001,'runAsNonRoot':True,'readOnlyRootFilesystem':True,'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},
            'volumeMounts':[{'name':'kai-seed','mountPath':'/kai-seed','readOnly':True},{'name':'kai-private','mountPath':PRIVATE},{'name':gateway_data_volume_name,'mountPath':'/data'}]},
        'private_files':files,
        'materialization_requirement':'UID10001 owns directory0700 and regular files0600; config/policy/deployment copied by reviewed init before Gateway starts.'},
        'network_policy_intent':{'namespace':'cps-compute','podSelector':{'matchLabels':{'app':'compute-gateway'}},
            'ingress':[{'from':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':binder_account['metadata']['namespace']}},
                                  'podSelector':{'matchLabels':deepcopy(binder_pod_labels)}}],'ports':[{'protocol':'TCP','port':8000}]}]},
        'open_gates':['Actual resource RBAC/API audience/reservation digest and certificate SAN must be verified before activation.',
                      'Node remains cordoned: automatic scheduler placement is not qualified.']}


def snapshot_inputs(snapshot, node_reference):
    """Consume a private captured API bundle in memory; never return tokens.

    Caller supplies the protected NodeConfig six-key reference, not a name
    inferred from an arbitrary object in the bundle. Refresh before rollout.
    """
    import base64
    from cps_compute.policy import Policy
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    from cps_compute.native_scheduler_group_contract import GroupPendingContext
    objects=snapshot['objects']
    class CapturedAPI:
        def read_namespaced_config_map(self,name,namespace,**kwargs):
            return deepcopy(objects['configmap/'+namespace+'/'+name])
    policy=Policy(json.loads(objects['configmap/cps-compute/compute-policy']['data']['policy.json']))
    context=GroupPendingContext.load(CapturedAPI(),ImmutableConfigMapRef.from_dict(node_reference),policy)
    runtime=json.loads(base64.b64decode(objects['secret/cps-compute/cps-compute-runtime']['data']['runtime.json']))
    ledger=json.loads(objects['configmap/'+context.deployment.authority_namespace+'/cps-native-gpu-allocations']['data']['state.json'])
    require(all(x['state']=='released' for x in ledger['allocations'].values()), 'Empty active ledger required for activation proposal')
    settings={}
    for source,ns in (('cps','jupyterhub'),('cit','cit-jhub')):
        candidates=[json.loads(x['data']['settings.json']) for k,x in objects.items()
                    if k.startswith('configmap/'+ns+'/') and 'settings.json' in x.get('data',{})]
        require(len(candidates)==1,'One exact captured Hub settings projection required')
        settings[source]=candidates[0]
    gateway_pod=snapshot['deployments']['gateway']['spec']['template']['spec']
    gateway_container=next(c for c in gateway_pod['containers'] if c['name']==context._configuration.document['component_declarations']['gateway']['container'])
    data_mounts=[m for m in gateway_container.get('volumeMounts',[]) if m.get('mountPath')=='/data' and not m.get('readOnly') and not m.get('subPath') and not m.get('subPathExpr')]
    require(len(data_mounts)==1,'One actual writable complete Gateway data PVC mount required')
    data_volume=next(v for v in gateway_pod['volumes'] if v['name']==data_mounts[0]['name'])
    require(set(data_volume)=={'name','persistentVolumeClaim'} and not data_volume['persistentVolumeClaim'].get('readOnly'),'Existing writable Gateway data PVC required')
    return context, {'gateway_data_volume_name':data_volume['name'],'gateway_account':objects['serviceaccount/cps-compute/cps-compute-controller'],
        'hub_accounts':{s:objects['serviceaccount/'+ns+'/hub'] for s,ns in (('cps','jupyterhub'),('cit','cit-jhub'))},
        'hub_settings':settings,'readiness':runtime['nativeGroupApprovals'],
        'gateway_pod_security_context':snapshot['deployments']['gateway']['spec']['template']['spec']['securityContext']}


if __name__ == '__main__':
    print(json.dumps({'enabled':False,'api_calls':False,'gpu_calls':False}))

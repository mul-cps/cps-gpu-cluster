"""Offline, opt-in configuration for the existing TLS Gateway (no API client)."""
from copy import deepcopy
import json
import hashlib

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
        {'serviceAccountToken':{'audience':audience, 'expirationSeconds':3600, 'path':'token'}},
        {'configMap':{'name':'kube-root-ca.crt','items':[{'key':'ca.crt','path':'ca.crt'}]}}]}}


def render(context, *, gateway_account, binder_account, hub_accounts, hub_settings,
           readiness, reservation_template, api_audience, binder_pod_labels, gateway_pod_security_context, queue='cps-interactive'):
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
    gateway,binder=actor(gateway_account),actor(binder_account)
    require(binder_pod_labels and all(isinstance(k,str) and isinstance(v,str) and k and v for k,v in binder_pod_labels.items()), 'Exact dedicated binder Pod labels required')
    require(set(hub_accounts)==set(hub_settings)=={'cps','cit'}, 'Both source Hubs required')
    ReservationTemplate(reservation_template)
    settings={'authority_namespace':namespace,'binder_actor':binder,'coordinator_actor':gateway,
              'queue':queue,'fence_seconds':30,'gpu_memory_mib':dep.node_pool['total_memory_mib']}
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
            'origin':ORIGIN,'caFile':plain['gatewayCAFile'],'tokenFile':'/var/run/cps-kai-service/token','queue':queue}},
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
        'tokenFile':'/var/run/cps-kai-api/token','audience':api_audience,'serviceAccountUID':gateway_account['metadata']['uid']},
        'custodyPath':'/data/native-kai-custody.sqlite',
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
    # TokenReview validates a separate signed identity; ordinary API calls still
    # use existing, separately reviewed Gateway resource permissions.
    gateway_image=context._configuration.document['component_declarations']['gateway']['image']
    files={'coordinator.json':config,'policy.json':deepcopy(context._policy.catalog),'deployment.json':json.loads(dep.document)}
    data={k:json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False) for k,v in files.items()}
    seed='cps-native-kai-config-'+hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
    init_code=("from pathlib import Path; import os; p=Path('/kai-private/config'); p.mkdir(mode=0o700); "
               "[(p.joinpath(n).write_bytes(Path('/kai-seed').joinpath(n).read_bytes()),os.chmod(p/n,0o600)) "
               "for n in ('coordinator.json','policy.json','deployment.json')]")
    # A fresh emptyDir, explicit UID and root-owned immutable seed avoid the
    # projected-volume symlink rejection of private_bytes without weakening it.
    flags=['--native-pending-coordinator-enabled=false','--native-coordinator-url='+ORIGIN,
           '--native-coordinator-authority-namespace='+namespace,'--native-coordinator-token-file=/var/run/cps-kai-service/token',
           '--native-coordinator-ca-file=/etc/cps-kai-trust/ca.crt']
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
            'volumeMounts':[{'name':'kai-seed','mountPath':'/kai-seed','readOnly':True},{'name':'kai-private','mountPath':PRIVATE}]},
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
    return context, {'gateway_account':objects['serviceaccount/cps-compute/cps-compute-controller'],
        'hub_accounts':{s:objects['serviceaccount/'+ns+'/hub'] for s,ns in (('cps','jupyterhub'),('cit','cit-jhub'))},
        'hub_settings':settings,'readiness':runtime['nativeGroupApprovals'],
        'gateway_pod_security_context':snapshot['deployments']['gateway']['spec']['template']['spec']['securityContext']}


if __name__ == '__main__':
    print(json.dumps({'enabled':False,'api_calls':False,'gpu_calls':False}))

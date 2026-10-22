"""Pure, non-executable cold-retirement proposal renderer. No cluster/host calls."""
from copy import deepcopy
import hashlib
import json
import re
import uuid

NAMESPACES = ('cps-native-system','cps-compute','jupyterhub','cit-jhub','kai-scheduler')
CONTROLLERS = (('cps-native-system','cps-native-node-agent','cps-native-node-agent'),
               ('cps-native-system','cps-native-observer-operator','cps-native-observer-operator'),
               ('cps-compute','cps-native-head-delivery','cps-native-head-delivery'),
               ('cps-compute','cps-native-approval-delivery','cps-native-approval-delivery'))
DEDICATED = {ns+'/'+sa for ns,_,sa in CONTROLLERS} | {'cps-compute/cps-native-handover-operator'}
PRINCIPALS = DEDICATED | {'cps-compute/cps-compute-controller','jupyterhub/hub','cit-jhub/hub','kai-scheduler/binder'}
READ_ONLY = {'get','list','watch'}
POLICY = 'cps-retired-native-authority'


def require(value,message):
    if not value: raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def valid_uid(value):
    require(type(value) is str,'Canonical actual UID required')
    try: parsed=uuid.UUID(value)
    except ValueError: raise ValueError('Canonical actual UID required') from None
    require(str(parsed)==value and parsed.int!=0,'Canonical actual UID required')


def metadata(obj):
    m=obj.get('metadata',{})
    require(type(m) is dict and type(m.get('name')) is str and m['name']
            and type(m.get('resourceVersion')) is str and m['resourceVersion'],'Actual UID/RV/name preimage required')
    valid_uid(m.get('uid'));return m


def key(obj):
    m=metadata(obj);return obj['kind'],m.get('namespace',''),m['name']


def target(obj):
    m=metadata(obj);return {'kind':obj['kind'],'namespace':m.get('namespace',''),'name':m['name'],'uid':m['uid']}


def tests(obj):
    m=metadata(obj)
    return [{'op':'test','path':'/metadata/uid','value':m['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':m['resourceVersion']}]


def subject(value):
    require(type(value) is dict and value.get('kind')=='ServiceAccount'
            and set(value)<= {'kind','name','namespace','apiGroup'}
            and value.get('apiGroup','')=='','Only exact service-account native grants supported')
    identity=value.get('namespace','')+'/'+value.get('name','')
    require(identity in PRINCIPALS,'Unexpected native grant principal; independent review required')
    return identity


def candidate_policy(controller_keys,role_keys,binding_keys):
    namespaces=list(NAMESPACES[:-1]);sa=sorted(DEDICATED)
    users=['system:serviceaccount:'+x.replace('/',':') for x in sa]
    j=lambda v:json.dumps(v,separators=(',',':'))
    workload_resources=['pods','deployments','daemonsets','statefulsets','replicasets','jobs','cronjobs']
    # All field access is guarded because one policy matches multiple API kinds.
    variables=[{'name':'name','expression':"request.name"},
      {'name':'spec','expression':"object != null && has(object.spec) ? object.spec : {}"},
      {'name':'podspec','expression':"request.resource.resource == 'pods' ? variables.spec : (request.resource.resource == 'cronjobs' ? (has(variables.spec.jobTemplate) ? variables.spec.jobTemplate.spec.template.spec : {}) : (has(variables.spec.template) ? variables.spec.template.spec : {}))"},
      {'name':'sa','expression':"has(variables.podspec.serviceAccountName) ? request.namespace + '/' + variables.podspec.serviceAccountName : ''"},
      {'name':'objectkey','expression':"request.kind.kind + '/' + request.namespace + '/' + variables.name"},
      {'name':'bindingrole','expression':"object != null && has(object.roleRef) ? (object.roleRef.kind == 'ClusterRole' ? 'ClusterRole//' + object.roleRef.name : 'Role/' + request.namespace + '/' + object.roleRef.name) : ''"}]
    validations=[
      {'expression':"!(request.subResource == 'scale' && request.namespace + '/' + variables.name in "+j([x.split('/',1)[1] for x in controller_keys])+")",
       'message':'Retired dedicated controllers cannot be scaled through Scale objects.'},
      {'expression':"!(request.resource.resource == 'configmaps' && request.namespace in "+j(namespaces)+" && (request.namespace == 'cps-native-system' || variables.name.startsWith('cps-native-') || variables.name.startsWith('cps-packaged-')))",
       'message':'Retired native ConfigMaps are read-only, including namespace root CA.'},
      {'expression':"!(request.resource.resource in "+j(workload_resources)+" && ((request.operation != 'DELETE' && variables.sa in "+j(sa)+") || variables.objectkey in "+j(controller_keys)+"))",
       'message':'Retired dedicated native processes/controllers cannot resurrect.'},
      {'expression':"!(request.resource.resource == 'serviceaccounts' && request.namespace + '/' + variables.name in "+j(sa)+")",
       'message':'Retired native service accounts/token requests are frozen.'},
      {'expression':"!(request.resource.resource in ['rolebindings','clusterrolebindings'] && (variables.objectkey in "+j(binding_keys)+" || variables.bindingrole in "+j(role_keys)+" || (object != null && has(object.subjects) && object.subjects.exists(s, ((s.kind == 'ServiceAccount' && (has(s.namespace) && s.namespace != '' ? s.namespace : request.namespace) + '/' + s.name in "+j(sa)+") || (s.kind == 'User' && s.name in "+j(users)+"))))))",
       'message':'Retired native grants and dedicated principals cannot be reauthorized.'},
      {'expression':"!(request.resource.resource in ['roles','clusterroles'] && variables.objectkey in "+j(role_keys)+")",
       'message':'Retired native role definitions remain archival.'},
      {'expression':"!(request.resource.resource == 'namespaces' && variables.name == 'cps-native-system')",
       'message':'Retired namespace labels/identity cannot be removed or namespace deleted.'},
      {'expression':"!(request.resource.resource in ['validatingadmissionpolicies','validatingadmissionpolicybindings'] && variables.name == '"+POLICY+"')",
       'message':'Retirement admission fence cannot be changed or removed.'}]
    resources=['configmaps','pods','pods/ephemeralcontainers','deployments','deployments/scale','daemonsets','statefulsets','statefulsets/scale','replicasets','replicasets/scale','jobs','cronjobs','serviceaccounts','serviceaccounts/token','roles','rolebindings','clusterroles','clusterrolebindings','namespaces','validatingadmissionpolicies','validatingadmissionpolicybindings']
    policy={'apiVersion':'admissionregistration.k8s.io/v1','kind':'ValidatingAdmissionPolicy','metadata':{'name':POLICY},
      'spec':{'failurePolicy':'Fail','matchConstraints':{'resourceRules':[{'apiGroups':['*'],'apiVersions':['*'],'operations':['CREATE','UPDATE','DELETE'],'resources':resources,'scope':'*'}]},'variables':variables,'validations':validations}}
    binding={'apiVersion':'admissionregistration.k8s.io/v1','kind':'ValidatingAdmissionPolicyBinding','metadata':{'name':POLICY},'spec':{'policyName':POLICY,'validationActions':['Deny']}}
    return [policy,binding]


def render(capture,*,reviewed_sha256):
    require(type(capture) is dict and set(capture)=={'version','scope','old_namespace','new_namespace','node','namespaced','cluster','secret_metadata','fleet_metadata'},'Closed reviewed retirement capture required')
    require(type(capture['version']) is int and capture['version']==1,'Exact capture version required')
    raw=canonical(capture);require(len(raw)<=32*1024*1024 and hashlib.sha256(raw).hexdigest()==reviewed_sha256,'Exact bounded independently reviewed capture SHA required')
    scope=capture['scope'];require(type(scope) is dict and set(scope)=={'node','node_uid','gpu_uuid'} and scope['node']=='k3s-wk-gpu2','Only reviewed GPU2 retirement supported')
    valid_uid(scope['node_uid']);require(type(scope['gpu_uuid']) is str and scope['gpu_uuid'].startswith('GPU-'),'Actual GPU UUID required');valid_uid(scope['gpu_uuid'][4:])
    require(capture['node']['metadata']['name']==scope['node'] and capture['node']['metadata']['uid']==scope['node_uid'],'Actual GPU2 node identity changed')
    old=capture['old_namespace'];new=capture['new_namespace'];metadata(old);metadata(new)
    require(old['kind']==new['kind']=='Namespace' and old['metadata']['name']=='cps-native-system' and new['metadata']['name']=='cps-native-runtime' and old['metadata']['uid']!=new['metadata']['uid'],'Distinct actual old/new domain namespaces required')
    require(new['metadata'].get('labels',{}).get('pod-security.kubernetes.io/enforce')=='restricted','Inactive successor namespace must remain restricted')
    require(type(capture['namespaced']) is dict and set(capture['namespaced'])==set(NAMESPACES),'Complete five namespace captures required')
    objects={};preimages={}
    for ns,listing in capture['namespaced'].items():
        require(type(listing.get('items')) is list,'Actual namespaced object inventory required')
        for obj in listing['items']:
            k=key(obj);require(k not in objects and k[1]==ns,'Duplicate/foreign namespaced capture object');objects[k]=obj
        for p in listing.get('capture_preimages',[]):preimages[(p['kind'],p['namespace'],p['name'])]=p
    for obj in capture['cluster']['items']:
        k=key(obj);require(k not in objects and not k[1],'Duplicate/foreign cluster capture object');objects[k]=obj
    for listing in capture['secret_metadata'].values():
        for item in listing.get('items',[]):require(type(item) is dict and set(item)<={'metadata','type','immutable','keys'},'Secret values are prohibited in retirement capture')
    controller_intents=[];sa_intents=[];controller_keys=[]
    for ns,name,account in CONTROLLERS:
        dep=objects.get(('Deployment',ns,name));sa=objects.get(('ServiceAccount',ns,account));require(dep is not None and sa is not None,'Actual dedicated controller/SA capture missing')
        dm=metadata(dep);sm=metadata(sa);spec=dep['spec'];pod=spec['template']['spec'];require(pod.get('serviceAccountName')==account,'Dedicated controller service account changed')
        if name=='cps-native-node-agent':
            selector=pod.get('nodeSelector',{});fixed=pod.get('nodeName')
            require(type(selector) is dict and (fixed==scope['node'] or selector=={'kubernetes.io/hostname':scope['node']})
                    and fixed in (None,scope['node']) and selector in ({},{'kubernetes.io/hostname':scope['node']}),
                    'Node controller must target GPU2 only')
        pin=preimages.get(('Deployment',ns,name));require(type(pin) is dict and pin.get('uid')==dm['uid'] and re.fullmatch(r'[a-f0-9]{64}',pin.get('raw_spec_sha256','')),'Actual original full-spec preimage SHA required')
        controller_intents.append({'object':target(dep),'operation':'scale-zero','preconditions':{'uid':dm['uid'],'resourceVersion':dm['resourceVersion'],'raw_spec_sha256':pin['raw_spec_sha256'],'raw_object_sha256':pin['raw_object_sha256']},'desired_replicas':0,'materialization':'fresh-full-spec-matching-original-sha256'})
        controller_keys.append('Deployment/'+ns+'/'+name)
        sa_intents.append({'object':target(sa),'operations':tests(sa)+[{'op':'add','path':'/automountServiceAccountToken','value':False}]})
    roles={k:o for k,o in objects.items() if k[0] in ('Role','ClusterRole')};rbac=[];role_keys=set();binding_keys=[]
    for k,binding in sorted(objects.items()):
        if k[0] not in ('RoleBinding','ClusterRoleBinding'):continue
        rr=binding['roleRef'];rk=(rr['kind'],k[1] if rr['kind']=='Role' else '',rr['name']);role=roles.get(rk)
        if not rr['name'].startswith('cps-native-'):continue
        require(role is not None,'Native referenced role missing')
        rules=role.get('rules',[])
        if not any(set(rule['verbs'])-READ_ONLY for rule in rules):continue
        for rule in rules:
            require(all('*' not in rule.get(field,[]) for field in ('verbs','resources','apiGroups','nonResourceURLs')),'Broad native RBAC requires separate review')
        require(type(binding.get('subjects')) is list and binding['subjects'],'Exact original native binding subjects required')
        principals=[subject(s) for s in binding['subjects']];require(len(principals)==len(set(principals)),'Duplicate native subjects')
        rbac.append({'object':target(binding),'operation':'empty-subjects','role_ref':deepcopy(rr),'role_rules_sha256':digest(rules),'operations':tests(binding)+[{'op':'test','path':'/roleRef','value':deepcopy(rr)},{'op':'test','path':'/subjects','value':deepcopy(binding['subjects'])},{'op':'replace','path':'/subjects','value':[]}]})
        role_keys.add('/'.join(rk));binding_keys.append('/'.join(k))
    labels=deepcopy(old['metadata'].get('labels',{}));annotations=deepcopy(old['metadata'].get('annotations',{}))
    labels.update({'pod-security.kubernetes.io/enforce':'restricted','pod-security.kubernetes.io/enforce-version':'latest','cps.compute/native-authority-retired':'true'})
    annotations.update({'cps.compute/retired-node-uid':scope['node_uid'],'cps.compute/retired-gpu-uuid':scope['gpu_uuid'],'cps.compute/retirement-capture-sha256':reviewed_sha256,'cps.compute/successor-namespace-uid':new['metadata']['uid']})
    operations=tests(old)
    for field in ('labels','annotations'):
        if field in old['metadata']:operations.append({'op':'test','path':'/metadata/'+field,'value':deepcopy(old['metadata'][field])})
    operations += [{'op':'add','path':'/metadata/labels','value':labels},{'op':'add','path':'/metadata/annotations','value':annotations}]
    preserved=[{'object':target(o),'captured_spec_sha256':digest(o.get('spec',{}))} for k,o in sorted(objects.items()) if k[0] in ('Deployment','DaemonSet','StatefulSet') and '/'.join(k) not in controller_keys]
    return {'version':1,'status':'draft-incomplete','executable':False,'reviewed_capture_sha256':reviewed_sha256,'scope':deepcopy(scope),
      'old_namespace':target(old),'successor_namespace':target(new),'controller_intents':controller_intents,'service_account_intents':sa_intents,'rbac_intents':rbac,
      'namespace_patch':{'object':target(old),'operations':operations},'admission_candidates':candidate_policy(controller_keys,sorted(role_keys),sorted(binding_keys)),
      'preserved_controllers':preserved,'fleet_source_capture_sha256':digest(capture['fleet_metadata']),'credential_metadata_capture_sha256':digest(capture['secret_metadata']),
      'coverage':{'native_mutating_bindings':len(rbac),'no_hardware_fence_claim':True,'redacted_capture_not_api_preimage':True},
      'ordering':['archive-exact-old-authority-and-approved-loss-boundary','materialize-full-spec-CAS-and-stop-dedicated-controllers','revoke-native-binding-subjects-and-dedicated-SA-automount','verify-old-process-token-and-GitOps-incapability','apply-restricted-namespace-and-inactive-policy-only','server-typecheck-and-negative-matrix-before-self-protecting-binding-promotion','qualify-explicit-SAR-and-admission-denials','separate-reviewed-new-domain-activation'],
      'unmet_gates':['authenticated-Root-retirement-approval','fresh-full-spec-materialization-and-UID-RV-recheck','complete-GPU2-privileged-process-and-host-alias-exclusion','old-native-credential-audience-and-existing-token-incapability','broad-group-and-aggregated-capability-closure-with-complete-retired-credential-denial','GitOps-native-resource-source-retirement-and-no-resurrection-observation','admission-CEL-server-typechecking-and-negative-request-qualification','explicit-SubjectAccessReview-user-groups-resourceAttributes-not-impersonation','CPU-batch-API-NFS-entitlement-home-and-personal-workload-invariance','separately-qualified-guarded-driver-new-epoch-and-four-fresh-ACKs']}

"""Pure, staged v3-to-v4 head bootstrap; actual API readbacks bind each stage.

This module performs no API calls. Root applies candidates and supplies actual
readbacks between stages. It does not mutate workloads or migrate a journal.
"""
from copy import deepcopy
import re

from cps_compute.immutable_configmap import ImmutableConfigMapRef
from cps_compute.native_approval_head import validate_binding
from cps_compute.native_group_revision import ApprovalRevision, COMPONENTS, _uid
from cps_compute.native_groups import _canonical, canonical_sha256
from cps_compute.native_node.config import NodeConfiguration


def require(condition,message):
    if not condition:raise ValueError(message)


def _authorities(configuration,approvals,policy):
    require(type(configuration) is NodeConfiguration and configuration.document['version']==3,
        'Actual enabled v3 Node configuration required for one-time migration')
    require(isinstance(approvals,dict) and set(approvals)==COMPONENTS,'Exactly four actual approval objects required')
    result={}
    for component,cm in approvals.items():
        approval=ApprovalRevision.from_configmap(cm,policy,configuration.deployment)
        require(approval.reference['namespace']==configuration.document['component_declarations'][component]['namespace'],
            'Initial approval must remain namespace-local')
        result[component]=approval
    require(result['node'].reference==configuration.initial_approval_ref,'Actual initial Node authority changed')
    bodies=[a.document for a in result.values()]
    require(all(body==bodies[0] for body in bodies),'Four current approval registries must agree with identical initial v3 history')
    return result


def _candidate(namespace,name,key,body,*,immutable):
    value={'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':namespace,'name':name},
        'data':{key:_canonical(body).decode()}}
    if immutable:value['immutable']=True
    return value


def _readback(candidate,actual,*,immutable):
    require(isinstance(actual,dict),'Actual ConfigMap readback required')
    meta=actual.get('metadata',{})
    require(actual.get('apiVersion')=='v1' and actual.get('kind')=='ConfigMap'
        and all(meta.get(k)==candidate['metadata'][k] for k in ('namespace','name'))
        and _uid(meta.get('uid')) and isinstance(meta.get('resourceVersion'),str)
        and re.fullmatch(r'[1-9][0-9]*',meta['resourceVersion'])
        and not meta.get('deletionTimestamp') and not meta.get('ownerReferences')
        and not actual.get('binaryData') and actual.get('data')==candidate['data'],
        'Actual candidate UID/resourceVersion/content readback required')
    require(actual.get('immutable') is True if immutable else actual.get('immutable') in (None,False),
        'Actual ConfigMap mutability differs')
    return deepcopy(actual)


def pointer_candidates(configuration,approvals,policy,*,domain_uid=None):
    """A domain UID only separates names; Root must authenticate its boundary."""
    require(domain_uid is None or (type(domain_uid) is str and _uid(domain_uid)
        and domain_uid.replace('-','')!='0'*32),'Canonical nonzero domain UID naming token required')
    suffix='' if domain_uid is None else '-'+domain_uid.replace('-','')
    current=_authorities(configuration,approvals,policy)
    return {component:_candidate(approval.reference['namespace'],
        'cps-native-current-approval-'+component.replace(':','-')+suffix,'head.json',
        {'version':1,'generation':approval.document['registry']['generation'],'reference':approval.reference},
        immutable=False) for component,approval in current.items()}


def anchor_candidates(configuration,approvals,policy,pointers,*,domain_uid=None):
    candidates=pointer_candidates(configuration,approvals,policy,domain_uid=domain_uid)
    require(isinstance(pointers,dict) and set(pointers)==COMPONENTS,'Four actual pointer readbacks required')
    current=_authorities(configuration,approvals,policy);result={}
    for component,candidate in candidates.items():
        actual=_readback(candidate,pointers[component],immutable=False)
        anchor={'version':1,'pointer':{k:actual['metadata'][k] for k in ('namespace','name','uid')}
            | {'key':'head.json'},'initial':current[component].reference}
        name='cps-native-head-anchor-'+canonical_sha256(anchor).removeprefix('sha256:')[:16]
        result[component]=_candidate(actual['metadata']['namespace'],name,'anchor.json',anchor,immutable=True)
    return result


def bind(configuration,approvals,policy,pointers,anchors,*,domain_uid=None):
    candidates=anchor_candidates(configuration,approvals,policy,pointers,domain_uid=domain_uid)
    require(isinstance(anchors,dict) and set(anchors)==COMPONENTS,'Four actual anchor readbacks required')
    heads={}
    for component,candidate in candidates.items():
        actual=_readback(candidate,anchors[component],immutable=True)
        reference={k:actual['metadata'][k] for k in ('namespace','name','uid','resourceVersion')}
        reference.update(key='anchor.json',data_sha256=canonical_sha256(actual['data']))
        ref=ImmutableConfigMapRef.from_dict(reference)
        anchor=ref.validate(actual)
        heads[component]=validate_binding({'version':2,'anchor':anchor,'projection':reference})
    body=configuration.document;body.pop('approval_ref');body.update(version=4,approval_head=heads['node'])
    name='cps-native-node-head-'+canonical_sha256(body).removeprefix('sha256:')[:16]
    return {'heads':heads,'node_configuration':_candidate(configuration.reference.to_dict()['namespace'],
        name,'config.json',body,immutable=True)}


def runtime_candidates(configuration,approvals,policy,pointers,anchors,*,domain_uid=None):
    """Stage immutable binding files; each is distinct from the anchor payload."""
    heads=bind(configuration,approvals,policy,pointers,anchors,domain_uid=domain_uid)['heads']
    result={}
    for component,head in heads.items():
        if component=='node':continue
        name='cps-native-head-binding-'+canonical_sha256(head).removeprefix('sha256:')[:16]
        result[component]=_candidate(head['projection']['namespace'],name,'head-binding.json',head,immutable=True)
    return result


def bind_runtime(configuration,approvals,policy,pointers,anchors,bindings,controllers,*,domain_uid=None):
    """CAS intents for the one-time held rollout; never used for head advances.

    Call only after image adoption. Existing image/SA/commands/resources stay
    unchanged. Node bootstrap, observer release and Gateway readiness adoption
    must be composed separately before these intents can be released.
    """
    heads=bind(configuration,approvals,policy,pointers,anchors,domain_uid=domain_uid)['heads']
    candidates=runtime_candidates(configuration,approvals,policy,pointers,anchors,domain_uid=domain_uid)
    require(isinstance(bindings,dict) and set(bindings)==set(candidates),'Three actual binding readbacks required')
    for component,candidate in candidates.items():_readback(candidate,bindings[component],immutable=True)
    require(isinstance(controllers,dict) and set(controllers)==COMPONENTS,'Four actual Deployment readbacks required')
    result={}
    for component,original in controllers.items():
        declaration=configuration.document['component_declarations'][component]
        meta=original.get('metadata',{})
        require(original.get('apiVersion')=='apps/v1' and original.get('kind')=='Deployment'
            and all(meta.get(key)==declaration[key] for key in ('namespace','name','uid'))
            and _uid(meta.get('uid')) and isinstance(meta.get('resourceVersion'),str)
            and re.fullmatch(r'[1-9][0-9]*',meta['resourceVersion']) and not meta.get('deletionTimestamp'),
            'Actual declared Deployment UID/resourceVersion required')
        desired=deepcopy(original['spec']);pod=desired['template']['spec']
        require(pod.get('serviceAccountName')==declaration['service_account'],'Declared service account changed')
        matches=[c for c in pod['containers'] if c.get('name')==declaration['container']]
        require(len(matches)==1 and matches[0].get('image')==declaration['image'],'Exact selected declared image/container required')
        container=matches[0]
        volumes=pod.setdefault('volumes',[]);mounts=container.setdefault('volumeMounts',[])
        names={'cps-native-head-anchor','cps-native-head-binding'}
        require(not any(v.get('name') in names for v in volumes)
            and not any(m.get('name') in names or m.get('mountPath') in {
                '/var/run/cps-native-approvals/head-anchor.json','/etc/cps-native-head-binding.json'} for m in mounts),
            'Head mount collision; compare original staged adoption instead of overwriting')
        require(not any(e.get('name')=='CPS_NATIVE_GROUP_APPROVAL_HEAD' for e in container.get('env',[])),
            'Head binding environment already installed')
        volumes.append({'name':'cps-native-head-anchor','configMap':{
            'name':heads[component]['projection']['name'],'defaultMode':0o644,'items':[{'key':'anchor.json','path':'anchor.json'}]}})
        mounts.append({'name':'cps-native-head-anchor','mountPath':'/var/run/cps-native-approvals/head-anchor.json',
            'subPath':'anchor.json','readOnly':True})
        if component!='node':
            volumes.append({'name':'cps-native-head-binding','configMap':{'name':bindings[component]['metadata']['name'],'defaultMode':0o644,
                'items':[{'key':'head-binding.json','path':'head-binding.json'}]}})
            mounts.append({'name':'cps-native-head-binding','mountPath':'/etc/cps-native-head-binding.json',
                'subPath':'head-binding.json','readOnly':True})
            container.setdefault('env',[]).append({'name':'CPS_NATIVE_GROUP_APPROVAL_HEAD',
                'value':'/etc/cps-native-head-binding.json'})
        result[component]=[
            {'op':'test','path':'/metadata/uid','value':meta['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':meta['resourceVersion']},
            {'op':'test','path':'/spec','value':deepcopy(original['spec'])},
            {'op':'replace','path':'/spec','value':desired}]
    return result


def readiness_settings(configuration,approvals,policy,pointers,anchors,settings,*,domain_uid=None):
    """Pure one-time Gateway v1-to-v2 readback migration, without new authority.

    Qualify the exact old cohort before adding the actual bound heads. This
    changes neither the runtime Secret nor a process; compose it with the held
    Node, capture, observer and mount rollout before applying.
    """
    from cps_compute.runtime import native_group_approval_configuration
    heads=bind(configuration,approvals,policy,pointers,anchors,domain_uid=domain_uid)['heads']
    original=native_group_approval_configuration({'nativeGroupApprovals':settings})
    require(original is not None and original.get('version') is None,
        'Enabled legacy readiness settings required for one-time migration')
    body=configuration.document
    declarations={c:{k:v for k,v in d.items() if k!='service_account_uid'}
        for c,d in body['component_declarations'].items()}
    epoch={k:configuration.deployment.node_pool[k]
        for k in ('node_uid','boot_id','driver_generation','gpu_uuid')}
    require(original['acknowledgments']==body['acknowledgment_targets']
        and original['processes']==declarations and original['driver_epoch']==epoch,
        'Existing readiness authority differs from the reviewed Node cohort')
    result=deepcopy(original);result.update(version=2,heads=heads)
    return native_group_approval_configuration({'nativeGroupApprovals':result})


def domain_runtime_review_sha256(*,configuration,approvals,policy,pointers,anchors,bindings,
        controllers,adoption,previous_heads,previous_objects,domain_uid,retirement):
    """Review pin, not authorization: includes exact upstream adoption and readbacks."""
    require(type(configuration) is NodeConfiguration,'Actual typed target configuration required')
    return canonical_sha256({'configuration':configuration.document,
        'configuration_reference':configuration.reference.to_dict(),'policy_hash':policy.hash,
        'approvals':approvals,'pointers':pointers,'anchors':anchors,'bindings':bindings,
        'controllers':controllers,'adoption':adoption,'previous_heads':previous_heads,
        'previous_objects':previous_objects,'domain_uid':domain_uid,'retirement':retirement})


def bind_domain_runtime(*,configuration,approvals,policy,pointers,anchors,bindings,
        controllers,adoption,previous_heads,previous_objects,domain_uid,retirement,reviewed_sha256):
    """Compose reviewed cold-domain heads into existing qualified adoption CAS.

    No API calls or retirement authorization. The operator must separately qualify
    the target deployment, adoption intents and external physical/credential fence.
    Old authority is checked as captured bytes, never reinterpreted as new proof.
    Node rollout is separate. Ordinary bind_runtime remains a one-time bootstrap.
    """
    require(type(domain_uid) is str and _uid(domain_uid) and domain_uid.replace('-','')!='0'*32,
        'Explicit canonical nonzero domain UID required')
    require(type(retirement) is dict and set(retirement)=={'version','retirement_id','evidence_sha256'}
        and type(retirement['version']) is int and retirement['version']==1
        and type(retirement['retirement_id']) is str and 0<len(retirement['retirement_id'])<=256
        and type(retirement['evidence_sha256']) is str
        and re.fullmatch(r'sha256:[0-9a-f]{64}',retirement['evidence_sha256'])
        and retirement['evidence_sha256']!='sha256:'+'0'*64,'Reviewed retirement descriptor required')
    inputs=dict(configuration=configuration,approvals=approvals,policy=policy,pointers=pointers,
        anchors=anchors,bindings=bindings,controllers=controllers,adoption=adoption,
        previous_heads=previous_heads,previous_objects=previous_objects,domain_uid=domain_uid,retirement=retirement)
    require(reviewed_sha256==domain_runtime_review_sha256(**inputs),'Exact reviewed composition inputs required')
    heads=bind(configuration,approvals,policy,pointers,anchors,domain_uid=domain_uid)['heads']
    authority=configuration.deployment.qualification_authority
    require(not authority.policy_transitions and authority.lifetime_transition is None,
        'Fresh root qualification required for cold domain')
    candidates=runtime_candidates(configuration,approvals,policy,pointers,anchors,domain_uid=domain_uid)
    keys=COMPONENTS-{'node'}
    require(all(type(value) is dict and set(value)==keys for value in
        (bindings,controllers,adoption,previous_objects)),'Exactly three runtime component inputs required')
    require(type(previous_heads) is dict and set(previous_heads)==COMPONENTS,'Four captured previous heads required')
    old={k:validate_binding(v) for k,v in previous_heads.items()}
    require(old['node']['anchor']['pointer']['namespace']!=heads['node']['anchor']['pointer']['namespace'],
        'Cold domain requires distinct Node authority namespace')
    result={}
    for component in sorted(keys):
        _readback(candidates[component],bindings[component],immutable=True)
        previous=old[component];objects=previous_objects[component]
        require(type(objects) is dict and set(objects)=={'anchor','binding'},'Actual old head objects required')
        _readback(_candidate(previous['projection']['namespace'],previous['projection']['name'],
            'anchor.json',previous['anchor'],immutable=True),objects['anchor'],immutable=True)
        oldref=ImmutableConfigMapRef.from_dict(previous['projection'])
        require(oldref.validate(objects['anchor'])==previous['anchor'],'Old anchor body changed')
        oldbinding=objects['binding'];meta=oldbinding.get('metadata',{})
        oldcandidate=_candidate(previous['projection']['namespace'],meta.get('name'),
            'head-binding.json',previous,immutable=True)
        _readback(oldcandidate,oldbinding,immutable=True)
        require(heads[component]['anchor']['pointer']!=previous['anchor']['pointer']
            and heads[component]['projection']['name']!=previous['projection']['name']
            and bindings[component]['metadata']['name']!=meta['name'],'New head identities must be disjoint')
        original=controllers[component];m=original.get('metadata',{})
        declaration=configuration.document['component_declarations'][component]
        require(original.get('apiVersion')=='apps/v1' and original.get('kind')=='Deployment'
            and all(m.get(k)==declaration[k] for k in ('namespace','name','uid'))
            and _uid(m.get('uid')) and type(m.get('resourceVersion')) is str
            and re.fullmatch(r'[1-9][0-9]*',m['resourceVersion']) and not m.get('deletionTimestamp'),
            'Actual declared Deployment UID/resourceVersion required')
        prefix=[{'op':'test','path':'/metadata/uid','value':m['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':m['resourceVersion']},
            {'op':'test','path':'/spec','value':deepcopy(original['spec'])}]
        patch=adoption[component]
        require(type(patch) is list and len(patch)==4 and patch[:3]==prefix
            and type(patch[3]) is dict and set(patch[3])=={'op','path','value'}
            and patch[3]['op']=='replace' and patch[3]['path']=='/spec'
            and type(patch[3]['value']) is dict,'Exact original full-spec adoption CAS required')
        desired=deepcopy(patch[3]['value'])
        for spec in (original['spec'],desired):
            pod=spec['template']['spec']
            require(pod.get('serviceAccountName')==declaration['service_account'],'Declared service account changed')
            matches=[c for c in pod['containers'] if c.get('name')==declaration['container']]
            require(len(matches)==1,'Exact selected container required')
            container=matches[0]
            if spec is desired:require(container.get('image')==declaration['image'],'Qualified desired image required')
            for name,path,key,cmname in (
                ('cps-native-head-anchor','/var/run/cps-native-approvals/head-anchor.json','anchor.json',previous['projection']['name']),
                ('cps-native-head-binding','/etc/cps-native-head-binding.json','head-binding.json',meta['name'])):
                volumes=[v for v in pod.get('volumes',[]) if v.get('name')==name]
                require(volumes==[{'name':name,'configMap':{'name':cmname,'defaultMode':0o644,
                    'items':[{'key':key,'path':key}]}}],'Exact captured head volume required')
                mounts=[v for v in container.get('volumeMounts',[]) if v.get('name')==name or v.get('mountPath')==path]
                require(mounts==[{'name':name,'mountPath':path,'subPath':key,'readOnly':True}],
                    'Exact captured head mount required')
            require([e for e in container.get('env',[]) if e.get('name')=='CPS_NATIVE_GROUP_APPROVAL_HEAD']==[
                {'name':'CPS_NATIVE_GROUP_APPROVAL_HEAD','value':'/etc/cps-native-head-binding.json'}],
                'Exact captured head environment required')
        for volume in desired['template']['spec']['volumes']:
            if volume['name']=='cps-native-head-anchor':volume['configMap']['name']=heads[component]['projection']['name']
            elif volume['name']=='cps-native-head-binding':volume['configMap']['name']=bindings[component]['metadata']['name']
        result[component]=deepcopy(prefix)+[{'op':'replace','path':'/spec','value':desired}]
    return result

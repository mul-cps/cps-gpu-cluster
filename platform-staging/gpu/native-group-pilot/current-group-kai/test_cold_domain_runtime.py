"""Offline composition of reviewed adoption CAS intents, with real head codecs."""
import copy
import uuid
import pytest
from test_head_bootstrap import fixture, actual, stages
from cps_compute.native_groups import canonical_sha256


def setup():
    f=fixture();m=f.module
    p,a=stages(f)
    old=m.bind(f.configuration,f.approvals,f.f.policy,p,a)['heads']
    b={k:actual(v) for k,v in m.runtime_candidates(f.configuration,f.approvals,f.f.policy,p,a).items()}
    controllers={k:f.f.apps.read_namespaced_deployment(d['name'],d['namespace'])
        for k,d in f.configuration.document['component_declarations'].items()}
    for c in controllers.values():c['metadata']['resourceVersion']='21'
    mounted=m.bind_runtime(f.configuration,f.approvals,f.f.policy,p,a,b,controllers)
    keys={'gateway','hub:cps','hub:cit'}
    controllers={k:copy.deepcopy(controllers[k]) for k in keys}
    for k in keys:
        controllers[k]['spec']=mounted[k][-1]['value']
        main=next(c for c in controllers[k]['spec']['template']['spec']['containers'] if c['name']==f.configuration.document['component_declarations'][k]['container'])
        main['image']='ghcr.io/example/previous@sha256:'+'2'*64
    adoption={k:[{'op':'test','path':'/metadata/uid','value':controllers[k]['metadata']['uid']},
        {'op':'test','path':'/metadata/resourceVersion','value':'21'},
        {'op':'test','path':'/spec','value':copy.deepcopy(controllers[k]['spec'])},
        {'op':'replace','path':'/spec','value':copy.deepcopy(controllers[k]['spec'])}] for k in keys}
    for k,patch in adoption.items():
        pod=patch[-1]['value']['template']['spec']
        main=next(c for c in pod['containers'] if c['name']==f.configuration.document['component_declarations'][k]['container'])
        main['image']=f.configuration.document['component_declarations'][k]['image']
        pod['volumes'].append({'name':'reviewed-publisher','configMap':{'name':'qualified-new-publisher'}})
        main.setdefault('env',[]).append({'name':'REVIEWED_RUNTIME','valueFrom':{'secretKeyRef':{'name':'qualified-runtime','key':'config'}}})
        patch[-1]['value']['template']['metadata'].setdefault('annotations',{})['reviewed-adoption']='preserve'
    # Independently captured retired Node authority was in the old namespace.
    old['node']['anchor']['pointer']['namespace']='retired-native-domain'
    old['node']['anchor']['initial']['namespace']='retired-native-domain'
    old['node']['projection']['namespace']='retired-native-domain'
    objects={k:{'anchor':a[k],'binding':b[k]} for k in keys}
    token=str(uuid.uuid4())
    np={k:actual(v) for k,v in m.pointer_candidates(f.configuration,f.approvals,f.f.policy,domain_uid=token).items()}
    na={k:actual(v) for k,v in m.anchor_candidates(f.configuration,f.approvals,f.f.policy,np,domain_uid=token).items()}
    nb={k:actual(v) for k,v in m.runtime_candidates(f.configuration,f.approvals,f.f.policy,np,na,domain_uid=token).items()}
    args=dict(configuration=f.configuration,approvals=f.approvals,policy=f.f.policy,pointers=np,anchors=na,
        bindings=nb,controllers=controllers,adoption=adoption,previous_heads=old,previous_objects=objects,
        domain_uid=token,retirement={'version':1,'retirement_id':'reviewed-boundary','evidence_sha256':'sha256:'+'1'*64})
    return f,args


def call(f,args):
    digest=f.module.domain_runtime_review_sha256(**args)
    return f.module.bind_domain_runtime(**args,reviewed_sha256=digest)


def test_exact_adoption_and_original_cas_are_preserved():
    f,args=setup();before=f.module.domain_runtime_review_sha256(**args)
    result=call(f,args)
    for k,patch in result.items():
        assert patch[:3]==args['adoption'][k][:3]
        desired=copy.deepcopy(args['adoption'][k][-1]['value'])
        for v in desired['template']['spec']['volumes']:
            if v['name']=='cps-native-head-anchor':v['configMap']['name']=args['anchors'][k]['metadata']['name']
            if v['name']=='cps-native-head-binding':v['configMap']['name']=args['bindings'][k]['metadata']['name']
        assert patch[-1]['value']==desired
    assert f.module.domain_runtime_review_sha256(**args)==before


@pytest.mark.parametrize('change', ['uid','rv','preimage','extra-op','old-anchor','old-binding','duplicate-volume','mount','env','desired-image','same-domain'])
def test_closed_inputs_and_exact_preimages_fail_closed(change):
    f,args=setup();k='gateway'
    if change=='uid':args['adoption'][k][0]['value']=str(uuid.uuid4())
    elif change=='rv':args['adoption'][k][1]['value']='22'
    elif change=='preimage':args['adoption'][k][2]['value']['replicas']=99
    elif change=='extra-op':args['adoption'][k].append({'op':'remove','path':'/metadata/labels'})
    elif change=='old-anchor':args['previous_objects'][k]['anchor']['data']['anchor.json']='{}'
    elif change=='old-binding':args['previous_objects'][k]['binding']['data']['head-binding.json']='{}'
    elif change=='same-domain':args['previous_heads']['node']=copy.deepcopy(f.module.bind(args['configuration'],args['approvals'],args['policy'],args['pointers'],args['anchors'],domain_uid=args['domain_uid'])['heads']['node'])
    else:
        pod=args['adoption'][k][-1]['value']['template']['spec'];container=next(c for c in pod['containers'] if c['name']==args['configuration'].document['component_declarations'][k]['container'])
        if change=='duplicate-volume':pod['volumes'].append(copy.deepcopy(next(v for v in pod['volumes'] if v['name']=='cps-native-head-anchor')))
        elif change=='mount':next(v for v in container['volumeMounts'] if v['name']=='cps-native-head-anchor')['readOnly']=False
        elif change=='env':next(v for v in container['env'] if v['name']=='CPS_NATIVE_GROUP_APPROVAL_HEAD')['value']='different'
        elif change=='desired-image':container['image']='other'
    with pytest.raises(ValueError):call(f,args)


def test_review_pin_must_match_all_actual_inputs():
    f,args=setup();digest=f.module.domain_runtime_review_sha256(**args)
    args['adoption']['gateway'][-1]['value']['replicas']=7
    with pytest.raises(ValueError):f.module.bind_domain_runtime(**args,reviewed_sha256=digest)


@pytest.mark.parametrize('change', ['token','retirement-extra','retirement-zero','anchor-uid','binding-owner','missing-head','missing-component'])
def test_explicit_review_boundary_and_actual_objects_required(change):
    f,args=setup()
    if change=='token':args['domain_uid']='00000000-0000-0000-0000-000000000000'
    elif change=='retirement-extra':args['retirement']['authorized']=True
    elif change=='retirement-zero':args['retirement']['evidence_sha256']='sha256:'+'0'*64
    elif change=='anchor-uid':args['previous_objects']['gateway']['anchor']['metadata']['uid']=str(uuid.uuid4())
    elif change=='binding-owner':args['previous_objects']['gateway']['binding']['metadata']['ownerReferences']=[{'uid':str(uuid.uuid4())}]
    elif change=='missing-head':args['previous_heads'].pop('node')
    elif change=='missing-component':args['adoption'].pop('gateway')
    with pytest.raises(ValueError):call(f,args)


def test_ordinary_bootstrap_still_rejects_mounted_controller():
    f,args=setup()
    controllers=copy.deepcopy(args['controllers'])
    d=f.configuration.document['component_declarations']['node']
    controllers['node']=f.f.apps.read_namespaced_deployment(d['name'],d['namespace'])
    controllers['node']['metadata']['resourceVersion']='21'
    for k,c in controllers.items():
        main=next(v for v in c['spec']['template']['spec']['containers'] if v['name']==f.configuration.document['component_declarations'][k]['container'])
        main['image']=f.configuration.document['component_declarations'][k]['image']
    with pytest.raises(ValueError,match='Head mount collision'):
        f.module.bind_runtime(args['configuration'],args['approvals'],args['policy'],args['pointers'],args['anchors'],args['bindings'],controllers,domain_uid=args['domain_uid'])

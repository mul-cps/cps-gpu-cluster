"""Offline ownership handover: never race two binders or the operator."""
import copy
import importlib.util
from pathlib import Path
import pytest


def load():
    spec=importlib.util.spec_from_file_location('operator_handover',Path(__file__).with_name('operator_handover.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def obj(api,kind,namespace,name,uid):
    return {'apiVersion':api,'kind':kind,'metadata':{'namespace':namespace,'name':name,
        'uid':uid,'resourceVersion':'12','generation':2}}


def fixture():
    config=obj('kai.scheduler/v1','Config','','kai-config','config-uid')
    config['spec']={'binder':{'service':{'enabled':True}},'global':{'gpuSharingMode':'HamiCore'}}
    operator=obj('apps/v1','Deployment','kai-scheduler','kai-operator','operator-uid')
    operator['spec']={'replicas':0,'selector':{'matchLabels':{'app':'kai-operator'}}}
    operator['status']={'observedGeneration':2,'replicas':0,'readyReplicas':0,'availableReplicas':0}
    identities=[('apps/v1','Deployment','kai-scheduler','binder'),('v1','ServiceAccount','kai-scheduler','binder'),
        ('v1','Service','kai-scheduler','binder'),('policy/v1','PodDisruptionBudget','kai-scheduler','binder-pdb'),
        ('v1','ServiceAccount','kai-resource-reservation','kai-resource-reservation')]
    resources=[]
    for n,(api,kind,ns,name) in enumerate(identities):
        r=obj(api,kind,ns,name,str(n));r['metadata']['labels']={'app':name,'app.kubernetes.io/managed-by':'kai-operator'}
        r['metadata']['ownerReferences']=[{'apiVersion':'kai.scheduler/v1','kind':'Config','name':'kai-config',
            'uid':'config-uid','controller':True}]
        resources.append(r)
    resources[0]['spec']={'replicas':1,'strategy':{'type':'Recreate'},'template':{'spec':{'containers':[{'name':'binder','image':'stock'}]}}}
    return config,operator,resources


def test_handover_detaches_exact_five_resources_without_replacing_uids_or_specs():
    m=load();c,o,r=fixture();before=copy.deepcopy((c,o,r));out=m.detach_intent(c,o,[],r)
    assert (c,o,r)==before
    assert len(out['resource_patches'])==5
    for original,row in zip(r,out['resource_patches']):
        patch=row['patch'];assert patch[:2]==[
            {'op':'test','path':'/metadata/uid','value':original['metadata']['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':'12'}]
        assert next(p for p in patch if p['path']=='/metadata/ownerReferences' and p['op']=='replace')['value']==[]
        assert all(p['path'].startswith('/metadata/') for p in patch)
    assert out['config_patch'][-1]=={'op':'replace','path':'/spec/binder/service/enabled','value':False}
    assert out['apply_order']==['resource_patches','config_patch']
    assert out['live_operations'] is False


@pytest.mark.parametrize('case',['running-operator','unobserved-pause','remaining-pod','missing-resource','extra-resource',
    'foreign-owner','missing-owner','deleting-resource','wrong-config','disabled-config','rolling-binder'])
def test_handover_rejects_incomplete_or_racing_capture(case):
    m=load();c,o,r=fixture();pods=[]
    if case=='running-operator':o['status']['replicas']=1
    elif case=='unobserved-pause':o['status']['observedGeneration']=1
    elif case=='remaining-pod':pods=[{'metadata':{'name':'terminating-operator'}}]
    elif case=='missing-resource':r.pop()
    elif case=='extra-resource':r.append(copy.deepcopy(r[0]))
    elif case=='foreign-owner':r[0]['metadata']['ownerReferences'][0]['uid']='replacement'
    elif case=='missing-owner':r[0]['metadata'].pop('ownerReferences')
    elif case=='deleting-resource':r[0]['metadata']['deletionTimestamp']='now'
    elif case=='wrong-config':c['metadata']['name']='other'
    elif case=='disabled-config':c['spec']['binder']['service']['enabled']=False
    elif case=='rolling-binder':r[0]['spec']['strategy']['type']='RollingUpdate'
    with pytest.raises(ValueError):m.detach_intent(c,o,pods,r)


def test_pause_and_resume_only_change_operator_replica_field_with_cas():
    m=load();c,o,r=fixture();running=copy.deepcopy(o);running['spec']['replicas']=1
    assert m.pause_patch(running)[-1]=={'op':'replace','path':'/spec/replicas','value':0}
    with pytest.raises(ValueError):m.pause_patch(o)
    with pytest.raises(ValueError):m.resume_patch(c,o,[],r)
    c['spec']['binder']['service']['enabled']=False
    for v in r:v['metadata']['ownerReferences']=[];v['metadata']['labels']['app.kubernetes.io/managed-by']='cps-compute-gitops'
    assert m.resume_patch(c,o,[],r)[-1]=={'op':'replace','path':'/spec/replicas','value':1}
    r[0]['metadata']['ownerReferences']=[{'kind':'Config'}]
    with pytest.raises(ValueError):m.resume_patch(c,o,[],r)


def test_resume_accepts_api_omission_of_empty_owner_references():
    m=load();c,o,r=fixture();c['spec']['binder']['service']['enabled']=False
    for v in r:
        v['metadata'].pop('ownerReferences')
        v['metadata']['labels']['app.kubernetes.io/managed-by']='cps-compute-gitops'
    assert m.resume_patch(c,o,[],r)[-1]['value']==1


def test_live_operand_shape_has_four_resources_and_optional_binder_pdb():
    m=load();c,o,r=fixture();r.pop(3)
    for v in r:
        v['metadata'].get('labels',{}).pop('app.kubernetes.io/managed-by',None)
    r[-1]['metadata'].pop('labels')
    assert len(m.detach_intent(c,o,[],r)['resource_patches'])==4
    pdb=obj('policy/v1','PodDisruptionBudget','kai-scheduler','binder-pdb','pdb-uid')
    pdb['metadata']['ownerReferences']=copy.deepcopy(r[0]['metadata']['ownerReferences'])
    assert len(m.detach_intent(c,o,[],[*r,pdb])['resource_patches'])==5


@pytest.mark.parametrize('scope',['global','binder'])
def test_handover_refuses_enabled_vpa_operand_outside_transferred_resource_set(scope):
    m=load();c,o,r=fixture();c['spec'][scope]['vpa']={'enabled':True}
    with pytest.raises(ValueError):m.detach_intent(c,o,[],r)

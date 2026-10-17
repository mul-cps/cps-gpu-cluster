"""Synthetic actual-shaped image+observer composition; no private inputs or API."""
import copy
import importlib.util
import json
from pathlib import Path
import uuid

import pytest

from cps_compute.native_group_revision import ApprovalRevision
from cps_compute.native_observer_permissions import ObserverRelease, role_targets
from cps_compute.immutable_configmap import ImmutableConfigMapRef

HERE=Path(__file__).parent


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


image_tests=module('observer_image_fixture',HERE/'test_image_adoption.py')
image=image_tests.h


def fixture():
    snapshot,images,revision=image_tests.fixture()
    policy,configuration=image._context(snapshot)
    node_ref=configuration.reference.to_dict()
    node=image._get(snapshot,'ConfigMap',node_ref['namespace'],node_ref['name'])
    body=json.loads(node['data']['config.json'])
    namespaces={'gateway':'gateway-system','hub:cps':'cps-hub','hub:cit':'cit-hub','node':node_ref['namespace']}
    original_objects=list(snapshot['objects'].values())
    moved=set()
    for component,dep in snapshot['deployments'].items():
        oldns=dep['metadata']['namespace'];newns=namespaces[component]
        name=dep['metadata']['name'];dep['metadata']['namespace']=newns
        declaration=body['component_declarations'][component];declaration['namespace']=newns
        body['acknowledgment_targets'][component]['namespace']=newns
        account=image._get(snapshot,'ServiceAccount',oldns,declaration['service_account'])
        account['metadata']['namespace']=newns
        own_name='cps-native-approval-'+{'gateway':'gateway','hub:cps':'hub-cps','hub:cit':'hub-cit','node':'node'}[component]
        own=image._get(snapshot,'Role',oldns,own_name);own['metadata']['namespace']=newns
        moved.update((id(account),id(own),id(dep)))
        for volume in dep['spec']['template']['spec']['volumes']:
            if 'configMap' in volume:kind='ConfigMap';vname=volume['configMap']['name']
            elif 'secret' in volume:kind='Secret';vname=volume['secret']['secretName']
            else:continue
            obj=image._get(snapshot,kind,oldns,vname)
            if id(obj) in moved:continue
            obj['metadata']['namespace']=newns;moved.add(id(obj))
    snapshot['objects']={image._key(o['kind'],o['metadata']['namespace'],o['metadata']['name']):o for o in original_objects}
    processes={c:{k:v for k,v in d.items()if k!='service_account_uid'}for c,d in body['component_declarations'].items()}
    for component in image.COMPONENTS:
        document=image.volume(snapshot,component,'cps-native-approval-document')
        if component!='node':
            refcm=image.volume(snapshot,component,'cps-native-approval-reference')
            refcm['data']['reference.json']=image.canonical(ApprovalRevision.from_configmap(document,policy,configuration.deployment).reference)
            pub=image.volume(snapshot,component,'cps-native-approval-publisher')
            p=json.loads(pub['data']['publisher.json']);p['process']=copy.deepcopy(processes[component]);p['acknowledgment']=body['acknowledgment_targets'][component]
            pub['data']['publisher.json']=image.canonical(p)
    runtime=image.secret_volume(snapshot,'gateway','config')
    r=image._decode(runtime['data']['runtime.json']);r['nativeGroupApprovals']['processes']=copy.deepcopy(processes)
    r['nativeGroupApprovals']['acknowledgments']=copy.deepcopy(body['acknowledgment_targets']);runtime['data']['runtime.json']=image._encoded(r)
    seed=image.secret_volume(snapshot,'gateway','capture-seed')
    s=image._decode(seed['data']['config.json']);s['node_process']=copy.deepcopy(processes['node']);s['node_acknowledgment']=body['acknowledgment_targets']['node']
    seed['data']['config.json']=image._encoded(s)
    node['data']['config.json']=image.canonical(body)
    boot=image.volume(snapshot,'node','packaged-bootstrap-input')
    old_ref=ImmutableConfigMapRef.from_dict({**{k:node['metadata'][k]for k in ('namespace','name','uid','resourceVersion')},'key':'config.json','data_sha256':image.sha(node['data'])})
    boot['data']['config-ref.json']=image.canonical(old_ref.to_dict())
    release={'version':1,'node_configuration':old_ref.to_dict(),'held_node_template_sha256':None,'roles':[]}
    roles=[]
    for index,(ns,name) in enumerate(role_targets(body)):
        key=image._key('Role',ns,name)
        role=snapshot['objects'].get(key)
        if role is None:
            role={'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':{'namespace':ns,'name':name,'uid':str(uuid.UUID(int=4000+index)),'resourceVersion':'12'},
                  'rules':[{'apiGroups':[''],'resources':['configmaps'],'verbs':['get'],'resourceNames':['other-authority']}]}
            snapshot['objects'][key]=role
        role['rules']=[r for r in role['rules']if r['resources']!=['pods']]
        role['rules'] += [{'apiGroups':[''],'resources':['pods'],'verbs':['get'],'resourceNames':['baseline-pod']},
                          {'apiGroups':['apps'],'resources':['replicasets'],'verbs':['get'],'resourceNames':['baseline-rs']}]
        component=next(c for c,n in namespaces.items()if n==ns)
        own='cps-native-approval-'+{'gateway':'gateway','hub:cps':'hub-cps','hub:cit':'hub-cit','node':'node'}[component]
        if name==own:role['rules'].append({'apiGroups':[''],'resources':['configmaps'],'verbs':['patch'],'resourceNames':[body['acknowledgment_targets'][component]['name']]})
        release['roles'].append({**{k:role['metadata'][k]for k in ('namespace','name','uid')},'rules':copy.deepcopy(role['rules'])})
        roles.append(copy.deepcopy(role))
    ObserverRelease.from_dict(release)
    capture={'version':1,'configmaps':[copy.deepcopy(o)for o in snapshot['objects'].values()if o['kind']=='ConfigMap'],
             'deployments':copy.deepcopy(list(snapshot['deployments'].values())),'roles':roles}
    plan=image.render(snapshot,images,expected_snapshot_sha256=image.sha(snapshot),expected_revision=revision)
    actual={}
    for index,(label,cm) in enumerate(plan['creates'].items()):
        if cm['kind']!='ConfigMap':continue
        actual[label]=copy.deepcopy(cm);actual[label]['metadata'].update(uid=str(uuid.UUID(int=5000+index)),resourceVersion=str(50+index))
    bound=image.bind_node(snapshot,plan,actual['node-config'])
    bootstrap=copy.deepcopy(bound['creates']['node.bootstrap']);bootstrap['metadata'].update(uid=str(uuid.UUID(int=6000)),resourceVersion='90')
    actual['node.bootstrap']=bootstrap
    return dict(previous_release=release,reviewed_sha256=image.sha(release),catalog=policy.catalog,
        image_snapshot=snapshot,image_plan=plan,actual_node_config=actual['node-config'],actual_bootstrap=bootstrap,
        capture=capture,actual_configmaps=actual)


def compose(inputs):
    target=module('observer_adoption_under_test',HERE/'observer_adoption.py')
    return target.compose(**inputs)


def test_composition_advances_exact_four_static_gets_and_actual_authority():
    inputs=fixture();original=copy.deepcopy(inputs);result=compose(inputs)
    assert inputs==original
    assert result['prospective'] is True and result['live_applied'] is False and result['process_readiness_verified'] is False
    node=inputs['actual_node_config']
    expected_ref={**{k:node['metadata'][k]for k in ('namespace','name','uid','resourceVersion')},'key':'config.json','data_sha256':image.sha(node['data'])}
    assert result['release']['node_configuration']==expected_ref
    bound=image.bind_node(inputs['image_snapshot'],inputs['image_plan'],inputs['actual_node_config'])
    assert result['release']['held_node_template_sha256']==image.sha(bound['patches']['node.deployment']['patch'][-1]['value']['template'])
    before={(r['namespace'],r['name']):r for r in inputs['previous_release']['roles']}
    after={(r['namespace'],r['name']):r for r in result['release']['roles']}
    assert set(before)==set(after) and len(after)==7
    additions=[]
    for key,old in before.items():
        new=after[key];assert new['uid']==old['uid']
        assert len(new['rules'])==len(old['rules'])
        for a,b in zip(old['rules'],new['rules']):
            assert {k:v for k,v in a.items()if k!='resourceNames'}=={k:v for k,v in b.items()if k!='resourceNames'}
            if a!=b:
                assert a['resources']==['configmaps'] and a['verbs']==['get']
                assert set(a['resourceNames'])<set(b['resourceNames'])
                additions.extend(set(b['resourceNames'])-set(a['resourceNames']))
    assert set(additions)=={v['metadata']['name']for k,v in inputs['actual_configmaps'].items()if k!='node.bootstrap'}
    assert len(additions)==4 and len(result['static_role_patches'])==4
    ObserverRelease.from_dict(result['release'])


@pytest.mark.parametrize('fault',['extra-static','verbs','role-uid','plan','missing-gateway','owner','mutable-cm','cm-data','release-true'])
def test_unreviewed_static_or_actual_identity_drift_fails_closed(fault):
    inputs=fixture()
    if fault=='extra-static':inputs['capture']['roles'][0]['rules'][0]['resourceNames'].append('foreign-static')
    elif fault=='verbs':inputs['capture']['roles'][0]['rules'][0]['verbs'].append('patch')
    elif fault=='role-uid':inputs['capture']['roles'][0]['metadata']['uid']=str(uuid.UUID(int=99999))
    elif fault=='plan':inputs['image_plan']['preservation']['policy_hash']='sha256:'+'0'*64
    elif fault=='missing-gateway':inputs['actual_configmaps'].pop('gateway.publisher')
    elif fault=='owner':inputs['actual_configmaps']['gateway.publisher']['metadata']['ownerReferences']=[{'uid':str(uuid.UUID(int=3))}]
    elif fault=='mutable-cm':inputs['actual_configmaps']['gateway.publisher']['immutable']=False
    elif fault=='cm-data':inputs['actual_configmaps']['gateway.publisher']['data']['publisher.json']='{}'
    else:inputs['actual_bootstrap']['data']['release']='true'
    with pytest.raises(ValueError):compose(inputs)


def test_only_current_mutable_pod_rs_names_may_differ_from_reviewed_baseline():
    inputs=fixture()
    for role in inputs['capture']['roles']:
        for rule in role['rules']:
            if rule['resources'] in (['pods'],['replicasets']):rule['resourceNames']=['api-observed-name']
    result=compose(inputs)
    for old,new in zip(inputs['previous_release']['roles'],result['release']['roles']):
        for a,b in zip(old['rules'],new['rules']):
            if a['resources'] in (['pods'],['replicasets']):assert a==b


def test_prospective_controllers_are_exact_reviewed_specs_with_original_uid_rv():
    inputs=fixture();result=compose(inputs)
    old=inputs['image_snapshot']['deployments']
    actual={(d['metadata']['namespace'],d['metadata']['name']):d for d in result['capture']['deployments']}
    bound=image.bind_node(inputs['image_snapshot'],inputs['image_plan'],inputs['actual_node_config'])
    for component,dep in old.items():
        prospective=actual[(dep['metadata']['namespace'],dep['metadata']['name'])]
        assert prospective['metadata']==dep['metadata']
        expected=copy.deepcopy(dep['spec'])
        if component=='node':expected=bound['patches']['node.deployment']['patch'][-1]['value']
        else:expected['template']=inputs['image_plan']['patches'][component+'.deployment']['patch'][-1]['value']
        assert prospective['spec']==expected

"""CPU-only coherent v4 runtime migration; synthetic Secret inputs only."""
import copy
import importlib.util
import json
from pathlib import Path
import uuid
import pytest
from test_image_adoption import fixture as image_fixture, h as image


def module(name):
    spec=importlib.util.spec_from_file_location('head_runtime_test_'+name,Path(__file__).with_name(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def actual(candidate):
    result=copy.deepcopy(candidate);result['metadata'].update(uid=str(uuid.uuid4()),resourceVersion='31');return result


def fixture():
    snapshot,_,_=image_fixture();policy,configuration=image._context(snapshot)
    seed=image.secret_volume(snapshot,'gateway','capture-seed');body=image._decode(seed['data']['config.json'])
    body.update(database='/data/control.sqlite',policy_json='/inputs/policy.json',token_file='/inputs/token',
        ttl_seconds=30,host='0.0.0.0',port=8001,tls_cert_file='/inputs/cert',tls_key_file='/inputs/key')
    seed['data']['config.json']=image._encoded(body)
    approvals={c:image.volume(snapshot,c,'cps-native-approval-document') for c in snapshot['deployments']}
    heads=module('head_bootstrap')
    pointers={c:actual(v) for c,v in heads.pointer_candidates(configuration,approvals,policy).items()}
    anchors={c:actual(v) for c,v in heads.anchor_candidates(configuration,approvals,policy,pointers).items()}
    bindings={c:actual(v) for c,v in heads.runtime_candidates(configuration,approvals,policy,pointers,anchors).items()}
    node=actual(heads.bind(configuration,approvals,policy,pointers,anchors)['node_configuration'])
    return dict(snapshot=snapshot,pointers=pointers,anchors=anchors,bindings=bindings,actual_node_config=node)


def prepare(values):
    return module('head_runtime_adoption').prepare(**values,expected_snapshot_sha256=image.sha(values['snapshot']))


def test_cohort_proposal_preserves_images_commands_storage_and_private_seed_bytes():
    values=fixture();before=copy.deepcopy(values);plan=prepare(values)
    assert values==before and set(plan['creates'])=={'node.bootstrap','gateway.capture-seed'}
    assert plan['creates']['node.bootstrap']['data']['release']=='false'
    for c,spec in plan['runtime_specs'].items():
        old=values['snapshot']['deployments'][c]['spec']
        assert spec['replicas']==old['replicas'] and spec['selector']==old['selector']
        for before_container,after_container in zip(old['template']['spec']['containers'],spec['template']['spec']['containers']):
            assert before_container['image']==after_container['image'] and before_container['command']==after_container['command']
    seed=image.secret_volume(values['snapshot'],'gateway','capture-seed');new=plan['creates']['gateway.capture-seed']
    assert {k:v for k,v in new['data'].items() if k!='config.json'}=={k:v for k,v in seed['data'].items() if k!='config.json'}
    old=image._decode(seed['data']['config.json']);expected=copy.deepcopy(old);expected.update(version=2,approval_head=plan['heads']['node'])
    assert image._decode(new['data']['config.json'])==expected
    oldsecret=image.secret_volume(values['snapshot'],'gateway','config');desired=plan['gateway_runtime_patch']['patch'][-1]['value']
    oldruntime=image._decode(oldsecret['data']['runtime.json']);newruntime=image._decode(desired['runtime.json'])
    assert newruntime['nativeGroupApprovals']['version']==2 and newruntime['nativeGroupApprovals']['heads']==plan['heads']
    oldruntime.pop('nativeGroupApprovals');newruntime.pop('nativeGroupApprovals');assert newruntime==oldruntime
    assert desired['other.key']==oldsecret['data']['other.key']


def test_bind_requires_actual_two_readbacks_and_exact_plan_then_emits_guarded_four_specs():
    values=fixture();plan=prepare(values);created={k:actual(v) for k,v in plan['creates'].items()}
    patches=module('head_runtime_adoption').bind(**values,plan=plan,actual_creates=created)
    assert set(patches)==set(values['snapshot']['deployments'])
    for c,p in patches.items():
        old=values['snapshot']['deployments'][c]
        assert p[:3]==[{'op':'test','path':'/metadata/uid','value':old['metadata']['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':old['metadata']['resourceVersion']},
            {'op':'test','path':'/spec','value':old['spec']}]
        assert p[-1]=={'op':'replace','path':'/spec','value':plan['runtime_specs'][c]}
    created['node.bootstrap']['data']['release']='true'
    with pytest.raises(ValueError):module('head_runtime_adoption').bind(**values,plan=plan,actual_creates=created)


@pytest.mark.parametrize('change',['capture-authority','capture-schema','node-data','active-ledger','pin'])
def test_mismatched_authority_or_migration_precondition_is_refused(change):
    v=fixture()
    if change.startswith('capture'):
        secret=image.secret_volume(v['snapshot'],'gateway','capture-seed');body=image._decode(secret['data']['config.json'])
        if change=='capture-authority':body['node_process']['image']='example.invalid/other@sha256:'+'b'*64
        else:body['extra']='unreviewed'
        secret['data']['config.json']=image._encoded(body)
    elif change=='node-data':v['actual_node_config']['data']['config.json']='{}'
    elif change=='active-ledger':
        ledger=image._get(v['snapshot'],'ConfigMap',v['snapshot']['deployments']['node']['metadata']['namespace'],'cps-native-gpu-allocations')
        body=json.loads(ledger['data']['state.json']);body['allocations']['one']['state']='running';ledger['data']['state.json']=image.canonical(body)
    if change=='pin':
        with pytest.raises(ValueError):module('head_runtime_adoption').prepare(**v,expected_snapshot_sha256='sha256:'+'0'*64)
    else:
        with pytest.raises(ValueError):prepare(v)


def test_duplicate_controller_capture_cannot_change_the_reviewed_mount_preimage():
    values=fixture();dep=values['snapshot']['deployments']['gateway'];key=image._key('Deployment',dep['metadata']['namespace'],dep['metadata']['name'])
    different=copy.deepcopy(dep);different['spec']['replicas']=2;values['snapshot']['objects'][key]=different
    with pytest.raises(ValueError):prepare(values)


def test_modified_runtime_plan_and_owned_or_foreign_staging_are_refused():
    values=fixture();plan=prepare(values);created={k:actual(v) for k,v in plan['creates'].items()}
    bad=copy.deepcopy(plan);bad['runtime_specs']['gateway']['replicas']=3
    with pytest.raises(ValueError):module('head_runtime_adoption').bind(**values,plan=bad,actual_creates=created)
    created['gateway.capture-seed']['metadata']['ownerReferences']=[{'uid':str(uuid.uuid4())}]
    with pytest.raises(ValueError):module('head_runtime_adoption').bind(**values,plan=plan,actual_creates=created)

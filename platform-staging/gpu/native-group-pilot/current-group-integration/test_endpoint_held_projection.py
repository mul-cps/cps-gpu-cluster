"""Held cleanup projection is explicit, pinned, and cannot authorize activation."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest
from cps_compute.native_groups import canonical_sha256
from test_held_cleanup_maintenance import compiler_fixture
from test_head_gateway_rotation import image


def fixture():
    v,packet=compiler_fixture();snapshot=copy.deepcopy(v['snapshot']);_,configuration=image._context(snapshot)
    for source,ns in [('cps','jupyterhub'),('cit','cit-jhub')]:
        for key,obj in list(snapshot['objects'].items()):
            if key.startswith('configmap/'+ns+'/') and 'settings.json' in obj.get('data',{}):
                settings=json.loads(obj['data']['settings.json'])
                if set(settings)=={'enabled','version','groupHub','coordinator'}:del snapshot['objects'][key]
    path=Path(__file__).with_name('endpoint.py');spec=importlib.util.spec_from_file_location('endpoint_held_test',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    policy,_=image._context(snapshot)
    return m,snapshot,configuration,packet,policy


def test_default_projection_rejects_held_custody():
    m,s,c,p,policy=fixture()
    with pytest.raises(ValueError,match='Empty active ledger'):m._validate_ledger_projection(s['objects']['configmap/'+c.deployment.authority_namespace+'/cps-native-gpu-allocations'],c,policy)


def test_explicit_projection_preserves_every_captured_object():
    m,s,c,p,policy=fixture();before=copy.deepcopy((s,p))
    m._validate_ledger_projection(s['objects']['configmap/'+c.deployment.authority_namespace+'/cps-native-gpu-allocations'],c,policy,held_cleanup=p,expected_held_cleanup_sha256=canonical_sha256(p))
    assert (s,p)==before


@pytest.mark.parametrize('fault',['missing-pin','wrong-pin','pin-only','epoch','policy','authority','new-claim'])
def test_projection_refuses_pin_scope_and_custody_drift(fault):
    m,s,c,p,policy=fixture();args={'held_cleanup':p,'expected_held_cleanup_sha256':canonical_sha256(p)}
    if fault=='missing-pin':args.pop('expected_held_cleanup_sha256')
    elif fault=='wrong-pin':args['expected_held_cleanup_sha256']='sha256:'+'0'*64
    elif fault=='pin-only':args.pop('held_cleanup')
    else:
        o=p['observation']
        if fault=='epoch':o['epoch_after']['boot_id']='66666666-6666-4666-8666-666666666666'
        elif fault=='policy':
            r=json.loads(o['journal_raw']);r['intent']['policy_hash']='sha256:'+'0'*64;o['journal_raw']=json.dumps(r)
        elif fault=='authority':o['enrollment']['metadata']['namespace']='foreign'
        else:
            key='configmap/'+c.deployment.authority_namespace+'/cps-native-gpu-allocations';cm=s['objects'][key];state=json.loads(cm['data']['state.json']);state['allocations']['f'*60]={'state':'enrolled'};cm['data']['state.json']=json.dumps(state)
        p['review']['observation_sha256']=canonical_sha256(o);args['expected_held_cleanup_sha256']=canonical_sha256(p)
    with pytest.raises(ValueError):m._validate_ledger_projection(s['objects']['configmap/'+c.deployment.authority_namespace+'/cps-native-gpu-allocations'],c,policy,**args)

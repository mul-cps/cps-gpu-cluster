import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from cps_compute.native_groups import _canonical, canonical_sha256
from cps_compute.native_node.config import NodeConfiguration, ImmutableConfigMapRef

HERE = Path(__file__).parent


def load(name):
    spec = importlib.util.spec_from_file_location('head_observer_test_' + name, HERE / (name + '.py'))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def actual(candidate):
    result = copy.deepcopy(candidate); result['metadata'].update(uid=str(uuid.uuid4()), resourceVersion='17')
    return result


def fixture():
    from test_native_observer_permissions import fixture as legacy
    from test_native_node_config import ref
    f = legacy(); boot = load('head_bootstrap')
    old = NodeConfiguration.load(f.core, ref(f.cm), f.policy)
    approvals = {}
    for component, declaration in old.document['component_declarations'].items():
        cm = copy.deepcopy(f.maps['approval'])
        if component != 'node':
            cm['metadata'].update(namespace=declaration['namespace'], name='initial-' + component.replace(':', '-'), uid=str(uuid.uuid4()))
        approvals[component] = cm
    pointers = {c: actual(value) for c, value in boot.pointer_candidates(old, approvals, f.policy).items()}
    anchors = {c: actual(value) for c, value in boot.anchor_candidates(old, approvals, f.policy, pointers).items()}
    bound = boot.bind(old, approvals, f.policy, pointers, anchors)
    new_cm = actual(bound['node_configuration'])
    maps = {(o['metadata']['namespace'], o['metadata']['name']): copy.deepcopy(o)
        for o in list(f.maps.values()) + [f.cm] if o.get('kind') == 'ConfigMap'}
    for cm in maps.values():
        cm['metadata'].setdefault('uid', str(uuid.uuid4())); cm['metadata'].setdefault('resourceVersion', '1')
    for cm in list(approvals.values()) + list(pointers.values()) + list(anchors.values()) + [new_cm]:
        maps[(cm['metadata']['namespace'], cm['metadata']['name'])] = copy.deepcopy(cm)
    bindings = {c: actual(cm) for c, cm in boot.runtime_candidates(old, approvals, f.policy, pointers, anchors).items()}
    for cm in bindings.values(): maps[(cm['metadata']['namespace'], cm['metadata']['name'])] = copy.deepcopy(cm)
    class Core:
        def read_namespaced_config_map(self, name, namespace): return copy.deepcopy(maps[(namespace, name)])
    new = NodeConfiguration.load(Core(), ref(new_cm), f.policy)
    held = actual(copy.deepcopy(maps[(old.reference.to_dict()['namespace'], 'bootstrap')]))
    held['metadata']['name'] = 'head-bootstrap'
    held['data'].update({'release': 'false', 'config-ref.json': _canonical(new.reference.to_dict()).decode()})
    maps[(held['metadata']['namespace'], held['metadata']['name'])] = held
    controllers = {c: copy.deepcopy(f.deps[(d['namespace'], d['name'])])
        for c, d in old.document['component_declarations'].items()}
    for dep in controllers.values(): dep['metadata'].setdefault('resourceVersion', '12')
    controllers['gateway']['spec']['template']['spec'].setdefault('volumes', []).append(
        {'name': 'capture-seed', 'secret': {'secretName': 'old-capture-seed'}})
    patches = boot.bind_runtime(old, approvals, f.policy, pointers, anchors, bindings, controllers)
    specs = {c: value[-1]['value'] for c, value in patches.items()}
    next(v for v in specs['node']['template']['spec']['volumes'] if v['name'] == 'packaged-bootstrap-input')['configMap']['name'] = held['metadata']['name']
    seed = {'apiVersion': 'v1', 'kind': 'Secret', 'immutable': True, 'metadata': {
        'namespace': old.document['component_declarations']['gateway']['namespace'], 'name': 'new-capture-seed',
        'uid': str(uuid.uuid4()), 'resourceVersion': '20'}}
    next(v for v in specs['gateway']['template']['spec']['volumes'] if v['name'] == 'capture-seed')['secret']['secretName'] = seed['metadata']['name']
    previous = f.release.document
    # This is the independently pinned existing NodeConfig read, distinct from
    # names authorized dynamically by the future head protocol.
    for row in previous['roles']:
        if row['namespace'] == old.reference.to_dict()['namespace']:
            row['rules'][0]['resourceNames'].append(old.reference.to_dict()['name'])
    roles = []
    for row in previous['roles']:
        obj = copy.deepcopy(f.roles[(row['namespace'], row['name'])]); obj['rules'] = copy.deepcopy(row['rules']); roles.append(obj)
    capture = {'version': 1, 'configmaps': list(maps.values()), 'deployments': list(controllers.values()), 'roles': roles}
    return dict(previous_release=previous, reviewed_sha256=canonical_sha256(previous), catalog=f.policy.catalog,
        old_configuration=old, new_configuration=new, held_bootstrap=held, heads=bound['heads'], capture=capture,
        runtime_specs=specs, reviewed_runtime_specs_sha256=canonical_sha256(specs), actual_gateway_capture_seed=seed)


def test_real_v3_to_v4_composition_preserves_seven_identities_and_pins_held_template():
    inputs = fixture(); before = copy.deepcopy(inputs['capture'])
    result = load('head_observer_adoption').compose(**inputs)
    release = result['release']; assert release['version'] == 2
    assert release['heads'] == inputs['heads'] and len(release['head_get_rows']) == 7
    assert release['node_configuration'] == inputs['new_configuration'].reference.to_dict()
    assert release['held_node_template_sha256'] == canonical_sha256(inputs['runtime_specs']['node']['template'])
    for old, new in zip(inputs['previous_release']['roles'], release['roles']):
        assert (old['namespace'], old['name'], old['uid']) == (new['namespace'], new['name'], new['uid'])
        for index, (a, b) in enumerate(zip(old['rules'], new['rules'])):
            if a['resources'] != ['configmaps'] or a['verbs'] != ['get']: assert a == b
            else: assert set(a['resourceNames']) <= set(b['resourceNames'])
    assert result['prospective'] is True and result['live_applied'] is False
    assert result['process_readiness_verified'] is False and result['actual_only_render_required'] is True
    assert inputs['capture'] == before
    actuals = {(d['metadata']['namespace'], d['metadata']['name']): d for d in result['capture']['deployments']}
    for component, declaration in inputs['old_configuration'].document['component_declarations'].items():
        assert actuals[(declaration['namespace'], declaration['name'])]['spec'] == inputs['runtime_specs'][component]
    assert all(row['patch'][0]['path'] == '/metadata/uid' and row['patch'][1]['path'] == '/metadata/resourceVersion'
        and row['patch'][2]['path'] == '/rules' for row in result['static_role_patches'].values())


@pytest.mark.parametrize('fault', ['release-pin', 'spec-pin', 'extra-mount', 'image', 'command', 'role-uid',
    'static-verb', 'foreign-get', 'missing-map', 'pointer-uid', 'bootstrap-release', 'bootstrap-ref', 'foreign-seed'])
def test_unreviewed_authority_or_runtime_drift_is_rejected(fault):
    values = fixture()
    if fault == 'release-pin': values['reviewed_sha256'] = 'sha256:' + '0' * 64
    elif fault == 'spec-pin': values['reviewed_runtime_specs_sha256'] = 'sha256:' + '0' * 64
    elif fault in ('extra-mount', 'image', 'command'):
        pod = values['runtime_specs']['gateway']['template']['spec']
        if fault == 'extra-mount': pod['volumes'].append({'name': 'foreign', 'hostPath': {'path': '/'}})
        elif fault == 'image': pod['containers'][0]['image'] = 'foreign:latest'
        else: pod['containers'][0]['command'] = ['foreign']
        values['reviewed_runtime_specs_sha256'] = canonical_sha256(values['runtime_specs'])
    elif fault == 'role-uid': values['capture']['roles'][0]['metadata']['uid'] = str(uuid.uuid4())
    elif fault == 'static-verb': values['capture']['roles'][0]['rules'][0]['verbs'].append('list')
    elif fault == 'foreign-get': values['capture']['roles'][0]['rules'][0]['resourceNames'].append('unrelated')
    elif fault == 'missing-map':
        projection = values['heads']['gateway']['projection']; values['capture']['configmaps'] = [
            cm for cm in values['capture']['configmaps'] if (cm['metadata']['namespace'], cm['metadata']['name']) != (projection['namespace'], projection['name'])]
    elif fault == 'pointer-uid': values['heads']['gateway']['anchor']['pointer']['uid'] = str(uuid.uuid4())
    elif fault == 'bootstrap-release': values['held_bootstrap']['data']['release'] = 'true'
    elif fault == 'bootstrap-ref': values['held_bootstrap']['data']['config-ref.json'] = '{}'
    else: values['actual_gateway_capture_seed']['metadata']['namespace'] = 'foreign'
    with pytest.raises(ValueError): load('head_observer_adoption').compose(**values)


def test_second_static_get_row_stays_pinned_while_initial_authority_row_receives_heads():
    values = fixture(); namespace = values['old_configuration'].document['component_declarations']['hub:cps']['namespace']
    row = next(r for r in values['previous_release']['roles'] if r['namespace'] == namespace)
    row['rules'][0]['resourceNames'].append(values['heads']['hub:cps']['anchor']['initial']['name'])
    row['rules'].append({'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get'], 'resourceNames': ['independent-static-authority']})
    actual = next(r for r in values['capture']['roles'] if (r['metadata']['namespace'], r['metadata']['name']) == (row['namespace'], row['name']))
    actual['rules'] = copy.deepcopy(row['rules']); values['reviewed_sha256'] = canonical_sha256(values['previous_release'])
    result = load('head_observer_adoption').compose(**values)
    successor = next(r for r in result['release']['roles'] if (r['namespace'], r['name']) == (row['namespace'], row['name']))
    assert successor['rules'][-1] == row['rules'][-1]
    assert next(r for r in result['release']['head_get_rows'] if (r['namespace'], r['name']) == (row['namespace'], row['name']))['index'] == 0


def test_exact_prepared_get_deltas_and_actual_mutable_names_are_preserved():
    values = fixture(); initial = load('head_observer_adoption').compose(**values)
    values['capture']['roles'][0]['rules'] = initial['capture']['roles'][0]['rules']
    for role in values['capture']['roles']:
        for row in role['rules']:
            if row['resources'] in (['pods'], ['replicasets']): row['resourceNames'] = ['actual-observed-name']
    result = load('head_observer_adoption').compose(**values)
    assert len(result['static_role_patches']) == 6
    for old, new in zip(values['previous_release']['roles'], result['release']['roles']):
        for a, b in zip(old['rules'], new['rules']):
            if a['resources'] in (['pods'], ['replicasets']): assert a == b
    for role in result['capture']['roles']:
        for row in role['rules']:
            if row['resources'] in (['pods'], ['replicasets']): assert row['resourceNames'] == ['actual-observed-name']


@pytest.mark.parametrize('fault', ['controller-uid', 'new-config-uid', 'bootstrap-owner', 'bool-row', 'missing-row', 'role-order'])
def test_additional_identity_and_explicit_row_guards(fault):
    values = fixture()
    if fault == 'controller-uid': values['capture']['deployments'][0]['metadata']['uid'] = str(uuid.uuid4())
    elif fault == 'new-config-uid':
        ref = values['new_configuration'].reference.to_dict()
        next(cm for cm in values['capture']['configmaps'] if (cm['metadata']['namespace'], cm['metadata']['name']) == (ref['namespace'], ref['name']))['metadata']['uid'] = str(uuid.uuid4())
    elif fault == 'bootstrap-owner': values['held_bootstrap']['metadata']['ownerReferences'] = [{'uid': str(uuid.uuid4())}]
    elif fault in ('bool-row', 'missing-row'):
        values['head_get_rows'] = [{'namespace': r['namespace'], 'name': r['name'], 'index': 0} for r in values['previous_release']['roles']]
        if fault == 'bool-row': values['head_get_rows'][0]['index'] = False
        else: values['head_get_rows'].pop()
    else: values['capture']['roles'][0]['rules'].reverse()
    with pytest.raises(ValueError): load('head_observer_adoption').compose(**values)

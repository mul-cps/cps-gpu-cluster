import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

HERE = Path(__file__).parent


def module():
    spec = importlib.util.spec_from_file_location('head_delivery_render', HERE / 'render.py')
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def fixture():
    from test_native_observer_head_permissions import fixture as heads
    from cps_compute.native_node.config import NodeConfiguration, ImmutableConfigMapRef
    f = heads()
    configuration = NodeConfiguration.load(f.core,
        ImmutableConfigMapRef.from_dict(f.release.document['node_configuration']), f.f.policy)
    rows = []
    for component, declaration in configuration.document['component_declarations'].items():
        namespace = declaration['namespace']
        rows.append({'namespace': namespace, 'name': 'cps-native-observer-operator', 'uid': str(uuid.uuid4()),
            'index': 0, 'rules': [
                {'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get'], 'resourceNames': ['static-config']},
                {'apiGroups': [''], 'resources': ['pods'], 'verbs': ['get', 'list']}]})
    config = {'version': 1, 'enabled': True, 'policy_path': '/inputs/delivery/policy.json',
        'node_configuration': configuration.reference.to_dict(), 'observer_release': f.release.document,
        'pregrant_roles': rows, 'capture': {'origin': 'https://capture.example:8443',
            'ca_file': '/inputs/delivery/gateway-ca.pem', 'token_file': '/inputs/delivery/export.token'}, 'ttlSeconds': 60}
    return config, configuration


def rendered(config=None, configuration=None):
    if config is None: config, configuration = fixture()
    return module().render(config, configuration=configuration,
        image='ghcr.io/mul-cps/cps-compute@sha256:' + 'a' * 64,
        config_secret='reviewed-head-delivery', journal_pvc='existing-delivery-journal')


def test_disabled_runtime_uses_installed_sdk_and_separate_private_journal_child():
    config, configuration = fixture(); before = copy.deepcopy(config)
    docs = rendered(config, configuration)
    deployment = next(o for o in docs if o['kind'] == 'Deployment')
    assert deployment['spec']['replicas'] == 0
    pod = deployment['spec']['template']['spec']; main = pod['containers'][0]
    assert main['command'] == ['python', '-I', '-B', '-m', 'cps_compute.native_approval_delivery']
    assert main['args'] == ['--config', '/inputs/delivery/delivery.json', '--state-dir', '/journal/delivery', '--execute']
    assert {'name': 'journal', 'mountPath': '/journal/delivery', 'subPath': 'head-delivery'} in main['volumeMounts']
    assert all(v['mountPath'] != '/journal' for v in main['volumeMounts'])
    assert pod['securityContext']['fsGroup'] == 1000
    assert main['securityContext']['readOnlyRootFilesystem'] is True
    assert main['securityContext']['capabilities']['drop'] == ['ALL']
    assert config == before


def test_routine_permissions_have_no_deployment_or_node_or_secret_writes():
    config, configuration = fixture(); docs = rendered(config, configuration)
    roles = [o for o in docs if o['kind'] == 'Role']; assert len(roles) == 4
    declarations = configuration.document['component_declarations']
    for role in roles:
        ns = role['metadata']['namespace']
        pointer = next(h['anchor']['pointer'] for h in config['observer_release']['heads'].values()
            if h['anchor']['pointer']['namespace'] == ns)
        for row in role['rules']:
            assert '*' not in json.dumps(row) and 'secrets' not in row['resources'] and 'nodes' not in row['resources']
            if row['resources'] == ['configmaps'] and row['verbs'] == ['patch']:
                assert row['resourceNames'] == [pointer['name']]
            if row['resources'] == ['roles']:
                assert row['resourceNames'] == ['cps-native-observer-operator']
            if row['resources'] == ['deployments']:
                assert row['verbs'] == ['get']
                assert row['resourceNames'] == [next(d['name'] for d in declarations.values() if d['namespace'] == ns)]
            if row['resources'] == ['serviceaccounts']:
                assert row['verbs'] == ['get'] and row['resourceNames']
            assert 'list' not in row['verbs']
    assert not any(o['kind'] == 'Secret' for o in docs)


@pytest.mark.parametrize('fault', ['extra', 'foreign-ref', 'v1-observer', 'missing-role', 'duplicate-role',
    'foreign-role', 'wrong-index', 'bool-index', 'relative-policy', 'http-capture', 'unsafe-image', 'zero-image', 'capture-slash', 'capture-port', 'capture-space', 'capture-empty-query'])
def test_unreviewed_or_incompatible_inputs_are_rejected(fault):
    config, configuration = fixture(); image = 'ghcr.io/mul-cps/cps-compute@sha256:' + 'a' * 64
    if fault == 'extra': config['surprise'] = True
    elif fault == 'foreign-ref': config['node_configuration']['uid'] = str(uuid.uuid4())
    elif fault == 'v1-observer': config['observer_release']['version'] = 1
    elif fault == 'missing-role': config['pregrant_roles'].pop()
    elif fault == 'duplicate-role': config['pregrant_roles'][-1] = config['pregrant_roles'][0]
    elif fault == 'foreign-role': config['pregrant_roles'][0]['name'] = 'unrelated'
    elif fault == 'wrong-index': config['pregrant_roles'][0]['index'] = 1
    elif fault == 'bool-index': config['pregrant_roles'][0]['index'] = False
    elif fault == 'relative-policy': config['policy_path'] = 'policy.json'
    elif fault == 'http-capture': config['capture']['origin'] = 'http://capture.example'
    elif fault == 'capture-slash': config['capture']['origin'] += '/'
    elif fault == 'capture-port': config['capture']['origin'] = 'https://capture.example:70000'
    elif fault == 'capture-space': config['capture']['origin'] = 'https://capture.example ' 
    elif fault == 'capture-empty-query': config['capture']['origin'] += '?'
    elif fault == 'zero-image': image = 'ghcr.io/mul-cps/cps-compute@sha256:' + '0' * 64
    else: image = 'ghcr.io/mul-cps/cps-compute:latest'
    with pytest.raises(ValueError):
        module().render(config, configuration=configuration, image=image,
            config_secret='reviewed-head-delivery', journal_pvc='existing-delivery-journal')


def evaluate(policy, obj, old, namespace, actor, operation='UPDATE'):
    executable = os.environ.get('CPS_NATIVE_PENDING_CEL_EVALUATOR')
    if not executable: pytest.skip('Set CPS_NATIVE_PENDING_CEL_EVALUATOR to qualified official Go CEL evaluator')
    result = subprocess.run([executable], input=json.dumps({'policy': policy, 'inputs': {'object': obj,
        'oldObject': old, 'request': {'namespace': namespace, 'operation': operation,
            'userInfo': {'username': actor}}, 'params': {}}}), text=True, capture_output=True, check=True)
    value = json.loads(result.stdout)
    assert value['decision'] != 'error', value
    return value['decision']


@pytest.mark.parametrize('fault', ['none', 'actor', 'name', 'namespace', 'uid', 'extra-key', 'owner', 'wire', 'metadata'])
def test_pointer_update_admission_actual_cel(fault):
    config, configuration = fixture(); docs = rendered(config, configuration)
    policy = next(o for o in docs if o['kind'] == 'ValidatingAdmissionPolicy' and o['metadata']['name'].endswith('-pointer-update'))
    pointer = config['observer_release']['heads']['node']['anchor']['pointer']
    namespace = pointer['namespace']; actor = 'system:serviceaccount:cps-compute:cps-native-head-delivery'
    obj = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {
        'namespace': namespace, 'name': pointer['name'], 'uid': pointer['uid'], 'resourceVersion': '20'},
        'data': {'head.json': '{"generation":2,"reference":{"namespace":"' + namespace + '"},"version":1}'}}
    old = copy.deepcopy(obj); old['data']['head.json'] = '{"generation":1,"reference":{},"version":1}'
    if fault == 'actor': actor = 'system:serviceaccount:cps-compute:foreign'
    elif fault == 'name': obj['metadata']['name'] = 'foreign'
    elif fault == 'namespace': namespace = 'foreign'; obj['metadata']['namespace'] = namespace
    elif fault == 'uid': obj['metadata']['uid'] = str(uuid.uuid4())
    elif fault == 'extra-key': obj['data']['extra'] = 'x'
    elif fault == 'owner': obj['metadata']['ownerReferences'] = [{'uid': str(uuid.uuid4())}]
    elif fault == 'wire': obj['data']['head.json'] = '{}'
    elif fault == 'metadata': obj['metadata']['annotations'] = {'changed': 'true'}
    assert evaluate(policy, obj, old, namespace, actor) == ('pass' if fault == 'none' else 'deny')


@pytest.mark.parametrize('fault', ['none', 'actor', 'role', 'uid', 'index-rule', 'static-row', 'nonmonotonic', 'name', 'metadata'])
def test_pregrant_role_admission_actual_cel(fault):
    config, configuration = fixture(); docs = rendered(config, configuration)
    policy = next(o for o in docs if o['kind'] == 'ValidatingAdmissionPolicy' and o['metadata']['name'].endswith('-pregrant-update'))
    row = config['pregrant_roles'][0]; actor = 'system:serviceaccount:cps-compute:cps-native-head-delivery'
    old = {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': {
        'namespace': row['namespace'], 'name': row['name'], 'uid': row['uid'], 'resourceVersion': '20'}, 'rules': copy.deepcopy(row['rules'])}
    obj = copy.deepcopy(old); obj['rules'][row['index']]['resourceNames'].append('cps-native-approvals-' + 'a' * 16)
    if fault == 'actor': actor = 'system:serviceaccount:cps-compute:foreign'
    elif fault == 'role': obj['metadata']['name'] = 'foreign'
    elif fault == 'uid': obj['metadata']['uid'] = str(uuid.uuid4())
    elif fault == 'index-rule': obj['rules'][0]['verbs'].append('list')
    elif fault == 'static-row': obj['rules'][1]['verbs'] = ['get']
    elif fault == 'nonmonotonic': obj['rules'][0]['resourceNames'].remove('static-config')
    elif fault == 'name': obj['rules'][0]['resourceNames'].append('unrelated')
    elif fault == 'metadata': obj['metadata']['labels'] = {'changed': 'true'}
    assert evaluate(policy, obj, old, row['namespace'], actor) == ('pass' if fault == 'none' else 'deny')


@pytest.mark.parametrize('fault', ['unknown', 'symlink', 'held-lock'])
def test_private_initializer_preserves_legacy_state_and_repairs_only_new_owned_child(tmp_path, fault):
    config, configuration = fixture(); docs = rendered(config, configuration)
    init = next(o for o in docs if o['kind'] == 'Deployment')['spec']['template']['spec']['initContainers'][0]
    seed = tmp_path / 'seed'; seed.mkdir(); inputs = tmp_path / 'inputs'; inputs.mkdir()
    journal = tmp_path / 'journal'; journal.mkdir(); journal.chmod(0o2770)
    legacy = journal / 'delivery'; legacy.mkdir(); old = legacy / 'state.json'; old.write_bytes(b'untouched legacy state')
    for name in ('delivery.json', 'policy.json', 'gateway-ca.pem', 'export.token'): (seed / name).write_bytes(b'private fixture')
    code = init['command'][-1].replace('/inputs/delivery', str(inputs / 'delivery')).replace('/seed', str(seed)).replace('/journal', str(journal))
    subprocess.run([sys.executable, '-I', '-c', code], check=True)
    state = journal / 'head-delivery'; assert state.stat().st_mode & 0o7777 == 0o700
    assert old.read_bytes() == b'untouched legacy state' and journal.stat().st_mode & 0o7777 == 0o2770
    names = ('state.json', 'anchor.json', 'legacy-state.json', 'legacy-seed.json',
        'state.json.new', 'anchor.json.new', 'legacy-state.json.new', 'legacy-seed.json.new')
    for name in names:
        (state / name).write_bytes(b'unchanged ' + name.encode()); (state / name).chmod(0o660)
    state_file = state / 'state.json'
    state.chmod(0o2770)
    import shutil
    shutil.rmtree(inputs / 'delivery')
    subprocess.run([sys.executable, '-I', '-c', code], check=True)
    assert all((state / name).read_bytes() == b'unchanged ' + name.encode()
        and (state / name).stat().st_mode & 0o7777 == 0o600 for name in names)
    assert state.stat().st_mode & 0o7777 == 0o700
    if fault == 'unknown': (state / 'unrecognized').write_bytes(b'no repair')
    elif fault == 'symlink':
        (state / 'anchor.json').unlink(); (state / 'anchor.json').symlink_to(old)
    else:
        import fcntl
        lock = (state / 'lock').open('wb'); os.chmod(state / 'lock', 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    shutil.rmtree(inputs / 'delivery')
    try:
        result = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True)
    finally:
        if fault == 'held-lock': lock.close()
    assert result.returncode != 0 and old.read_bytes() == b'untouched legacy state'
    assert state_file.read_bytes() == b'unchanged state.json'


@pytest.mark.parametrize('fault', ['none', 'actor', 'name', 'namespace', 'object-namespace', 'extra-key',
    'mutable', 'owner', 'labels', 'annotations', 'finalizers', 'generate-name', 'deleted', 'binary', 'oversize', 'wire'])
def test_immutable_approval_create_admission_actual_cel(fault):
    config, configuration = fixture(); docs = rendered(config, configuration)
    policy = next(o for o in docs if o['kind'] == 'ValidatingAdmissionPolicy' and o['metadata']['name'].endswith('-approval-create'))
    namespace = config['pregrant_roles'][0]['namespace']
    actor = 'system:serviceaccount:cps-compute:cps-native-head-delivery'
    obj = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {
        'namespace': namespace, 'name': 'cps-native-approvals-' + 'a' * 16,
        'uid': str(uuid.uuid4()), 'resourceVersion': '1', 'creationTimestamp': '2026-10-17T00:00:00Z'},
        'immutable': True, 'data': {'approval.json': '{"history":[],"version":2}'}}
    if fault == 'actor': actor = 'system:serviceaccount:cps-compute:foreign'
    elif fault == 'name': obj['metadata']['name'] = 'cps-native-approvals-' + 'g' * 16
    elif fault == 'namespace': namespace = 'foreign'; obj['metadata']['namespace'] = namespace
    elif fault == 'object-namespace': obj['metadata']['namespace'] = 'foreign'
    elif fault == 'extra-key': obj['data']['extra'] = 'x'
    elif fault == 'mutable': obj['immutable'] = False
    elif fault == 'owner': obj['metadata']['ownerReferences'] = [{'uid': str(uuid.uuid4())}]
    elif fault == 'labels': obj['metadata']['labels'] = {'extra': 'value'}
    elif fault == 'annotations': obj['metadata']['annotations'] = {'extra': 'value'}
    elif fault == 'finalizers': obj['metadata']['finalizers'] = ['extra']
    elif fault == 'generate-name': obj['metadata']['generateName'] = 'extra-'
    elif fault == 'deleted': obj['metadata']['deletionTimestamp'] = '2026-10-17T00:00:00Z'
    elif fault == 'binary': obj['binaryData'] = {'extra': 'eA=='}
    elif fault == 'oversize': obj['data']['approval.json'] = '{"history":[' + 'x' * 1048576 + '],"version":2}'
    elif fault == 'wire': obj['data']['approval.json'] = '{"history":[],"version":1}'
    assert evaluate(policy, obj, None, namespace, actor, 'CREATE') == ('pass' if fault == 'none' else 'deny')


def test_unrelated_foreign_actor_is_not_matched_by_bounded_policies():
    config, configuration = fixture(); docs = rendered(config, configuration)
    obj = {'metadata': {'namespace': 'unrelated', 'name': 'unrelated'}}
    for policy in [o for o in docs if o['kind'] == 'ValidatingAdmissionPolicy']:
        assert evaluate(policy, obj, obj, 'unrelated', 'system:serviceaccount:unrelated:unrelated') == 'not-matched'


def test_default_script_entrypoint_is_inert():
    result = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'render.py')], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == {'enabled': False, 'api_calls': False, 'gpu_calls': False}

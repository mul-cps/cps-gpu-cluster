import copy
import importlib.util
import json
import os
from pathlib import Path
import uuid

import pytest

HERE = Path(__file__).parent


def module():
    spec = importlib.util.spec_from_file_location('delivery_admission_qualification', HERE / 'qualify_admission.py')
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def fixture():
    namespaces = ['cps-head-admission-qa-' + 'a' * 12 + '-' + str(i) for i in range(4)]
    def obj(kind, namespace, name):
        return {'apiVersion': 'v1' if kind == 'ConfigMap' else 'rbac.authorization.k8s.io/v1', 'kind': kind,
            'metadata': {'namespace': namespace, 'name': name, 'uid': str(uuid.uuid4()), 'resourceVersion': '1'}}
    pointers, roles, foreign = [], [], []
    for ns in namespaces:
        pointer = obj('ConfigMap', ns, 'qa-head'); pointer['data'] = {'head.json': '{}'}; pointers.append(pointer)
        role = obj('Role', ns, 'cps-native-observer-operator'); role['rules'] = [
            {'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get'], 'resourceNames': ['static-config']},
            {'apiGroups': [''], 'resources': ['pods'], 'verbs': ['get'], 'resourceNames': ['static-pod']}]
        roles.append(role)
        other = obj('ConfigMap', ns, 'foreign-head'); other['data'] = copy.deepcopy(pointer['data']); foreign.append(other)
    return namespaces, pointers, roles, foreign


def test_clones_keep_production_validations_and_add_only_isolated_namespace_scopes():
    m = module(); namespaces, pointers, roles, _ = fixture()
    config = m.policy_config(pointers, roles); originals = m.runtime()._policies(config, namespaces[0])
    clones = m.isolated_policies(config, namespaces, 'a' * 12)
    for old, new in zip(originals, clones):
        assert new['metadata']['name'].endswith('-qa-' + 'a' * 12)
        if old['kind'] == 'ValidatingAdmissionPolicy':
            assert old['spec']['validations'] == new['spec']['validations']
            assert old['spec']['matchConstraints']['resourceRules'] == new['spec']['matchConstraints']['resourceRules']
            assert new['spec']['matchConditions'][:-1] == old['spec']['matchConditions']
            assert new['spec']['matchConstraints']['namespaceSelector']['matchExpressions'][0]['values'] == namespaces
        else:
            assert new['spec']['policyName'] == new['metadata']['name']
            assert new['spec']['matchResources']['namespaceSelector']['matchExpressions'][0]['values'] == namespaces
    with pytest.raises(ValueError): m.isolated_policies(config, namespaces[:3] + ['production'], 'a' * 12)


@pytest.mark.parametrize('status,reason,message,allowed', [
    (403, 'Forbidden', 'ValidatingAdmissionPolicy qa-policy denied request', True),
    (403, 'Forbidden', 'RBAC forbidden', False), (422, 'Invalid', 'qa-policy', False),
    (403, 'Forbidden', 'another-policy denied request', False), (200, '', 'qa-policy', False)])
def test_expected_denial_requires_our_policy_not_rbac_or_api_validation(status, reason, message, allowed):
    result = {'status': status, 'reason': reason, 'message': message}
    assert module().policy_denial(result, 'qa-policy') is allowed


def test_default_cli_is_inert_without_creating_private_directory(tmp_path, capsys):
    m = module(); target = tmp_path / 'not-created'
    m.execute = lambda *args, **kwargs: pytest.fail('Inert command invoked execution')
    assert m.main(['--private-dir', str(target)]) == 0
    assert json.loads(capsys.readouterr().out) == {'state': 'inert', 'api_calls': False}
    assert not target.exists()


@pytest.mark.parametrize('fault', ['git', 'symlink', 'mode', 'nonempty'])
def test_private_directory_refuses_unsafe_destinations(tmp_path, fault):
    parent = tmp_path / 'parent'; parent.mkdir(mode=0o700); target = parent / 'receipt'
    if fault == 'git': (parent / '.git').mkdir()
    elif fault == 'symlink': target.symlink_to(parent, target_is_directory=True)
    else:
        target.mkdir(mode=0o700)
        if fault == 'mode': target.chmod(0o755)
        else: (target / 'existing').write_text('retain')
    with pytest.raises(ValueError): module().private_directory(target)


def test_cleanup_uses_fresh_resource_version_and_original_uid():
    m = module(); namespaces, pointers, _, _ = fixture(); original = pointers[0]; calls = []
    live = copy.deepcopy(original); live['metadata']['resourceVersion'] = '19'
    class Api:
        def request(self, method, path, body=None, **kwargs):
            calls.append((method, path, body))
            if method == 'GET': return {'status': 200, 'object': live}
            return {'status': 200, 'object': {}}
    result = m.cleanup(Api(), [m.identity(original)])
    assert result[0]['deleted'] is True
    assert calls[-1][0] == 'DELETE'
    assert calls[-1][2]['preconditions'] == {'uid': original['metadata']['uid'], 'resourceVersion': '19'}
    live['metadata']['uid'] = str(uuid.uuid4()); calls.clear()
    result = m.cleanup(Api(), [m.identity(original)])
    assert result[0]['deleted'] is False and not any(c[0] == 'DELETE' for c in calls)


def test_case_matrix_uses_only_server_dryrun_test_resources_and_all_four_namespaces():
    m = module(); namespaces, pointers, roles, foreign = fixture()
    cases = m.cases(pointers, roles, foreign, 'a' * 12)
    positive = [c for c in cases if c['accepted']]
    assert {c['namespace'] for c in positive if c['actor'] == 'test'} == set(namespaces)
    assert all(c['method'] in ('POST', 'PATCH') for c in cases)
    assert {'foreign-root-pointer', 'foreign-root-role', 'foreign-root-unrelated-create', 'foreign-root-unrelated-role'} <= {c['name'] for c in cases}
    assert all(c.get('policy') for c in cases if not c['accepted'])


def test_whole_isolated_flow_with_actual_go_cel_and_no_live_client(tmp_path, monkeypatch):
    import subprocess
    executable = os.environ.get('CPS_NATIVE_PENDING_CEL_EVALUATOR')
    if not executable: pytest.skip('Qualified official Go CEL evaluator required for complete offline matrix')
    m = module(); objects = {}; calls = []
    class OfflineApi:
        def __init__(self, context): pass
        def request(self, method, path, body=None, *, actor=None, dryrun=False):
            calls.append((method, path, dryrun))
            old = copy.deepcopy(objects.get(path)); obj = copy.deepcopy(body)
            if method == 'GET': return {'status': 200, 'object': old} if old else {'status': 404}
            if method == 'DELETE':
                if not old: return {'status': 404}
                assert body['preconditions'] == {k: old['metadata'][k] for k in ('uid', 'resourceVersion')}
                del objects[path]; return {'status': 200}
            if method == 'PATCH':
                assert dryrun and old
                obj = copy.deepcopy(old)
                for op in body:
                    parts = op['path'].strip('/').split('/'); target = obj
                    for part in parts[:-1]: target = target[part]
                    if op['op'] == 'test': assert target[parts[-1]] == op['value']
                    else: target[parts[-1]] = copy.deepcopy(op['value'])
            if dryrun:
                assert method in ('POST', 'PATCH')
                for policy in [p for p in objects.values() if p['kind'] == 'ValidatingAdmissionPolicy']:
                    rule = policy['spec']['matchConstraints']['resourceRules'][0]
                    plural = m.ROUTES[obj['kind']][1]
                    if plural not in rule['resources'] or ('CREATE' if method == 'POST' else 'UPDATE') not in rule['operations']: continue
                    result = subprocess.run([executable], input=json.dumps({'policy': policy, 'inputs': {
                        'request': {'namespace': obj['metadata']['namespace'], 'operation': 'CREATE' if method == 'POST' else 'UPDATE',
                            'userInfo': {'username': actor or 'root-operator'}}, 'object': obj, 'oldObject': old, 'params': {}}}),
                        text=True, capture_output=True, check=True)
                    decision = json.loads(result.stdout)['decision']; assert decision != 'error', result.stdout
                    if decision == 'deny': return {'status': 403, 'reason': 'Forbidden',
                        'message': 'ValidatingAdmissionPolicy ' + policy['metadata']['name'] + ' denied request'}
                return {'status': 200, 'object': obj}
            assert method == 'POST'
            target = path + '/' + obj['metadata']['name']; assert target not in objects
            obj['metadata'].update(uid=str(uuid.uuid4()), resourceVersion='1')
            if obj['kind'] == 'ValidatingAdmissionPolicy':
                obj['metadata']['generation'] = 1; obj['status'] = {'observedGeneration': 1, 'typeChecking': {'expressionWarnings': []}}
            objects[target] = obj; return {'status': 200, 'object': copy.deepcopy(obj)}
    monkeypatch.setattr(m, 'Kube', OfflineApi)
    result = m.execute(tmp_path / 'private')
    assert result['passed'] is True and result['residual_count'] == 0 and not objects
    assert len(result['barriers']) == 3 and all(b['enforced'] for b in result['barriers'])
    assert {'configmap-actual-replaced-uid', 'role-actual-replaced-uid'} <= {row['name'] for row in result['tests']}
    assert all(dryrun for method, path, dryrun in calls if method == 'PATCH')
    for filename in ('resources.private.json', 'receipt.private.json'):
        assert (tmp_path / 'private' / filename).stat().st_mode & 0o7777 == 0o600
    assert not any('/secrets' in path or '/pods' in path for _, path, _ in calls)

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
    (403, 'Forbidden', 'ValidatingAdmissionPolicy qa-policy denied request', False),
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
    assert calls[-1][2]['propagationPolicy'] == 'Foreground'
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


@pytest.mark.parametrize('proxy_strips,async_delete,warning_case', [
    (False, False, False), (True, False, False), (False, True, False), (True, True, False), (False, False, True)])
def test_whole_isolated_flow_with_actual_go_cel_and_no_live_client(tmp_path, monkeypatch, proxy_strips, async_delete, warning_case):
    import subprocess
    executable = os.environ.get('CPS_NATIVE_PENDING_CEL_EVALUATOR')
    if not executable: pytest.skip('Qualified official Go CEL evaluator required for complete offline matrix')
    m = module(); objects = {}; calls = []; terminating = {}; delayed_gets = []; delete_uids = []; propagation = []
    policy_reads = {}; warning = {'fieldRef': 'spec.validations[0].expression', 'warning': 'Actual type-check detail: ' + 'x' * 3000}
    clock = [0.0]
    if async_delete:
        monkeypatch.setattr(m.time, 'monotonic', lambda: clock[0])
        monkeypatch.setattr(m.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    class OfflineApi:
        def __init__(self, context): pass
        def request(self, method, path, body=None, *, actor=None, dryrun=False):
            calls.append((method, path, dryrun))
            if path == m.SSR: return {'status':200,'object':{'status':{'userInfo':{'username':(actor if not proxy_strips else None) or 'root-operator','groups':['system:authenticated']}}}}
            old = copy.deepcopy(objects.get(path)); obj = copy.deepcopy(body)
            if method == 'GET':
                if warning_case and old and old['kind'] == 'ValidatingAdmissionPolicy' and '-pregrant-update-qa-' in old['metadata']['name']:
                    policy_reads[path] = policy_reads.get(path, 0) + 1
                    if policy_reads[path] == 2: old['status']['typeChecking']['expressionWarnings'] = [warning] + [dict(warning, fieldRef='f' * 3000)] * 16
                if path in terminating:
                    if old['metadata'].get('finalizers') == ['foregroundDeletion']:
                        # Removing the GC finalizer requires an UPDATE. The
                        # protected metadata/foreign-actor policy denies it
                        # until finally removes the temporary policies.
                        active = any(p['kind'] == 'ValidatingAdmissionPolicy' and not p['metadata'].get('deletionTimestamp') for p in objects.values())
                        if active: return {'status': 200, 'object': old}
                        del objects[path]['metadata']['finalizers']
                    if terminating[path] == 0:
                        del terminating[path]; del objects[path]; return {'status': 404}
                    terminating[path] -= 1; delayed_gets.append(path)
                return {'status': 200, 'object': old} if old else {'status': 404}
            if method == 'DELETE':
                if not old: return {'status': 404}
                assert body['preconditions'] == {k: old['metadata'][k] for k in ('uid', 'resourceVersion')}
                delete_uids.append(old['metadata']['uid'])
                propagation.append((old['kind'], old['metadata']['namespace'] if 'namespace' in old['metadata'] else None, old['metadata']['name'], body['propagationPolicy']))
                if async_delete:
                    objects[path]['metadata']['deletionTimestamp'] = '2026-10-17T00:00:00Z'
                    if old['metadata']['name'] in ('qa-head', m.ROLE) and body['propagationPolicy'] == 'Foreground':
                        objects[path]['metadata']['finalizers'] = ['foregroundDeletion']
                    terminating.setdefault(path, 2); return {'status': 202, 'object': copy.deepcopy(objects[path])}
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
                        'message': "ValidatingAdmissionPolicy '" + policy['metadata']['name'] + "' with binding '" + policy['metadata']['name'] + "' denied request: Only the reviewed dynamic delivery write is permitted"}
                return {'status': 200, 'object': obj}
            assert method == 'POST'
            target = path + '/' + obj['metadata']['name']; assert target not in objects
            obj['metadata'].update(uid=str(uuid.uuid4()), resourceVersion='1')
            if obj['kind']=='Namespace':obj['metadata']['labels']['kubernetes.io/metadata.name']=obj['metadata']['name']
            if obj['kind'] == 'ValidatingAdmissionPolicy':
                obj['metadata']['generation'] = 1; obj['status'] = {'observedGeneration': 1, 'typeChecking': {'expressionWarnings': []}}
            objects[target] = obj; return {'status': 200, 'object': copy.deepcopy(obj)}
    monkeypatch.setattr(m, 'Kube', OfflineApi)
    result = m.execute(tmp_path / 'private')
    assert result['residual_count'] == 0 and not objects
    if proxy_strips:
        assert result['passed'] is False and result['stage'] == 'identity-proof' and not result['barriers']
        assert result['identity_checks']['test']['matches_expected'] is False
        return
    if warning_case:
        assert result['passed'] is False and len(result['tests']) == 37
        row = next(row for row in result['type_checking'] if '-pregrant-update-qa-' in row['policy'])
        assert row['warning_count'] == 17 and len(row['expressionWarnings']) == 16
        assert row['expressionWarnings'][0] == {'fieldRef': warning['fieldRef'], 'warning': warning['warning'][:2048]}
        assert len(row['expressionWarnings'][1]['fieldRef']) == 2048
        saved = json.loads((tmp_path / 'private' / 'receipt.private.json').read_text())
        assert saved['type_checking'] == result['type_checking']
        return
    assert result['passed'] is True
    if async_delete: assert delayed_gets and len(delete_uids) == len(set(delete_uids))
    backgrounds = [row for row in propagation if row[3] == 'Background']
    assert {(kind, name) for kind, _, name, _ in backgrounds} == {('ConfigMap', 'qa-head'), ('Role', m.ROLE)}
    assert len(backgrounds) == 2 and len({ns for _, ns, _, _ in backgrounds}) == 1
    assert all(mode == 'Foreground' for row in propagation if row not in backgrounds for mode in [row[3]])
    assert len(result['barriers']) == 3 and all(b['enforced'] for b in result['barriers'])
    assert {'configmap-actual-replaced-uid', 'role-actual-replaced-uid'} <= {row['name'] for row in result['tests']}
    assert all(dryrun for method, path, dryrun in calls if method == 'PATCH')
    for filename in ('resources.private.json', 'receipt.private.json'):
        assert (tmp_path / 'private' / filename).stat().st_mode & 0o7777 == 0o600
    assert not any('/secrets' in path or '/pods' in path for _, path, _ in calls)


@pytest.mark.parametrize('fault', ['timeout', 'replaced-uid'])
def test_replacement_wait_rejects_timeout_or_changed_uid_without_delete(monkeypatch, fault):
    m = module(); _, pointers, _, _ = fixture(); original = pointers[0]; calls = []; clock = [0.0]
    live = copy.deepcopy(original); live['metadata']['deletionTimestamp'] = '2026-10-17T00:00:00Z'
    if fault == 'replaced-uid': live['metadata']['uid'] = str(uuid.uuid4())
    class Api:
        def request(self, method, path):
            calls.append((method, path)); return {'status': 200, 'object': live}
    monkeypatch.setattr(m.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(m.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    with pytest.raises(ValueError, match='disappearance timed out|UID changed'):
        m.wait_fixture_absent(Api(), m.identity(original))
    assert clock[0] <= 30 and all(method == 'GET' for method, _ in calls)
    if fault == 'replaced-uid': assert len(calls) == 1 and clock[0] == 0


def test_proxy_identity_mismatch_is_explicit_and_real_username_redacted():
    m = module(); expected = 'system:serviceaccount:cps-head-admission-qa-' + 'a' * 12 + '-0:' + m.SA
    response = {'status': 200, 'object': {'status': {'userInfo': {'username': 'proxy-real-person', 'groups': ['system:masters']}}}}
    diagnostic = m.user_info_diagnostic(response, expected)
    assert diagnostic['matches_expected'] is False and diagnostic['group_classes']['masters'] is True
    assert 'proxy-real-person' not in json.dumps(diagnostic)
    response['object']['status']['userInfo']['username'] = expected
    assert m.user_info_diagnostic(response, expected)['matches_expected'] is True


@pytest.mark.parametrize('method,path,dryrun,allowed', [
    ('POST', '/apis/authentication.k8s.io/v1/selfsubjectreviews', False, True),
    ('POST', '/api/v1/namespaces/cps-head-admission-qa-aaaaaaaaaaaa-0/configmaps', True, True),
    ('PATCH', '/apis/rbac.authorization.k8s.io/v1/namespaces/cps-head-admission-qa-aaaaaaaaaaaa-3/roles/cps-native-observer-operator', True, True),
    ('POST', '/api/v1/namespaces/cps-compute/configmaps', True, False),
    ('POST', '/api/v1/namespaces/cps-head-admission-qa-aaaaaaaaaaaa-0/configmaps', False, False),
    ('GET', '/api/v1/namespaces/cps-head-admission-qa-aaaaaaaaaaaa-0/secrets', True, False)])
def test_static_broker_accepts_only_nonpersistent_review_or_qa_dryruns(method, path, dryrun, allowed):
    m = module(); namespaces, *_ = fixture()
    assert m.broker_request_allowed(method, path, dryrun, namespaces) is allowed


def test_last_response_diagnostic_is_bounded_and_contains_no_object_or_token():
    token = 'eyJ' + 'a' * 30 + '.bbbb.cccc'
    result = module().response_diagnostic({'status': 403, 'reason': 'Forbidden',
        'message': 'Bearer ' + token + ' ' + 'x' * 5000, 'object': {'secret': token}}, 'qa-user')
    assert len(result['message']) <= 1024 and token not in json.dumps(result)
    assert 'object' not in result and result['intended_username'] == 'qa-user'


def test_broker_uses_fixed_code_and_token_only_in_stdin_then_rechecks_identity(monkeypatch):
    from types import SimpleNamespace
    m=module();namespaces,*_=fixture();actor='system:serviceaccount:'+namespaces[0]+':'+m.SA
    options={'namespace':'gateway-system','deployment':'gateway','deployment_uid':str(uuid.uuid4()),
        'pod':'gateway-pod','pod_uid':str(uuid.uuid4()),'container':'gateway',
        'image':'ghcr.io/mul-cps/cps-compute@sha256:'+'a'*64,'audience':'https://kubernetes.default.svc.cluster.local'}
    token='synthetic-token-only-in-memory-0123456789';calls=[];rsuid=str(uuid.uuid4())
    dep={'metadata':{'uid':options['deployment_uid']},'spec':{'template':{'spec':{
        'serviceAccountName':'gateway','containers':[{'name':'gateway','image':options['image']}]}}}}
    pod={'metadata':{'uid':options['pod_uid'],'ownerReferences':[{'kind':'ReplicaSet','name':'gateway-rs','uid':rsuid,'controller':True}]},
        'spec':copy.deepcopy(dep['spec']['template']['spec']),'status':{'phase':'Running','conditions':[{'type':'Ready','status':'True'}],
        'containerStatuses':[{'name':'gateway','ready':True,'imageID':'containerd://sha256:'+'a'*64}]}}
    rs={'metadata':{'uid':rsuid,'ownerReferences':[{'kind':'Deployment','name':'gateway','uid':options['deployment_uid'],'controller':True}]}}
    class Api:
        def request(self,method,path,body=None,**kwargs):
            if path.endswith('/token'):
                assert body['spec']=={'audiences':[options['audience']],'expirationSeconds':600}
                return {'status':200,'object':{'status':{'token':token}}}
            return {'status':200,'object':dep if '/deployments/' in path else pod if '/pods/' in path else rs}
    def run(args,**kwargs):
        assert token not in repr(args) and args[-1]==m.BROKER_CODE
        assert json.loads(kwargs['input'])['token']==token
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout='{"status":200}')
    monkeypatch.setattr(m.subprocess,'run',run)
    broker=m.Broker(Api(),options,namespaces,actor,None)
    assert broker.request('POST',m.SSR,{},actor=actor)['status']==200 and len(calls)==1
    pod['metadata']['uid']=str(uuid.uuid4())
    with pytest.raises(ValueError):broker.request('POST',m.SSR,{},actor=actor)
    assert len(calls)==1


def test_remote_static_program_rejects_production_request_before_network():
    import subprocess
    m=module();namespaces,*_=fixture()
    response=subprocess.run([__import__('sys').executable,'-I','-B','-c',m.BROKER_CODE],input=json.dumps({
        'namespaces':namespaces,'method':'POST','path':'/api/v1/namespaces/cps-compute/configmaps',
        'body':{},'dryrun':True,'token':'synthetic-token-never-print'}),text=True,capture_output=True,check=True)
    assert json.loads(response.stdout)['status']==0
    assert 'synthetic-token' not in response.stdout+response.stderr


@pytest.mark.parametrize('status,reason,policy,binding,detail,expected', [
    (403, 'Forbidden', 'qa-policy', 'qa-policy', 'Only the reviewed dynamic delivery write is permitted', True),
    (403, 'Forbidden', 'qa-policy', 'qa-policy', 'CEL evaluation error: no such key', False),
    (422, 'Invalid', 'qa-policy', 'qa-policy', 'Only the reviewed dynamic delivery write is permitted', True),
    (422, 'Invalid', 'qa-policy', 'qa-policy', 'CEL evaluation error: no such key', False),
    (422, 'Invalid', 'other-policy', 'qa-policy', 'Only the reviewed dynamic delivery write is permitted', False),
    (422, 'Invalid', 'qa-policy', 'other-binding', 'Only the reviewed dynamic delivery write is permitted', False),
    (422, 'Invalid', 'qa-policy-suffix', 'qa-policy', 'Only the reviewed dynamic delivery write is permitted', False),
    (422, 'Forbidden', 'qa-policy', 'qa-policy', 'Only the reviewed dynamic delivery write is permitted', False),
    (403, 'Forbidden', 'other-policy', 'qa-policy', 'Only the reviewed dynamic delivery write is permitted', False),
    (403, 'Forbidden', 'qa-policy', 'other-binding', 'Only the reviewed dynamic delivery write is permitted', False)])
def test_kubernetes_default_invalid_requires_exact_policy_binding_and_validation(status, reason, policy, binding, detail, expected):
    message = 'configmaps "unapproved-name" is forbidden: ValidatingAdmissionPolicy ' + repr(policy) + ' with binding ' + repr(binding) + ' denied request: ' + detail
    assert module().policy_denial({'status': status, 'reason': reason, 'message': message}, 'qa-policy') is expected

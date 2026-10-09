import asyncio
import base64
import copy
import importlib.util
import json
from pathlib import Path
import sys
import ssl
from types import SimpleNamespace

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'hub_gateway_proposal.py'
spec = importlib.util.spec_from_file_location('hub_gateway_proposal', MODULE)
proposal = importlib.util.module_from_spec(spec); spec.loader.exec_module(proposal)


def test_default_cli_is_inert(capsys, monkeypatch):
    monkeypatch.setattr(proposal, 'prepare', lambda *args: pytest.fail('Default CLI performed preparation'))
    proposal.main([])
    assert json.loads(capsys.readouterr().out) == {'prepared': False, 'activationPerformed': False}


def test_mapping_merge_retains_all_existing_aliases_and_fences_conflicts():
    baseline = {'human': 'person-a'}
    assert proposal.merge_people(baseline, {'alias': 'person-a'}, {'fixture': 'fixture-person'}) == {
        'human': 'person-a', 'alias': 'person-a', 'fixture': 'fixture-person'}
    assert baseline == {'human': 'person-a'}
    with pytest.raises(ValueError, match='conflict'):
        proposal.merge_people(baseline, {'human': 'different-person'})


def test_json_patch_fences_exact_baseline_identity():
    baseline = {'metadata': {'uid': 'uid-1', 'resourceVersion': '12'}}
    operations = [{'op': 'replace', 'path': '/image', 'value': 'digest'}]
    assert proposal.patch(baseline, operations)[:2] == [
        {'op': 'test', 'path': '/metadata/uid', 'value': 'uid-1'},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '12'}]
    with pytest.raises(ValueError): proposal.patch({'metadata': {'uid': 'uid-1'}}, operations)


def test_scopes_are_exact_owner_server_group_filters():
    item = {'owner': 'neutral-a', 'server': 'rtc', 'group_id': 'course-a'}
    assert proposal.group_scopes([item]) == ['admin:groups!group=course-a', 'servers!user=neutral-a', 'shares!server=neutral-a/rtc']
    from jupyterhub.scopes import _check_scopes_exist, expand_scopes
    _check_scopes_exist(proposal.group_scopes([item]))
    expanded = expand_scopes(proposal.group_scopes([item]))
    assert 'read:users:name!user=neutral-a' in expanded
    assert all('!' in scope for scope in expanded)


def test_login_guard_preserves_humans_marker_roles_and_existing_permissions():
    from jupyterhub.auth import Authenticator
    from traitlets.config import Config
    refreshed = []
    class Prior(Authenticator):
        def check_blocked_users(self, username, authentication=None): return username != 'existing-denied'
        async def refresh_user(self, user, handler=None, **kwargs):
            refreshed.append((user.name, handler, kwargs))
            return {'name': user.name, 'auth_state': {'keep': 'human-oauth-refresh'}}
    c = Config(); c.JupyterHub.authenticator_class = Prior
    c.JupyterHub.load_roles = [{'name': 'legacy', 'scopes': ['read:metrics']},
                             {'name': 'cps-workspace-kernel', 'scopes': [], 'users': ['old-neutral']}]
    c.Authenticator.blocked_users = {'existing-denied'}
    c.GenericOAuthenticator.manage_groups = True
    item = {'owner': 'neutral-a', 'server': 'rtc', 'group_id': 'course-a'}
    code = proposal.access_config('cps', [item], group_snapshot_confirmed=True)
    exec(compile(code, 'trusted-operator-config', 'exec'), {'c': c})
    guard = c.JupyterHub.authenticator_class()
    assert asyncio.run(guard.check_blocked_users('neutral-a')) is False
    assert asyncio.run(guard.check_blocked_users('existing-denied')) is False
    assert asyncio.run(guard.check_blocked_users('human')) is True
    machine = SimpleNamespace(name='neutral-a', admin=False,
        orm_user=SimpleNamespace(roles=[SimpleNamespace(name='cps-workspace-kernel')]))
    assert asyncio.run(guard.refresh_user(machine)) is True
    assert refreshed == []
    assert asyncio.run(guard.refresh_user(SimpleNamespace(name='human'), handler='human-handler', fresh=True)) == {
        'name': 'human', 'auth_state': {'keep': 'human-oauth-refresh'}}
    assert refreshed == [('human', 'human-handler', {'fresh': True})]
    assert asyncio.run(guard.refresh_user(SimpleNamespace(name='neutral-a'))) != True
    machine.admin = True
    assert asyncio.run(guard.refresh_user(machine)) != True
    assert c.Authenticator.blocked_users == {'existing-denied'}
    assert c.GenericOAuthenticator.manage_groups is False
    marker = next(role for role in c.JupyterHub.load_roles if role['name'] == 'cps-workspace-kernel')
    assert marker['users'] == ['neutral-a', 'old-neutral'] and marker['scopes'] == []
    assert c.JupyterHub.load_roles[0] == {'name': 'legacy', 'scopes': ['read:metrics']}
    with pytest.raises(ValueError, match='snapshot'):
        proposal.access_config('cps', [item], group_snapshot_confirmed=False)


@pytest.fixture
def render_inputs(tmp_path):
    import yaml
    catalog = json.loads((MODULE.parents[3] / 'compute-policy/catalog.json').read_text())
    def obj(kind, data=None):
        result = {'apiVersion': 'v1', 'kind': kind, 'metadata': {'uid': 'fixture-uid', 'resourceVersion': '1'}}
        if data is not None: result['data'] = data
        return result
    def deployment(name):
        result = obj('Deployment'); result['spec'] = {'template': {'spec': {'volumes': [],
            'containers': [{'name': name, 'image': 'old-image', 'env': [], 'volumeMounts': []}]}}}
        return result
    runtime = {'policy_hash': 'sha256:' + '0' * 64, 'hubs': {source: {'canonical_people': {'existing': 'existing-person'}} for source in ('cps', 'cit')},
        'service_token_envs': {'cps': 'CPS_CONTROL', 'cit': 'CIT_CONTROL'}, 'preserveOtherRuntime': True}
    b64 = lambda value: base64.b64encode(value.encode()).decode()
    baselines = {'policy': obj('ConfigMap', {'policy.json': json.dumps(catalog)}),
        'runtime': obj('Secret', {'runtime.json': b64(json.dumps(runtime))}), 'gateway': deployment('gateway'),
        'gatewaySecret': obj('Secret', {'CPS_CONTROL': b64('fake-cps-token'), 'CIT_CONTROL': b64('fake-cit-token')})}
    for source in ('cps', 'cit'):
        baselines[source] = {'deployment': deployment('hub'), 'secret': obj('Secret', {
            'values.yaml': b64(yaml.safe_dump({'hub': {'extraConfig': {'legacy': 'legacy hook'}, 'keep': 'personal config'}, 'singleuser': {'keep': True}})),
            'cookie': b64('fake-cookie')})}
    inputs = {'version': 1, 'groupSnapshotConfirmed': True,
        'images': {name: name + '@sha256:' + str(i) * 64 for i, name in enumerate(('hub', 'gateway', 'notebook', 'gate'), 1)},
        'gatewayUrl': 'https://gateway.invalid', 'gatewayCAFile': ssl.get_default_verify_paths().cafile,
        'nodePool': {'node': 'k3s-wk-gpu2', 'node_uid': '3336cdd5-d245-436e-b57c-2f66c6dcaa41',
            'gpu_uuid': 'GPU-16128952-b438-556a-00bb-93039ee24e56', 'max_workspaces': 2},
        'canonicalMappings': {source: {'alias': 'existing-person'} for source in ('cps', 'cit')},
        'fixturePeople': {source: {'fixture': source + '-fixture-person'} for source in ('cps', 'cit')},
        'workspaces': [{'source': source, 'workspace': name, 'owner': 'neutral-' + name, 'server': 'rtc', 'group_id': 'group-' + name}
                       for source, name in [('cps', 'a'), ('cps', 'b'), ('cit', 'c')]]}
    return inputs, baselines


def test_render_preserves_personal_values_tokens_and_exact_storage_binding(render_inputs):
    import yaml
    from cps_compute.policy import Policy
    from cps_compute.storage import binding
    inputs, baselines = render_inputs; before = copy.deepcopy(baselines)
    rendered = proposal.render(inputs, baselines)
    assert baselines == before
    catalog = json.loads(rendered['compute-policy.patch.json'][-1]['value'])
    assert Policy(catalog).native_pilot_resources(proposal.PROFILE) == {'cpu': '4', 'memory': '16Gi'}
    assert catalog['profiles'][proposal.PROFILE]['enabled'] is False
    for source, namespace in proposal.NAMESPACES.items():
        values = yaml.safe_load(base64.b64decode(rendered[namespace + '-hub-secret.patch.json'][-1]['value']))
        assert values['hub']['extraConfig']['legacy'] == 'legacy hook'
        assert values['hub']['keep'] == 'personal config' and values['singleuser']['keep'] is True
        cm = rendered[namespace + '-config.json']; settings = json.loads(cm['data']['settings.json'])
        groups = [item['group_id'] for item in inputs['workspaces'] if item['source'] == source]
        assert settings['writablePVCClaims'] == sorted('cps-workspace-' + binding(source, group)[0][:40] for group in groups)
        assert rendered[namespace + '-control-secret.json']['data'] == {source.upper() + '_CONTROL': baselines['gatewaySecret']['data'][source.upper() + '_CONTROL']}
        assert 'api_token' not in cm['data']['settings.json']
    runtime = json.loads(base64.b64decode(rendered['runtime-secret.patch.json'][-1]['value']))
    assert runtime['preserveOtherRuntime'] is True
    assert runtime['hubs']['cps']['canonical_people']['existing'] == 'existing-person'
    assert len(runtime['nativeGpuPilot']['native_pilot_workspaces']) == 3


def test_prepare_writes_private_new_files_and_preserves_baseline_bytes(render_inputs, tmp_path):
    inputs, baselines = render_inputs
    root = tmp_path / 'baseline'; root.mkdir(mode=0o700)
    files = {'cps-compute-compute-policy-baseline.json': baselines['policy'],
             'cps-compute-runtime-secret-baseline.json': baselines['runtime'],
             'cps-compute-compute-gateway-baseline.json': baselines['gateway'],
             'gateway-secret-baseline.json': baselines['gatewaySecret']}
    for source, namespace in proposal.NAMESPACES.items():
        files[namespace + '-hub-baseline.json'] = baselines[source]['deployment']
        files[namespace + '-hub-secret-baseline.json'] = baselines[source]['secret']
    for name, body in files.items(): (root / name).write_text(json.dumps(body))
    before = {name: (root / name).read_bytes() for name in files}
    input_path = tmp_path / 'inputs.json'; input_path.write_text(json.dumps(inputs))
    output = tmp_path / 'private-proposal'
    result = proposal.prepare(input_path, root, output)
    assert result['activationPerformed'] is False
    assert output.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in output.iterdir())
    assert before == {name: (root / name).read_bytes() for name in files}
    with pytest.raises(ValueError): proposal.prepare(input_path, root, output)

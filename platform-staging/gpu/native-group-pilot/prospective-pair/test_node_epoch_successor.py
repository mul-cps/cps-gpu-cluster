"""Real flat source/factory/publisher; only external I/O and hardware are synthetic."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import uuid

import pytest

from test_node_successor import BASE, baseline, fixture, generator

HERE = Path(__file__).parent
EPOCH = (HERE / 'epoch8c.py').read_bytes()
EPOCH_SHA = '890cebd7c1903a680e4dc836ec6f81f097198c2fed438ade6b2fa62157864bbd'
REVISION_SHA = 'ddaaf9593dfbc9cba2d4aa3227102895a435e2537346ddd467c4941c0201658d'
PROCESS_SHA = 'e121dd491d709d945b96fa475902486f783151f76f903344d06871b49aab2875'


def sources(contract):
    raw = json.dumps(contract, sort_keys=True).encode()
    tool = generator()
    if not hasattr(tool, 'successor_bundle'):
        return {'node_agent.py': tool.successor_source(BASE, raw, hashlib.sha256(raw).hexdigest()),
                'native_operator_epoch.py': EPOCH.decode()}
    return tool.successor_bundle(BASE, EPOCH, raw, hashlib.sha256(raw).hexdigest())


def scope():
    config, _, _, _, contract = fixture()
    ns = config['authority_namespace']
    uid = lambda n: str(uuid.UUID(int=n))
    image = 'registry.example/operator@sha256:' + 'f' * 64
    declared = dict(namespace=ns, kind='Deployment', name='node-operator', uid=uid(101),
        container='node', image=image, service_account='node-operator', service_account_uid=uid(102))
    own = {k: declared[k] for k in ('namespace', 'container', 'image', 'service_account')}
    own.update(name='node-operator-pod', uid=uid(103))
    template = dict(metadata={'labels': {'app': 'node-operator'}}, spec={
        'serviceAccountName': 'node-operator', 'nodeName': config['pool']['node'],
        'containers': [{'name': 'node', 'image': image}]})
    controller = dict(apiVersion='apps/v1', kind='Deployment',
        metadata={k: declared[k] for k in ('namespace', 'name', 'uid')},
        spec={'selector': {'matchLabels': {'app': 'node-operator'}}, 'template': copy.deepcopy(template)})
    owner = lambda kind, name, ident: dict(apiVersion='apps/v1', kind=kind, name=name, uid=ident, controller=True)
    rs = dict(apiVersion='apps/v1', kind='ReplicaSet', metadata=dict(namespace=ns, name='node-rs',
        uid=uid(104), ownerReferences=[owner('Deployment', declared['name'], declared['uid'])]),
        spec={'template': copy.deepcopy(template)})
    pod = dict(apiVersion='v1', kind='Pod', metadata=dict(namespace=ns, name=own['name'], uid=own['uid'],
        labels={'app': 'node-operator'}, ownerReferences=[owner('ReplicaSet', 'node-rs', uid(104))]),
        spec=copy.deepcopy(template['spec']), status={'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'True'}]})
    config_cm = dict(apiVersion='v1', kind='ConfigMap', immutable=True,
        metadata=dict(namespace=ns, name='operator-node-config', uid=uid(105), resourceVersion='2'),
        data={'config.json': baseline.canonical_json(config)})
    ref = dict(config_cm['metadata'], data_sha256=baseline.canonical_sha256(config_cm['data']))
    target = dict(namespace=ns, name='cps-native-kai-epoch-node', uid=uid(106))
    ack = dict(apiVersion='v1', kind='ConfigMap', metadata=dict(target, resourceVersion='3'), data={'epoch.json': '{}'})
    epoch = {k: config['pool'][k] for k in ('node_uid', 'boot_id', 'driver_generation', 'gpu_uuid')}
    node = dict(apiVersion='v1', kind='Node', metadata={'name': config['pool']['node'], 'uid': epoch['node_uid']},
        status={'nodeInfo': {'bootID': epoch['boot_id']}})
    sa = dict(apiVersion='v1', kind='ServiceAccount', metadata=dict(namespace=ns,
        name=declared['service_account'], uid=declared['service_account_uid']))
    settings = dict(version=1, enabled=True, target=target, node_configuration=ref, process=declared, ttlSeconds=30)
    calls = []

    class API:
        def read_namespaced_config_map(self, name, namespace):
            assert namespace == ns
            calls.append(('cm', name))
            return copy.deepcopy({ref['name']: config_cm, target['name']: ack}[name])
        def read_namespaced_pod(self, *args): return copy.deepcopy(pod)
        def read_namespaced_deployment(self, *args): return copy.deepcopy(controller)
        def read_namespaced_replica_set(self, *args): return copy.deepcopy(rs)
        def read_namespaced_service_account(self, *args): return copy.deepcopy(sa)
        def read_node(self, *args): return copy.deepcopy(node)
        def patch_namespaced_config_map(self, name, namespace, patch):
            calls.append(('patch', name))
            assert name == target['name'] and namespace == ns
            assert [p['op'] for p in patch] == ['test', 'test', 'test', 'replace']
            assert patch[0]['value'] == ack['metadata']['uid']
            assert patch[1]['value'] == ack['metadata']['resourceVersion']
            assert patch[2]['value'] == ack['data'] and patch[3]['path'] == '/data'
            ack['data'] = copy.deepcopy(patch[3]['value'])
            ack['metadata']['resourceVersion'] = '4'
            return copy.deepcopy(ack)

    api = API()
    return locals()


def factory(tmp_path, monkeypatch, s, source_map):
    """Run actual Node main and immediate publisher ACK, with no external calls."""
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    snapshot = json.loads((HERE.parent / 'source-snapshot.json').read_text())
    (bundle / 'source-snapshot.json').write_text(json.dumps(snapshot))
    for name, text in snapshot['sources'].items(): (bundle / name).write_text(text)
    for name in ('native_approval_revision.py', 'native_approval_process.py'):
        (bundle / name).write_bytes((HERE / 'reference' / name).read_bytes())
    for name, text in source_map.items(): (bundle / name).write_text(text)
    agent = ModuleType('selected_node_epoch_test')
    agent.__file__ = str(bundle / 'node_agent.py')
    sys.modules[agent.__name__] = agent
    exec(compile(source_map['node_agent.py'], agent.__file__, 'exec'), agent.__dict__)
    state = tmp_path / 'state'
    state.mkdir(mode=0o700)
    real_load, real_bundle = agent.load_source, agent.load_bundle
    loaded = []

    def selected(name, raw, expected, filename):
        module = real_load(name, raw, expected, filename)
        loaded.append((filename, expected))
        if name == '_operator_epoch_private_backend': module.private_read = lambda *a: copy.deepcopy(s['settings'])
        if filename == 'native_operator_epoch.py': module.OperatorEpochRawAPI = lambda *a: s['api']
        return module

    def actual_bundle(path):
        adapter, poll, modules = real_bundle(path)
        adapter.private_directory = lambda path: state
        modules['manual'].Nvml = lambda: SimpleNamespace(close=lambda: None)
        return adapter, poll, modules

    monkeypatch.setattr(agent, 'load_source', selected)
    monkeypatch.setattr(agent, 'load_bundle', actual_bundle)
    monkeypatch.setattr(agent, 'read_config', lambda path: copy.deepcopy(s['config']))
    monkeypatch.setattr(agent, 'api_class', lambda _: lambda _: s['api'])
    monkeypatch.setattr(agent, 'abort_current_epoch', lambda *a: SimpleNamespace(**s['epoch']))
    monkeypatch.setattr(agent.os, 'geteuid', lambda: 0)
    real_fstat = agent.os.fstat
    monkeypatch.setattr(agent.os, 'fstat', lambda fd: SimpleNamespace(
        st_mode=real_fstat(fd).st_mode, st_uid=0, st_nlink=real_fstat(fd).st_nlink))
    monkeypatch.setenv('CPS_NATIVE_OPERATOR_POD_NAME', s['own']['name'])
    monkeypatch.setenv('CPS_NATIVE_OPERATOR_POD_UID', s['own']['uid'])
    monkeypatch.setenv('CPS_NATIVE_OPERATOR_POD_NAMESPACE', s['own']['namespace'])
    reconciled = []

    def run(config, bundle, state, kube, driver, **kwargs):
        assert kwargs['approval'] is None and callable(kwargs['operator_epoch'])
        assert json.loads(s['ack']['data']['epoch.json'])['driver_epoch'] == s['epoch']
        reconciled.append(config)

    monkeypatch.setattr(agent, 'run', run)
    agent.main(['--execute', '--config', '/synthetic/config', '--operator-epoch-config', '/synthetic/epoch',
                '--bundle', str(bundle), '--state-root', str(state), '--service-account', '/synthetic/sa'])
    return loaded, reconciled


def test_actual890_publisher_factory_reproduces_pair_blocker(tmp_path, monkeypatch):
    s = scope()
    with pytest.raises(ValueError, match='qualification10'):
        factory(tmp_path, monkeypatch, s, {'node_agent.py': BASE.decode(), 'native_operator_epoch.py': EPOCH.decode()})
    assert not any(call[0] == 'patch' for call in s['calls'])


def test_selected_node_factory_loads_exact_successor_and_acknowledges_pair(tmp_path, monkeypatch):
    s = scope()
    selected = sources(s['contract'])
    loaded, reconciled = factory(tmp_path, monkeypatch, s, selected)
    assert ('native_operator_epoch.py', hashlib.sha256(selected['native_operator_epoch.py'].encode()).hexdigest()) in loaded
    assert ('native_approval_revision.py', REVISION_SHA) in loaded
    assert ('native_approval_process.py', PROCESS_SHA) in loaded
    assert reconciled == [s['config']]
    assert sum(kind == 'patch' for kind, _ in s['calls']) == 1


@pytest.mark.parametrize('fault', ['policy', 'history', 'scope', 'cap', 'free', 'budget', 'maximum', 'headroom',
    'config-uid', 'config-rv', 'config-mutable', 'pod', 'controller', 'sa', 'boot', 'generation', 'helper-bytes'])
def test_selected_factory_denies_drift_before_epoch_patch(tmp_path, monkeypatch, fault):
    s = scope()
    selected = sources(s['contract'])
    if fault == 'policy': s['config']['policy_hash'] = 'sha256:' + 'b' * 64
    elif fault == 'history': s['config']['terminal_history'] = {}
    elif fault == 'scope': s['config']['workspaces']['cps:shared-gpu-lab'] = s['config']['workspaces'].pop(next(iter(s['config']['workspaces'])))
    elif fault == 'cap': next(iter(s['config']['workspaces'].values()))['cap_mib'] = 10240
    elif fault in ('free', 'budget', 'maximum', 'headroom'):
        key, value = {'free': ('free_memory_mib', 26623), 'budget': ('memory_budget_mib', 15360),
            'maximum': ('max_workspaces', 3), 'headroom': ('headroom_mib', 2048)}[fault]
        s['config']['pool'][key] = value
    elif fault == 'config-uid': s['config_cm']['metadata']['uid'] = str(uuid.UUID(int=999))
    elif fault == 'config-rv': s['config_cm']['metadata']['resourceVersion'] = '99'
    elif fault == 'config-mutable': s['config_cm']['immutable'] = False
    elif fault == 'pod': s['pod']['metadata']['uid'] = str(uuid.UUID(int=999))
    elif fault == 'controller': s['controller']['spec']['template']['spec']['containers'][0]['command'] = ['foreign']
    elif fault == 'sa': s['sa']['metadata']['uid'] = str(uuid.UUID(int=999))
    elif fault == 'boot': s['node']['status']['nodeInfo']['bootID'] = str(uuid.UUID(int=999))
    elif fault == 'generation': s['epoch']['driver_generation'] = str(uuid.UUID(int=999))
    else: selected['native_operator_epoch.py'] += '\n'
    if fault in ('policy', 'history', 'scope', 'cap', 'free', 'budget', 'maximum', 'headroom'):
        s['config_cm']['data']['config.json'] = baseline.canonical_json(s['config'])
        s['settings']['node_configuration']['data_sha256'] = baseline.canonical_sha256(s['config_cm']['data'])
    with pytest.raises(ValueError): factory(tmp_path, monkeypatch, s, selected)
    assert not any(call[0] == 'patch' for call in s['calls'])


@pytest.mark.parametrize('original', [True, False])
def test_legacy10_factory_remains_unchanged(tmp_path, monkeypatch, original):
    s = scope()
    s['config']['workspaces'] = {'cit:legacy-operator': {'profile': 'interactive-native-qualification-10', 'cap_mib': 10240}}
    s['config']['pool']['memory_budget_mib'] = 15360
    s['config_cm']['data']['config.json'] = baseline.canonical_json(s['config'])
    s['settings']['node_configuration']['data_sha256'] = baseline.canonical_sha256(s['config_cm']['data'])
    selected = {'node_agent.py': BASE.decode(), 'native_operator_epoch.py': EPOCH.decode()} if original else sources(s['contract'])
    _, reconciled = factory(tmp_path, monkeypatch, s, selected)
    assert reconciled == [s['config']]
    assert sum(kind == 'patch' for kind, _ in s['calls']) == 1


def test_unknown_epoch_patch_outcome_never_replays_or_reconciles_caps(tmp_path, monkeypatch):
    s = scope()
    patch = s['api'].patch_namespaced_config_map
    def ambiguous(*args):
        patch(*args)
        raise TimeoutError('Synthetic response lost after CAS')
    s['api'].patch_namespaced_config_map = ambiguous
    with pytest.raises(TimeoutError): factory(tmp_path, monkeypatch, s, sources(s['contract']))
    assert sum(kind == 'patch' for kind, _ in s['calls']) == 1


@pytest.mark.parametrize('flag', ['--emit', '--emit-bundle'])
def test_missing_independent_pin_never_opens_any_file(monkeypatch, flag):
    tool = generator()
    monkeypatch.setattr(tool.os, 'open', lambda *a, **k: pytest.fail('No file may be opened'))
    with pytest.raises(ValueError, match='independent'):
        tool.main([flag, '--contract', '/must-not-open'])


def test_unreviewed_flat_helper_bytes_are_denied():
    s = scope()
    raw = json.dumps(s['contract'], sort_keys=True).encode()
    with pytest.raises(ValueError, match='flat epoch helper'):
        generator().successor_bundle(BASE, EPOCH + b'\n', raw, hashlib.sha256(raw).hexdigest())


def test_only_reviewed_epoch_history_reader_and_pin_change():
    s = scope()
    selected = sources(s['contract'])
    def replace_definition(source, name):
        names = {name} if isinstance(name,str) else set(name)
        nodes = [n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in names]
        assert len(nodes)==len(names)
        lines = source.splitlines(True)
        for n in sorted(nodes,key=lambda n:n.lineno,reverse=True):
            lines[n.lineno-1:n.end_lineno]=['<definition>\n']
        return ''.join(lines)
    assert hashlib.sha256(EPOCH).hexdigest() == EPOCH_SHA
    assert replace_definition(EPOCH.decode(), 'node_configuration') == replace_definition(selected['native_operator_epoch.py'], 'node_configuration')
    pin = hashlib.sha256(selected['native_operator_epoch.py'].encode()).hexdigest()
    node = selected['node_agent.py'].replace(pin, EPOCH_SHA)
    assert node.count("len(history) <= 128, 'Bounded explicit terminal history required'") == 1
    node = node.replace("len(history) <= 128, 'Bounded explicit terminal history required'",
        "len(history) <= 64, 'Bounded explicit terminal history required'", 1)
    assert replace_definition(BASE.decode(), ('validate_historical_configuration','read_config','validate_authority_enrollments')) == replace_definition(node, ('validate_historical_configuration','read_config','validate_authority_enrollments'))

"""Synthetic authority only; the reference source is exact published Node8c."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
import uuid

import pytest

HERE = Path(__file__).parent
D48 = 'sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'
OLD = 'sha256:39ef15d3b5a76f96d135beb1afcd538775c64301cb51751086b44d68c54f8012'
PAIR = {
    'cps:operator-qualification-531-test-five': {'profile': 'interactive-native-qualification-5', 'cap_mib': 5120},
    'cps:operator-qualification-531-test-twenty': {'profile': 'interactive-native-qualification-20', 'cap_mib': 20480},
}


def loaded(source, name):
    module = ModuleType(name)
    module.__file__ = str(HERE / 'node8c.py')
    sys.modules[name] = module
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    return module


BASE = (HERE / 'node8c.py').read_bytes()
baseline = loaded(BASE, 'published_node8c_reference')


def fixture():
    pool = dict(node='k3s-wk-gpu2', node_uid='3336cdd5-d245-436e-b57c-2f66c6dcaa41',
        gpu_uuid='GPU-16128952-b438-556a-00bb-93039ee24e56', max_workspaces=2,
        total_memory_mib=40960, free_memory_mib=26624, headroom_mib=1024,
        memory_budget_mib=25600, boot_id=str(uuid.UUID(int=20)), driver_generation=str(uuid.UUID(int=21)))
    old = dict(version=2, enabled=True, mode='operator-qualification', authority_namespace='cps-native-system',
        policy_hash=OLD, pool=pool, workspaces={
            'cps:native-group-b': {'profile': 'interactive-native-qualification-5', 'cap_mib': 5120},
            'cit:native-group-a': {'profile': 'interactive-native-qualification-20', 'cap_mib': 20480}},
        terminal_history={})
    cm = dict(apiVersion='v1', kind='ConfigMap', immutable=True,
        metadata=dict(namespace='cps-native-system', name='cps-native-node-qualification-synthetic', uid=str(uuid.UUID(int=22))),
        data={'config.json': baseline.canonical_json(old)})
    reference = {k: cm['metadata'][k] for k in ('namespace', 'name', 'uid')}
    reference.update(data_sha256=baseline.canonical_sha256(cm['data']), policy_hash=OLD)
    history = {}
    for index, cap in enumerate((5120, 20480), 30):
        history[str(uuid.UUID(int=index))] = dict(binding_id=str(index % 10) * 60, policy_hash=OLD,
            profile='interactive-native-qualification-' + str(cap // 1024), cap_mib=cap,
            enrollment_uid=str(uuid.UUID(int=index + 10)), enrollment_sha256='sha256:' + '1' * 64,
            completion_kind='cleanup', completion_uid=str(uuid.UUID(int=index + 20)),
            completion_sha256='sha256:' + '2' * 64, ledger_uid=str(uuid.UUID(int=70)),
            journal_sha256='sha256:' + '3' * 64, configuration_authority=copy.deepcopy(reference))
    current = copy.deepcopy(old)
    current.update(policy_hash='sha256:' + 'a' * 64, workspaces=copy.deepcopy(PAIR), terminal_history=history)
    people = [str(uuid.UUID(int=9001)), str(uuid.UUID(int=9002))]
    contract = dict(version=1, policy_hash=current['policy_hash'], workspaces=copy.deepcopy(PAIR),
        terminal_history_sha256=baseline.canonical_sha256(history), operator_people=people,
        operator_members={key: [people[i]] for i, key in enumerate(PAIR)})
    return current, cm, reference, history[str(uuid.UUID(int=30))], contract


def generator():
    spec = importlib.util.spec_from_file_location('node_successor_generator', HERE / 'node_successor.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def successor(contract):
    # Before implementation this executes the actual released validator and
    # produces the meaningful prospective-pair RED rather than a missing import.
    if not (HERE / 'node_successor.py').exists():
        return baseline
    raw = json.dumps(contract, sort_keys=True).encode()
    source = generator().successor_source(BASE, raw, hashlib.sha256(raw).hexdigest())
    return loaded(source, 'prospective_node_successor_test')


def test_actual_node8c_reproduces_prospective_pair_history_blocker():
    config, cm, ref, entry, _ = fixture()
    baseline.validate_config(config)
    with pytest.raises(ValueError, match='Original enabled'):
        baseline.validate_historical_configuration(cm, ref, config, entry)


def test_successor_accepts_only_pinned_pair_retained_original_history():
    config, cm, ref, entry, contract = fixture()
    candidate = successor(contract)
    candidate.validate_config(config)
    assert candidate.validate_historical_configuration(cm, ref, config, entry)['policy_hash'] == OLD


def returned_fixture():
    old, _, _, _, contract = fixture()
    cm = dict(apiVersion='v1', kind='ConfigMap', immutable=True,
        metadata=dict(namespace='cps-native-system', name='cps-native-node-qualification-returned-pair',
                      uid=str(uuid.UUID(int=100))),
        data={'config.json': baseline.canonical_json(old)})
    reference = {k: cm['metadata'][k] for k in ('namespace', 'name', 'uid')}
    reference.update(data_sha256=baseline.canonical_sha256(cm['data']), policy_hash=old['policy_hash'])
    config = copy.deepcopy(old)
    config.update(mode='qualified-group', policy_hash=D48, workspaces={
        'cps:native-group-b': {'profile': 'interactive-shared-5', 'cap_mib': 5120},
        'cit:native-group-a': {'profile': 'interactive-shared-10', 'cap_mib': 10240}})
    config['pool']['memory_budget_mib'] = 15360
    for index, original in enumerate(old['terminal_history'].values(), 101):
        entry = copy.deepcopy(original)
        entry.update(policy_hash=old['policy_hash'], configuration_authority=reference)
        config['terminal_history'][str(uuid.UUID(int=index))] = entry
    return config, cm, reference, config['terminal_history'][str(uuid.UUID(int=101))], contract


@pytest.mark.parametrize('cap', [5120, 20480])
def test_successor_returns_to_d48_with_exact_root_pair_retained_as_terminal_history(cap):
    config, cm, ref, entry, contract = returned_fixture()
    entry = next(e for e in config['terminal_history'].values()
                 if e['policy_hash'] == contract['policy_hash'] and e['cap_mib'] == cap)
    candidate = successor(contract)
    candidate.validate_config(config)
    restored = candidate.validate_historical_configuration(cm, ref, config, entry)
    assert restored['policy_hash'] == 'sha256:' + 'a' * 64
    assert restored['workspaces'] == PAIR


@pytest.mark.parametrize('fault', ['policy', 'history', 'workspace', 'cap', 'budget', 'maximum',
                                  'free', 'headroom', 'epoch', 'reference', 'mutable', 'members', 'image'])
def test_returned_pair_history_drift_is_denied(fault):
    config, cm, ref, entry, contract = returned_fixture()
    candidate = successor(contract)
    old = json.loads(cm['data']['config.json'])
    if fault == 'policy':
        old['policy_hash'] = 'sha256:' + 'b' * 64
        ref['policy_hash'] = entry['policy_hash'] = old['policy_hash']
    elif fault == 'history': old['terminal_history'].pop(next(iter(old['terminal_history'])))
    elif fault == 'workspace': old['workspaces']['cps:operator-qualification-531-other-five'] = old['workspaces'].pop(next(iter(PAIR)))
    elif fault == 'cap':
        old['workspaces'][list(PAIR)[1]] = {'profile': 'interactive-native-qualification-10', 'cap_mib': 10240}
    elif fault in ('budget', 'maximum', 'free', 'headroom'):
        key, value = {'budget': ('memory_budget_mib', 24576), 'maximum': ('max_workspaces', 1),
                      'free': ('free_memory_mib', 26623), 'headroom': ('headroom_mib', 2048)}[fault]
        old['pool'][key] = value
    elif fault == 'epoch': old['pool']['boot_id'] = str(uuid.UUID(int=999))
    elif fault == 'reference': cm['metadata']['uid'] = str(uuid.UUID(int=999))
    elif fault == 'mutable': cm['immutable'] = False
    elif fault == 'members': old['operator_members'] = copy.deepcopy(contract['operator_members'])
    else: old['workloadImage'] = 'ghcr.io/mul-cps/unreviewed@sha256:' + 'b' * 64
    cm['data']['config.json'] = baseline.canonical_json(old)
    ref['data_sha256'] = baseline.canonical_sha256(cm['data'])
    with pytest.raises(ValueError): candidate.validate_historical_configuration(cm, ref, config, entry)


def test_returned_d48_cannot_authorize_an_active20_in_its15gib_pool():
    config, _, _, _, contract = returned_fixture()
    config['workspaces']['cps:operator-qualification-531-active-twenty'] = {
        'profile': 'interactive-shared-20', 'cap_mib': 20480}
    with pytest.raises(ValueError, match='profile/cap'):
        successor(contract).validate_config(config)


def test_legacy_d48_behavior_and_all_other_function_bytes_are_preserved():
    import ast
    config, cm, ref, entry, contract = fixture()
    config.update(mode='qualified-group', policy_hash=D48, workspaces={
        'cps:native-group-b': {'profile': 'interactive-shared-5', 'cap_mib': 5120},
        'cit:native-group-a': {'profile': 'interactive-shared-10', 'cap_mib': 10240}})
    config['pool']['memory_budget_mib'] = 15360
    candidate = successor(contract)
    assert candidate.validate_historical_configuration(cm, ref, config, entry) == baseline.validate_historical_configuration(cm, ref, config, entry)
    raw = json.dumps(contract, sort_keys=True).encode()
    result = generator().successor_source(BASE, raw, hashlib.sha256(raw).hexdigest())
    def definitions(source):
        text = source.decode() if isinstance(source, bytes) else source
        return {n.name: ''.join(text.splitlines(True)[n.lineno-1:n.end_lineno]) for n in ast.parse(text).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    a, b = definitions(BASE), definitions(result)
    assert a.keys() == b.keys()
    assert {name for name in a if a[name] != b[name]} == {'validate_config', 'validate_historical_configuration', 'read_config'}
    assert b['validate_config'] == a['validate_config'].replace(
        "len(history) <= 64, 'Bounded explicit terminal history required'",
        "len(history) <= 128, 'Bounded explicit terminal history required'", 1)


@pytest.mark.parametrize('fault', ['policy', 'history', 'workspace', 'source', 'free', 'budget', 'maximum', 'headroom', 'epoch', 'reference', 'old-policy', 'recursive'])
def test_pair_or_historical_drift_is_denied(fault):
    config, cm, ref, entry, contract = fixture()
    candidate = successor(contract)
    if fault == 'policy': config['policy_hash'] = 'sha256:' + 'b' * 64
    elif fault == 'history': config['terminal_history'].pop(next(iter(config['terminal_history'])))
    elif fault == 'workspace': config['workspaces']['cps:shared-gpu-lab'] = config['workspaces'].pop(next(iter(PAIR)))
    elif fault == 'source': config['workspaces']['cit:operator-qualification-531-test-five'] = config['workspaces'].pop(next(iter(PAIR)))
    elif fault in ('free', 'budget', 'maximum', 'headroom'):
        key, value = {'free': ('free_memory_mib', 26623), 'budget': ('memory_budget_mib', 15360), 'maximum': ('max_workspaces', 3), 'headroom': ('headroom_mib', 2048)}[fault]
        config['pool'][key] = value
    elif fault == 'epoch': config['pool']['boot_id'] = str(uuid.UUID(int=999))
    elif fault == 'reference': cm['metadata']['uid'] = str(uuid.UUID(int=999))
    else:
        old = json.loads(cm['data']['config.json'])
        if fault == 'old-policy': old['policy_hash'] = D48
        else: old['terminal_history'] = copy.deepcopy(config['terminal_history'])
        cm['data']['config.json'] = baseline.canonical_json(old)
        ref['data_sha256'] = baseline.canonical_sha256(cm['data'])
    with pytest.raises(ValueError): candidate.validate_historical_configuration(cm, ref, config, entry)


@pytest.mark.parametrize('fault', ['same-person', 'student', 'unknown-person', 'extra-field', 'old-policy', 'wrong-profile', 'wrong-history', 'source-bytes', 'raw-pin'])
def test_invalid_independent_contract_or_source_is_denied(fault):
    _, _, _, _, contract = fixture()
    source = BASE
    if fault == 'same-person': contract['operator_members'][list(PAIR)[1]] = contract['operator_members'][list(PAIR)[0]]
    elif fault == 'student': contract['operator_people'][0] = '85de720c-94b0-4bc7-807e-c04512133494'; contract['operator_members'][list(PAIR)[0]] = [contract['operator_people'][0]]
    elif fault == 'unknown-person': contract['operator_members'][list(PAIR)[0]] = [str(uuid.UUID(int=999))]
    elif fault == 'extra-field': contract['activation_ready'] = True
    elif fault == 'old-policy': contract['policy_hash'] = D48
    elif fault == 'wrong-profile': contract['workspaces'][list(PAIR)[1]]['cap_mib'] = 10240
    elif fault == 'wrong-history': contract['terminal_history_sha256'] = 'sha256:' + '0' * 64
    elif fault == 'source-bytes': source += b'\n'
    raw = json.dumps(contract).encode()
    pin = '0' * 64 if fault == 'raw-pin' else hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError): generator().successor_source(source, raw, pin)


def test_default_and_missing_pin_do_not_read_files(monkeypatch, capsys):
    module = generator()
    monkeypatch.setattr(Path, 'read_bytes', lambda *a: pytest.fail('No file read permitted'))
    assert module.main([]) == 0
    assert json.loads(capsys.readouterr().out)['state'] == 'inert'
    with pytest.raises(ValueError, match='independent'):
        module.main(['--emit', '--contract', '/must-not-read'])


@pytest.mark.parametrize('count', [75, 85, 128])
def test_successor_retains_complete_bounded_history_without_changing_frozen_node(count):
    config, _, _, _, contract = fixture()
    entry = next(iter(config['terminal_history'].values()))
    config['terminal_history'] = {str(uuid.UUID(int=1000+i)): copy.deepcopy(entry) for i in range(count)}
    contract['terminal_history_sha256'] = baseline.canonical_sha256(config['terminal_history'])
    before = copy.deepcopy(config)
    with pytest.raises(ValueError, match='Bounded explicit terminal history'):
        baseline.validate_config(config)
    assert successor(contract).validate_config(config) == before
    assert config == before


@pytest.mark.parametrize('fault', ['overflow', 'invalid-record', 'current-policy'])
def test_successor_extended_history_still_denies_invalid_or_unbounded_history(fault):
    config, _, _, _, contract = fixture()
    entry = next(iter(config['terminal_history'].values()))
    config['terminal_history'] = {str(uuid.UUID(int=1000+i)): copy.deepcopy(entry) for i in range(128)}
    if fault == 'overflow': config['terminal_history'][str(uuid.UUID(int=9999))] = copy.deepcopy(entry)
    elif fault == 'invalid-record': next(iter(config['terminal_history'].values()))['completion_sha256'] = 'invalid'
    else: next(iter(config['terminal_history'].values()))['policy_hash'] = config['policy_hash']
    contract['terminal_history_sha256'] = baseline.canonical_sha256(config['terminal_history'])
    with pytest.raises(ValueError): successor(contract).validate_config(config)

@pytest.mark.parametrize('padding,mode,accepted',[(40000,0o400,True),(262145,0o400,False),(0,0o600,False)])
def test_generated_entrypoint_reads_bounded_full_history_configuration(tmp_path,padding,mode,accepted):
 import os
 config,_,_,_,contract=fixture();raw=json.dumps(contract,sort_keys=True,separators=(',',':')).encode();pin=hashlib.sha256(raw).hexdigest()
 bundle=generator().successor_bundle(BASE,(HERE/'epoch8c.py').read_bytes(),raw,pin)
 node=loaded(bundle['node_agent.py'],'full_history_entrypoint_'+str(padding)+'_'+str(mode))
 path=tmp_path/'config.json';path.write_text(' '*padding+json.dumps(config));path.chmod(mode)
 if accepted:assert node.read_config(path,trusted_uid=os.getuid())==config
 else:
  with pytest.raises(ValueError):node.read_config(path,trusted_uid=os.getuid())


def test_larger_reader_bound_does_not_expand_unreviewed_legacy_configurations(tmp_path):
 import os
 import test_gateway_transition as gateway
 _,_,_,_,contract=fixture();raw=json.dumps(contract,sort_keys=True,separators=(',',':')).encode();pin=hashlib.sha256(raw).hexdigest()
 node=loaded(generator().successor_source(BASE,raw,pin),'legacy_large_file_guard')
 config=gateway.fixture()['originals']['node_config']
 path=tmp_path/'legacy.json';path.write_text(' '*40000+json.dumps(config));path.chmod(0o400)
 with pytest.raises(ValueError,match='outside reviewed pair'):node.read_config(path,trusted_uid=os.getuid())

"""Synthetic protected policy epochs over the exact installed Delivery baseline."""
import copy
import hashlib
import json

import pytest

import native_group_approval_delivery as d
import native_group_approval_renderer as r
from cps_compute.native_groups import NativeGroupDeployment
from cps_compute.native_policy_transition import PolicyWorkloadTransition
from cps_compute.policy import Policy
import test_native_policy_transition as core_case
from test_native_policy_transition_config import mounted
from test_native_group_approval_delivery import MemoryAPI
from test_native_group_approval_renderer import actual_documents, readiness_fixture, NOW
from test_native_group_approval_rollover import installed_fixture


def epoch_fixture(tmp_path, monkeypatch):
    fixture = installed_fixture(); initial, prior, old, kwargs, roles = fixture
    # The new protected epoch seed retains actual API UID/data readbacks, not
    # the initial publication's unbound create candidates.
    prior['bootstrap_maps'] = copy.deepcopy(kwargs['previous_bootstrap_maps'])
    monkeypatch.setattr(core_case, 'qualified_fixture', lambda: (initial.f[0], initial.f[1]._config()))
    value = core_case.request()
    value['old']['registry'] = copy.deepcopy(initial.f[2])
    value['new']['registry']['generation'] = initial.f[2]['generation']+1
    value['retired_references'] = copy.deepcopy(r.parse(initial.docs['node']['data']['approval.json'])['history']) + [
        prior['references'][component] for component in r.COMPONENTS]
    value, settings, _, chain = mounted(tmp_path, value)
    authority = PolicyWorkloadTransition.from_operator_config(value,
        expected_sha256=settings['intent_sha256'], current_record=lambda: json.loads(chain.read_text()))
    policy = Policy(value['new']['policy'])
    group = NativeGroupDeployment.from_config(value['new']['registry']['deployment'], policy, transition=authority)
    raw = r.canonical(value['new']['registry']).encode()
    args = {**kwargs, 'policy': policy, 'qualification': group, 'source_raw': raw,
        'source_sha256': 'sha256:'+hashlib.sha256(raw).hexdigest(),
        'trusted_revision': r.canonical_sha256(value['new']['registry'])}
    for key in ('documents', 'previous_publication', 'previous_publication_sha256', 'previous_bootstrap_maps',
                'acknowledgments', 'driver_epoch', 'ttl_seconds'):args.pop(key, None)
    return locals()


def projection(state):
    documents = actual_documents(r.document_intent(**state['args']))
    return r.revision_projection_intent(**state['args'], documents=documents,
        previous_publication=state['prior'], previous_publication_sha256=r.canonical_sha256(state['prior']),
        previous_bootstrap_maps=state['kwargs']['previous_bootstrap_maps'], acknowledgments=state['initial'].acks,
        driver_epoch=state['initial'].epoch, ttl_seconds=30), documents


def test_explicit_epoch_retains_complete_old_history_and_only_replaces_node_template(tmp_path, monkeypatch):
    state = epoch_fixture(tmp_path, monkeypatch); before = copy.deepcopy(state['kwargs']['previous_bootstrap_maps'])
    result, documents = projection(state)
    assert r.parse(documents['node']['data']['approval.json'])['history'] == state['value']['retired_references']
    assert state['kwargs']['previous_bootstrap_maps'] == before
    assert result['bootstrap_maps']['node']['metadata']['name'] != before['node']['metadata']['name']
    assert r.parse(result['bootstrap_maps']['node']['data']['template.json']) == state['group']._config()
    for component in r.COMPONENTS:
        if component != 'node':assert result['bootstrap_maps'][component] == before[component]
        spec = copy.deepcopy(state['args']['baselines'][component]['deployment']['spec'])
        for volume in spec['template']['spec']['volumes']:
            if volume['name'] == r.DOC_VOLUME:volume['configMap']['name'] = documents[component]['metadata']['name']
            if volume['name'] == r.REF_VOLUME:volume['configMap']['name'] = result['reference_maps'][component]['metadata']['name']
            if component == 'node' and volume['name'] == r.BOOTSTRAP_VOLUME:
                volume['configMap']['name'] = result['bootstrap_maps']['node']['metadata']['name']
        assert result['expected_deployments'][component]['spec'] == spec
    records = {key:state['old'][key] for key in ('deployments', 'replicasets', 'pods')}
    with pytest.raises(ValueError):
        r.revision_access_intent(projection=result, previous_publication=state['prior'], roles=state['roles'], **records)
    access = r.revision_access_intent(projection=result, previous_publication=state['prior'],
        roles=state['roles'], transition=state['authority'], **records)
    assert len(access['patches']) == 7
    for key, patch in access['patches'].items():
        assert patch[0]['value'] == state['roles'][key]['metadata']['uid']
        assert patch[2]['value'] == state['roles'][key]['rules']


@pytest.mark.parametrize('fault', ['no_authority', 'unknown_prior', 'missing_history', 'wrong_registry',
    'changed_bootstrap_data', 'changed_bootstrap_uid', 'missing_bootstrap_uid', 'changed_fullspec', 'revoked'])
def test_epoch_unknown_mixed_or_changed_prior_custody_is_denied(tmp_path, monkeypatch, fault):
    state = epoch_fixture(tmp_path, monkeypatch)
    if fault == 'no_authority':
        state['args']['qualification'] = state['initial'].f[1]
    elif fault == 'unknown_prior':
        cm = state['args']['baselines']['node']['previous_document']
        value = r.parse(cm['data']['approval.json']); value['policy_hash'] = 'sha256:'+'a'*64
        cm['data']['approval.json'] = r.canonical(value)
    elif fault == 'missing_history':
        state['value']['retired_references'].pop()
        state['chain'].write_text(json.dumps([state['value']]))
    elif fault == 'wrong_registry':
        registry = r.parse(state['args']['source_raw']); registry['generation'] += 1
        state['args'].update(source_raw=r.canonical(registry).encode(), trusted_revision=r.canonical_sha256(registry))
        state['args']['source_sha256'] = 'sha256:'+hashlib.sha256(state['args']['source_raw']).hexdigest()
    elif fault == 'changed_bootstrap_data':state['kwargs']['previous_bootstrap_maps']['node']['data']['template.json'] += ' '
    elif fault == 'changed_bootstrap_uid':state['kwargs']['previous_bootstrap_maps']['node']['metadata']['uid'] = '99999999-1234-4234-8234-123456789abc'
    elif fault == 'missing_bootstrap_uid':state['prior']['bootstrap_maps']['node']['metadata'].pop('uid')
    elif fault == 'changed_fullspec':state['args']['baselines']['gateway']['deployment']['spec']['replicas'] += 1
    else:
        current = {'value': copy.deepcopy(state['value'])}; core_case.advance(current, state='revoked')
        state['chain'].write_text(json.dumps([state['value'], current['value']]))
    with pytest.raises(ValueError):projection(state)


def delivery_fixture(state, tmp_path):
    api = MemoryAPI(state['fixture'])
    config = {'version': 1, 'policy': state['policy'].catalog, 'qualification': state['group']._config(),
        'previous_publication': state['prior'], 'previous_publication_sha256': r.canonical_sha256(state['prior']),
        'baselines': state['args']['baselines'], 'ttlSeconds': 30, 'policyTransition': state['settings']}
    capture = {key:state['args'][key] for key in ('source_sha256', 'trusted_revision')}
    capture.update(version=1, source_raw=state['args']['source_raw'].decode(), captured_at=NOW.isoformat())
    def controller():
        return d.Delivery(config, tmp_path/'delivery', api, lambda:copy.deepcopy(capture), lambda:NOW,
            epoch_reader=lambda:state['initial'].epoch.__dict__)
    return api, capture, controller


def test_delivery_restarts_after_bootstrap_creation_and_waits_for_four_real_validator_acks(tmp_path, monkeypatch):
    state = epoch_fixture(tmp_path, monkeypatch); api, capture, controller = delivery_fixture(state, tmp_path)
    api.crash_at = 9
    with pytest.raises(RuntimeError, match='injected crash'):controller().tick()
    api.crash_at = None
    result = controller().tick(); assert result['phase'] == 'processes' and result['ready'] is False
    journal = r.parse((tmp_path/'delivery/state.json').read_bytes()); publication = journal['transition']['publication']
    old_bootstrap = state['kwargs']['previous_bootstrap_maps']['node']
    assert api.get('ConfigMap', old_bootstrap['metadata']['namespace'], old_bootstrap['metadata']['name']) == old_bootstrap
    api.initial.f = (state['policy'], state['group'], state['value']['new']['registry'],
        state['args']['source_raw'], state['initial'].f[-1])
    api.launch(publication)
    ref = publication['acknowledgment_references']['node']
    ack = api.get('ConfigMap', ref['namespace'], ref['name']); valid_ack = copy.deepcopy(ack)
    value = r.parse(ack['data']['ack.json']); value['policy_hash'] = state['prior']['policy_hash']
    ack['data']['ack.json'] = r.canonical(value); api.put(ack)
    assert controller().tick()['ready'] is False
    api.put(valid_ack)
    assert controller().tick() == {'phase': 'current', 'ready': True, 'revision': publication['revision']}
    with pytest.raises(ValueError):state['authority'].require_runtime(state['policy'].hash)
    before = len(api.mutations)
    assert controller().tick()['ready'] is True and len(api.mutations) == before


@pytest.mark.parametrize('fault', ['unknown_source_head', 'recreated_successor_bootstrap'])
def test_delivery_conflicting_epoch_authority_holds_before_any_further_mutation(tmp_path, monkeypatch, fault):
    state = epoch_fixture(tmp_path, monkeypatch); api, capture, controller = delivery_fixture(state, tmp_path)
    if fault == 'unknown_source_head':
        document = r.parse(capture['source_raw']); document['generation'] += 1
        capture.update(source_raw=r.canonical(document), trusted_revision=r.canonical_sha256(document))
        capture['source_sha256'] = 'sha256:'+hashlib.sha256(capture['source_raw'].encode()).hexdigest()
    else:
        assert controller().tick()['phase'] == 'processes'
        journal = r.parse((tmp_path/'delivery/state.json').read_bytes())
        cm = journal['transition']['bootstrap_targets']['node']; meta = cm['metadata']
        api.objects['ConfigMap', meta['namespace'], meta['name']]['metadata']['uid'] = '99999999-1234-4234-8234-123456789abc'
    before = len(api.mutations)
    with pytest.raises(ValueError):controller().tick()
    assert len(api.mutations) == before


def test_root_precreated_bootstrap_is_reused_without_delivery_create_permission(tmp_path, monkeypatch):
    state = epoch_fixture(tmp_path, monkeypatch); result, _ = projection(state)
    api, _, controller = delivery_fixture(state, tmp_path)
    candidate = result['bootstrap_maps']['node']; api.create(candidate)
    actual = api.get('ConfigMap', candidate['metadata']['namespace'], candidate['metadata']['name'])
    original = api.create
    def admitted_create(obj):
        assert len(obj['data']) == 1, 'Installed Delivery admission permits document/reference creation only'
        original(obj)
    api.create = admitted_create
    assert controller().tick()['phase'] == 'processes'
    journal = r.parse((tmp_path/'delivery/state.json').read_bytes())
    assert journal['transition']['bootstrap_targets']['node'] == actual
    assert sum(name == candidate['metadata']['name'] for _, _, name in api.mutations) == 1


def test_absent_transition_keeps_actual_installed_two_argument_core_factory_compatible(tmp_path, monkeypatch):
    initial, prior, _, kwargs, _ = installed_fixture()
    original = r.NativeGroupDeployment.from_config
    class InstalledLegacyFactory:
        @staticmethod
        def from_config(config, policy):return original(config, policy)
    monkeypatch.setattr(r, 'NativeGroupDeployment', InstalledLegacyFactory)
    config = {'version': 1, 'policy': initial.f[0].catalog, 'qualification': initial.f[1]._config(),
        'previous_publication': prior, 'previous_publication_sha256': r.canonical_sha256(prior),
        'baselines': kwargs['baselines'], 'ttlSeconds': 30}
    controller = d.Delivery(config, tmp_path/'legacy-delivery', None, None, epoch_reader=lambda:initial.epoch.__dict__)
    assert controller.transition is None and controller.qualification.policy_hash == initial.f[0].hash


def test_transition_plan_cannot_emit_consumer_invalid_document_without_retained_baselines(tmp_path, monkeypatch):
    state = epoch_fixture(tmp_path, monkeypatch); args = copy.deepcopy(state['args'])
    for row in args['baselines'].values():row.update(previous_document=None, previous_reference=None)
    with pytest.raises(ValueError):r.document_intent(**args)

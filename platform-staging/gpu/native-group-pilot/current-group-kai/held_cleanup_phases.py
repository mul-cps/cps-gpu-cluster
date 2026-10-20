"""Pure three-phase custody validation; no API, host, SQL or release operations.

Freshness, authenticated Stop, quiescence, backups, protected processes and
fullspec CAS are executor obligations. Independently pin every supplied capture.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path

from cps_compute.native_groups import canonical_sha256


def _base():
    spec = importlib.util.spec_from_file_location('held_phase_base', Path(__file__).with_name('held_cleanup_maintenance.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pinned(value, expected):
    base = _base()
    base.require(canonical_sha256(value) == expected, 'Independent exact phase capture pin required')
    return base


def validate_pre_upgrade(held_ledger, packet, observation, *, expected_sha256):
    """Require fresh observations to equal the reviewed original held snapshot."""
    base = _pinned(observation, expected_sha256)
    base.require(observation == packet['observation'], 'Original prepared maintenance snapshot changed')
    summary = base.validate(held_ledger, packet)
    return {**summary, 'phase': 'pre-upgrade'}


def validate_cleanup_published(held_ledger, packet, current, *, expected_sha256):
    """Accept only the typed terminal journal and its actual immutable receipt."""
    from cps_compute.native_gpu_controller import CapRecord, prepared_offline_provenance, validate_prepared_offline_inventory
    from cps_compute.native_gpu_control import KubernetesNativeAuthorityBackend, validate_cleanup_record
    base = _pinned(current, expected_sha256)
    base.closed(current, {'observation', 'cleanup_configmap'}, 'Closed cleanup-published capture required')
    summary = base.validate(held_ledger, packet)
    observed = current['observation']
    original_observation = packet['observation']
    original = CapRecord.from_dict(base.parse(original_observation['journal_raw']))
    terminal = CapRecord.from_dict(base.parse(observed['journal_raw']))
    base.require(terminal.state == 'prepared-offline-unlimited' and terminal.prepared_offline is not None,
        'Actual distinct prepared cleanup journal required')
    reconstructed = replace(terminal, state='prepared', prepared_offline=None)
    base.require(reconstructed == original, 'Terminal cleanup changed original prepared custody')
    canonical = json.dumps(terminal.to_dict(), sort_keys=True, separators=(',', ':'), allow_nan=False)
    base.require(observed['journal_raw'] == canonical + '\n', 'Exact canonical terminal journal bytes required')
    before = deepcopy(observed)
    before['journal_raw'] = original_observation['journal_raw']
    validate_pre_upgrade(held_ledger, packet, before, expected_sha256=canonical_sha256(original_observation))
    fresh_proof = validate_prepared_offline_inventory(observed['inventory'], terminal.identity)
    base.require(terminal.prepared_offline == fresh_proof, 'Terminal cleanup differs from complete observed inventory')
    enrollment = observed['enrollment']; body = base.envelope(enrollment)['enrollment']
    binding = summary['held_binding_id']; cm = current['cleanup_configmap']
    backend = KubernetesNativeAuthorityBackend(None, enrollment['metadata']['namespace'])
    receipt = backend._immutable_document(cm, 'receipt.json', 'cps-native-cleanup-' + binding[:40], binding)
    base.require(not cm['metadata'].get('ownerReferences'), 'Cleanup receipt cannot have mutable owner custody')
    expected = {'version': 1, 'binding_id': binding, 'attempt': body['attempt'],
        'intent': body['intent'], 'cleanup_confirmed': True}
    validate_cleanup_record(receipt, expected)
    provenance = prepared_offline_provenance(terminal, enrollment['metadata']['uid'], canonical_sha256(body))
    base.require(receipt == {**expected, 'prepared_offline': provenance}, 'Exact original enrollment/journal cleanup provenance required')
    base.require(provenance['original_journal_sha256'] == summary['journal_raw_sha256'],
        'Cleanup proof does not retain original raw prepared journal hash')
    return {**summary, 'phase': 'cleanup-published-held',
        'terminal_journal_raw_sha256': 'sha256:' + hashlib.sha256(observed['journal_raw'].encode()).hexdigest(),
        'cleanup_configmap_sha256': canonical_sha256(cm), 'cleanup_uid': cm['metadata']['uid']}


def validate_released_successor(held_ledger, packet, prior_cleanup, current, *, expected_prior_sha256, expected_sha256):
    """Observe only canonical release effects after the executor's normal Stop.

    This function does not authenticate or invoke Stop and cannot authorize a
    release. The executor must pin its actual authenticated request/response.
    """
    summary = validate_cleanup_published(held_ledger, packet, prior_cleanup, expected_sha256=expected_prior_sha256)
    base = _pinned(current, expected_sha256)
    base.closed(current, {'ledger', 'observation', 'cleanup_configmap'}, 'Closed released-successor capture required')
    base.require(current['cleanup_configmap'] == prior_cleanup['cleanup_configmap'], 'Original cleanup receipt identity changed')
    ledger = current['ledger']; original_rows = base._rows(held_ledger); rows = base._rows(ledger)
    base.require(all(ledger['metadata'][k] == held_ledger['metadata'][k] for k in ('namespace', 'name', 'uid')),
        'Released successor changed ledger ownership')
    expected_rows = deepcopy(original_rows)
    expected_rows[summary['held_binding_id']]['state'] = 'released'
    base.require(rows == expected_rows, 'Only the selected canonical releasing-to-released successor is permitted')
    expected_observation = deepcopy(prior_cleanup['observation'])
    expected_observation['sql'] = {'reservation': [], 'reservation_binding': []}
    for row in expected_observation['workspaces']['cps']:
        if row['id'] == 'shared-gpu-lab': row['state'] = 'stopped'
    base.require(current['observation'] == expected_observation,
        'Released successor must preserve physical/enrollment/journal facts and only clear held SQL/stop target workspace')
    return {**summary, 'phase': 'released-successor-observed', 'release_authorized': False, 'ledger_unchanged': False,
        'released_ledger_sha256': canonical_sha256(ledger), 'sql_empty': True, 'target_stopped': True}

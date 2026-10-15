#!/usr/bin/env python3
"""Prepare additive historical pins from actual terminal custody, with no transport."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import node_agent as agent

OLD_POLICY = 'sha256:4f1dff1a92aba5cd7376dfb897612b7e6f2e6f15a09515dbdf29efa4c522359d'
CURRENT_POLICY = 'sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'
SCOPES = {'cps:native-group-b': {'profile': 'interactive-shared-5', 'cap_mib': 5120},
          'cit:native-group-a': {'profile': 'interactive-shared-10', 'cap_mib': 10240}}


def derive(config, enrollments, cleanups, ledger, journals, models):
    agent.validate_config(config)
    agent.require(config['policy_hash'] == CURRENT_POLICY, 'Exact new CPU-only policy required')
    state = agent.abort_ledger(ledger, config['authority_namespace'])
    agent.require(all(isinstance(row, dict) and row.get('state') == 'released'
        for row in state['allocations'].values()), 'All existing native allocations must be released')
    existing = config.get('terminal_history', {})
    missing = {row['intent']['pod_uid'] for row in state['allocations'].values()
        if isinstance(row.get('intent'), dict) and row['intent']['pod_uid'] not in existing}
    agent.require(isinstance(enrollments, list) and isinstance(cleanups, list) and isinstance(journals, dict),
        'Captured immutable enrollment/cleanup and complete journal objects required')
    completions = {cm.get('metadata', {}).get('name'): cm for cm in cleanups}
    agent.require(len(completions) == len(cleanups), 'Distinct actual completion objects required')
    result = copy.deepcopy(config)
    result.setdefault('terminal_history', {})
    added = set()
    for cm in enrollments:
        body = agent.parse(cm.get('data', {}).get('enrollment.json', '{}'))
        uid = body.get('intent', {}).get('pod_uid')
        if uid in existing:
            continue
        key = str(body.get('source')) + ':' + str(body.get('workspace'))
        agent.require(uid not in added and uid in missing and key in SCOPES
            and body.get('policy_hash') == OLD_POLICY and body.get('profile') == SCOPES[key]['profile']
            and body.get('cap_mib') == SCOPES[key]['cap_mib']
            and config['workspaces'].get(key) == SCOPES[key],
            'Only exact released prior-policy CPS5/CIT10 lifetimes may become historical')
        old = {k: copy.deepcopy(config[k]) for k in ('version', 'enabled', 'authority_namespace', 'pool')}
        old.update(policy_hash=OLD_POLICY, workspaces={key: copy.deepcopy(SCOPES[key])})
        if config['version'] == 2: old['mode'] = 'qualified-group'
        else: old['workspaces'][key].pop('cap_mib')
        envelope = agent.validate_enrollment(cm, old, models)
        row = state['allocations'].get(body['binding_id'])
        agent.require(isinstance(row, dict) and row.get('state') == 'released'
            and all(row.get(k) == v for k, v in body.items()), 'Exact original full released enrollment required')
        raw_record = journals.get(uid)
        agent.require(isinstance(raw_record, dict), 'Complete original terminal journal required')
        record = models.CapRecord.from_dict(raw_record)
        agent.require(record.to_dict() == raw_record and record.state == 'retired-inert-cap'
            and record.intent.to_dict() == body['intent'], 'Exact original finite terminal lifetime required')
        agent.validate_pool_epoch(config, record.identity.epoch)
        completion = completions.get('cps-native-cleanup-' + body['binding_id'][:40])
        agent.require(isinstance(completion, dict) and not completion.get('metadata', {}).get('ownerReferences'),
            'Independent original immutable completion required')
        agent.validate_cleanup(completion, agent.cleanup_object(envelope, record))
        entry = {'binding_id': body['binding_id'], 'policy_hash': body['policy_hash'], 'profile': body['profile'],
            'enrollment_uid': envelope['configmap_uid'], 'enrollment_sha256': agent.canonical_sha256(body),
            'completion_kind': 'cleanup', 'completion_uid': completion['metadata']['uid'],
            'completion_sha256': agent.canonical_sha256(agent.parse(completion['data']['receipt.json'])),
            'ledger_uid': ledger['metadata']['uid'], 'journal_sha256': agent.canonical_sha256(raw_record)}
        if config['version'] == 2: entry['cap_mib'] = body['cap_mib']
        result['terminal_history'][uid] = entry
        added.add(uid)
    agent.require(added == missing, 'Every missing released enrolled lifetime requires its original custody')
    agent.validate_config(result)
    agent.require(len((agent.canonical_json(result) + '\n').encode()) <= 32768, 'Bounded node configuration required')
    return result


def from_capture(capture, models):
    agent.closed(capture, {'current_node_config', 'historical_entries_preserved', 'late', 'ledger', 'protected'},
        'Exact additive custody capture required')
    config, rows, protected = capture['current_node_config'], capture['late'], capture['protected']
    agent.require(capture['historical_entries_preserved'] == len(config.get('terminal_history', {}))
        and isinstance(rows, list) and 1 <= len(rows) <= 8, 'Complete bounded new historical capture required')
    agent.closed(protected, {'records', 'caps'}, 'Complete protected record and physical cap capture required')
    journals, enrollments, cleanups = {}, [], []
    for row in rows:
        agent.closed(row, {'pod_uid', 'enrollment', 'completion', 'pod_absent'}, 'Exact old lifetime capture required')
        uid = row['pod_uid']; body = agent.parse(row['enrollment']['data']['enrollment.json'])
        agent.require(row['pod_absent'] is True and uid == body['intent']['pod_uid'] and uid not in journals,
            'Actual original Pod UID absence and distinct lifetime required')
        saved = protected['records'].get(uid)
        agent.closed(saved, {'enrollments', 'intents', 'journal'}, 'Complete original protected lifetime mirrors required')
        envelope = {'authority_namespace': row['enrollment']['metadata']['namespace'],
            'configmap_name': row['enrollment']['metadata']['name'],
            'configmap_uid': row['enrollment']['metadata']['uid'], 'enrollment': body}
        agent.require(saved['enrollments'] == envelope and saved['intents'] == body['intent'],
            'Original protected enrollment and frozen intent must agree')
        record = models.CapRecord.from_dict(saved['journal'])
        caps = protected['caps']
        expected = record.retirement.to_dict()['entry'] if record.retirement is not None else None
        agent.require(caps.get('gpu_uuid') == config['pool']['gpu_uuid']
            and record.retirement is not None and caps.get('gpu_id') == record.retirement.gpu_id
            and isinstance(caps.get('entries'), list) and expected in caps['entries']
            and expected.get('offline') is True and expected.get('pinned') is True and expected.get('used') == 0,
            'Actual original offline pinned zero-use finite cap required')
        journals[uid] = saved['journal']; enrollments.append(row['enrollment']); cleanups.append(row['completion'])
    agent.require(set(protected['records']) == set(journals), 'No omitted or unrelated protected lifetime records')
    return derive(config, enrollments, cleanups, capture['ledger'], journals, models)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--capture-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if not args.prepare:
        print(json.dumps({'prepared': False, 'activationPerformed': False})); return
    if args.capture is None or args.capture_sha256 is None or args.output is None:
        parser.error('--prepare requires --capture, --capture-sha256 and --output')
    raw = args.capture.read_bytes()
    agent.require(hashlib.sha256(raw).hexdigest() == args.capture_sha256, 'Actual capture raw checksum changed')
    capture = agent.parse(raw)
    result = from_capture(capture, agent.load_models_from_snapshot())
    agent.require(not args.output.exists() and not args.output.is_symlink(), 'New private output directory required')
    args.output.mkdir(mode=0o700)
    path = args.output / 'node-config.json'
    path.write_text(agent.canonical_json(result) + '\n'); path.chmod(0o600)
    before = capture['current_node_config']['terminal_history']
    receipt = {'prepared': True, 'activationPerformed': False, 'capture_sha256': args.capture_sha256,
        'target_policy_hash': result['policy_hash'], 'node_config_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'historical_entries_preserved': len(before), 'historical_entries_added': len(result['terminal_history']) - len(before),
        'host_revalidation_required': True, 'hardware_test_performed': False,
        'node_source_modified': False, 'ledger_or_journal_write_performed': False}
    path = args.output / 'preparation-receipt.json'
    path.write_text(agent.canonical_json(receipt) + '\n'); path.chmod(0o600)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()

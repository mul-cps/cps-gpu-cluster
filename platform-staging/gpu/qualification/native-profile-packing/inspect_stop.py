#!/usr/bin/env python3
"""Offline inspection of actual immutable Stop/physical cleanup witnesses; no release operations."""
import argparse
import hashlib
import json
from pathlib import Path
import prepare_harness as p

def immutable(cm, key, binding_id):
    meta = cm.get('metadata', {})
    prefix = 'cps-native-enrollment-' if key == 'enrollment.json' else 'cps-native-cleanup-'
    p.require(cm.get('apiVersion') == 'v1' and cm.get('kind') == 'ConfigMap'
        and cm.get('immutable') is True and set(cm.get('data', {})) == {key} and not cm.get('binaryData')
        and meta.get('namespace') == 'cps-native-system' and meta.get('name') == prefix + binding_id[:40]
        and meta.get('labels') == {'cps.compute/native-binding': binding_id} and not meta.get('deletionTimestamp'),
        'Actual immutable authority ConfigMap required')
    p.valid_uuid(meta.get('uid'))
    return p.parse(cm['data'][key])

def validate(binding, before, ledger, pods, physical, enrollments, cleanups, journals=None):
    from cps_compute.native_gpu_control import validate_cleanup_record
    from cps_compute.native_gpu_controller import CapRecord
    p.validate_binding(binding)
    p.require(isinstance(journals, list) and len(journals) == 2
        and all(type(raw) is bytes for raw in journals), 'Exact pair of raw full journal records required')
    p.require(ledger.get('apiVersion') == 'v1' and ledger.get('kind') == 'ConfigMap'
        and ledger.get('metadata', {}).get('namespace') == 'cps-native-system'
        and ledger['metadata'].get('name') == 'cps-native-gpu-allocations', 'Actual central ledger required')
    p.valid_uuid(ledger['metadata'].get('uid'))
    state = p.parse(ledger['data']['state.json'])
    p.require(type(state.get('version')) is int and state['version'] in (1, 2)
        and isinstance(state.get('allocations'), dict), 'Typed complete allocation ledger required')
    p.require(pods.get('apiVersion') == 'v1' and pods.get('kind') == 'PodList'
        and isinstance(pods.get('items'), list) and isinstance(pods.get('metadata', {}), dict)
        and not pods.get('metadata', {}).get('continue')
        and pods.get('metadata', {}).get('remainingItemCount', 0) == 0,
        'Actual complete unpaginated post-Stop Pod list required')
    observed_uids = {x.get('metadata', {}).get('uid') for x in pods['items']}
    pool = binding['pool']
    p.require(physical.get('kind') == 'native-group-host-observation'
        and all(physical.get(k) == pool[k] for k in ('node', 'node_uid', 'boot_id', 'gpu_uuid', 'driver_generation'))
        and physical.get('targets') == [] and isinstance(physical.get('retired_caps'), list),
        'Actual healthy post-Stop complete retirement inventory required')
    prior_retired = before['host'].get('retired_caps')
    p.require(isinstance(prior_retired, list), 'Original complete retirement observations required')
    prior = {r['pod_uid']: r for r in prior_retired}
    actual = {r['pod_uid']: r for r in physical['retired_caps']}
    controlled = {t['pod_uid'] for t in binding['targets']}
    p.require(len(prior) == len(prior_retired) and len(actual) == len(physical['retired_caps'])
        and not set(prior) & controlled and set(actual) == set(prior) | controlled
        and all(actual[uid] == row for uid, row in prior.items()),
        'All prior retirement observations must be preserved plus exactly two new lifetimes')
    results = []
    for index, target in enumerate(binding['targets']):
        uid = target['pod_uid']
        p.require(uid not in observed_uids, 'Original Pod UID must be physically absent')
        natives = [t for t in before['host']['targets'] if t.get('pod_uid') == uid]
        p.require(len(natives) == 1, 'Exact original sealed lifetime required'); native = natives[0]
        intent = native['intent']
        p.require(all(intent.get(k) == target[k] for k in ('namespace', 'name', 'pod_uid', 'spec_sha256', 'cap_mib'))
            and intent.get('policy_hash') == binding['policy_hash'] and all(intent.get(k) == pool[k]
                for k in ('node', 'node_uid', 'gpu_uuid')), 'Exact original controlled intent required')
        enrollment_cm = enrollments[index]
        enrollment = p.parse(enrollment_cm['data']['enrollment.json']); binding_id = enrollment.get('binding_id')
        p.require(isinstance(binding_id, str) and p.re.fullmatch('[a-f0-9]{60}', binding_id), 'Exact binding ID required')
        p.require(immutable(enrollment_cm, 'enrollment.json', binding_id) == enrollment
            and enrollment.get('version') == 1 and type(enrollment['version']) is int
            and enrollment.get('source') == enrollment.get('actor') == target['source']
            and enrollment.get('workspace') == target['workspace'] and enrollment.get('profile') == target['profile']
            and enrollment.get('policy_hash') == binding['policy_hash'] and enrollment.get('intent') == intent
            and all(enrollment.get(k) == target[k] for k in ('namespace', 'name'))
            and isinstance(enrollment.get('attempt'), str) and enrollment['attempt'], 'Exact immutable Source enrollment required')
        row = state['allocations'].get(binding_id)
        p.require(isinstance(row, dict) and row.get('state') == 'released'
            and all(row.get(k) == v for k, v in enrollment.items()), 'Exact full released ledger allocation required')
        cleanup = immutable(cleanups[index], 'receipt.json', binding_id)
        expected = {'version': 1, 'binding_id': binding_id, 'attempt': enrollment['attempt'],
                    'intent': intent, 'cleanup_confirmed': True}
        validate_cleanup_record(cleanup, expected)
        retirement = cleanup.get('retirement')
        p.require(isinstance(retirement, dict) and retirement['enrollment_uid'] == enrollment_cm['metadata']['uid']
            and retirement['enrollment_sha256'] == 'sha256:' + p.sha(p.canonical(enrollment).encode()),
            'Cleanup must bind original immutable enrollment')
        retired = [r for r in physical['retired_caps'] if r.get('pod_uid') == uid]
        p.require(len(retired) == 1, 'Exact original physical retirement required'); retired = retired[0]
        proof = retirement['proof']; identity = native['identity']; inv = retired['inventory_row']
        raw_journal = journals[index]; journal = p.parse(raw_journal)
        record = CapRecord.from_dict(journal)
        raw_sha = 'sha256:' + p.sha(raw_journal)
        canonical_sha = 'sha256:' + p.sha(p.canonical(journal).encode())
        p.require(record.to_dict() == journal and journal['state'] == 'retired-inert-cap'
            and journal['seal_id'] == native['seal_id'] and journal['intent'] == intent
            and journal['identity'] == identity and journal['retirement'] == proof
            and journal['readback'] == {'soft': target['cap_mib'] * p.MIB, 'hard': target['cap_mib'] * p.MIB}
            and raw_sha == retired['journal_sha256'] and canonical_sha == retirement['journal_sha256'],
            'Full original terminal journal must match raw physical and canonical cleanup pins')
        p.require(retired['identity'] == identity == proof['identity'] and retired['retirement'] == proof
            and proof['entry'] == inv and proof['epoch'] == {k: pool[k] for k in ('node_uid', 'boot_id', 'gpu_uuid', 'driver_generation')}
            and inv.get('offline') is True and inv.get('pinned') is True and inv.get('default_hierarchy') is True
            and type(inv.get('used')) is int and inv['used'] == 0 and inv['soft'] == inv['hard'] == target['cap_mib'] * p.MIB
            and inv['inode'] == inv['cgroup_id'] == inv['kernfs_id'] == identity['cgroup_inode'],
            'Original finite cap must be physically inert and zero charge')
        results.append({'source': target['source'], 'workspace': target['workspace'], 'pod_uid': uid,
            'cap_mib': target['cap_mib'], 'binding_id': binding_id, 'attempt': enrollment['attempt'],
            'journal_raw_sha256': raw_sha, 'journal_canonical_sha256': canonical_sha})
    p.require(len({r['binding_id'] for r in results}) == 2 and len({r['attempt'] for r in results}) == 2,
              'Distinct exact terminal lifetimes required')
    return {'state': 'stop-witnesses-consistent-awaiting-Root-review', 'api_calls': False, 'gpu_calls': False,
        'hardware_qualification': False, 'production_qualified': False, 'terminal_lifetimes': results,
        'orphan_scope': 'original Pod UID/cgroup only', 'normal_source_stop_claim': 'Root reviews separately'}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--manifest', type=Path); parser.add_argument('--manifest-sha256'); args = parser.parse_args(argv)
    if not args.inspect:
        print(json.dumps({'state': 'inert', 'api_calls': False, 'gpu_calls': False, 'hardware_qualification': False})); return
    manifest = p.parse(p.read_pinned(args.manifest, args.manifest_sha256, private=True))
    p.require(isinstance(manifest, dict) and set(manifest) == {'binding', 'before', 'ledger', 'pods',
        'physical', 'enrollments', 'cleanups', 'journals'}, 'Closed actual raw witness manifest required')
    def raw(pin):
        p.file_pin(pin); return p.read_pinned(Path(pin['path']), pin['sha256'], private=True)
    def read(pin):
        return p.parse(raw(pin))
    p.require(all(isinstance(manifest[k], list) and len(manifest[k]) == 2
        for k in ('enrollments', 'cleanups', 'journals')), 'Exact pair of authority and full journal records required')
    result = validate(*(read(manifest[k]) for k in ('binding', 'before', 'ledger', 'pods', 'physical')),
        [read(x) for x in manifest['enrollments']], [read(x) for x in manifest['cleanups']],
        [raw(x) for x in manifest['journals']])
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__': main()

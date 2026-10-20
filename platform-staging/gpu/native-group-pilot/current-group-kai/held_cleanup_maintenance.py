"""Pure evidence checks for one reserved, observed-prepared/null-readback cleanup during upgrade.

This is not cleanup/release proof or permission to execute maintenance. Root must
independently pin these observations and reobserve host/API facts at each stage.
"""
from copy import deepcopy
from dataclasses import fields
import hashlib
import json

from cps_compute.native_gpu_controller import CapRecord, CapLimit, DriverEpoch, RetiredCapEntry
from cps_compute.native_groups import canonical_sha256
from cps_compute.native_node.custody import envelope, read_ledger


def require(value, message):
    if not value: raise ValueError(message)


def closed(value, keys, message):
    require(isinstance(value, dict) and set(value) == set(keys), message)


def parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate evidence JSON key')
            result[key] = value
        return result
    require(isinstance(raw, str) and 0 < len(raw.encode()) <= 32768, 'Bounded raw journal required')
    return json.loads(raw, object_pairs_hook=unique)


def _rows(cm):
    class Core:
        def read_namespaced_config_map(self, name, namespace): return deepcopy(cm)
    return read_ledger(Core(), cm['metadata']['namespace'])[1]


def validate(ledger, packet):
    """Return a custody-preserving summary; never mutate inputs or release rows."""
    closed(packet, {'version', 'kind', 'observation', 'review'}, 'Closed held-cleanup packet required')
    require(type(packet['version']) is int and packet['version'] == 1
        and packet['kind'] == 'single-held-prepared-cleanup-maintenance', 'Explicit held-cleanup mode required')
    o = packet['observation']; review = packet['review']
    closed(o, {'baseline_ledger', 'enrollment', 'journal_raw', 'inventory', 'epoch_before', 'epoch_after',
        'original_pod', 'pod_absent', 'cgroup_absent', 'gate_receipt_before', 'gate_receipt_after', 'sql', 'workspaces'}, 'Closed held-cleanup observation required')
    closed(review, {'binding_id', 'ledger_sha256', 'observation_sha256', 'expected_counts'}, 'Closed independent review pins required')
    require(canonical_sha256(ledger) == review['ledger_sha256']
        and canonical_sha256(o) == review['observation_sha256'], 'Independent held-cleanup evidence pins changed')
    counts = review['expected_counts']
    closed(counts, {'released_claims', 'workspaces', 'reservation', 'reservation_binding'}, 'Closed reviewed counts required')
    closed(counts['workspaces'], {'cps', 'cit'}, 'Reviewed workspace counts required')
    require(type(counts['released_claims']) is int and 0 <= counts['released_claims'] <= 4096
        and type(counts['reservation']) is int and 1 <= counts['reservation'] <= 256
        and type(counts['reservation_binding']) is int and counts['reservation_binding'] == 1
        and all(type(v) is int and 1 <= v <= 10000 for v in counts['workspaces'].values()),
        'Bounded exact reviewed counts required')
    rows = _rows(ledger); old = _rows(o['baseline_ledger'])
    require(all(ledger['metadata'][k] == o['baseline_ledger']['metadata'][k] for k in ('namespace', 'name', 'uid')),
        'Original ledger identity changed')
    binding = review['binding_id']
    require(isinstance(binding, str) and len(binding) == 60 and all(c in '0123456789abcdef' for c in binding)
        and len(old) == counts['released_claims'] and binding not in old and set(rows) == set(old) | {binding}
        and all(row.get('state') == 'released' and rows[key] == row for key, row in old.items()),
        'Exactly one held addition and unchanged released predecessors required')
    claim = rows[binding]
    require(claim.get('state') == 'releasing' and claim.get('binding_id') == binding,
        'Exact releasing claim must remain reserved')
    enrolled = envelope(o['enrollment']); body = enrolled['enrollment']
    require(set(claim) == set(body) | {'state', 'group_id', 'ceiling'}
        and body['binding_id'] == binding and all(claim.get(k) == v for k, v in body.items()),
        'Actual immutable enrollment differs from held claim')
    require(body['source'] == 'cps' and body['workspace'] == 'shared-gpu-lab'
        and body['principal'] == 'workspace:cps:shared-gpu-lab' and body['profile'] == 'interactive-shared-5'
        and body['cap_mib'] == 5120, 'Only the reviewed CPS5GiB workspace cleanup may use this mode')
    record = CapRecord.from_dict(parse(o['journal_raw']))
    require(record.state == 'prepared' and record.readback is None and record.retirement is None
        and record.recovery is None and record.intent.to_dict() == body['intent'],
        'Original observed-prepared/null-readback transaction required')
    record.identity.require_intent(record.intent)
    require(DriverEpoch(**o['epoch_before']) == DriverEpoch(**o['epoch_after']) == record.identity.epoch,
        'Exact unchanged original driver epoch required')
    pod = o['original_pod']; meta = pod.get('metadata', {})
    require(pod.get('apiVersion') == 'v1' and pod.get('kind') == 'Pod'
        and (meta.get('namespace'), meta.get('name'), meta.get('uid')) ==
            (record.intent.namespace, record.intent.name, record.intent.pod_uid)
        and pod.get('spec', {}).get('nodeName') == record.intent.node
        and canonical_sha256(pod['spec'])[7:] == record.intent.spec_sha256,
        'Original admitted Pod fullspec/identity changed')
    from cps_compute.native_gpu_runtime import RECEIPTS
    for key in ('gate_receipt_before', 'gate_receipt_after'):
        closed(o[key], {'path', 'absent'}, 'Explicit before/after gate-file observation required')
        require(o[key]['path'] == RECEIPTS + '/' + record.intent.pod_uid + '.json'
            and o[key]['absent'] is True, 'Exact original gate receipt must be absent on both sides')
    require(o['pod_absent'] is True and o['cgroup_absent'] is True, 'Original Pod and cgroup must both be absent')
    inventory = o['inventory']
    closed(inventory, {'version', 'backend', 'gpu_uuid', 'gpu_id', 'entries'}, 'Complete native inventory required')
    require(type(inventory['version']) is int and inventory['version'] == 1
        and inventory['backend'] == 'misc-fallback' and inventory['gpu_uuid'] == record.identity.gpu_uuid
        and type(inventory['gpu_id']) is int and 0 <= inventory['gpu_id'] < 2**32
        and isinstance(inventory['entries'], list) and 1 <= len(inventory['entries']) <= 256,
        'Exact guarded GPU inventory required')
    seen = set(); target = None
    keys = {f.name for f in fields(RetiredCapEntry)}
    for row in inventory['entries']:
        closed(row, keys, 'Closed inventory entry required')
        # Every retained entry must be physically inert, not merely the target.
        entry = RetiredCapEntry(**row)
        require(entry.inode not in seen, 'Duplicate retained inventory identity')
        seen.add(entry.inode)
        if entry.inode == record.identity.cgroup_inode: target = entry
    require(target is not None and CapLimit(target.soft, target.hard).unlimited,
        'Original exact offline pinned zero-charge unlimited entry required')
    sql = o['sql']; closed(sql, {'reservation', 'reservation_binding'}, 'Complete SQL row snapshot required')
    members = body['members']; workspace = 'cps:' + body['workspace']
    require(isinstance(members, list) and all(isinstance(p, str) and p and len(p) <= 256 and not any(c.isspace() for c in p) for p in members)
        and len(members) == len(set(members)) == counts['reservation']
        and isinstance(sql['reservation'], list) and len(sql['reservation']) == counts['reservation'],
        'Exact reviewed held member reservations required')
    for row in sql['reservation']: closed(row, {'person', 'workspace'}, 'Closed reservation row required')
    require({r['person'] for r in sql['reservation']} == set(members)
        and all(r['workspace'] == workspace for r in sql['reservation']), 'Held member reservation ownership changed')
    require(isinstance(sql['reservation_binding'], list) and len(sql['reservation_binding']) == 1,
        'Exactly one held SQL binding required')
    sql_binding = sql['reservation_binding'][0]
    closed(sql_binding, {'workspace', 'attempt', 'binding'}, 'Closed SQL binding row required')
    require(sql_binding['workspace'] == workspace and sql_binding['attempt'] == body['attempt'],
        'Held SQL binding attempt changed')
    payload = parse(sql_binding['binding'])
    expected = {k: claim[k] for k in ('policy_hash', 'principal', 'profile', 'ceiling')}
    if 'approval_ref' in claim: expected['approval_ref'] = claim['approval_ref']
    require(payload == expected, 'Held SQL binding payload changed')
    closed(o['workspaces'], {'cps', 'cit'}, 'Both complete workspace inventories required')
    stopped_target = 0
    for source, workspaces in o['workspaces'].items():
        require(isinstance(workspaces, list) and len(workspaces) == counts['workspaces'][source],
            'Exact reviewed CPS/CIT workspace inventory sizes required')
        seen_ids = set()
        for row in workspaces:
            closed(row, {'id', 'state', 'hub_user', 'hub_server', 'profile'}, 'Closed workspace row required')
            require(row['id'] not in seen_ids, 'Duplicate workspace row')
            seen_ids.add(row['id'])
            if source == body['source'] and row['id'] == body['workspace']:
                stopped_target += 1
                require(row['state'] == 'stopping' and row['profile'] == body['profile']
                    and record.intent.name == 'jupyter-' + row['hub_user'] + '--' + row['hub_server'],
                    'Held workspace stopping/server identity changed')
            else: require(row['state'] == 'stopped', 'Another workspace is not stopped')
    require(stopped_target == 1, 'Exactly one original stopping workspace required')
    return {'held_binding_id': binding, 'epoch': deepcopy(o['epoch_before']),
        'policy_hash': record.intent.policy_hash, 'node': record.intent.node, 'namespace': record.intent.namespace,
        'authority_namespace': enrolled['authority_namespace'], 'claim_sha256': canonical_sha256(claim),
        'enrollment_sha256': canonical_sha256(o['enrollment']),
        'journal_raw_sha256': 'sha256:' + hashlib.sha256(o['journal_raw'].encode()).hexdigest(),
        'journal_sha256': canonical_sha256(record.to_dict()), 'inventory_sha256': canonical_sha256(inventory),
        'pod_spec_sha256': 'sha256:' + record.intent.spec_sha256,
        'reservation_counts': {'reservation': counts['reservation'], 'reservation_binding': 1},
        'ledger_unchanged': True, 'release_authorized': False}

"""Pure historical exception reader; never enrollment, recovery or Stop authority.

Only the one captured CPS transaction can carry recovery. Every new lifetime
continues to require normal finite retirement. CLI consumers pin actual files.
"""
import hashlib
import json
from pathlib import Path
import re
import uuid

MODEL_SHA = '630d43cc115b5bddf3e5d110a25cc891e0941953bbabd833f0a77a3773ad7880'
CONTROL_SHA = 'babeb6eea18821a678b06ce6cc4e6d7ad1bafbc3c543b20522af09d5276fb7dc'
POD = '8066366f-6e7e-42ea-83b2-86a58e9c3bad'
BINDING = '16d264e00ee6778319a8961f9da510147c3bebc925e674bf95880689cd25'
ATTEMPT = 'cbdbd6be-c340-4e2b-9a6a-71230258a367'
BASELINE_PIN = '52cb2097c4562d308c77e81aa3c42ff4a961ccbd113f57b065a748ca45b56f17'

def require(ok, message):
    if not ok: raise ValueError(message)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def raw_sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()

def digest(value):
    return raw_sha(canonical(value).encode())

def closed(value, keys):
    require(type(value) is dict and set(value) == set(keys), 'Closed historical authority required')

def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate historical field'); result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: require(False, 'Nonfinite history rejected'))

def uuid_value(value):
    try: return type(value) is str and str(uuid.UUID(value)) == value and uuid.UUID(value).int != 0
    except (ValueError, TypeError, AttributeError): return False

def immutable(cm, prefix, key):
    require(type(cm) is dict, 'Actual immutable ConfigMap required')
    meta = cm.get('metadata', {})
    require(cm.get('apiVersion') == 'v1' and cm.get('kind') == 'ConfigMap'
        and cm.get('immutable') is True and cm.get('binaryData') in (None, {})
        and type(cm.get('data')) is dict and set(cm['data']) == {key}
        and meta.get('namespace') == 'cps-native-system'
        and meta.get('name') == prefix + BINDING[:40]
        and meta.get('labels') == {'cps.compute/native-binding': BINDING}
        and uuid_value(meta.get('uid')) and not meta.get('ownerReferences')
        and not meta.get('deletionTimestamp'), 'Exact immutable recovery authority metadata required')
    return parse(cm['data'][key])

def baseline_pins():
    raw = Path(__file__).with_name('recovery-baseline-journal-pins.json').read_bytes()
    require(hashlib.sha256(raw).hexdigest() == BASELINE_PIN, 'Original seventeen journal closure changed')
    return parse(raw)['records']

def validate_history(history, binding, **kwargs):
    try:
        return _validate_history(history, binding, **kwargs)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Incomplete or mistyped historical recovery closure') from exc

def _validate_history(history, binding, *, agent, recovery_codec, models=None,
                     cleanup_validator=None, audit_body=None, baseline=None, allow_current=False):
    if models is None:
        from cps_compute import native_gpu_controller as models
        require(hashlib.sha256(Path(models.__file__).read_bytes()).hexdigest() == MODEL_SHA,
                'Exact reviewed recovery model required')
    if cleanup_validator is None:
        from cps_compute import native_gpu_control as control
        require(hashlib.sha256(Path(control.__file__).read_bytes()).hexdigest() == CONTROL_SHA,
                'Exact reviewed cleanup codec required')
        cleanup_validator, audit_body = control.validate_cleanup_record, control.recovery_audit_body
    baseline = baseline_pins() if baseline is None else baseline
    closed(history, {'version', 'protocol', 'node', 'node_uid', 'boot_id', 'gpu_uuid',
        'driver_generation', 'controller_sha256', 'records', 'recovery'})
    require(type(history['version']) is int and history['version'] == 2
        and history['protocol'] == 'native-packing-terminal-history/v2'
        and history['controller_sha256'] == MODEL_SHA
        and all(history[k] == binding['pool'][k] for k in
                ('node', 'node_uid', 'boot_id', 'gpu_uuid', 'driver_generation')),
        'Exact versioned current-epoch history required')
    require(type(history['records']) is list and 17 <= len(history['records']) <= 32,
            'Complete bounded journal history required')
    finite, cleaned, recovered, seen, inodes = [], [], None, set(), set()
    targets = {row['pod_uid'] for row in binding['targets']}
    for row in history['records']:
        closed(row, {'pod_uid', 'journal_sha256', 'record'})
        uid = row['pod_uid']; require(uuid_value(uid) and uid not in seen,
                                    'Distinct historical UID required')
        seen.add(uid); record = models.CapRecord.from_dict(row['record'])
        require(uid not in targets or (allow_current and record.state == 'retired-inert-cap'),
                'Current target must have normal finite retirement, never recovery')
        require(record.to_dict() == row['record'] and record.intent.pod_uid == uid
            and row['journal_sha256'] == raw_sha((canonical(row['record']) + '\n').encode()),
            'Exact complete protected writer bytes required')
        if uid in baseline and uid != POD:
            require(digest(row['record']) == baseline[uid]['canonical_sha256']
                and row['journal_sha256'] == baseline[uid]['raw_sha256'],
                'Every original finite/cleaned journal must remain unchanged')
        require(record.identity.cgroup_inode not in inodes, 'Distinct original journal inode required')
        inodes.add(record.identity.cgroup_inode)
        if record.state == 'retired-inert-cap':
            require(record.intent.node == history['node'] and record.intent.cap_mib in (5120, 10240)
                and record.identity.epoch == models.DriverEpoch(history['node_uid'], history['boot_id'],
                    history['driver_generation'], history['gpu_uuid']), 'Current healthy finite retirement required')
            finite.append(row)
        elif record.state == 'cleaned':
            require(uid in baseline and baseline[uid]['state'] == 'cleaned', 'No inferred cleaned history')
            cleaned.append(row)
        else:
            require(uid == POD and record.state == 'recovered-cleared-offline-cap' and recovered is None,
                    'Only the exact original CPS exception may be recovered')
            recovered = row
    require(set(baseline) <= seen and recovered is not None and len(cleaned) == 5,
            'All seventeen original journals and one authenticated exception required')
    if allow_current:
        require(targets <= {row['pod_uid'] for row in finite},
                'Both actual new lifetimes must have normal finite retirements')
    closure = history['recovery']
    closed(closure, {'original_raw', 'plan', 'review', 'enrollment', 'audit', 'cleanup', 'marker', 'protected_raw_sha256'})
    closed(closure['protected_raw_sha256'], {'plan', 'review', 'marker'})
    require(all(type(v) is str and re.fullmatch(r'sha256:[a-f0-9]{64}', v)
                for v in closure['protected_raw_sha256'].values()), 'Actual protected durable raw pins required')
    plan, review = closure['plan'], closure['review']
    terminal = models.CapRecord.from_dict(recovered['record']); proof = terminal.recovery
    require(proof is not None and type(closure['original_raw']) is str
        and raw_sha(closure['original_raw'].encode()) == baseline[POD]['raw_sha256']
        and closure['original_raw'] == canonical(proof.original.to_dict()) + '\n'
        and digest(proof.original.to_dict()) == baseline[POD]['canonical_sha256']
        and proof.original.state == 'cleanup-prepared' and proof.identity.cgroup_inode == 1390814
        and proof.binding_id == BINDING and proof.attempt == ATTEMPT,
        'Exact archived failed finite CPS transaction required')
    require(plan['journal_sha256s'] == {uid: row['canonical_sha256'] for uid, row in baseline.items()}
        and set(plan['physical_pods']) == {uid for uid, row in baseline.items() if row['state'] != 'cleaned'},
        'Recovery plan must preserve all seventeen journals and twelve physical identities')
    recovery_codec.validate_plan(agent, models, plan)
    recovery_codec.validate_review(agent, review, plan, fresh=False)
    require(recovery_codec.make_proof(agent, models, plan, review) == proof,
            'Historical proof differs from the protected approved operation')
    enrollment = immutable(closure['enrollment'], 'cps-native-enrollment-', 'enrollment.json')
    require(closure['enrollment'] == plan['enrollment'] and enrollment['binding_id'] == BINDING
        and enrollment['attempt'] == ATTEMPT and enrollment['intent'] == terminal.intent.to_dict()
        and proof.enrollment_uid == closure['enrollment']['metadata']['uid']
        and proof.enrollment_sha256 == digest(enrollment), 'Original full immutable enrollment changed')
    receipt = immutable(closure['cleanup'], 'cps-native-cleanup-', 'receipt.json')
    expected = {'version': 1, 'binding_id': BINDING, 'attempt': ATTEMPT,
                'intent': enrollment['intent'], 'cleanup_confirmed': True}
    cleanup_validator(receipt, expected)
    require(set(receipt) == set(expected) | {'recovery'} and receipt['recovery']['proof'] == proof.to_dict()
        and receipt['recovery']['journal_sha256'] == digest(terminal.to_dict()),
        'Distinct full terminal cleanup required')
    audit = immutable(closure['audit'], 'cps-native-recovery-', 'recovery.json')
    require(audit == audit_body(receipt) and digest(audit) == receipt['recovery']['audit_sha256']
        and closure['audit']['metadata']['uid'] == receipt['recovery']['audit_uid'],
        'Actual immutable operator audit UID/body/hash required')
    closed(closure['marker'], {'enrollment_uid', 'receipt_uid', 'receipt'})
    require(closure['marker'] == {'enrollment_uid': closure['enrollment']['metadata']['uid'],
        'receipt_uid': closure['cleanup']['metadata']['uid'], 'receipt': receipt},
        'Exact durable published-cleanup marker required')
    return {'finite': finite, 'cleaned': cleaned, 'recovered': recovered,
            'normal_stop_passed': False, 'hardware_qualification': False}

def validate_physical(history, inventory, *, active_inodes=frozenset(), models=None):
    """After validate_history, compare current rows; never freeze the old full map."""
    if models is None:
        from cps_compute import native_gpu_controller as models
    closed(inventory, {'version', 'backend', 'gpu_uuid', 'gpu_id', 'entries'})
    require(type(inventory['version']) is int and inventory['version'] == 1
        and inventory['backend'] == 'misc-fallback' and inventory['gpu_uuid'] == history['gpu_uuid']
        and type(inventory['gpu_id']) is int and 0 <= inventory['gpu_id'] < 2 ** 32
        and type(inventory['entries']) is list and len(inventory['entries']) <= 256,
        'Complete current selected-device inventory required')
    rows = {}; bound = set(active_inodes); count = 0
    for row in inventory['entries']:
        require(type(row) is dict and type(row.get('inode')) is int and row['inode'] not in rows,
                'Unique typed current inventory required')
        rows[row['inode']] = row
    for row in history['records']:
        record = models.CapRecord.from_dict(row['record'])
        if record.state == 'cleaned':
            require(record.identity.cgroup_inode not in rows, 'Historical cleaned row returned')
            continue
        inode = record.identity.cgroup_inode
        require(inode not in bound, 'Historical cap cannot be active'); bound.add(inode); count += 1
        if record.state == 'retired-inert-cap':
            proof = models.validate_retired_inventory(inventory, record.identity, record.limit)
            require(proof.entry == record.retirement.entry and proof.gpu_id == record.retirement.gpu_id,
                    'Historical finite body or inventory changed')
        else:
            require(record.intent.pod_uid == POD and record.recovery is not None
                and rows.get(inode) == record.recovery.to_dict()['entry']
                and inventory['gpu_id'] == record.recovery.gpu_id,
                'Original authenticated cleared row changed')
    require(set(rows) == bound, 'Unbound or missing native inventory entry')
    return count

def observe_history(history, inventory, *, binding, agent, recovery_codec, models,
                    cleanup_validator, audit_body, baseline, read, absent, retired_mount,
                    active_inodes=frozenset(), allow_current=False):
    """Protected host reads supplied by the unchanged Root-only observer transport."""
    checked = validate_history(history, binding, agent=agent, recovery_codec=recovery_codec,
        models=models, cleanup_validator=cleanup_validator, audit_body=audit_body,
        baseline=baseline, allow_current=allow_current)
    validate_physical(history, inventory, active_inodes=active_inodes, models=models)
    closure = history['recovery']; proof = models.CapRecord.from_dict(checked['recovered']['record']).recovery
    root = '/run/cps-native-gpu/'
    durable = {root + 'journal/recovery-originals/' + POD + '.' + proof.operation_id + '.json':
                   (closure['original_raw'], proof.journal_raw_sha256)}
    operation = root + 'operator/cleared-offline-recovery/' + proof.operation_id + '/'
    for name in ('plan', 'review'):
        durable[operation + name + '.json'] = (closure[name], closure['protected_raw_sha256'][name])
    durable[root + 'published-cleanup/' + POD + '.json'] = (closure['marker'], closure['protected_raw_sha256']['marker'])
    for _ in range(2):
        for path, (expected, pin) in durable.items():
            raw = read(path)
            require(raw_sha(raw) == pin and (raw.decode() == expected if type(expected) is str else parse(raw) == expected),
                    'Protected archived operation or durable marker changed')
        for row in history['records']:
            record = models.CapRecord.from_dict(row['record']); identity = record.identity
            raw = read(root + 'journal/' + row['pod_uid'] + '.json')
            require(raw_sha(raw) == row['journal_sha256'] and parse(raw) == row['record'],
                    'All actual protected original journal bodies must remain unchanged')
            retired_mount(identity); absent(identity.cgroup_path)
            absent(root + 'receipts/' + row['pod_uid'] + '.json')
    rows = {row['inode']: row for row in inventory['entries']}
    observed = []
    for row in checked['finite'] + [checked['recovered']]:
        record = models.CapRecord.from_dict(row['record'])
        extension = {'retirement': record.retirement.to_dict()} if record.retirement is not None else {'recovery': record.recovery.to_dict()}
        observed.append({'pod_uid': row['pod_uid'], 'journal_sha256': row['journal_sha256'],
            'identity': record.identity.to_dict(), **extension,
            'inventory_row': rows[record.identity.cgroup_inode]})
    return observed

def validate_observed(history, observed):
    physical = [r for r in history['records'] if r['record']['state'] != 'cleaned']
    require(type(observed) is list and len(observed) == len(physical), 'Exact complete historical observation required')
    actual = {r['pod_uid']: r for r in observed}
    require(len(actual) == len(observed) and set(actual) == {r['pod_uid'] for r in physical},
            'No historical physical lifetime may be dropped')
    for row in physical:
        record = row['record']; kind = 'recovery' if record['state'] == 'recovered-cleared-offline-cap' else 'retirement'
        expected = {'pod_uid': row['pod_uid'], 'journal_sha256': row['journal_sha256'],
            'identity': record['identity'], kind: record[kind], 'inventory_row': record[kind]['entry']}
        require(actual[row['pod_uid']] == expected, 'Exact original physical history changed')

#!/usr/bin/env python3
"""Pure, default-inert source transformation of the exact published Node8c."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

BASE_SHA256 = 'f01b24bc984a153e9995549ef09f73167500f375d79e078a7e7aa9e1171c3664'
EPOCH_SHA256 = '890cebd7c1903a680e4dc836ec6f81f097198c2fed438ade6b2fa62157864bbd'
OLD_POLICIES = {
    'sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0',
    'sha256:39ef15d3b5a76f96d135beb1afcd538775c64301cb51751086b44d68c54f8012',
}
STUDENTS = {'15164372-7ae5-4cfd-8b5d-fd402aa891bd', '85de720c-94b0-4bc7-807e-c04512133494'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def raw_pin(value):
    require(isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value)
            and value != '0' * 64, 'Explicit independent nonzero raw contract SHA256 required')


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'Duplicate contract key')
        result[key] = value
    return result


def people(values):
    require(isinstance(values, list) and 1 <= len(values) <= 8, 'Bounded operator people required')
    require(all(isinstance(v, str) and str(uuid.UUID(v)) == v and uuid.UUID(v).int
                and v not in STUDENTS for v in values), 'Canonical nonstudent operator UUIDs required')
    require(len(set(values)) == len(values), 'Unique operator people required')
    return set(values)


def validate_contract(raw, reviewed_sha256):
    raw_pin(reviewed_sha256)
    require(isinstance(raw, bytes) and len(raw) <= 65536
            and hashlib.sha256(raw).hexdigest() == reviewed_sha256, 'Reviewed raw contract bytes required')
    contract = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Finite JSON required')))
    require(isinstance(contract, dict) and set(contract) == {'version', 'policy_hash', 'workspaces',
        'terminal_history_sha256', 'operator_people', 'operator_members'}, 'Closed Root contract required')
    require(type(contract['version']) is int and contract['version'] == 1, 'Contract version1 required')
    for key in ('policy_hash', 'terminal_history_sha256'):
        value = contract[key]
        require(isinstance(value, str) and re.fullmatch('sha256:[a-f0-9]{64}', value)
                and value != 'sha256:' + '0' * 64, 'Nonzero canonical contract SHA256 required')
    require(contract['policy_hash'] not in OLD_POLICIES, 'Distinct prospective policy required')
    scopes = contract['workspaces']
    require(isinstance(scopes, dict) and len(scopes) == 2, 'Exactly two prospective workspaces required')
    require(all(isinstance(k, str) and re.fullmatch(
        r'cps:operator-qualification-531-[a-z0-9](?:[a-z0-9-]{0,36}[a-z0-9])?', k)
        for k in scopes), 'Dedicated CPS operator qualification scopes required')
    require(all(isinstance(v, dict) and set(v) == {'profile', 'cap_mib'}
                and type(v['cap_mib']) is int for v in scopes.values()), 'Closed profile caps required')
    require(sorted((v['profile'], v['cap_mib']) for v in scopes.values()) == [
        ('interactive-native-qualification-20', 20480), ('interactive-native-qualification-5', 5120)],
        'One qualification5 and one qualification20 required')
    allowed = people(contract['operator_people'])
    members = contract['operator_members']
    require(isinstance(members, dict) and members.keys() == scopes.keys(), 'Exact operator member scopes required')
    left, right = (people(members[k]) for k in scopes)
    require(not left.intersection(right) and left.union(right) == allowed,
            'Disjoint members must exhaust the independent operator allowlist')
    return contract


def successor_source(original, contract_raw, reviewed_raw_sha256):
    contract = validate_contract(contract_raw, reviewed_raw_sha256)
    require(isinstance(original, bytes) and hashlib.sha256(original).hexdigest() == BASE_SHA256,
            'Exact published Node8c source required')
    source = original.decode('utf-8')
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                and n.name == 'validate_historical_configuration')
    before = ''.join(source.splitlines(True)[node.lineno - 1:node.end_lineno])
    marker = '    validate_configuration_reference(reference, config, entry)\n'
    guard = f'''    # Independently reviewed Root contract raw SHA256: {reviewed_raw_sha256}
    # Membership here is provenance only; Source/Gateway enforce captured people.
    prospective_pair = (config.get('version') == 2 and config.get('enabled') is True
        and config.get('mode') == 'operator-qualification'
        and config.get('policy_hash') == {contract['policy_hash']!r}
        and config.get('workspaces') == {contract['workspaces']!r}
        and canonical_sha256(config.get('terminal_history')) == {contract['terminal_history_sha256']!r}
        and isinstance(config.get('pool'), dict)
        and all(type(config['pool'].get(k)) is int for k in
                ('max_workspaces', 'memory_budget_mib', 'headroom_mib', 'free_memory_mib'))
        and config['pool']['max_workspaces'] == 2
        and config['pool']['memory_budget_mib'] == 25600
        and config['pool']['headroom_mib'] == 1024
        and config['pool']['free_memory_mib'] >= 26624)
'''
    after = before.replace(marker, guard + marker, 1)
    legacy = "config['mode'] == 'qualified-group' and old['mode'] == 'operator-qualification'\n            and config['policy_hash'] == 'sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'"
    after = after.replace(legacy, "(prospective_pair or (config['mode'] == 'qualified-group'\n                 and config['policy_hash'] == 'sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'))\n            and old['mode'] == 'operator-qualification'", 1)
    returned_guard = f'''    returned_pair = (config['mode'] == 'qualified-group'
        and config['policy_hash'] == 'sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'
        and old['version'] == 2 and old['enabled'] is True
        and old['mode'] == 'operator-qualification'
        and old['policy_hash'] == {contract['policy_hash']!r}
        and old['workspaces'] == {contract['workspaces']!r}
        and canonical_sha256(old.get('terminal_history')) == {contract['terminal_history_sha256']!r}
        and old['pool']['max_workspaces'] == 2
        and old['pool']['memory_budget_mib'] == 25600
        and old['pool']['headroom_mib'] == 1024
        and old['pool']['free_memory_mib'] >= 26624)
'''
    after = after.replace("and old['policy_hash'] == 'sha256:39ef15d3b5a76f96d135beb1afcd538775c64301cb51751086b44d68c54f8012'",
        "and (returned_pair or old['policy_hash'] == 'sha256:39ef15d3b5a76f96d135beb1afcd538775c64301cb51751086b44d68c54f8012')", 1)
    after = after.replace("and not any('configuration_authority' in e for e in old.get('terminal_history', {}).values())",
        "and (returned_pair or not any('configuration_authority' in e for e in old.get('terminal_history', {}).values()))", 1)
    after = after.replace("and old['workspaces'] == {", "and (returned_pair or old['workspaces'] == {", 1)
    after = after.replace("'cit:native-group-a': {'profile':'interactive-native-qualification-20', 'cap_mib':20480}},",
        "'cit:native-group-a': {'profile':'interactive-native-qualification-20', 'cap_mib':20480}}),", 1)
    old_marker = "    old = validate_config(parse(cm['data']['config.json']))\n"
    after = after.replace(old_marker, old_marker + returned_guard, 1)
    after = after.replace("config['pool']['memory_budget_mib'] == 15360", "config['pool']['memory_budget_mib'] == (25600 if prospective_pair else 15360)", 1)
    after = after.replace("require(config['workspaces'] == {", "require((prospective_pair or config['workspaces'] == {", 1)
    after = after.replace("'cit:native-group-a': {'profile':'interactive-shared-10', 'cap_mib':10240}}", "'cit:native-group-a': {'profile':'interactive-shared-10', 'cap_mib':10240}})", 1)
    require(after != before and source.count(before) == 1, 'Unique exact validator replacement required')
    result = source.replace(before, after, 1)
    # Change only the retained terminal collection bound; all entry validation
    # and all unrelated workspace/member bounds remain byte-for-byte exact.
    history_guard = "len(history) <= 64, 'Bounded explicit terminal history required'"
    require(result.count(history_guard) == 1, 'Unique exact terminal history bound required')
    result = result.replace(history_guard,
        "len(history) <= 128, 'Bounded explicit terminal history required'", 1)
    reader = next(n for n in ast.parse(result).body if isinstance(n, ast.FunctionDef) and n.name == 'read_config')
    reader_before = ''.join(result.splitlines(True)[reader.lineno - 1:reader.end_lineno])
    reader_after = reader_before
    for old, new in [('info.st_size <= 32768', 'info.st_size <= 262144'),
                     ('os.read(fd, 32769)', 'os.read(fd, 262145)'),
                     ("len(raw) <= 32768, 'Oversized node config'", "len(raw) <= 262144, 'Oversized node config'")]:
        require(reader_after.count(old) == 1, 'Unique exact operator file size guard required')
        reader_after = reader_after.replace(old, new, 1)
    original_return = '        return validate_config(parse(raw))'
    require(reader_after.count(original_return) == 1, 'Unique exact operator reader validation required')
    reader_after = reader_after.replace(original_return, f"""        config = validate_config(parse(raw))
        # Full preserved history may exceed the legacy 32 KiB file limit.
        # Only the independently pinned pair receives the larger bound.
        require(len(raw) <= 32768 or (config['mode'] == 'operator-qualification'
            and config['policy_hash'] == {contract['policy_hash']!r}
            and config['workspaces'] == {contract['workspaces']!r}
            and canonical_sha256(config['terminal_history']) == {contract['terminal_history_sha256']!r}),
            'Oversized node config outside reviewed pair')
        return config""", 1)
    require(result.count(reader_before) == 1, 'Unique exact operator configuration reader required')
    result = result.replace(reader_before, reader_after, 1)
    historical = next(n for n in ast.parse(result).body if isinstance(n, ast.FunctionDef)
                      and n.name == 'validate_authority_enrollments')
    historical_before = ''.join(result.splitlines(True)[historical.lineno - 1:historical.end_lineno])
    historical_after = historical_before
    bridge = f'''        def historical_envelope(actual):
            if 'approval_ref' not in body:
                return validate_enrollment(actual, old, models)
            # Historical-only custody bridge. Never admit a new live intent.
            require(config.get('mode') == 'operator-qualification'
                and config['policy_hash'] == {contract['policy_hash']!r}
                and config['workspaces'] == {contract['workspaces']!r}
                and canonical_sha256(history) == {contract['terminal_history_sha256']!r}
                and reference is None and entry['policy_hash'] ==
                'sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'
                and canonical_sha256(body) == entry['enrollment_sha256'],
                'Only Root-pinned completed dynamic history may use approval custody')
            approval = load_source('_historical_approval_revision',
                (HERE / 'native_approval_revision.py').read_bytes(),
                'ddaaf9593dfbc9cba2d4aa3227102895a435e2537346ddd467c4941c0201658d',
                'native_approval_revision.py')
            ref = approval.reference(body['approval_ref'])
            require(ref['namespace'] == config['authority_namespace']
                and ref['policy_hash'] == entry['policy_hash'], 'Historical approval policy/namespace required')
            document_cm = kube.configmap(ref['namespace'], ref['name'])
            # The frozen consumer verifies this entire immutable document against
            # the full-data reference already pinned in the original enrollment.
            template = parse(document_cm['data']['approval.json'])['registry']['deployment']
            base = dict(old, pool=template['node_pool'], terminal_history={{}})
            require(all(base['pool'].get(k) == config['pool'].get(k) for k in
                ('node', 'node_uid', 'gpu_uuid', 'boot_id', 'driver_generation', 'total_memory_mib')),
                'Historical approval must retain the current physical GPU epoch')
            consumer = approval.ApprovalConsumer(sys.modules[__name__], base, template, ref, kube.configmap)
            document = consumer.document(ref)
            value = consumer._envelope(actual, models, document, ref)
            expected = dict(version=1, approval_ref=ref, enrollment_uid=value['configmap_uid'],
                            enrollment_sha256=canonical_sha256(value['enrollment']))
            require(store.backend.private_read(store.state / 'approval-references' / (uid + '.json'), store.uid)
                    == expected, 'Original protected historical approval reference required')
            return value
'''
    target = '        envelope = validate_enrollment(cm, old, models)'
    require(historical_after.count(target) == 1, 'Unique historical envelope validation required')
    historical_after = historical_after.replace(target, bridge + '        envelope = historical_envelope(cm)', 1)
    target = 'require(validate_enrollment(actual, old, models) == envelope,'
    require(historical_after.count(target) == 1, 'Unique fresh historical envelope validation required')
    historical_after = historical_after.replace(target, 'require(historical_envelope(actual) == envelope,', 1)
    result = result.replace(historical_before, historical_after, 1)
    compile(result, 'prospective_node_successor.py', 'exec')
    return result


def successor_bundle(original, epoch_original, contract_raw, reviewed_raw_sha256):
    """Return the matched finite helper and exact helper-pinned Node source."""
    contract = validate_contract(contract_raw, reviewed_raw_sha256)
    node_source = successor_source(original, contract_raw, reviewed_raw_sha256)
    require(isinstance(epoch_original, bytes) and hashlib.sha256(epoch_original).hexdigest() == EPOCH_SHA256,
            'Exact published Node8c flat epoch helper required')
    source = epoch_original.decode('utf-8')
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'node_configuration')
    before = ''.join(source.splitlines(True)[node.lineno - 1:node.end_lineno])
    marker = "    require(isinstance(config['workspaces'],dict) and 1<=len(config['workspaces'])<=2\n"
    guard = f'''    # Independently reviewed Root contract raw SHA256: {reviewed_raw_sha256}
    prospective_pair = (config['policy_hash'] == {contract['policy_hash']!r}
        and config['workspaces'] == {contract['workspaces']!r}
        and canonical_sha(config['terminal_history']) == {contract['terminal_history_sha256']!r}
        and isinstance(config['pool'],dict)
        and all(type(config['pool'].get(k)) is int for k in
                ('max_workspaces','memory_budget_mib','headroom_mib','free_memory_mib'))
        and config['pool']['max_workspaces'] == 2
        and config['pool']['memory_budget_mib'] == 25600
        and config['pool']['headroom_mib'] == 1024
        and config['pool']['free_memory_mib'] >= 26624)
'''
    after = before.replace(marker, guard + marker.replace('require(', 'require(prospective_pair or (', 1), 1)
    after = after.replace("for k,v in config['workspaces'].items()),'Only exact bounded qualification10 scopes are admitted')",
        "for k,v in config['workspaces'].items())),'Only exact bounded qualification10 or pinned prospective pair scopes are admitted')", 1)
    after = after.replace("require(type(pool.get('max_workspaces')) is int", "require(prospective_pair or (type(pool.get('max_workspaces')) is int", 1)
    after = after.replace("10240<=pool['memory_budget_mib']<=15360)", "10240<=pool['memory_budget_mib']<=15360))", 1)
    require(after != before and source.count(before) == 1, 'Unique exact flat helper validator replacement required')
    epoch_source = source.replace(before, after, 1)
    epoch_pin = hashlib.sha256(epoch_source.encode()).hexdigest()
    require(node_source.count(EPOCH_SHA256) == 1, 'Unique exact Node epoch helper pin required')
    node_source = node_source.replace(EPOCH_SHA256, epoch_pin, 1)
    for name, text in [('node_agent.py', node_source), ('native_operator_epoch.py', epoch_source)]:
        compile(text, name, 'exec')
    return {'node_agent.py': node_source, 'native_operator_epoch.py': epoch_source}


def bounded_contract(path):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size <= 65536, 'Bounded regular contract file required')
        raw = os.read(fd, 65537)
        require(len(raw) <= 65536, 'Bounded contract required')
        return raw
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    emit = parser.add_mutually_exclusive_group()
    emit.add_argument('--emit', action='store_true')
    emit.add_argument('--emit-bundle', action='store_true')
    parser.add_argument('--contract', type=Path)
    parser.add_argument('--contract-sha256')
    args = parser.parse_args(argv)
    if not (args.emit or args.emit_bundle):
        print(json.dumps({'state': 'inert', 'source_only': True, 'production_qualified': False}))
        return 0
    raw_pin(args.contract_sha256)
    require(args.contract is not None, 'Explicit reviewed contract path required')
    raw = bounded_contract(args.contract)
    validate_contract(raw, args.contract_sha256)
    original = Path(__file__).with_name('node8c.py').read_bytes()
    if args.emit_bundle:
        epoch_original = Path(__file__).with_name('epoch8c.py').read_bytes()
        print(json.dumps(successor_bundle(original, epoch_original, raw, args.contract_sha256), sort_keys=True))
    else:
        sys.stdout.write(successor_source(original, raw, args.contract_sha256))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

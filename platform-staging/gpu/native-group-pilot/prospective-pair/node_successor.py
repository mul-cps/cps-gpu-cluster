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
    after = after.replace("config['pool']['memory_budget_mib'] == 15360", "config['pool']['memory_budget_mib'] == (25600 if prospective_pair else 15360)", 1)
    after = after.replace("require(config['workspaces'] == {", "require((prospective_pair or config['workspaces'] == {", 1)
    after = after.replace("'cit:native-group-a': {'profile':'interactive-shared-10', 'cap_mib':10240}}", "'cit:native-group-a': {'profile':'interactive-shared-10', 'cap_mib':10240}})", 1)
    require(after != before and source.count(before) == 1, 'Unique exact validator replacement required')
    result = source.replace(before, after, 1)
    compile(result, 'prospective_node_successor.py', 'exec')
    return result


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
    parser.add_argument('--emit', action='store_true')
    parser.add_argument('--contract', type=Path)
    parser.add_argument('--contract-sha256')
    args = parser.parse_args(argv)
    if not args.emit:
        print(json.dumps({'state': 'inert', 'source_only': True, 'production_qualified': False}))
        return 0
    raw_pin(args.contract_sha256)
    require(args.contract is not None, 'Explicit reviewed contract path required')
    raw = bounded_contract(args.contract)
    original = Path(__file__).with_name('node8c.py').read_bytes()
    sys.stdout.write(successor_source(original, raw, args.contract_sha256))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

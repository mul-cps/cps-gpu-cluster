#!/usr/bin/env python3
"""Compile an email-free reviewed own-account handover; never activate or grant.

Runtime input/output can contain credentials. The CLI requires private files and
prints only sanitized references/checksums. API mutation uses the existing console
/api/identities endpoint with its actual owning Hub authentication and audit actor.
"""
import argparse
import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import uuid

ALIASES = {'cps': 'bjoern', 'cit': 'akadmin'}
CHECKOUT = Path(__file__).resolve().parents[4]
SOURCE = 'f5c005ca8b36995c6b4221873d3d0b4d334be3d4'
IMAGE = 'ghcr.io/mul-cps/e2x-course-hub:qualification-reviewed-alias-f5c005c@sha256:735f891ba008c58a9d3f4d324c22893d13b094dabe7ea39f80c776ffb6c89767'
REASON = ('Explicit administrative review of the user-authorized own accounts CPS bjoern '
          'and CIT akadmin by Rancher operator u-vhm9n/cpsadmin. Exact owning Hub '
          'accounts independently checked; one explicitly assigned canonical UUID; '
          'unchanged usernames and storage; no email/name matching or new entitlement. '
          'Operator-assisted native owning Hub issuance of a minimal 900-second '
          'user token; unchanged console authentication; token revoked after review.')


def require(condition, message):
    if not condition: raise ValueError(message)


def person_id(value):
    require(isinstance(value, str), 'Explicit canonical UUID string required')
    canonical = str(uuid.UUID(value))
    require(value == canonical, 'Existing UUID representation requires separate review')
    return canonical


def mappings(runtime):
    require(isinstance(runtime, dict) and isinstance(runtime.get('hubs'), dict), 'Runtime Hub settings required')
    result = {}
    for hub in ALIASES:
        setting = runtime['hubs'].get(hub)
        require(isinstance(setting, dict) and isinstance(setting.get('canonical_people'), dict), 'Explicit owning Hub mapping required')
        result[hub] = setting['canonical_people']
        for alias, value in result[hub].items():
            require(isinstance(alias, str) and alias and alias == alias.strip(), 'Unchanged nonempty runtime alias required')
            person_id(value)
        require(len(set(result[hub].values())) == len(result[hub]), 'Duplicate person aliases within one Hub require separate migration')
    return result


def select_person(inventory, runtime, *, proposed=None):
    """Preserve literal IDs on these explicit accounts; never join by metadata."""
    require(isinstance(inventory, dict) and set(inventory) == set(ALIASES), 'Both exact owning Hub account inventories required')
    existing = set()
    current = mappings(runtime)
    for hub, alias in ALIASES.items():
        account = inventory[hub]
        require(account.get('username') == alias and account.get('admin') is True, 'Fresh exact owning admin account required')
        ids = account.get('person_ids')
        require(isinstance(ids, list), 'Explicit existing identity references required')
        existing.update(person_id(value) for value in ids)
        if alias in current[hub]: existing.add(person_id(current[hub][alias]))
    require(len(existing) <= 1, 'Conflicting existing canonical UUIDs require operator reconciliation')
    selected = next(iter(existing)) if existing else (person_id(proposed) if proposed is not None else str(uuid.uuid4()))
    if proposed is not None: require(person_id(proposed) == selected, 'Proposed UUID would reassign an existing identity')
    for hub, alias in ALIASES.items():
        require(all(name == alias or value != selected for name, value in current[hub].items()), 'Canonical person already assigned to another owning Hub alias')
    return selected


def alias_payload(hub, person):
    require(hub in ALIASES, 'Exact owning console source required')
    return {'mappings': [{'authority': 'reviewed_account_alias', 'hub': hub,
                          'username': ALIASES[hub], 'person_id': person_id(person),
                          'administrator_reviewed': True, 'review_reason': REASON}]}


def validate_proof(proof, person):
    require(isinstance(proof, dict), 'Persisted reviewed alias proof required')
    fields = {'console', 'username', 'canonical_person_id', 'review_actor', 'review_reason',
              'reviewed_at', 'source', 'image', 'schema', 'audit'}
    require(set(proof) == fields, 'Exact email-free console alias and API audit proof required')
    hub = proof['console']
    require(hub in ALIASES and proof['username'] == ALIASES[hub], 'Proof must belong to the exact reviewed owning account')
    require(person_id(proof['canonical_person_id']) == person, 'Console canonical UUID conflicts with explicit reviewed handover')
    require(proof['source'] == SOURCE and proof['image'] == IMAGE and type(proof['schema']) is int and proof['schema'] == 6, 'Qualified source image/schema required')
    require(proof['review_actor'] == ALIASES[hub], 'Truthful owning Hub audit actor required')
    require(isinstance(proof['review_reason'], str) and proof['review_reason'].strip() and 'u-vhm9n/cpsadmin' in proof['review_reason'], 'Explicit administrative review provenance required')
    require(datetime.fromisoformat(proof['reviewed_at']).tzinfo is not None, 'Service-owned timezone-aware review timestamp required')
    audit = proof['audit']
    require(isinstance(audit, dict) and all(audit.get(k) == v for k, v in {
        'actor': proof['review_actor'], 'console': hub, 'kind': 'identity-aliases',
        'id': proof['username'], 'outcome': 'success'}.items()), 'Successful exact owning Hub API audit required')
    require(datetime.fromisoformat(audit['time']).tzinfo is not None, 'Timezone-aware API audit timestamp required')
    identity = audit.get('new')
    require(isinstance(identity, dict) and all(identity.get(k) == v for k, v in {
        'person_id': person, 'authority': 'reviewed_account_alias',
        'review_actor': proof['review_actor'], 'review_reason': proof['review_reason'],
        'reviewed_at': proof['reviewed_at']}.items()), 'Audit must prove the exact persisted alias UUID and review provenance')
    return hub


def compile_runtime(runtime, proofs, approved_person):
    person = person_id(approved_person)
    current = mappings(runtime)
    require(isinstance(proofs, list) and len(proofs) == len(ALIASES), 'Exactly both independently audited source aliases required')
    reviewed = [validate_proof(proof, person) for proof in proofs]
    require(set(reviewed) == set(ALIASES), 'Foreign, missing or duplicate source alias proof')
    result = copy.deepcopy(runtime)
    for hub, alias in ALIASES.items():
        require(current[hub].get(alias, person) == person, 'Existing alias reassignment is forbidden')
        require(all(name == alias or value != person for name, value in current[hub].items()), 'Duplicate person alias requires separate reviewed migration')
        result['hubs'][hub]['canonical_people'][alias] = person
    return result


def rollback_runtime(before, after, current):
    require(current == after, 'Concurrent runtime changes require explicit reconciliation before rollback')
    # Validate the original ownership/UUID structure; never remove newer aliases.
    mappings(before)
    return copy.deepcopy(before)


def private_read(path):
    path = Path(path)
    require(not path.resolve().is_relative_to(CHECKOUT), 'Private input must be outside the checkout')
    require(path.is_file() and not path.is_symlink() and path.stat().st_uid == os.getuid()
            and path.stat().st_mode & 0o777 == 0o600, 'Operator-owned private 0600 input required')
    return json.loads(path.read_text())


def private_write(path, value):
    path = Path(path)
    require(not path.resolve().is_relative_to(CHECKOUT), 'Private output must be outside the checkout')
    require(path.parent.is_dir() and path.parent.stat().st_uid == os.getuid()
            and path.parent.stat().st_mode & 0o777 == 0o700, 'Operator-owned 0700 output directory required')
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--proofs', type=Path, required=True)
    parser.add_argument('--person', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runtime = compile_runtime(private_read(args.runtime), private_read(args.proofs), args.person)
    digest = private_write(args.output, runtime)
    print(json.dumps({'staged': True, 'activated': False, 'grants_changed': False,
                      'runtime_sha256': digest, 'canonical_people': {h: runtime['hubs'][h]['canonical_people'] for h in ALIASES}}))


if __name__ == '__main__': main()

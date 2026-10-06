#!/usr/bin/env python3
"""Compile reviewed university issuer/subject aliases without changing Hub names.

Input records: hub, username, issuer, subject, upstreamVerified, reviewed,
optional personId. Email and display names are deliberately ignored.
"""
import argparse
import json
from pathlib import Path
import runpy
import uuid

TRUSTED_ISSUER = 'https://login.unileoben.ac.at/realms/unileoben'
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, 'compute.cps.unileoben.ac.at/people')


def compile_mapping(records):
    people, per_hub, identities = {}, {}, {}
    for record in records:
        hub, username = record.get('hub'), record.get('username')
        subject = record.get('subject')
        if hub not in ('cps', 'cit') or not isinstance(username, str) or not username or username.strip() != username:
            raise ValueError('Known Hub and unchanged username required')
        if record.get('issuer') != TRUSTED_ISSUER:
            raise ValueError('Exact trusted university issuer required')
        if record.get('upstreamVerified') is not True or record.get('reviewed') is not True:
            raise ValueError('Upstream identity provenance and aliases must be reviewed')
        if not isinstance(subject, str) or not 1 <= len(subject) <= 255 or any(ord(c) < 33 or ord(c) > 126 for c in subject):
            raise ValueError('Subject must be an opaque nonempty ASCII identifier without whitespace')
        identity = (TRUSTED_ISSUER, subject)
        person = str(uuid.UUID(record['personId'])) if record.get('personId') else str(uuid.uuid5(NAMESPACE, json.dumps(identity, separators=(',', ':'))))
        if identity in identities and identities[identity] != person:
            raise ValueError('Conflicting canonical person for upstream identity')
        if person in people and people[person]['subject'] != subject:
            raise ValueError('Multiple upstream identities require a separate reviewed migration')
        identities[identity] = person
        aliases = per_hub.setdefault(hub, {})
        if username in aliases or person in aliases.values():
            raise ValueError('Duplicate Hub alias/person requires explicit alias migration')
        aliases[username] = person
        people.setdefault(person, {'personId': person, 'issuer': TRUSTED_ISSUER, 'subject': subject, 'aliases': []})['aliases'].append({'hub': hub, 'username': username})
    if not people:
        raise ValueError('Empty identity mapping cannot activate shared allowances')
    return {'schemaVersion': 1, 'authority': 'university-keycloak-reviewed-subjects', 'canonical_people': per_hub, 'people': people}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reviewed_export', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    write_private = runpy.run_path(str(Path(__file__).with_name('link-identity-emails.py')))['write_private']
    write_private(args.output, compile_mapping(json.loads(args.reviewed_export.read_text())))
    print('Private subject mapping written; no Hub or policy activation performed')

#!/usr/bin/env python3
"""Compile an explicitly reviewed email directory export into canonical aliases.

Input: [{hub, username, email, verified, reviewed, personId?}]. Existing personIds
remain stable when an email changes through a reviewed migration. This script never
queries a user-supplied identity endpoint, changes Hub usernames, or writes to Git.
"""
import argparse
import json
import os
from pathlib import Path
import re
import uuid

NAMESPACE=uuid.uuid5(uuid.NAMESPACE_DNS,'compute.cps.unileoben.ac.at/people')

def compile_mapping(records):
    people={}; per_hub={}; emails={}
    for record in records:
        if record.get('hub') not in ('cps','cit') or not record.get('username'):
            raise ValueError('Known Hub and unchanged username required')
        if record.get('verified') is not True or record.get('reviewed') is not True:
            raise ValueError('Identity email must be verified and mapping explicitly reviewed')
        email=record.get('email','').strip().casefold()
        if not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',email):
            raise ValueError('A complete authoritative email address is required')
        person=str(uuid.UUID(record['personId'])) if record.get('personId') else str(uuid.uuid5(NAMESPACE,email))
        if email in emails and emails[email]!=person:
            raise ValueError('One email cannot refer to two canonical persons')
        emails[email]=person
        aliases=per_hub.setdefault(record['hub'],{})
        if record['username'] in aliases:
            raise ValueError('Duplicate username in Hub mapping')
        if person in aliases.values():
            raise ValueError('Duplicate email/person accounts within one Hub require explicit alias migration')
        aliases[record['username']]=person
        people.setdefault(person,{'personId':person,'emails':[],'aliases':[]})
        if email not in people[person]['emails']:people[person]['emails'].append(email)
        people[person]['aliases'].append({'hub':record['hub'],'username':record['username']})
    if not people:raise ValueError('Empty identity mapping cannot activate shared allowances')
    return {'schemaVersion':1,'authority':'verified-email-reviewed-mapping','canonical_people':per_hub,'people':people}

def write_private(path,value):
    path=Path(path).resolve()
    ancestor=path.parent
    while not ancestor.exists():ancestor=ancestor.parent
    import subprocess
    if subprocess.run(['git','-C',str(ancestor),'rev-parse','--show-toplevel'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
        raise ValueError('Identity mappings must be stored outside Git worktrees')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as file:json.dump(value,file,indent=2);file.write('\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reviewed_export',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    write_private(args.output,compile_mapping(json.loads(args.reviewed_export.read_text())))
    print('Private canonical mapping written; Hub accounts and storage remain unchanged')

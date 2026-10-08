#!/usr/bin/env python3
"""Publish only a reviewed immutable runtime candidate; never restart or grant."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

import capture
import handover


def stage(private, person):
    original=handover.private_read(private/'runtime-secret-before.json')
    runtime=handover.private_read(private/'runtime-before.json')
    proofs=handover.private_read(private/'alias-proofs.json')
    desired=handover.compile_runtime(runtime,proofs,person)
    current=capture.get('secret','cps-compute-runtime')
    fields=('uid','resourceVersion')
    handover.require(all(current['metadata'][k]==original['metadata'][k] for k in fields)
                     and current['data']==original['data'], 'Concurrent runtime generation/configuration change requires re-review')
    key=next(iter(original['data']))
    raw=(json.dumps(desired,sort_keys=True,indent=2)+'\n').encode()
    name='cps-compute-runtime-reviewed-alias-'+person[:8]
    manifest={'apiVersion':'v1','kind':'Secret','type':original['type'],'immutable':True,
        'metadata':{'name':name,'namespace':capture.NS,
            'labels':{'compute.cps/qualification':'reviewed-own-alias'},
            'annotations':{'compute.cps/identity-authority':'reviewed-account-alias',
                'compute.cps/source-secret':'cps-compute-runtime',
                'compute.cps/source-resource-version':original['metadata']['resourceVersion']}},
        'data':dict(original['data'])}
    manifest['data'][key]=base64.b64encode(raw).decode()
    # Credential bytes travel only through subprocess stdin/captured memory.
    reply=json.loads(capture.run('create','-f','-','-o','json',body=json.dumps(manifest)))
    handover.require(reply['immutable'] is True and reply['data']==manifest['data'], 'Exact immutable candidate must persist')
    after=capture.get('secret','cps-compute-runtime')
    handover.require(all(after['metadata'][k]==original['metadata'][k] for k in fields)
                     and after['data']==original['data'], 'Source changed during staging; do not adopt this candidate')
    proof={'secret':name,'resourceVersion':reply['metadata']['resourceVersion'],'uid':reply['metadata']['uid'],
        'source_secret':'cps-compute-runtime','source_resourceVersion':original['metadata']['resourceVersion'],
        'source_uid':original['metadata']['uid'],'runtime_sha256':hashlib.sha256(raw).hexdigest(),
        'canonical_people':{h:desired['hubs'][h]['canonical_people'] for h in handover.ALIASES},
        'active':False,'grants_changed':False,'other_runtime_fields_preserved':True}
    handover.private_write(private/'runtime-stage-proof.json',proof)
    return proof


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir',type=Path,required=True)
    parser.add_argument('--person',required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    handover.require(args.execute,'Explicit reviewed staging required')
    print(json.dumps(stage(args.private_dir,handover.person_id(args.person)),indent=2))


if __name__=='__main__':main()

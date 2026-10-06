#!/usr/bin/env python3
"""Compile IPv4 NAS exclusions into an existing user NetworkPolicy, no writes."""
import copy
import ipaddress
import json
import sys
from pathlib import Path

CONFIG=Path(__file__).resolve().parents[2]/'platform-staging/network/nas-endpoints.json'

def restrict(policy,targets):
    destinations=[ipaddress.ip_network(x,strict=True) for x in targets]
    if not destinations or any(x.version!=4 or x.prefixlen!=32 for x in destinations):
        raise ValueError('Explicit IPv4 NAS host destinations required')
    out=copy.deepcopy(policy);spec=out['spec'];types=spec.get('policyTypes',['Ingress'] if 'ingress' in spec else [])
    if 'Egress' not in types:
        types=[*types,'Egress'];spec.setdefault('egress',[{}])
    spec['policyTypes']=types
    for rule in spec.get('egress',[]):
        if not rule.get('to'):
            rule['to']=[{'ipBlock':{'cidr':'0.0.0.0/0','except':list(targets)}}]
        for peer in rule['to']:
            if 'ipBlock' not in peer:continue
            block=peer['ipBlock'];cidr=ipaddress.ip_network(block['cidr']);excluded=block.get('except',[]).copy()
            for network in destinations:
                if (network.version==cidr.version and network.subnet_of(cidr)
                        and not any(network.version==ipaddress.ip_network(x).version
                            and network.subnet_of(ipaddress.ip_network(x)) for x in excluded)):
                    excluded.append(str(network))
            if excluded:block['except']=excluded
    return out

if __name__=='__main__':
    settings=json.loads(CONFIG.read_text())
    if settings['schemaVersion']!=1:raise ValueError('Unsupported NAS network catalog')
    result=restrict(json.load(sys.stdin),settings['blockedPodDestinations'])
    json.dump(result,sys.stdout,indent=2);print()

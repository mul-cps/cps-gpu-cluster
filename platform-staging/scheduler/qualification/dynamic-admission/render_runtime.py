#!/usr/bin/env python3
"""Render three inactive, coordinated admission candidates for operator review.

No live registry protocol is implemented. Exact preregistration and the binder
rollback/generation race remain blocking integration gates, not solved by YAML.
"""
import argparse
import hashlib
import json
from pathlib import Path

import yaml

import binding_policy
import compiled_fixtures
import injected_policy
import quota_policy

REGISTRY_FIELDS = {'createCreators', 'updateCreators', 'owners', 'reviewedPods',
                   'quotaWriters', 'quotaRecords', 'bindingWriters', 'bindingRecords'}


def build(*, registry=None, namespace=compiled_fixtures.NAMESPACE, executor_image,
          wheel=compiled_fixtures.DEFAULT_WHEEL, artifact_secret='cps-artifacts', artifact_ca_secret='cps-artifacts-ca'):
    registry = {} if registry is None else registry
    if not isinstance(registry, dict) or set(registry) - REGISTRY_FIELDS:
        raise ValueError('Only the explicit protected qualification registry fields are permitted')
    pod = injected_policy.build(namespace=namespace, executor_image=executor_image, wheel=wheel,
        artifact_secret=artifact_secret, artifact_ca_secret=artifact_ca_secret,
        create_creators=registry.get('createCreators', []), update_creators=registry.get('updateCreators', []),
        owners=registry.get('owners', []), reviewed_pods=registry.get('reviewedPods', []))
    quota = quota_policy.build(namespace=namespace, writers=registry.get('quotaWriters', []), records=registry.get('quotaRecords', []))
    binding = binding_policy.build(namespace=namespace, writers=registry.get('bindingWriters', []), records=registry.get('bindingRecords', []))
    pods = {record['name']: record for record in pod['items'][1]['reviewedPods']}
    maps = {record['name']: record for record in quota['items'][1]['records']}
    for record in maps.values():
        expected = pods.get(record['podName'])
        if expected is None:
            raise ValueError('Quota map requires a registered exact Pod plan')
        name = expected['capabilitiesName'] if record['type'] == 'capabilities' else expected['evarName']
        if record['name'] != name or int(record['cudaDeviceMemoryLimit'][:-1]) < int(expected['gpuMemory']):
            raise ValueError('Quota map references must match the fixed profile, and its independently reviewed KAI limit must cover the nominal indexed budget')
    for expected in pods.values():
        cap, evar = maps.get(expected['capabilitiesName']), maps.get(expected['evarName'])
        if cap is None and evar is None:
            continue  # Empty registries intentionally leave all map writes denied.
        if cap is None or evar is None:
            raise ValueError('A reviewed Pod requires both exact quota-map roles')
        for field in ('podName', 'podUid', 'gpuUuid', 'visibleDevices', 'physicalGpuMemoryMiB',
                      'gpuPortion', 'runaiNumOfGpus', 'cudaDeviceMemoryLimit'):
            if cap[field] != evar[field]:
                raise ValueError('Capabilities and evar map records must attest the same Pod, physical device and profile')
    for record in binding['items'][1]['records']:
        expected = pods.get(record['podName'])
        if expected is None:
            raise ValueError('Binding requires a registered exact Pod plan')
        for role, key in (('capabilities', 'capabilitiesName'), ('evar', 'evarName')):
            name = expected[key]
            cm = maps.get(name)
            if (cm is None or record[key] != name or record['podUid'] != cm['podUid'] or
                    record[role + 'Uid'] != cm.get('cmUid')):
                raise ValueError('Binding approval requires the same reviewed Pod and independently pinned quota-map generations')
    return {'apiVersion': 'v1', 'kind': 'List', 'items': pod['items'] + quota['items'] + binding['items']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--namespace', default=compiled_fixtures.NAMESPACE)
    parser.add_argument('--wheel', type=Path, default=compiled_fixtures.DEFAULT_WHEEL)
    parser.add_argument('--executor-image', required=True)
    parser.add_argument('--artifact-secret', default='cps-artifacts')
    parser.add_argument('--artifact-ca-secret', default='cps-artifacts-ca')
    parser.add_argument('--registry', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text()) if args.registry else {}
    manifest = build(registry=registry, namespace=args.namespace, wheel=args.wheel, executor_image=args.executor_image,
        artifact_secret=args.artifact_secret, artifact_ca_secret=args.artifact_ca_secret)
    with args.output.open('x') as output:
        yaml.safe_dump_all(manifest['items'], output, sort_keys=False)
    print(json.dumps({'resources': len(manifest['items']), 'applied': False, 'productionQualified': False,
        'controllerCoordinationImplemented': False, 'kubernetesTypecheckQualified': False,
        'manifestSha256': hashlib.sha256(compiled_fixtures.canonical(manifest)).hexdigest()}))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Render inert rollout candidates. This command never applies or nominates nodes."""
import argparse
import copy
import json
import re
import sys
import yaml


def os_plan(node, operation, image):
    if not re.fullmatch(r'k3s-wk-gpu[1-4]', node):
        raise ValueError('only GPU workers may be selected')
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', operation):
        raise ValueError('invalid operation identity')
    if not re.fullmatch(r'[^\s@]+@sha256:[0-9a-f]{64}', image):
        raise ValueError('a published image digest is required')
    return {
        'apiVersion': 'upgrade.cattle.io/v1', 'kind': 'Plan',
        'metadata': {'name': 'cps-ubuntu-' + operation, 'namespace': 'cattle-system'},
        'spec': {
            'concurrency': 1, 'exclusive': True, 'version': operation,
            'serviceAccountName': 'system-upgrade-controller',
            # Pre-cordon and PDB-respecting drain are mandatory. Omitting SUC
            # cordon/drain prevents SUC's completion handler from uncordoning.
            'cordon': False,
            'nodeSelector': {'matchLabels': {
                'kubernetes.io/hostname': node, 'cps.unileoben.ac.at/os-upgrade': operation}},
            'tolerations': [{'key': 'cps.unileoben.ac.at/os-upgrade',
                             'operator': 'Exists', 'effect': 'NoSchedule'}],
            'upgrade': {'image': image, 'command': ['/entrypoint.sh'], 'args': [operation, node]},
        },
    }


def fraction_config(documents):
    documents = copy.deepcopy(documents)
    configs = [doc for doc in documents if doc and doc.get('kind') == 'GpuFractioningConfig']
    if (len(configs) != 1 or configs[0].get('metadata', {}).get('name') != 'default'
            or configs[0].get('apiVersion') != 'gpu-fractioning.kai.scheduler/v1alpha1'
            or not isinstance(configs[0].get('spec'), dict)):
        raise ValueError('expected exactly one upstream default GpuFractioningConfig')
    spec = configs[0]['spec']
    spec['nodeSelector'] = {'kubernetes.io/hostname': 'k3s-wk-gpu2',
                           'cps.unileoben.ac.at/fractioning-runtime': 'upstream'}
    spec.setdefault('fractioningAgent', {}).update({
        'failOpen': False, 'retroactiveEnforcement': True,
        'nriSocketPath': '/var/run/nri/nri.sock',
        'criSocketPath': '/run/k3s/containerd/containerd.sock',
    })
    return documents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('os-plan')
    plan.add_argument('--node', required=True)
    plan.add_argument('--operation', required=True)
    plan.add_argument('--image', required=True)
    commands.add_parser('fraction-postrender')
    args = parser.parse_args()
    if args.command == 'os-plan':
        result = [os_plan(args.node, args.operation, args.image)]
    else:
        result = fraction_config(list(yaml.safe_load_all(sys.stdin)))
    yaml.safe_dump_all(result, sys.stdout, sort_keys=False)


if __name__ == '__main__':
    main()

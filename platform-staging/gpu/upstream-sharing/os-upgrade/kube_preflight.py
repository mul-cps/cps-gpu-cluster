#!/usr/bin/env python3
"""Read-only last-moment SUC gate. Fail before launching any host operation."""
import argparse
import json
import os
from pathlib import Path
import ssl
import urllib.parse
import urllib.request

LABEL = 'cps.unileoben.ac.at/os-upgrade'
WORKERS = {f'k3s-wk-gpu{i}' for i in range(1, 5)}


def check(nodes, pods, node, operation, own_uid):
    workers = {item['metadata']['name']: item for item in nodes if item['metadata']['name'] in WORKERS}
    if set(workers) != WORKERS or node not in WORKERS or not own_uid:
        raise RuntimeError('expected four GPU workers and the SUC pod identity')
    for name, item in workers.items():
        labels = item['metadata'].get('labels', {})
        spec = item.get('spec', {})
        ready = any(c['type'] == 'Ready' and c['status'] == 'True' for c in item['status']['conditions'])
        if name == node:
            if not spec.get('unschedulable') or labels.get(LABEL) != operation or not ready:
                raise RuntimeError('selected worker must be nominated, Ready and already cordoned')
        elif (not ready or spec.get('unschedulable') or LABEL in labels
              or int(item['status'].get('allocatable', {}).get('nvidia.com/gpu', '0')) < 2):
            raise RuntimeError('three healthy GPU peers and one maintenance worker are required')
    for pod in pods:
        metadata = pod['metadata']
        if metadata.get('uid') == own_uid or pod.get('status', {}).get('phase') in ('Succeeded', 'Failed'):
            continue
        if any(owner.get('controller') and owner.get('kind') == 'DaemonSet'
               for owner in metadata.get('ownerReferences', [])):
            continue
        raise RuntimeError('live workload remains; wait for work and complete a PDB-respecting drain: '
                           + metadata.get('namespace', '') + '/' + metadata.get('name', metadata.get('uid', '?')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True)
    parser.add_argument('--operation', required=True)
    args = parser.parse_args()
    service_account = Path('/var/run/secrets/kubernetes.io/serviceaccount')
    context = ssl.create_default_context(cafile=str(service_account / 'ca.crt'))
    token = (service_account / 'token').read_text().strip()
    def get(path):
        request = urllib.request.Request('https://kubernetes.default.svc' + path,
                                         headers={'Authorization': 'Bearer ' + token})
        with urllib.request.urlopen(request, context=context, timeout=30) as response:
            return json.load(response)['items']
    nodes = get('/api/v1/nodes')
    pods = get('/api/v1/pods?' + urllib.parse.urlencode({'fieldSelector': 'spec.nodeName=' + args.node}))
    check(nodes, pods, args.node, args.operation, os.environ.get('SYSTEM_UPGRADE_POD_UID'))


if __name__ == '__main__':
    main()

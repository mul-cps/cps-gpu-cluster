#!/usr/bin/env python3
"""Render a proposed GPU2-only driver DaemonSet. Never applies resources."""
import copy
import json
from pathlib import Path
import subprocess

import yaml

HERE = Path(__file__).resolve().parent
NODE = 'k3s-wk-gpu2'
NAME = 'gpu2-r615-driver-canary'
IMAGE = 'nvcr.io/nvidia/driver@sha256:bc7572b7f14177c467e4dd8b66c4f4535f462ea9cf6a65cebd7603cc966ebbd7'
MANAGER = 'nvcr.io/nvidia/cloud-native/k8s-driver-manager@sha256:a6c12abacc9c4f51d3653c90fcad32f19799069889338601407eba05fea4ba18'


def candidate(current):
    assert current['kind'] == 'DaemonSet'
    assert current['metadata']['name'] == 'nvidia-driver-daemonset'
    assert current['spec']['updateStrategy']['type'] == 'OnDelete'
    value = copy.deepcopy(current)
    value['metadata'] = {'name': NAME, 'namespace': 'gpu-operator',
                         'labels': {'qualification.cps/owner': NAME}}
    value.pop('status', None)
    value['spec']['selector'] = {'matchLabels': {'app': NAME}}
    value['spec']['template']['metadata'] = {'labels': {'app': NAME,
        'qualification.cps/owner': NAME}, 'annotations': {
        'qualification.cps/state': 'proposal-only-not-applied'}}
    pod = value['spec']['template']['spec']
    pod['nodeSelector'] = {'kubernetes.io/hostname': NODE}
    # The old driver pod must be gone first. Its anti-affinity stays in place.
    driver = next(c for c in pod['containers'] if c['name'] == 'nvidia-driver-ctr')
    driver['image'] = IMAGE
    manager = next(c for c in pod['initContainers'] if c['name'] == 'k8s-driver-manager')
    manager['image'] = MANAGER
    env = {e['name']: e for e in manager['env']}
    for key in ('ENABLE_GPU_POD_EVICTION', 'ENABLE_AUTO_DRAIN', 'DRAIN_USE_FORCE', 'DRAIN_DELETE_EMPTYDIR_DATA'):
        env[key] = {'name': key, 'value': 'false'}
    manager['env'] = list(env.values())
    assert pod['nodeSelector'] == {'kubernetes.io/hostname': NODE}
    assert 'ownerReferences' not in value['metadata']
    return value


if __name__ == '__main__':
    current = json.loads(subprocess.check_output(['kubectl', '-n', 'gpu-operator', 'get',
        'daemonset', 'nvidia-driver-daemonset', '-o', 'json']))
    expected = json.loads((HERE / 'preflight.json').read_text())
    assert current['metadata']['uid'] == '7347875f-1243-4b54-9fe7-8aed76a75a05'
    assert current['metadata']['resourceVersion'] == '244833173', 'Refresh preflight after driver DaemonSet drift'
    node = json.loads(subprocess.check_output(['kubectl', 'get', 'node', NODE, '-o', 'json']))
    assert node['metadata']['uid'] == expected['gpu2']['uid']
    output = candidate(current)
    (HERE / 'candidate-not-applied.yaml').write_text(yaml.safe_dump(output, sort_keys=False))
    print(json.dumps({'rendered': NAME, 'node': NODE, 'applied': False,
                      'driverReloadQualified': False, 'rollbackQualified': False}))

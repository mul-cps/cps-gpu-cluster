#!/usr/bin/env python3
"""Render a proposed GPU2-only driver DaemonSet. Never applies resources."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

import yaml

HERE = Path(__file__).resolve().parent
NODE = 'k3s-wk-gpu2'
NAME = 'gpu2-r615-driver-canary'
IMAGE = 'nvcr.io/nvidia/driver@sha256:bc7572b7f14177c467e4dd8b66c4f4535f462ea9cf6a65cebd7603cc966ebbd7'
FIRMWARE = '/run/nvidia/firmware-r615-canary'


def spec_digest(value):
    return hashlib.sha256(json.dumps(value['spec'], sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def verify_source(current, expected, node):
    assert current['metadata']['uid'] == expected['sourceDaemonSetUID']
    assert spec_digest(current) == expected['sourceDaemonSetSpecSHA256'], 'Source DaemonSet spec changed'
    assert node['metadata']['uid'] == expected['gpu2']['uid']


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
        'qualification.cps/state': 'proposal-only-manually-quiesced-no-manager'}}
    pod = value['spec']['template']['spec']
    pod['nodeSelector'] = {'kubernetes.io/hostname': NODE}
    # The old driver pod must be gone first. Its anti-affinity stays in place.
    driver = next(c for c in pod['containers'] if c['name'] == 'nvidia-driver-ctr')
    driver['image'] = IMAGE
    firmware_volume = next(v for v in pod['volumes'] if v['name'] == 'nv-firmware')
    assert firmware_volume['hostPath']['path'] == '/run/nvidia/driver/lib/firmware'
    assert any(v['name'] == 'nv-firmware' and v['mountPath'] == '/lib/firmware'
               for v in driver['volumeMounts'])
    # The old driver-root bind is unmounted during driver initialization.
    # Installing firmware into a directory below it loses the installation.
    firmware_volume['hostPath'] = {'path': FIRMWARE, 'type': 'DirectoryOrCreate'}
    # v0.9.0 ALWAYS recycles toolkit/MIG operands, irrespective of drain flags.
    # Root must verify no user clients, NVIDIA modules or FDs before starting
    # this manually quiesced candidate. It makes no node-label/API mutations.
    pod['initContainers'] = [c for c in pod.get('initContainers', [])
                             if c['name'] != 'k8s-driver-manager']
    pod['initContainers'].append({
        'name': 'gpu2-firmware-search-path', 'image': IMAGE,
        'imagePullPolicy': 'IfNotPresent', 'command': ['/bin/sh', '-ec'],
        'args': ['printf %s "' + FIRMWARE + '" > /sys/module/firmware_class/parameters/path'],
        'securityContext': {'privileged': True},
        'volumeMounts': [{'name': 'firmware-search-path',
                         'mountPath': '/sys/module/firmware_class/parameters/path'}]})
    assert pod['nodeSelector'] == {'kubernetes.io/hostname': NODE}
    assert 'ownerReferences' not in value['metadata']
    return value


if __name__ == '__main__':
    current = json.loads(subprocess.check_output(['kubectl', '-n', 'gpu-operator', 'get',
        'daemonset', 'nvidia-driver-daemonset', '-o', 'json']))
    expected = json.loads((HERE / 'preflight.json').read_text())
    node = json.loads(subprocess.check_output(['kubectl', 'get', 'node', NODE, '-o', 'json']))
    verify_source(current, expected, node)
    output = candidate(current)
    (HERE / 'candidate-not-applied.yaml').write_text(yaml.safe_dump(output, sort_keys=False))
    print(json.dumps({'rendered': NAME, 'node': NODE, 'applied': False,
                      'driverReloadQualified': False, 'rollbackQualified': False}))

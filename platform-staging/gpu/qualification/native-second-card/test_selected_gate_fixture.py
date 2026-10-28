"""Tests for the offline post-admission selected-gate QA fixture builder."""
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
BUILDER = HERE / 'selected-gate-fixture.py'
SDK = Path('/home/bjoern/git/cps-transport-worktrees/packaging-011-20261028/src')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_inputs():
    descriptor = {
        'version': 1, 'kind': 'controlled-qa-selected-gate/v1',
        'cohort_uid': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        'source': 'cps', 'workspace': 'qa-workspace',
        'attempt': 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
        'namespace': 'cps-native-second-card-qa',
        'name': 'native-second-card-b-aaaaaaaa',
        'node': 'k3s-wk-gpu2',
        'node_uid': 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
        'policy_hash': 'sha256:' + 'd' * 64,
    }
    physical = {
        'node': descriptor['node'], 'node_uid': descriptor['node_uid'],
        'boot_id': 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
        'driver_generation': 'ffffffff-ffff-4fff-8fff-ffffffffffff',
        'gpu_uuid': 'GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6',
    }
    qualification_ref = {
        'namespace': 'cps-native-runtime', 'name': 'cps-second-device-qualification-b65a5ca0fb59d8d4',
        'uid': '6cf5e783-a5c6-4b9d-a672-cc8fe9c4a0e6',
        'resourceVersion': '387170546',
        'data_sha256': 'sha256:50d2dd3dabdd991e30d7031b1143a3f4a72549b607109df06df9d499e2e5eab9',
        'key': 'qualification.json',
    }
    placement_id = 'placement-' + hashlib.sha256(json.dumps(
        descriptor, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()[:60]
    # The builder verifies the annotation against this admitted spec hash. All
    # other fields are deliberately ordinary Pod API fields.
    actual_pod = {
        'apiVersion': 'v1', 'kind': 'Pod',
        'metadata': {'namespace': descriptor['namespace'], 'name': descriptor['name'],
                     'uid': '33333333-3333-4333-8333-333333333333', 'annotations': {}},
        'spec': {'nodeName': descriptor['node'], 'initContainers': [
            {'name': 'cps-native-cap-gate'},
            {'name': 'cps-native-device-identity', 'env': [
                {'name': 'NVIDIA_VISIBLE_DEVICES',
                 'value': 'k8s.device-plugin.nvidia.com/gpu=' + physical['gpu_uuid']},
                {'name': 'CUDA_VISIBLE_DEVICES', 'value': '0'},
            ]},
        ], 'containers': []},
    }
    spec_raw = json.dumps(actual_pod['spec'], sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                          allow_nan=False).encode()
    actual_pod['metadata']['annotations']['cps.compute/native-spec-sha256'] = hashlib.sha256(spec_raw).hexdigest()
    review = {
        'request': {'cohort_uid': descriptor['cohort_uid'], 'namespace': descriptor['namespace'],
                    'policy_hash': descriptor['policy_hash']},
        'epoch': {'node_uid': descriptor['node_uid']},
        'selected_gate_delta': {
            'scope': 'controlled-qa-only', 'production_authority': False,
            'placement_token': placement_id,
            'selection_projection': 'deferred-until-actual-pod-uid-and-spec-readback',
        },
        'pods': {
            'a': {'metadata': {'namespace': descriptor['namespace'], 'name': 'native-second-card-a-aaaaaaaa'}, 'spec': {}},
            'b': {'metadata': {'namespace': descriptor['namespace'], 'name': descriptor['name'],
                               'annotations': {'cps.compute/native-spec-sha256': actual_pod['metadata']['annotations']['cps.compute/native-spec-sha256']}},
                  'spec': actual_pod['spec']},
        },
    }
    return review, descriptor, actual_pod, qualification_ref, physical


def test_builds_closed_selection_configmap_accepted_by_installed_sdk_parser(tmp_path):
    review, descriptor, actual_pod, qualification_ref, physical = fixture_inputs()
    before = copy.deepcopy((review, descriptor, actual_pod, qualification_ref, physical))
    builder = load_module('selected_gate_fixture', BUILDER)

    proposed = builder.build_selected_fixture(review, descriptor, actual_pod, qualification_ref, physical)

    assert (review, descriptor, actual_pod, qualification_ref, physical) == before
    assert proposed['live_applied'] is False
    assert proposed['production_authority'] is False
    configmap = proposed['configmap']
    assert configmap['immutable'] is True
    assert configmap['metadata']['name'] == 'cps-native-' + hashlib.sha256(
        review['selected_gate_delta']['placement_token'].encode()).hexdigest()[:32] + '-selection'
    assert set(configmap['data']) == {'selected.json', 'gpu_uuid'}
    document = json.loads(configmap['data']['selected.json'])
    assert configmap['data']['gpu_uuid'] == physical['gpu_uuid']
    assert document['pod_uid'] == actual_pod['metadata']['uid']
    assert document['spec_sha256'] == actual_pod['metadata']['annotations']['cps.compute/native-spec-sha256']
    assert document['gpu_uuid'] == physical['gpu_uuid']
    assert document['selected_placement']['qualification_ref'] == qualification_ref

    # Exercise the exact installed SDK parser against a local projected-file analogue.
    projection = tmp_path / 'projected' / 'selected.json'
    projection.parent.mkdir()
    projection.write_text(configmap['data']['selected.json'])
    expected = {key: document[key] for key in (
        'placement_id', 'source', 'workspace', 'attempt', 'namespace', 'name',
        'node', 'node_uid', 'cap_mib', 'policy_hash')}
    parser = """import json,sys
from cps_compute.native_gpu_runtime import read_selected_native_cap
path,pod_uid,spec_sha=sys.argv[1:]
expected=json.load(sys.stdin)
print(json.dumps(read_selected_native_cap(path,expected,pod_uid=pod_uid,spec_sha256=spec_sha)))
"""
    parsed = json.loads(subprocess.run(
        [sys.executable, '-c', parser, str(projection), actual_pod['metadata']['uid'], document['spec_sha256']],
        input=json.dumps(expected), text=True, capture_output=True, check=True,
        env={**__import__('os').environ, 'PYTHONPATH': str(SDK)}).stdout)
    assert parsed['gpu_uuid'] == physical['gpu_uuid']
    assert parsed['cap_mib'] == 10240


@pytest.mark.parametrize('mutation', ['uid', 'spec', 'name', 'namespace', 'qualification_ref', 'device_epoch', 'gpu', 'token'])
def test_rejects_unbound_or_fabricated_actual_evidence(mutation):
    review, descriptor, actual_pod, qualification_ref, physical = fixture_inputs()
    review = copy.deepcopy(review)
    descriptor = copy.deepcopy(descriptor)
    actual_pod = copy.deepcopy(actual_pod)
    qualification_ref = copy.deepcopy(qualification_ref)
    physical = copy.deepcopy(physical)
    if mutation == 'uid':
        actual_pod['metadata']['uid'] = ''
    elif mutation == 'spec':
        actual_pod['spec']['nodeName'] = 'other-node'
    elif mutation == 'name':
        actual_pod['metadata']['name'] = 'other-pod'
    elif mutation == 'namespace':
        actual_pod['metadata']['namespace'] = 'other-namespace'
    elif mutation == 'qualification_ref':
        qualification_ref.pop('uid')
    elif mutation == 'device_epoch':
        physical['node_uid'] = '44444444-4444-4444-8444-444444444444'
    elif mutation == 'gpu':
        physical['gpu_uuid'] = 'GPU-2e6145d5-8ee2-43e2-a0d5-6d345909e8a6'
    elif mutation == 'token':
        review['selected_gate_delta']['placement_token'] = 'placement-' + 'b' * 60
    builder = load_module('selected_gate_fixture_negative', BUILDER)

    with pytest.raises(ValueError):
        builder.build_selected_fixture(review, descriptor, actual_pod, qualification_ref, physical)


def test_rejects_arbitrary_reference_data_keys():
    review, descriptor, actual_pod, qualification_ref, physical = fixture_inputs()
    qualification_ref['key'] = '../selected.json'
    builder = load_module('selected_gate_fixture_paths', BUILDER)

    with pytest.raises(ValueError):
        builder.build_selected_fixture(review, descriptor, actual_pod, qualification_ref, physical)

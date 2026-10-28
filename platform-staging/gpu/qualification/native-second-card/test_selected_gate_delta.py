"""CPU-only tests for the selected B gate projection composer."""
import copy
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).parent
MODULE = HERE / 'selected-gate-delta.py'


def module():
    spec = importlib.util.spec_from_file_location('selected_gate_delta', MODULE)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def pod(name, cap):
    return {
        'metadata': {'name': name, 'namespace': 'qa-ns', 'annotations': {}},
        'spec': {
            'nodeName': 'gpu-node',
            'volumes': [{'name': 'work', 'emptyDir': {}},
                {'name': 'qa-gate-package', 'configMap': {'name': 'qa-source', 'defaultMode': 292}}],
            'initContainers': [
                {'name': 'cps-native-cap-gate', 'image': 'old-image',
                 'command': ['python', '-I', '-S', '-c', 'old-bootstrap'],
                 'args': ['wait-for-cap', '--cap-mib', str(cap)],
                 'env': [
                     {'name': 'NVIDIA_VISIBLE_DEVICES', 'value': 'void'},
                     {'name': 'CUDA_VISIBLE_DEVICES', 'value': ''},
                     {'name': 'CPS_NATIVE_POD_UID', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.uid'}}},
                     {'name': 'CPS_NATIVE_SPEC_SHA256', 'valueFrom': {'fieldRef': {'fieldPath': "metadata.annotations['cps.compute/native-spec-sha256']"}}},
                 ],
                 'volumeMounts': [{'name': 'work', 'mountPath': '/work'},
                              {'name': 'qa-gate-package', 'mountPath': '/opt/cps-qa', 'readOnly': True}]},
                {'name': 'cps-native-device-identity', 'image': 'workload-image',
                 'command': ['python', '-I', '-S', '-c', 'identity'],
                 'args': ['old-gpu'],
                 'env': [{'name': 'NVIDIA_VISIBLE_DEVICES', 'value': 'k8s.device-plugin.nvidia.com/gpu=GPU-11111111-1111-4111-8111-111111111111'},
                         {'name': 'CUDA_VISIBLE_DEVICES', 'value': '0'}]},
            ],
            'containers': [{'name': 'notebook', 'image': 'workload-image'}],
        },
    }


def qa_descriptor(cohort='dddddddd-dddd-4ddd-8ddd-dddddddddddd', name='native-second-card-b-dddddddd'):
    return {
        'version': 1, 'kind': 'controlled-qa-selected-gate/v1',
        'cohort_uid': cohort, 'source': 'cps', 'workspace': 'ws-test',
        'attempt': '55555555-5555-4555-8555-555555555555',
        'namespace': 'qa-ns', 'name': name, 'node': 'gpu-node',
        'node_uid': '11111111-1111-4111-8111-111111111111',
        'policy_hash': 'sha256:' + 'a' * 64,
    }


def test_compose_changes_only_b_gate_and_preserves_fresh_pair():
    m = module()
    review = {'cohort_uid': 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
        'request': {'cohort_uid': 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
                    'namespace': 'qa-ns', 'policy_hash': 'sha256:' + 'a' * 64},
        'epoch': {'node_uid': '11111111-1111-4111-8111-111111111111'}, 'pods': {
        'a': pod('native-second-card-a-dddddddd', 5120),
        'b': pod('native-second-card-b-dddddddd', 10240),
    }}
    before = copy.deepcopy(review)
    gate_image = module().GATE_IMAGE

    descriptor = qa_descriptor()
    result = m.compose(review, descriptor, gate_image=gate_image)

    assert result['cohort_uid'] == before['cohort_uid']
    assert result['pods']['a'] == before['pods']['a']
    assert set(result['pods']) == {'a', 'b'}
    gate, identity = result['pods']['b']['spec']['initContainers']
    assert gate['image'] == gate_image
    assert gate['command'] == ['python', '-m', 'cps_compute.native_gpu_runtime']
    assert gate['args'] == [
        'wait-for-selected-cap', '--placement-id', m._qa_placement_id(descriptor),
        '--source', 'cps', '--workspace', 'ws-test', '--attempt', '55555555-5555-4555-8555-555555555555',
        '--namespace', 'qa-ns', '--name', 'native-second-card-b-dddddddd',
        '--node', 'gpu-node', '--node-uid', '11111111-1111-4111-8111-111111111111',
        '--cap-mib', '10240', '--policy-hash', 'sha256:' + 'a' * 64,
    ]
    assert gate['env'] == [
        {'name': 'NVIDIA_VISIBLE_DEVICES', 'value': 'void'},
        {'name': 'CUDA_VISIBLE_DEVICES', 'value': ''},
        {'name': 'CPS_NATIVE_POD_UID', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.uid'}}},
        {'name': 'CPS_NATIVE_SPEC_SHA256', 'valueFrom': {'fieldRef': {'fieldPath': "metadata.annotations['cps.compute/native-spec-sha256']"}}},
    ]
    selection = m._selection_name(m._qa_placement_id(descriptor))
    assert {'name': 'cps-native-selection', 'configMap': {
        'name': selection, 'optional': True, 'defaultMode': 420,
    }} in result['pods']['b']['spec']['volumes']
    assert {'name': 'cps-native-selection', 'mountPath': '/run/cps-native-placement', 'readOnly': True} in gate['volumeMounts']
    assert identity['args'] == ['$(CPS_NATIVE_GPU_UUID)']
    assert identity['env'] == [
        {'name': 'NVIDIA_VISIBLE_DEVICES', 'value': 'k8s.device-plugin.nvidia.com/gpu=GPU-11111111-1111-4111-8111-111111111111'},
        {'name': 'CUDA_VISIBLE_DEVICES', 'value': '0'},
        {'name': 'CPS_NATIVE_GPU_UUID', 'valueFrom': {'configMapKeyRef': {'name': selection, 'key': 'gpu_uuid'}}},
    ]


def test_compose_rejects_non_pair_or_descriptor_mismatch():
    m = module()
    review = {'cohort_uid': 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
        'request': {'cohort_uid': 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
                    'namespace': 'qa-ns', 'policy_hash': 'sha256:' + 'a' * 64},
        'epoch': {'node_uid': '11111111-1111-4111-8111-111111111111'}, 'pods': {
        'a': pod('native-second-card-a-dddddddd', 5120),
        'b': pod('native-second-card-b-dddddddd', 10240),
    }}
    image = m.GATE_IMAGE
    with pytest.raises(ValueError, match='A/B'):
        m.compose({'cohort_uid': 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'pods': {'b': review['pods']['b']}}, qa_descriptor(), gate_image=image)
    wrong = qa_descriptor(name='another-pod')
    with pytest.raises(ValueError, match='QA descriptor'):
        m.compose(review, wrong, gate_image=image)


def test_compose_accepts_existing_native_second_card_renderer_output(tmp_path):
    spec = importlib.util.spec_from_file_location('second_card_test_prepare', HERE / 'test_prepare.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    prepared = fixture.module()
    observations = fixture.observations()
    generated = prepared.build_sources(observations)['files']
    renderer = prepared.load('selected_gate_test_renderer', generated['render_fixture.py'],
                             tmp_path / 'render_fixture.py')
    review = renderer.render(fixture.request(), approve_qa_hostpaths=True)
    original_identity_env = copy.deepcopy(review['pods']['b']['spec']['initContainers'][1]['env'])
    original_notebook_env = copy.deepcopy(review['pods']['b']['spec']['containers'][0].get('env', []))
    assert next(row['value'] for row in original_identity_env if row['name'] == 'NVIDIA_VISIBLE_DEVICES') == 'k8s.device-plugin.nvidia.com/gpu=' + observations['device']['gpu_uuid']
    assert next(row['value'] for row in original_identity_env if row['name'] == 'CUDA_VISIBLE_DEVICES') == '0'
    review['request']['cohort_uid'] = observations['cohort_uid']
    bmeta = review['pods']['b']['metadata']
    selected = qa_descriptor(observations['cohort_uid'], bmeta['name'])
    selected.update(namespace=bmeta['namespace'], node=observations['node']['metadata']['name'],
                    node_uid=observations['node']['metadata']['uid'],
                    policy_hash=observations['policy_hash'])

    result = module().compose(review, selected)

    assert result['pods']['a'] == review['pods']['a']
    gate = result['pods']['b']['spec']['initContainers'][0]
    assert gate['args'][0] == 'wait-for-selected-cap'
    assert gate['image'] == module().GATE_IMAGE
    assert result['selected_gate_delta']['scope'] == 'controlled-qa-only'
    assert result['selected_gate_delta']['production_authority'] is False
    assert result['selected_gate_delta']['launch_authorized'] is False
    identity_env = result['pods']['b']['spec']['initContainers'][1]['env']
    assert next(row for row in identity_env if row['name'] == 'NVIDIA_VISIBLE_DEVICES') == next(row for row in original_identity_env if row['name'] == 'NVIDIA_VISIBLE_DEVICES')
    assert next(row for row in identity_env if row['name'] == 'CUDA_VISIBLE_DEVICES') == next(row for row in original_identity_env if row['name'] == 'CUDA_VISIBLE_DEVICES')
    assert next(row for row in identity_env if row['name'] == 'CPS_NATIVE_GPU_UUID') == {'name': 'CPS_NATIVE_GPU_UUID', 'valueFrom': {'configMapKeyRef': {'name': module()._selection_name(result['selected_gate_delta']['placement_token']), 'key': 'gpu_uuid'}}}
    assert result['pods']['b']['spec']['containers'][0].get('env', []) == original_notebook_env
    assert not any(v.get('name') == 'qa-gate-package'
                   for v in result['pods']['b']['spec']['volumes'])


def test_composer_hash_matches_runtime_for_unicode_spec(tmp_path):
    spec = importlib.util.spec_from_file_location('second_card_test_prepare', HERE / 'test_prepare.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    prepared = fixture.module()
    observations = fixture.observations()
    generated = prepared.build_sources(observations)['files']
    renderer = prepared.load('selected_gate_unicode_hash_renderer', generated['render_fixture.py'],
                             tmp_path / 'render_fixture.py')
    request = fixture.request()
    request['cohort_uid'] = observations['cohort_uid']
    review = renderer.render(request, approve_qa_hostpaths=True)
    bmeta = review['pods']['b']['metadata']
    descriptor = qa_descriptor(observations['cohort_uid'], bmeta['name'])
    descriptor.update(namespace=bmeta['namespace'], node=observations['node']['metadata']['name'],
                      node_uid=observations['node']['metadata']['uid'], policy_hash=observations['policy_hash'])
    review['pods']['b']['spec']['containers'][0].setdefault('env', []).append(
        {'name': 'DISPLAY_LABEL', 'value': 'GPU Δ'})

    result = module().compose(review, descriptor)

    selected_b = result['pods']['b']
    assert selected_b['metadata']['annotations'][module().SPEC_ANNOTATION] == renderer.runtime.native_spec_sha256(selected_b)


def test_finalize_transformed_renderer_b_rebinds_exact_contract_and_hash(tmp_path):
    spec = importlib.util.spec_from_file_location('second_card_test_prepare', HERE / 'test_prepare.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    prepared = fixture.module()
    observations = fixture.observations()
    generated = prepared.build_sources(observations)['files']
    renderer = prepared.load('selected_gate_finalize_renderer', generated['render_fixture.py'],
                             tmp_path / 'render_fixture.py')
    request = fixture.request()
    request['cohort_uid'] = observations['cohort_uid']
    original = renderer.render(request, approve_qa_hostpaths=True)
    bmeta = original['pods']['b']['metadata']
    descriptor = qa_descriptor(observations['cohort_uid'], bmeta['name'])
    descriptor.update(namespace=bmeta['namespace'], node=observations['node']['metadata']['name'],
                      node_uid=observations['node']['metadata']['uid'], policy_hash=observations['policy_hash'])
    m = module()
    proposed = m.compose(original, descriptor)
    proposed_b = copy.deepcopy(proposed['pods']['b'])
    digest = renderer.runtime.native_spec_sha256(proposed_b)
    # A dry-run object is an offline API-shaped echo; no API call is made here.
    dryrun = copy.deepcopy(proposed_b)
    dryrun.update(apiVersion='v1', kind='Pod')

    finalized = m.finalize_transformed_b(renderer, request, original, descriptor, proposed, dryrun,
                                         approve_qa_hostpaths=True)

    assert finalized['spec_sha256'] == renderer.runtime.native_spec_sha256(finalized['pod'])
    assert finalized['pod']['metadata']['annotations'][m.SPEC_ANNOTATION] == digest
    assert finalized['intent'] is None
    assert finalized['production_authority'] is False
    actual = copy.deepcopy(finalized['pod'])
    actual.update(apiVersion='v1', kind='Pod')
    actual['metadata']['uid'] = '22222222-2222-4222-8222-222222222222'
    with_uid = m.finalize_transformed_b(renderer, request, original, descriptor, proposed, dryrun,
                                        actual=actual, approve_qa_hostpaths=True)
    assert with_uid['intent']['pod_uid'] == actual['metadata']['uid']
    actual['spec']['containers'][0]['image'] = 'tampered-after-admission'
    with pytest.raises(ValueError, match='actual admitted Pod'):
        m.finalize_transformed_b(renderer, request, original, descriptor, proposed, dryrun,
                                 actual=actual, approve_qa_hostpaths=True)
    tampered = copy.deepcopy(proposed)
    tampered['pods']['b']['spec']['containers'][0]['image'] = 'attacker/image'
    with pytest.raises(ValueError, match='descriptor regeneration'):
        m.finalize_transformed_b(renderer, request, original, descriptor, tampered, dryrun,
                                 approve_qa_hostpaths=True)


def test_cli_uses_explicit_files_and_creates_only_offline_output(tmp_path, capsys):
    import json
    m = module()
    review = {'cohort_uid': 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
              'request': {'cohort_uid': 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
                          'namespace': 'qa-ns', 'policy_hash': 'sha256:' + 'a' * 64},
              'epoch': {'node_uid': '11111111-1111-4111-8111-111111111111'},
              'pods': {'a': pod('native-second-card-a-dddddddd', 5120),
                       'b': pod('native-second-card-b-dddddddd', 10240)}}
    review_path = tmp_path / 'review.json'
    descriptor_path = tmp_path / 'qa-descriptor.json'
    output_path = tmp_path / 'review.selected.json'
    review_path.write_text(json.dumps(review))
    descriptor_path.write_text(json.dumps(qa_descriptor()))

    m.main(['--review-json', str(review_path), '--qa-descriptor-json', str(descriptor_path),
            '--output-json', str(output_path)])

    output = json.loads(output_path.read_text())
    status = json.loads(capsys.readouterr().out)
    assert status == {'prepared': True, 'scope': 'controlled-qa-only',
                      'production_authority': False, 'api_calls': False,
                      'gpu_calls': False, 'pair_preserved': True,
                      'launch_authorized': False}
    assert set(output['pods']) == {'a', 'b'} and output['pods']['a'] == review['pods']['a']
    assert 'uid' not in output['pods']['b']['metadata']
    assert 'selection_configmap' not in output
    assert output['selected_gate_delta']['production_authority'] is False
    with pytest.raises(FileExistsError):
        m.main(['--review-json', str(review_path), '--qa-descriptor-json', str(descriptor_path),
                '--output-json', str(output_path)])

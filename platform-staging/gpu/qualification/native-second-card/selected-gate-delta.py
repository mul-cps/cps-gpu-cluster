#!/usr/bin/env python3
"""Offline B selected-cap gate composer; no Kubernetes or native calls."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

GATE_IMAGE = 'ghcr.io/mul-cps/cps-compute@sha256:09c535b59fa9188e1942b0285632a6f3a1b1ced48211028cf8b1f2036157a6d5'
SELECTION_VOLUME = 'cps-native-selection'
SELECTION_DIRECTORY = '/run/cps-native-placement'
SPEC_ANNOTATION = 'cps.compute/native-spec-sha256'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _selection_name(placement_id):
    require(type(placement_id) is str and re.fullmatch(r'placement-[a-f0-9]{60}', placement_id),
            'Canonical current selected placement identifier required')
    token = hashlib.sha256(placement_id.encode()).hexdigest()[:32]
    return 'cps-native-' + token + '-selection'


def _qa_placement_id(descriptor):
    raw = json.dumps(descriptor, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return 'placement-' + hashlib.sha256(raw).hexdigest()[:60]


def compose(review, descriptor, *, gate_image=GATE_IMAGE):
    """Project a controlled-QA B gate from fresh observations, before Pod CREATE."""
    require(gate_image == GATE_IMAGE, 'Exact installed selected-cap gate image required')
    require(type(review) is dict and type(review.get('pods')) is dict
            and set(review['pods']) == {'a', 'b'}, 'Fresh A/B pair review required')
    fields = {'version', 'kind', 'cohort_uid', 'source', 'workspace', 'attempt',
              'namespace', 'name', 'node', 'node_uid', 'policy_hash'}
    require(type(descriptor) is dict and set(descriptor) == fields
            and descriptor.get('version') == 1
            and descriptor.get('kind') == 'controlled-qa-selected-gate/v1'
            and descriptor.get('source') in ('cps', 'cit')
            and all(type(descriptor.get(key)) is str and descriptor[key]
                    for key in fields - {'version', 'kind'}),
            'Closed controlled-QA descriptor from current operator observations required')
    require(re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', descriptor['attempt'])
            and re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', descriptor['node_uid'])
            and re.fullmatch(r'sha256:[0-9a-f]{64}', descriptor['policy_hash']),
            'Current QA attempt, node UID, and policy required')
    placement_id = _qa_placement_id(descriptor)
    node, node_uid = descriptor['node'], descriptor['node_uid']

    result = copy.deepcopy(review)
    b = result['pods']['b']
    meta = b.get('metadata', {})
    spec = b.get('spec', {})
    require('uid' not in meta and 'deletionTimestamp' not in meta,
            'Only an uncreated B Pod template may be composed offline')
    try:
        cohort = str(uuid.UUID(result.get('request', {}).get('cohort_uid', result.get('cohort_uid', ''))))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Fresh canonical A/B cohort UID required') from None
    require(cohort == result.get('request', {}).get('cohort_uid', result.get('cohort_uid'))
            and cohort != str(uuid.UUID(int=0))
            and descriptor['cohort_uid'] == cohort
            and descriptor['node_uid'] == result.get('epoch', {}).get('node_uid')
            and descriptor['policy_hash'] == result.get('request', {}).get('policy_hash')
            and descriptor['namespace'] == result.get('request', {}).get('namespace')
            and spec.get('nodeName') == descriptor['node']
            and result['pods']['a'].get('metadata', {}).get('name') == 'native-second-card-a-' + cohort[:8]
            and meta.get('name') == 'native-second-card-b-' + cohort[:8],
            'A/B pods must retain the same fresh cohort identity')
    require(meta.get('namespace') == descriptor['namespace'] and meta.get('name') == descriptor['name'],
            'QA descriptor namespace/name differs from the fresh A/B review')
    init = spec.get('initContainers')
    require(type(init) is list and len(init) >= 2
            and init[0].get('name') == 'cps-native-cap-gate'
            and init[1].get('name') == 'cps-native-device-identity',
            'Reviewed gate and post-cap identity init sequence required')
    gate, identity = init[0], init[1]

    volumes = spec.get('volumes')
    require(type(volumes) is list and not any(v.get('name') == SELECTION_VOLUME for v in volumes),
            'Unprojected selected-volume slot required')
    selection_name = _selection_name(placement_id)
    volumes.append({'name': SELECTION_VOLUME, 'configMap': {
        'name': selection_name, 'optional': True, 'defaultMode': 420,
    }})

    mounts = gate.get('volumeMounts')
    require(type(mounts) is list, 'Reviewed gate mounts required')
    package_mounts = [m for m in mounts if m.get('name') == 'qa-gate-package']
    package_volumes = [v for v in volumes if v.get('name') == 'qa-gate-package']
    require(len(package_mounts) == 1 and package_mounts[0].get('mountPath') == '/opt/cps-qa'
            and len(package_volumes) == 1,
            'Exact legacy QA source overlay required before using installed image runtime')
    mounts.remove(package_mounts[0])
    volumes.remove(package_volumes[0])

    gate['image'] = gate_image
    gate['command'] = ['python', '-m', 'cps_compute.native_gpu_runtime']
    gate['args'] = ['wait-for-selected-cap', '--placement-id', placement_id,
        '--source', descriptor['source'], '--workspace', descriptor['workspace'],
        '--attempt', descriptor['attempt'], '--namespace', descriptor['namespace'],
        '--name', descriptor['name'], '--node', node, '--node-uid', node_uid,
        '--cap-mib', '10240', '--policy-hash', descriptor['policy_hash']]
    gate['env'] = [
        {'name': 'NVIDIA_VISIBLE_DEVICES', 'value': 'void'},
        {'name': 'CUDA_VISIBLE_DEVICES', 'value': ''},
        {'name': 'CPS_NATIVE_POD_UID', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.uid'}}},
        {'name': 'CPS_NATIVE_SPEC_SHA256', 'valueFrom': {'fieldRef': {
            'fieldPath': "metadata.annotations['" + SPEC_ANNOTATION + "']"}}},
    ]
    mounts.append({'name': SELECTION_VOLUME, 'mountPath': SELECTION_DIRECTORY,
                   'readOnly': True})

    identity['args'] = ['$(CPS_NATIVE_GPU_UUID)']
    identity_env = identity.get('env')
    require(type(identity_env) is list
            and len([e for e in identity_env if e.get('name') == 'NVIDIA_VISIBLE_DEVICES']) == 1
            and len([e for e in identity_env if e.get('name') == 'CUDA_VISIBLE_DEVICES']) == 1
            and not any(e.get('name') == 'CPS_NATIVE_GPU_UUID' for e in identity_env),
            'Original CDI selection and CUDA identity environment required')
    nvidia = next(e for e in identity_env if e.get('name') == 'NVIDIA_VISIBLE_DEVICES')
    cuda = next(e for e in identity_env if e.get('name') == 'CUDA_VISIBLE_DEVICES')
    require(type(nvidia.get('value')) is str and nvidia['value'].startswith('k8s.device-plugin.nvidia.com/gpu=')
            and cuda == {'name': 'CUDA_VISIBLE_DEVICES', 'value': '0'},
            'Original CDI-qualified GPU and CUDA identity must remain intact')
    identity_env.append({'name': 'CPS_NATIVE_GPU_UUID', 'valueFrom': {'configMapKeyRef': {
        'name': selection_name, 'key': 'gpu_uuid'}}})
    result['selected_gate_delta'] = {
        'scope': 'controlled-qa-only', 'production_authority': False,
        'placement_token': placement_id,
        'selection_projection': 'deferred-until-actual-pod-uid-and-spec-readback',
        'launch_authorized': False,
    }
    # The projected Pod UID/spec field refs must see the transformed admitted spec.
    # This is an offline proposal hash; finalization rechecks it against dry-run.
    result['pods']['b']['metadata'].setdefault('annotations', {})[SPEC_ANNOTATION] = hashlib.sha256(
        json.dumps(result['pods']['b']['spec'], sort_keys=True, separators=(',', ':'),
                   ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()
    return result


def finalize_transformed_b(renderer, request, original_review, descriptor, proposed_review, dryrun,
                           *, actual=None, approve_qa_hostpaths=False):
    """Finalize only this exact offline B transformation through its reviewed source contract."""
    require(renderer.render(request, approve_qa_hostpaths=approve_qa_hostpaths) == original_review,
            'Original renderer review changed before selected-gate finalization')
    expected = compose(original_review, descriptor)
    require(proposed_review == expected, 'Selected-gate proposal differs from exact descriptor regeneration')
    _, _, contracts = renderer._contracts(request, approve_qa_hostpaths=approve_qa_hostpaths)
    base = contracts.get('b')
    require(base is not None and base.pod == original_review['pods']['b'],
            'Original renderer B binding and cap contract required')
    pod = copy.deepcopy(expected['pods']['b'])
    digest = renderer.runtime.native_spec_sha256(pod)
    require(pod['metadata'].get('annotations', {}).get(SPEC_ANNOTATION) == digest,
            'Selected-gate spec digest must match transformed spec')
    contract = renderer.runtime.NativePodContract(
        pod, base.binding, base.cap_mib, digest, qualification=base.qualification)
    finalized = renderer.runtime.finalize_native_admitted_pod(contract, dryrun)
    intent = None
    if actual is not None:
        require(type(actual) is dict and actual.get('apiVersion') == 'v1' and actual.get('kind') == 'Pod'
                and actual.get('metadata', {}).get('namespace') == finalized.binding.namespace
                and actual['metadata'].get('name') == finalized.binding.name
                and not actual['metadata'].get('deletionTimestamp')
                and renderer.runtime.native_spec_sha256(actual) == finalized.spec_sha256,
                'Exact actual admitted Pod identity and full spec readback required')
        intent = finalized.intent_for_pod_uid(actual['metadata'].get('uid'))
    return {'version': 1, 'pod': finalized.pod, 'spec_sha256': finalized.spec_sha256,
            'intent': intent, 'live_applied': False, 'hardware_qualified': False,
            'production_authority': False}


def _read_json(path, limit):
    raw = Path(path).read_bytes()
    require(0 < len(raw) <= limit, 'Bounded nonempty offline input required')
    return json.loads(raw)


def _write_new(path, value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__ + ' This output is never production placement authority.')
    parser.add_argument('--review-json', type=Path, required=True,
                        help='Existing fresh A/B review.json from native-second-card prepare.py')
    parser.add_argument('--qa-descriptor-json', type=Path, required=True,
                        help='Closed controlled-QA descriptor built from fresh operator observations; not a production claim')
    parser.add_argument('--output-json', type=Path, required=True,
                        help='New path; must not already exist')
    args = parser.parse_args(argv)
    review = _read_json(args.review_json, 1048576)
    descriptor = _read_json(args.qa_descriptor_json, 65536)
    result = compose(review, descriptor)
    _write_new(args.output_json, result)
    print(json.dumps({'prepared': True, 'scope': 'controlled-qa-only',
                      'production_authority': False, 'api_calls': False,
                      'gpu_calls': False, 'pair_preserved': True,
                      'launch_authorized': False}))


if __name__ == '__main__':
    main()

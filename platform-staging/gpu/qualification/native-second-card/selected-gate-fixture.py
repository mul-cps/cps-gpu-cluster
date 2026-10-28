#!/usr/bin/env python3
"""Build an offline controlled-QA selected-cap ConfigMap after Pod readback."""
import copy
import hashlib
import json
import re
import uuid

PROTOCOL = 'cps-native-selected-placement/v1'
SPEC_ANNOTATION = 'cps.compute/native-spec-sha256'
PHYSICAL_FIELDS = {'node', 'node_uid', 'boot_id', 'driver_generation', 'gpu_uuid'}
REFERENCE_FIELDS = {'namespace', 'name', 'uid', 'resourceVersion', 'data_sha256', 'key'}
STATIC_FIELDS = {'placement_id', 'source', 'workspace', 'attempt', 'namespace',
                 'name', 'node', 'node_uid', 'cap_mib', 'policy_hash'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def _name(value):
    require(type(value) is str and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', value),
            'Canonical Kubernetes identifier required')


def _uuid(value):
    require(type(value) is str, 'Canonical UUID required')
    try:
        require(str(uuid.UUID(value)) == value, 'Canonical UUID required')
    except ValueError:
        raise ValueError('Canonical UUID required') from None


def _gpu(value):
    require(type(value) is str and value.startswith('GPU-'), 'Bound full GPU UUID required')
    _uuid(value[4:])


def _reference(value):
    require(type(value) is dict and set(value) == REFERENCE_FIELDS,
            'Observed immutable QA qualification reference required')
    _name(value['namespace']); _name(value['name']); _uuid(value['uid'])
    require(type(value['resourceVersion']) is str
            and re.fullmatch(r'[1-9][0-9]*', value['resourceVersion']),
            'Canonical immutable qualification resourceVersion required')
    require(type(value['data_sha256']) is str
            and re.fullmatch(r'sha256:[0-9a-f]{64}', value['data_sha256'])
            and value['data_sha256'] != 'sha256:' + '0' * 64,
            'Immutable qualification data digest required')
    require(type(value['key']) is str and len(value['key']) <= 253
            and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*', value['key']),
            'Safe qualification data key required')


def _spec_sha256(pod):
    require(type(pod) is dict and type(pod.get('spec')) is dict, 'Final Pod spec required')
    return hashlib.sha256(_canonical(pod['spec']).encode()).hexdigest()


def _selection_name(placement_id):
    require(type(placement_id) is str
            and re.fullmatch(r'placement-[a-f0-9]{60}', placement_id),
            'Canonical controlled-QA placement token required')
    token = hashlib.sha256(placement_id.encode()).hexdigest()[:32]
    return 'cps-native-' + token + '-selection'


def _descriptor_placement_id(descriptor):
    raw = _canonical(descriptor).encode()
    return 'placement-' + hashlib.sha256(raw).hexdigest()[:60]


def build_selected_fixture(review, descriptor, actual_pod, qualification_ref, physical):
    """Return an immutable ConfigMap proposal bound to actual admitted B identity.

    The QA qualification reference is copied verbatim from current observations;
    this fixture builder confers no production placement or qualification authority.
    """
    require(type(review) is dict and type(review.get('pods')) is dict
            and set(review['pods']) == {'a', 'b'}, 'Fresh selected-gate A/B review required')
    delta = review.get('selected_gate_delta')
    require(type(delta) is dict and delta.get('scope') == 'controlled-qa-only'
            and delta.get('production_authority') is False
            and delta.get('selection_projection') == 'deferred-until-actual-pod-uid-and-spec-readback',
            'Controlled-QA offline selected-gate proposal required')
    placement_id = delta.get('placement_token')
    selection_name = _selection_name(placement_id)

    require(type(descriptor) is dict and descriptor.get('version') == 1
            and descriptor.get('kind') == 'controlled-qa-selected-gate/v1',
            'Controlled-QA descriptor required')
    expected_fields = {'version', 'kind', 'cohort_uid', 'source', 'workspace', 'attempt',
                       'namespace', 'name', 'node', 'node_uid', 'policy_hash'}
    require(set(descriptor) == expected_fields and descriptor['source'] in ('cps', 'cit'),
            'Closed controlled-QA descriptor required')
    require(placement_id == _descriptor_placement_id(descriptor),
            'Placement token does not match the exact controlled-QA descriptor')
    _reference(qualification_ref)
    require(type(physical) is dict and set(physical) == PHYSICAL_FIELDS,
            'Closed fresh physical-device observation required')
    for field in ('node', 'node_uid'):
        require(physical[field] == descriptor[field], 'Physical observation and QA node binding disagree')
    _uuid(physical['node_uid'])
    _uuid(physical['boot_id'])
    _uuid(physical['driver_generation'])
    _gpu(physical['gpu_uuid'])
    _name(descriptor['namespace'])
    _name(descriptor['name'])
    _name(descriptor['node'])
    _uuid(descriptor['attempt'])
    _uuid(descriptor['node_uid'])
    _uuid(descriptor['cohort_uid'])
    require(uuid.UUID(descriptor['cohort_uid']).int > 0,
            'Nonzero fresh QA cohort required')
    require(re.fullmatch(r'sha256:[0-9a-f]{64}', descriptor['policy_hash']) is not None,
            'Version-bound QA policy hash required')

    requested = review.get('request', {})
    epoch = review.get('epoch', {})
    require(type(requested) is dict
            and requested.get('cohort_uid') == descriptor['cohort_uid']
            and requested.get('namespace') == descriptor['namespace']
            and requested.get('policy_hash') == descriptor['policy_hash']
            and type(epoch) is dict and epoch.get('node_uid') == descriptor['node_uid'],
            'Descriptor differs from the original reviewed QA request')
    b = review['pods']['b']
    bmeta = b.get('metadata', {})
    require(bmeta.get('namespace') == descriptor['namespace']
            and bmeta.get('name') == descriptor['name'],
            'Descriptor differs from reviewed B identity')
    proposed_hash = _spec_sha256(b)
    require(bmeta.get('annotations', {}).get(SPEC_ANNOTATION) == proposed_hash,
            'Reviewed B spec annotation is not its full spec digest')

    require(type(actual_pod) is dict and actual_pod.get('apiVersion') == 'v1'
            and actual_pod.get('kind') == 'Pod', 'Actual API Pod readback required')
    meta = actual_pod.get('metadata', {})
    require(not meta.get('deletionTimestamp')
            and meta.get('namespace') == descriptor['namespace']
            and meta.get('name') == descriptor['name'],
            'Actual admitted B namespace/name mismatch or deletion in progress')
    pod_uid = meta.get('uid')
    _uuid(pod_uid)
    actual_hash = _spec_sha256(actual_pod)
    annotation_hash = meta.get('annotations', {}).get(SPEC_ANNOTATION)
    require(type(annotation_hash) is str and re.fullmatch(r'[0-9a-f]{64}', annotation_hash)
            and annotation_hash == actual_hash == proposed_hash,
            'Actual admitted B spec differs from reviewed annotated spec')
    require(actual_pod.get('spec', {}).get('nodeName') == descriptor['node'],
            'Actual admitted B is not bound to the reviewed node')
    init = actual_pod['spec'].get('initContainers')
    require(type(init) is list and len(init) >= 2
            and init[0].get('name') == 'cps-native-cap-gate'
            and init[1].get('name') == 'cps-native-device-identity',
            'Actual admitted B retained the ordered cap and device identity gates')
    identity_env = init[1].get('env')
    require(type(identity_env) is list, 'Actual B device identity environment required')
    selectors = [entry.get('value') for entry in identity_env
                 if entry.get('name') == 'NVIDIA_VISIBLE_DEVICES']
    cuda = [entry for entry in identity_env if entry.get('name') == 'CUDA_VISIBLE_DEVICES']
    require(len(selectors) == 1
            and selectors[0] == 'k8s.device-plugin.nvidia.com/gpu=' + physical['gpu_uuid']
            and cuda == [{'name': 'CUDA_VISIBLE_DEVICES', 'value': '0'}],
            'Actual CDI-qualified B device differs from the fresh physical UUID')

    document = {
        'protocol': PROTOCOL,
        'placement_id': placement_id,
        'source': descriptor['source'],
        'workspace': descriptor['workspace'],
        'attempt': descriptor['attempt'],
        'namespace': descriptor['namespace'],
        'name': descriptor['name'],
        'node': descriptor['node'],
        'node_uid': descriptor['node_uid'],
        'cap_mib': 10240,
        'policy_hash': descriptor['policy_hash'],
        'pod_uid': pod_uid,
        'spec_sha256': actual_hash,
        'gpu_uuid': physical['gpu_uuid'],
        'selected_placement': {
            'node': physical['node'],
            'node_uid': physical['node_uid'],
            'boot_id': physical['boot_id'],
            'driver_generation': physical['driver_generation'],
            'gpu_uuid': physical['gpu_uuid'],
            'qualification_ref': copy.deepcopy(qualification_ref),
        },
    }
    # Validate exactly what the selected-cap gate will parse, using its SDK code.
    require(set(document) == STATIC_FIELDS | {
        'protocol', 'pod_uid', 'spec_sha256', 'gpu_uuid', 'selected_placement'},
        'Closed selected-placement document required')
    require(type(document['cap_mib']) is int and document['cap_mib'] == 10240,
            'Controlled B cap must be 10,240 MiB')
    require(type(document['spec_sha256']) is str
            and re.fullmatch(r'[0-9a-f]{64}', document['spec_sha256']),
            'Actual full admitted spec digest required')
    selected = document['selected_placement']
    require(type(selected) is dict and set(selected) == PHYSICAL_FIELDS | {'qualification_ref'},
            'Closed selected qualified-device binding required')
    _reference(selected['qualification_ref'])
    configmap = {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {'namespace': descriptor['namespace'], 'name': selection_name},
        'immutable': True,
        'data': {'selected.json': _canonical(document), 'gpu_uuid': physical['gpu_uuid']},
    }
    return {
        'version': 1,
        'scope': 'controlled-qa-only',
        'live_applied': False,
        'hardware_qualified': False,
        'production_authority': False,
        'configmap': configmap,
    }

#!/usr/bin/env python3
"""Emit a disabled, isolated KAI quota-ConfigMap admission candidate.

Reviewed upstream code creates empty capabilities/evar maps, adds the selected
GPU, adds both portion aliases, then adds the HAMi limit. Same-owner empty upsert
retries preserve populated data. Owner replacement and reassignment are denied.
Explicitly registered binder rollback deletion is allowed; no garbage-collector
identity or live controller request identity is inferred from upstream source.

No namespace, RBAC, workload, deployment or live admission operation is emitted.
Kubernetes type checking, request attribution, retries and cleanup remain gates.
"""
import argparse
import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

KAI_COMMIT = 'bdf434e5e9201cccf4e05fad04d814363653f692'
KAI_TAG = 'v0.18.1'
SOURCE_FILES = {
    'pkg/binder/common/gpusharingconfigmap/config_map.go': '7133a370614f17b1ccfb88a01a1208ea4b2a62650ef4f6856a87b75ba7df7e30',
    'pkg/binder/common/gpu_access.go': 'af660f2812c6c06bc82a848c1180600471aa92220922efa8e1b71d1a6aa87612',
    'pkg/binder/plugins/gpusharing/gpu_sharing.go': 'c878c833d8f2785ddfd89eccafb22c08c1d8d92e12ac9a43e41da26f10c89e88',
    'pkg/binder/plugins/hamicore/hami_core.go': '337b84c939a36060990fb9b70c1e5223133444a5bc56da55575ab827a787f60f',
}
UID_PATTERN = '[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
GPU_PATTERN = 'GPU-' + UID_PATTERN
CDI_PREFIX = 'k8s.device-plugin.nvidia.com/gpu='
VISIBLE_DEVICES_PATTERN = '(?:' + GPU_PATTERN + '|k8s\\.device-plugin\\.nvidia\\.com/gpu=(?:' + GPU_PATTERN + '|(?:[0-9]|[12][0-9]|3[01])))'
PHYSICAL_MEMORY_PATTERN = '(?:[1-9][0-9]{0,4}|1[0-2][0-9]{4}|130[0-9]{3}|1310[0-6][0-9]|13107[0-2])'
DNS_PATTERN = '[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?'
NAMESPACE_PATTERN = 'cps-dynamic-admission-[a-z0-9](?:[a-z0-9-]*[a-z0-9])?'
ACTOR_PATTERN = 'system:serviceaccount:[a-z0-9-]+:[a-z0-9.-]+'
FIELDS = {'namespace', 'name', 'type', 'podName', 'podUid', 'gpuUuid', 'visibleDevices',
          'physicalGpuMemoryMiB', 'gpuPortion', 'runaiNumOfGpus', 'cudaDeviceMemoryLimit'}
LIMITATIONS = [
    'Offline candidate only; Kubernetes v1.34 CEL type checking and real admission requests are unqualified',
    'Exact Pod/ConfigMap names, UIDs, GPU and quotas must be independently reviewed; source code is not live identity or image attestation',
    'visibleDevices must be the actual observed single-device selection; numeric CDI index-to-physical-gpuUuid mapping requires independent review and is never inferred from its syntax',
    'physicalGpuMemoryMiB attests the reviewed node-advertised GPU-memory label, not a fresh physical-memory measurement; the injected HAMi quota truncates float64(label) * float64(received portion) and may exceed the separate strict nominal notebook limit',
    'Literal CEL interpreter tests do not establish Kubernetes CEL conformance, retry races, or API defaulting',
    'The cached cel-python engine rounds int(double), whereas KAI and Kubernetes CEL truncate; positive-floor arithmetic explicitly handles either conversion without an interpreter shim',
    'Different-owner replacement, GPU reassignment, quota resets, and unregistered ConfigMaps are intentionally denied',
    'Source same-owner empty upsert preserves existing data; a literal populated-to-empty reset is denied',
    'Binder rollback deletion requires a registered exact Pod-owned map and explicit writer; garbage collection needs a separately reviewed writer',
    'Parameters are a protected manual qualification registry; no production registry synchronization or writer RBAC is deployed',
]


def literal(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False)


def all_of(values):
    return ' && '.join('(' + value + ')' for value in values)


def quota_integer_expression(record):
    product = 'double(' + record + '.physicalGpuMemoryMiB) * double(' + record + '.gpuPortion)'
    converted = 'int(' + product + ')'
    # CEL int(double) is specified to truncate. The cached interpreter rounds;
    # this positive-floor correction has the same answer under both behaviors.
    return converted + ' - (double(' + converted + ') > (' + product + ') ? 1 : 0)'


def quota_expression(record):
    return 'string(' + quota_integer_expression(record) + ") + 'm'"


def verify_source_trace(directory):
    root = Path(directory)
    manifest = json.loads((root / 'source-manifest.json').read_text())
    if manifest['repositories']['kai']['commit'] != KAI_COMMIT:
        raise ValueError('Reviewed KAI source commit required')
    receipts = {entry['path']: entry for entry in manifest['files']}
    for filename, expected in SOURCE_FILES.items():
        path = 'kai/' + filename
        if (hashlib.sha256((root / path).read_bytes()).hexdigest() != expected
                or receipts[path]['sha256'] != expected or receipts[path]['treeShaMatch'] is not True):
            raise ValueError('Reviewed official source bytes/tree receipt changed')
    return hashlib.sha256((root / 'source-manifest.json').read_bytes()).hexdigest()


def reviewed_records(namespace, records):
    if not isinstance(records, (list, tuple)) or len(records) > 64:
        raise ValueError('At most 64 explicit ConfigMap records are permitted')
    seen = set()
    result = []
    for record in records:
        if not isinstance(record, dict) or set(record) - {'cmUid'} != FIELDS:
            raise ValueError('Exact reviewed per-ConfigMap record fields required')
        if (record['namespace'] != namespace or record['type'] not in ('capabilities', 'evar')
                or any(not isinstance(record[key], str) or len(record[key]) > 253
                       or not re.fullmatch(DNS_PATTERN, record[key]) for key in ('name', 'podName'))
                or not isinstance(record['podUid'], str) or not re.fullmatch(UID_PATTERN, record['podUid'])
                or not isinstance(record['gpuUuid'], str) or not re.fullmatch(GPU_PATTERN, record['gpuUuid'])
                or ('cmUid' in record and (not isinstance(record['cmUid'], str)
                                          or not re.fullmatch(UID_PATTERN, record['cmUid'])))):
            raise ValueError('Exact namespace, canonical names, Pod UID and physical GPU required')
        visible = record['visibleDevices']
        if (not isinstance(visible, str) or not re.fullmatch(VISIBLE_DEVICES_PATTERN, visible)
                or (visible.startswith('GPU-') and visible != record['gpuUuid'])
                or (visible.startswith(CDI_PREFIX + 'GPU-') and visible != CDI_PREFIX + record['gpuUuid'])):
            raise ValueError('One exact reviewed GPU UUID or CDI selection required; index correspondence is an independent review gate')
        portion = record['gpuPortion']
        limit = record['cudaDeviceMemoryLimit']
        memory = record['physicalGpuMemoryMiB']
        if not isinstance(memory, str) or not re.fullmatch(PHYSICAL_MEMORY_PATTERN, memory):
            raise ValueError('Canonical reviewed node-advertised GPU memory in 1..131072 MiB required')
        try:
            valid_portion = (isinstance(portion, str) and re.fullmatch(r'(?:0\.[0-9]{1,8}|1)', portion)
                             and 0 < Decimal(portion) <= 1)
        except InvalidOperation:
            valid_portion = False
        if (not valid_portion or record['runaiNumOfGpus'] != portion or not isinstance(limit, str)
                or not re.fullmatch('[1-9][0-9]{0,4}m', limit) or not 0 < int(limit[:-1]) <= 40960):
            raise ValueError('Exact positive bounded GPU portion aliases and MiB quota required')
        # Match the reviewed Go ParseInt/ParseFloat -> float64 multiply ->
        # int64 truncation. Decimal multiplication would not reproduce it.
        if limit != str(int(float(memory) * float(portion))) + 'm':
            raise ValueError('HAMi quota must equal truncation of the advertised memory label times received portion')
        key = (record['namespace'], record['name'])
        if key in seen:
            raise ValueError('Duplicate ConfigMap namespace/name records are forbidden')
        seen.add(key)
        result.append(copy.deepcopy(record))
    return result


def _owner(path):
    return all_of([
        'has(' + path + '.metadata)', 'has(' + path + '.metadata.ownerReferences)',
        'size(' + path + '.metadata.ownerReferences) == 1',
        path + '.metadata.ownerReferences.all(o, ' + all_of([
            'has(o.apiVersion)', "o.apiVersion == 'v1'", 'has(o.kind)', "o.kind == 'Pod'",
            'has(o.name)', 'o.name == variables.record.podName', 'has(o.uid)',
            'o.uid == variables.record.podUid', '!has(o.controller) || !o.controller',
            '!has(o.blockOwnerDeletion) || !o.blockOwnerDeletion']) + ')'])


def _stage(data):
    return ("size(" + data + ") == 0 ? 0 : " + data + " == variables.stages[1] ? 1 : " +
            data + " == variables.stages[2] ? 2 : " + data + " == variables.stages[3] ? 3 : -1")


def build(*, namespace='cps-dynamic-admission-review', writers=(), records=()):
    if not isinstance(namespace, str) or len(namespace) > 63 or not re.fullmatch(NAMESPACE_PATTERN, namespace):
        raise ValueError('Only a separate cps-dynamic-admission-* qualification namespace is permitted')
    if (not isinstance(writers, (list, tuple)) or len(writers) > 8 or len(set(writers)) != len(writers)
            or any(not isinstance(actor, str) or not re.fullmatch(ACTOR_PATTERN, actor) for actor in writers)):
        raise ValueError('At most eight distinct explicitly reviewed service-account identities required')
    records = reviewed_records(namespace, records)
    group = namespace + '.compute.cps.unileoben.ac.at'
    name = namespace + '-quota'
    annotations = {'compute.cps.unileoben.ac.at/qualification-state': 'disabled-offline-candidate',
        'compute.cps.unileoben.ac.at/kai-source': KAI_COMMIT,
        'compute.cps.unileoben.ac.at/source-files-sha256': hashlib.sha256(literal(SOURCE_FILES).encode()).hexdigest()}
    selector = {'matchLabels': {'kubernetes.io/metadata.name': namespace}}
    variables = [
        {'name': 'subject', 'expression': "request.operation == 'DELETE' ? oldObject : object"},
        {'name': 'records', 'expression': "has(variables.subject.metadata) && "
            "has(variables.subject.metadata.name) ? params.records.filter(r, r.namespace == request.namespace && "
            "r.name == variables.subject.metadata.name) : []"},
        {'name': 'record', 'expression': 'size(variables.records) == 1 ? variables.records[0] : {}'},
        {'name': 'data', 'expression': 'has(variables.subject.data) ? variables.subject.data : {}'},
        {'name': 'oldData', 'expression': 'has(oldObject.data) ? oldObject.data : {}'},
        {'name': 'stages', 'expression': "size(variables.records) == 1 ? [{}, "
            "{'NVIDIA_VISIBLE_DEVICES': variables.record.visibleDevices}, "
            "{'NVIDIA_VISIBLE_DEVICES': variables.record.visibleDevices, 'GPU_PORTION': variables.record.gpuPortion, "
            "'RUNAI_NUM_OF_GPUS': variables.record.runaiNumOfGpus}, "
            "{'NVIDIA_VISIBLE_DEVICES': variables.record.visibleDevices, 'GPU_PORTION': variables.record.gpuPortion, "
            "'RUNAI_NUM_OF_GPUS': variables.record.runaiNumOfGpus, "
            "'CUDA_DEVICE_MEMORY_LIMIT': variables.record.cudaDeviceMemoryLimit}] : [{},{},{},{}]"},
        {'name': 'stage', 'expression': _stage('variables.data')},
        {'name': 'oldStage', 'expression': '!has(oldObject.metadata) ? -1 : (' + _stage('variables.oldData') + ')'},
    ]
    validations = []
    def rule(expression, message):
        validations.append({'expression': expression, 'message': message})
    rule('request.namespace == ' + literal(namespace), 'Only the isolated qualification namespace is in scope')
    rule("request.operation in ['CREATE','UPDATE','DELETE']", 'Only the explicitly modelled ConfigMap operations are permitted')
    rule('has(request.userInfo) && has(request.userInfo.username) && request.userInfo.username in params.writers',
         'Every ConfigMap mutation requires an explicitly reviewed authenticated writer')
    rule('size(variables.records) == 1 && has(variables.record.name)',
         'Every ConfigMap name requires an explicit reviewed record; labels cannot authorize writes')
    rule(all_of(['has(variables.record.physicalGpuMemoryMiB)',
        "variables.record.physicalGpuMemoryMiB.matches('^" + PHYSICAL_MEMORY_PATTERN + "$')",
        'has(variables.record.gpuPortion)',
        "variables.record.gpuPortion.matches('^(?:0\\\\.[0-9]{1,8}|1)$')",
        'double(variables.record.gpuPortion) > 0', 'double(variables.record.gpuPortion) <= 1',
        'has(variables.record.runaiNumOfGpus)', 'variables.record.runaiNumOfGpus == variables.record.gpuPortion',
        'has(variables.record.cudaDeviceMemoryLimit)',
        "variables.record.cudaDeviceMemoryLimit.matches('^(?:[1-9][0-9]{0,3}|[1-3][0-9]{4}|40[0-8][0-9]{2}|409[0-5][0-9]|40960)m$')",
        'variables.record.cudaDeviceMemoryLimit == ' + quota_expression('variables.record')]),
        'The injected quota must match the reviewed bounded node-memory label and upstream float64 truncation')
    rule(all_of(['has(variables.subject.apiVersion)', "variables.subject.apiVersion == 'v1'",
        'has(variables.subject.kind)', "variables.subject.kind == 'ConfigMap'", 'has(variables.subject.metadata)',
        'has(variables.subject.metadata.name)', 'variables.subject.metadata.name == variables.record.name',
        'has(variables.subject.metadata.namespace)', 'variables.subject.metadata.namespace == variables.record.namespace',
        'variables.subject.metadata.namespace == request.namespace']), 'The exact registered namespace/name is required')
    rule(_owner('variables.subject'), 'Exactly the reviewed non-controller v1 Pod owner must remain attached')
    rule('!has(variables.subject.binaryData) && !has(variables.subject.immutable)',
         'Binary data and immutable quota ConfigMaps are outside the reviewed contract')
    rule("(variables.record.type == 'evar' && size(variables.data) == 0) || "
         "(variables.record.type == 'capabilities' && variables.stage >= 0)",
         'Only the exact reviewed empty evar or staged capabilities values are permitted')
    rule("request.operation != 'CREATE' || (oldObject == null && size(variables.data) == 0 && !has(variables.record.cmUid))",
         'Creation begins empty and cannot recreate an already UID-bound map')
    identity = all_of(['has(oldObject.metadata)', 'has(oldObject.metadata.uid)',
        "oldObject.metadata.uid.matches('^" + UID_PATTERN + "$')", 'has(object.metadata)',
        'has(object.metadata.uid)', 'object.metadata.uid == oldObject.metadata.uid',
        'has(oldObject.metadata.name)', 'object.metadata.name == oldObject.metadata.name',
        'has(oldObject.metadata.namespace)', 'object.metadata.namespace == oldObject.metadata.namespace',
        'has(oldObject.metadata.ownerReferences)', 'object.metadata.ownerReferences == oldObject.metadata.ownerReferences',
        '!has(oldObject.binaryData)', '!has(oldObject.immutable)',
        '!has(variables.record.cmUid) || object.metadata.uid == variables.record.cmUid'])
    rule("request.operation != 'UPDATE' || (" + identity + ')',
         'Updates preserve the observed ConfigMap UID, name, namespace and exact owner references')
    rule("request.operation != 'UPDATE' || ((variables.record.type == 'evar' && size(variables.oldData) == 0) || "
         "(variables.record.type == 'capabilities' && variables.oldStage >= 0 && variables.stage >= variables.oldStage && "
         'variables.stage <= variables.oldStage + 1))',
         'Same-stage retries or one forward population step are allowed; reset, removal and skipped stages are denied')
    rule("request.operation != 'DELETE' || (has(oldObject.metadata) && has(oldObject.metadata.uid) && "
         "oldObject.metadata.uid.matches('^" + UID_PATTERN + "$') && "
         '(!has(variables.record.cmUid) || oldObject.metadata.uid == variables.record.cmUid))',
         'Reviewed binder rollback uses the exact old Pod-owned ConfigMap and optional independently pinned ConfigMap UID')
    policy = {'apiVersion': 'admissionregistration.k8s.io/v1', 'kind': 'ValidatingAdmissionPolicy',
        'metadata': {'name': name, 'annotations': copy.deepcopy(annotations)},
        'spec': {'failurePolicy': 'Fail', 'paramKind': {'apiVersion': group + '/v1alpha1', 'kind': 'DynamicGpuQuotaPolicy'},
            'matchConstraints': {'matchPolicy': 'Exact', 'namespaceSelector': copy.deepcopy(selector),
                'resourceRules': [{'apiGroups': [''], 'apiVersions': ['v1'], 'resources': ['configmaps'],
                    'operations': ['CREATE', 'UPDATE', 'DELETE'], 'scope': 'Namespaced'}]},
            'variables': variables, 'validations': validations}}
    # CEL's schema cost estimator does not derive bounds from regex patterns.
    # Keep every string explicitly bounded to the same reviewed wire format.
    maximum_lengths = {'namespace': 63, 'name': 253, 'type': 12, 'podName': 253,
        'podUid': 36, 'cmUid': 36, 'gpuUuid': 40,
        'visibleDevices': len(CDI_PREFIX) + 40, 'physicalGpuMemoryMiB': 6,
        'gpuPortion': 10, 'runaiNumOfGpus': 10, 'cudaDeviceMemoryLimit': 6}
    record_properties = {field: {'type': 'string', 'maxLength': maximum_lengths[field]}
        for field in FIELDS | {'cmUid'}}
    record_properties['type']['enum'] = ['capabilities', 'evar']
    for field in ('podUid', 'cmUid'):
        record_properties[field]['pattern'] = '^' + UID_PATTERN + '$'
    record_properties['gpuUuid']['pattern'] = '^' + GPU_PATTERN + '$'
    record_properties['visibleDevices']['pattern'] = '^' + VISIBLE_DEVICES_PATTERN + '$'
    for field in ('name', 'podName'):
        record_properties[field].update(pattern='^' + DNS_PATTERN + '$', maxLength=253)
    record_properties['namespace'].update(enum=[namespace])
    record_properties['gpuPortion']['pattern'] = r'^(?:0\.[0-9]{1,8}|1)$'
    record_properties['physicalGpuMemoryMiB']['pattern'] = '^' + PHYSICAL_MEMORY_PATTERN + '$'
    record_properties['cudaDeviceMemoryLimit']['pattern'] = '^(?:[1-9][0-9]{0,3}|[1-3][0-9]{4}|40[0-8][0-9]{2}|409[0-5][0-9]|40960)m$'
    properties = {'writers': {'type': 'array', 'maxItems': 8, 'x-kubernetes-list-type': 'set',
        'items': {'type': 'string', 'maxLength': 343, 'pattern': '^' + ACTOR_PATTERN + '$'}},
        'records': {'type': 'array', 'maxItems': 64, 'x-kubernetes-list-type': 'map',
            'x-kubernetes-list-map-keys': ['namespace', 'name'], 'items': {'type': 'object',
                'required': sorted(FIELDS), 'properties': record_properties, 'x-kubernetes-validations': [
                    {'rule': 'self.gpuPortion == self.runaiNumOfGpus', 'message': 'Both upstream GPU portion aliases must match'},
                    {'rule': "self.visibleDevices.startsWith('GPU-') ? self.visibleDevices == self.gpuUuid : "
                        "(self.visibleDevices.startsWith('" + CDI_PREFIX + "GPU-') ? "
                        "self.visibleDevices == '" + CDI_PREFIX + "' + self.gpuUuid : true)",
                        'message': 'UUID selectors must match the physical UUID; numeric CDI mapping requires separate independent review'},
                    {'rule': "double(self.gpuPortion) > 0 && double(self.gpuPortion) <= 1", 'message': 'Positive fractional allocation at most one GPU required'},
                    # string(int(...)) has no finite estimated output bound.
                    # The pattern already fixes the canonical positive MiB
                    # wire format, so compare its bounded numeric part.
                    {'rule': 'int(self.cudaDeviceMemoryLimit.substring(0, size(self.cudaDeviceMemoryLimit) - 1)) == ' + quota_integer_expression('self'),
                        'message': 'HAMi quota must truncate the reviewed advertised memory label times received portion'}]}}}
    crd = {'apiVersion': 'apiextensions.k8s.io/v1', 'kind': 'CustomResourceDefinition',
        'metadata': {'name': 'dynamicgpuquotapolicies.' + group, 'annotations': copy.deepcopy(annotations)},
        'spec': {'group': group, 'scope': 'Namespaced', 'names': {'kind': 'DynamicGpuQuotaPolicy',
            'plural': 'dynamicgpuquotapolicies', 'singular': 'dynamicgpuquotapolicy'}, 'versions': [{
                'name': 'v1alpha1', 'served': True, 'storage': True, 'schema': {'openAPIV3Schema': {
                    'type': 'object', 'required': ['writers', 'records'], 'properties': properties}}}]}}
    params = {'apiVersion': group + '/v1alpha1', 'kind': 'DynamicGpuQuotaPolicy',
        'metadata': {'name': 'reviewed-quota-maps', 'namespace': namespace, 'annotations': copy.deepcopy(annotations)},
        'writers': list(writers), 'records': records}
    binding = {'apiVersion': 'admissionregistration.k8s.io/v1', 'kind': 'ValidatingAdmissionPolicyBinding',
        'metadata': {'name': name, 'annotations': copy.deepcopy(annotations)}, 'spec': {
            'policyName': name, 'validationActions': ['Deny'], 'matchResources': {'namespaceSelector': copy.deepcopy(selector)},
            'paramRef': {'name': 'reviewed-quota-maps', 'namespace': namespace, 'parameterNotFoundAction': 'Deny'}}}
    return {'apiVersion': 'v1', 'kind': 'List', 'items': [crd, params, policy, binding]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--namespace', default='cps-dynamic-admission-review')
    parser.add_argument('--registry', type=Path, help='Explicit reviewed JSON writers and records; missing registry denies all')
    parser.add_argument('--source-trace', type=Path, help='Optionally verify the independently captured official source bytes')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text()) if args.registry else {}
    if not isinstance(registry, dict) or set(registry) - {'writers', 'records'}:
        parser.error('Only explicit writers and records registry fields are permitted')
    source_sha = verify_source_trace(args.source_trace) if args.source_trace else None
    manifest = build(namespace=args.namespace, writers=registry.get('writers', []), records=registry.get('records', []))
    import yaml
    with args.output.open('x') as output:
        yaml.safe_dump_all(manifest['items'], output, sort_keys=False)
    print(json.dumps({'status': 'offline-candidate-rendered', 'applied': False,
        'kubernetesTypecheckQualified': False, 'liveWriterIdentityQualified': False, 'liveRetryQualified': False,
        'visibleDeviceMappingQualified': False,
        'nodeMemoryLabelAttestationQualified': False,
        'productionQualified': False, 'kaiSourceCommit': KAI_COMMIT, 'sourceTraceSha256': source_sha,
        'manifestSha256': hashlib.sha256(literal(manifest).encode()).hexdigest(), 'limitations': LIMITATIONS}))

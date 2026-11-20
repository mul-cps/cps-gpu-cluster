#!/usr/bin/env python3
"""Inactive, bounded Pod admission candidate for the pinned KAI/isolator shape.

This renders CEL; it does not execute a webhook or authenticate a controller.
Reviewed Pod records are protected operator inputs, never browser parameters.
The separate quota policy must protect both referenced ConfigMaps before use.
"""
import copy
import re

import render_policy

KAI_SOURCE = 'bdf434e5e9201cccf4e05fad04d814363653f692'
ISOLATOR_SOURCE = 'b7058586fe75e7c5a1addc553f408575bb31647f'
PREFIX_ANNOTATION = 'runai/shared-gpu-configmap'
ISOLATOR_HOSTS = {
    'kai-resource-isolator-vgpu': '/usr/local/vgpu',
    'kai-resource-isolator-containers': '/usr/local/vgpu/containers',
    'kai-resource-isolator-vgpulock': '/tmp/vgpulock',
}
ISOLATOR_MOUNTS = [
    {'name': 'kai-resource-isolator-vgpu', 'mountPath': '/usr/local/vgpu', 'readOnly': False},
    {'name': 'kai-resource-isolator-vgpu', 'mountPath': '/etc/ld.so.preload',
     'subPath': 'ld.so.preload', 'readOnly': True},
    {'name': 'kai-resource-isolator-containers', 'mountPath': '/usr/local/vgpu/containers', 'readOnly': False},
    {'name': 'kai-resource-isolator-vgpulock', 'mountPath': '/tmp/vgpulock', 'readOnly': False},
]
CAPABILITY_ENV = ['NVIDIA_VISIBLE_DEVICES', 'RUNAI_NUM_OF_GPUS', 'GPU_PORTION', 'CUDA_DEVICE_MEMORY_LIMIT']
ARGO_MAIN_ENV = ['ARGO_CONTAINER_NAME', 'ARGO_NODE_ID', 'ARGO_INCLUDE_SCRIPT_OUTPUT', 'ARGO_DEADLINE',
                 'ARGO_PROGRESS_FILE', 'ARGO_PROGRESS_PATCH_TICK_DURATION', 'ARGO_PROGRESS_FILE_TICK_DURATION',
                 'ARGO_TERMINATION_GRACE_PERIOD_SECONDS', 'ARGO_POD_NAME', 'ARGO_POD_UID']


def reviewed_records(records, owners):
    """Validate exact preregistration; copied prefix strings confer no authority."""
    if len(records) > 32:
        raise ValueError('At most 32 independently reviewed Pod plans are permitted')
    parents = {owner['uid']: owner['name'] for owner in owners}
    normalized = []
    for record in records:
        if set(record) != {'name', 'ownerUid', 'configMapPrefix', 'mainIndex', 'gpuMemory'}:
            raise ValueError('Exact Pod name, Workflow UID, KAI prefix, main index and profile required')
        name, owner_uid, prefix = record['name'], record['ownerUid'], record['configMapPrefix']
        if not isinstance(name, str) or len(name) > 253 or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', name):
            raise ValueError('Canonical reviewed Pod name required')
        if owner_uid not in parents or type(record['mainIndex']) is not int or record['mainIndex'] not in (0, 1):
            raise ValueError('Registered Workflow UID and regular-container index 0 or 1 required')
        # KAI 0.18.1 truncates the first owner's name to 33 bytes for one-digit
        # regular-container indexes, then removes trailing dots and hyphens.
        base = parents[owner_uid][:33].rstrip('.-')
        if not isinstance(prefix, str) or not re.fullmatch(re.escape(base) + r'-[bcdfghjklmnpqrstvwxz2456789]{7}-shared-gpu', prefix):
            raise ValueError('Reviewed KAI prefix must match the pinned owner/index naming rule')
        if record['gpuMemory'] not in ('5120', '10240', '20480'):
            raise ValueError('Only the three disabled fixed-profile qualification candidates are supported')
        value = copy.deepcopy(record)
        value['capabilitiesName'] = prefix + '-' + str(record['mainIndex'])
        value['evarName'] = value['capabilitiesName'] + '-evar'
        value['capabilitiesVolume'] = re.sub('[^a-z0-9-]+', '-', value['capabilitiesName'].lower() + '-vol').strip('-')
        normalized.append(value)
    for field in ('name', 'configMapPrefix', 'capabilitiesName', 'evarName'):
        if len({record[field] for record in normalized}) != len(normalized):
            raise ValueError('Pod names and per-Pod quota references must be unique')
    return normalized


def build(*, reviewed_pods=(), **kwargs):
    """Add the actual CREATE-time injection shape without changing production."""
    bundle = render_policy.build(**kwargs)
    crd, params, policy, binding = bundle['items']
    records = reviewed_records(reviewed_pods, params['owners'])
    params['reviewedPods'] = records
    properties = {name: {'type': 'integer' if name == 'mainIndex' else 'string'}
                  for name in ('name', 'ownerUid', 'configMapPrefix', 'mainIndex', 'gpuMemory',
                               'capabilitiesName', 'evarName', 'capabilitiesVolume')}
    properties['mainIndex']['enum'] = [0, 1]
    properties['gpuMemory']['enum'] = ['5120', '10240', '20480']
    schema = crd['spec']['versions'][0]['schema']['openAPIV3Schema']
    schema['properties']['reviewedPods'] = {'type': 'array', 'maxItems': 32,
        'x-kubernetes-list-type': 'map', 'x-kubernetes-list-map-keys': ['name'],
        'items': {'type': 'object', 'required': list(properties), 'properties': properties}}
    schema['required'].append('reviewedPods')
    annotations = policy['metadata']['annotations']
    annotations['compute.cps.unileoben.ac.at/kai-source'] = KAI_SOURCE
    annotations['compute.cps.unileoben.ac.at/isolator-source'] = ISOLATOR_SOURCE
    annotations['compute.cps.unileoben.ac.at/qualification-state'] = 'disabled-offline-injected-candidate'
    policy['spec']['variables'] = [{'name': 'records', 'expression':
        'params.reviewedPods.filter(p, p.name == object.metadata.name)'}]
    validations = policy['spec']['validations']
    replaced = {
        'The pre-injection shape requires exact indexed quota, private cache and MPS environment without loader or device overrides',
        'Only the two exact compiler MPS hostPaths and one private 64Mi cache are allowed; KAI injection is not yet qualified',
        'Only the main runtime may mount its private cache file and MPS sockets; alternate roots and binary shadow mounts are denied',
    }
    policy['spec']['validations'] = validations = [entry for entry in validations if entry['message'] not in replaced]
    L, tree = render_policy.literal, render_policy.required_tree
    def rule(expression, message):
        validations.append({'expression': expression, 'message': message})

    rule("size(variables.records) == 1 && variables.records.all(p, "
         "object.metadata.namespace == request.namespace && "
         "object.metadata.ownerReferences[0].uid == p.ownerUid && "
         "object.metadata.annotations['runai/shared-gpu-configmap'] == p.configMapPrefix && "
         "object.metadata.annotations['gpu-memory'] == p.gpuMemory && "
         "p.mainIndex < size(object.spec.containers) && object.spec.containers[p.mainIndex].name == 'main')",
         'The reviewed exact Pod plan fixes its Workflow owner, unique quota references, profile and actual main index')
    rule("object.spec.runtimeClassName == 'nvidia' && variables.records.all(p, "
         "object.metadata.annotations['nvidia.com/container.main.gpu-memory.request'] == "
         "(p.gpuMemory == '5120' ? '5Gi' : (p.gpuMemory == '10240' ? '10Gi' : '20Gi'))) && "
         "object.metadata.annotations.all(k, !k.startsWith('nvidia.com/container.') || "
         "k == 'nvidia.com/container.main.gpu-memory.request') && "
         "(!('kai-resource-isolator.io/inject' in object.metadata.annotations) || "
         "object.metadata.annotations['kai-resource-isolator.io/inject'] == 'true')",
         'The normalized KAI memory annotation and NVIDIA runtime remain exact; injector opt-out and other fraction targets are denied')
    rule("request.operation != 'UPDATE' || (has(oldObject.metadata.annotations) && "
         "object.metadata.annotations['runai/shared-gpu-configmap'] == oldObject.metadata.annotations['runai/shared-gpu-configmap'] && "
         "object.spec.containers == oldObject.spec.containers && object.spec.initContainers == oldObject.spec.initContainers && "
         "object.spec.volumes == oldObject.spec.volumes)",
         'Binding updates retain all executable containers, private volumes and quota references')

    compiler_plan = render_policy.compile_plan(kwargs.get('wheel', render_policy.DEFAULT_WHEEL), 5)
    runtime_clauses = []
    for key, value in {'CUDA_DEVICE_MEMORY_LIMIT_0': None, 'CUDA_DEVICE_MEMORY_SHARED_CACHE': '/tmp/cps-hami-cache/usage.cache',
                       'CUDA_MPS_PIPE_DIRECTORY': '/mps/pipe'}.items():
        expected = "p.gpuMemory + 'm'" if value is None else L(value)
        # Actual runtime's private cache path comes from the verified compiler.
        if key != 'CUDA_DEVICE_MEMORY_LIMIT_0':
            value = compiler_plan['environment'][key]
            expected = L(value)
        runtime_clauses.append("c.env.filter(e, e.name == " + L(key) + ").size() == 1 && "
            "c.env.filter(e, e.name == " + L(key) + ").all(e, has(e.value) && e.value == " + expected + " && !has(e.valueFrom))")
    for key in CAPABILITY_ENV:
        optional = ('has(e.valueFrom.configMapKeyRef.optional) && e.valueFrom.configMapKeyRef.optional'
                    if key == 'CUDA_DEVICE_MEMORY_LIMIT' else
                    '(!has(e.valueFrom.configMapKeyRef.optional) || !e.valueFrom.configMapKeyRef.optional)')
        runtime_clauses.append("c.env.filter(e, e.name == " + L(key) + ").size() == 1 && "
            "c.env.filter(e, e.name == " + L(key) + ").all(e, !has(e.value) && "
            "has(e.valueFrom.configMapKeyRef) && e.valueFrom.configMapKeyRef.name == p.capabilitiesName && "
            "e.valueFrom.configMapKeyRef.key == " + L(key) + ' && ' + optional + ')')
    runtime_clauses += [
        "c.env.filter(e, e.name == 'POD_UID').size() == 1 && c.env.filter(e, e.name == 'POD_UID').all(e, "
        "!has(e.value) && has(e.valueFrom.fieldRef) && e.valueFrom.fieldRef.apiVersion == 'v1' && e.valueFrom.fieldRef.fieldPath == 'metadata.uid')",
        "c.env.filter(e, e.name == 'CONTAINER_NAME').size() == 1 && c.env.filter(e, e.name == 'CONTAINER_NAME').all(e, e.value == 'main' && !has(e.valueFrom))",
        "c.env.filter(e, e.name == 'CONTAINER_VGPU_MOUNT').size() == 1 && c.env.filter(e, e.name == 'CONTAINER_VGPU_MOUNT').all(e, e.value == '/usr/local/vgpu' && !has(e.valueFrom))",
    ]
    allowed = list(CAPABILITY_ENV) + ['CUDA_DEVICE_MEMORY_LIMIT_0', 'CUDA_DEVICE_MEMORY_SHARED_CACHE',
        'CUDA_MPS_PIPE_DIRECTORY', 'POD_UID', 'CONTAINER_NAME', 'CONTAINER_VGPU_MOUNT']
    rule("variables.records.all(p, object.spec.containers.filter(c, c.name == 'main').all(c, "
         "has(c.env) && size(c.env) <= 64 && " + render_policy.all_of(runtime_clauses) + " && "
         "has(c.envFrom) && size(c.envFrom) == 1 && has(c.envFrom[0].configMapRef) && "
         "c.envFrom[0].configMapRef.name == p.evarName && has(c.envFrom[0].configMapRef.optional) && "
         "!c.envFrom[0].configMapRef.optional && !has(c.envFrom[0].secretRef) && !has(c.envFrom[0].prefix) && "
         "c.env.all(e, c.env.filter(other, other.name == e.name).size() == 1 && "
         "(e.name in " + L(allowed + ARGO_MAIN_ENV) + " || "
         "(!e.name.matches('(?i)^(CUDA_|NVIDIA_|GPU_|RUNAI_|LD_|HAMI_|VGPU_|MPS_|ARGO_)') && "
         "!e.name.matches('(?i)^PYTHONPATH$'))) && "
         "(!has(e.valueFrom) || e.name in " + L(CAPABILITY_ENV + ['POD_UID']) + " || "
         "(has(e.valueFrom.fieldRef) && e.name in ['ARGO_POD_NAME','ARGO_POD_UID'] && "
         "e.valueFrom.fieldRef.fieldPath == (e.name == 'ARGO_POD_NAME' ? 'metadata.name' : 'metadata.uid'))))))",
         'Exact KAI quota sources and isolator metrics are required; loader, duplicate and alternate device sources are denied')

    host_clauses = ["(v.name == " + L(name) + " && v.hostPath.path == " + L(path) +
                    " && v.hostPath.type == " + L(kind) + ')' for name, (path, kind, _) in render_policy.HOSTS.items()]
    host_clauses += ["(v.name == " + L(name) + " && v.hostPath.path == " + L(path) +
                     " && v.hostPath.type == 'DirectoryOrCreate')" for name, path in ISOLATOR_HOSTS.items()]
    rule("variables.records.all(p, has(object.spec.volumes) && size(object.spec.volumes) <= 16 && "
         "object.spec.volumes.all(v, object.spec.volumes.filter(other, other.name == v.name).size() == 1 && "
         "((has(v.hostPath) && (" + ' || '.join(host_clauses) + ")) || "
         "(has(v.emptyDir) && v.name in ['cps-gpu-cache','var-run-argo','tmp-dir-argo','input-artifacts','argo-staging']) || "
         "(has(v.secret) && (v.secret.secretName == params.data['artifact-secret'] || "
         "v.secret.secretName == params.data['artifact-ca-secret'] || "
         "v.secret.secretName == 'cps-workflow-executor.service-account-token')) || "
         "(v.name == p.capabilitiesVolume && has(v.configMap) && v.configMap.name == p.capabilitiesName && "
         "(!has(v.configMap.optional) || !v.configMap.optional) && (!has(v.configMap.items) || size(v.configMap.items) == 0)))) && "
         "object.spec.volumes.filter(v, v.name == p.capabilitiesVolume).size() == 1 && "
         "object.spec.volumes.filter(v, v.name == 'cps-gpu-cache').size() == 1 && "
         "object.spec.volumes.filter(v, v.name == 'cps-gpu-cache').all(v, has(v.emptyDir) && "
         "has(dyn(v.emptyDir).sizeLimit) && dyn(v.emptyDir).sizeLimit == '64Mi' && !has(v.emptyDir.medium)) && " +
         render_policy.all_of(["object.spec.volumes.filter(v, v.name == " + L(name) + ").size() == 1" for name in
                              list(render_policy.HOSTS) + list(ISOLATOR_HOSTS)]) + ')',
         'Only exact compiler and pinned isolator host paths, private cache, executor volumes and this Pod quota ConfigMap are permitted')

    compiler_mounts = compiler_plan['volume_mounts']
    def mount_contract(mount):
        # VolumeMount.readOnly is a non-pointer omitempty Go bool. The JSONPatch
        # contains false, but the API's later serialization can omit it.
        fields = {key: value for key, value in mount.items() if key != 'readOnly' or value}
        expression = tree('m', fields)
        if not mount.get('readOnly', False):
            expression += ' && (!has(m.readOnly) || !m.readOnly)'
        return expression
    tests = []
    for mount in compiler_mounts + ISOLATOR_MOUNTS:
        selector = "m.name == " + L(mount['name']) + " && m.mountPath == " + L(mount['mountPath'])
        contract = mount_contract(mount) + ' && !has(m.subPathExpr) && !has(m.mountPropagation)'
        if 'subPath' not in mount:
            contract += ' && !has(m.subPath)'
        tests.append('c.volumeMounts.filter(m, ' + selector + ').size() == 1 && ' +
                     'c.volumeMounts.filter(m, ' + selector + ').all(m, ' + contract + ')')
    candidates = [mount_contract(mount) + (' && !has(m.subPath)' if 'subPath' not in mount else '')
                  for mount in compiler_mounts + ISOLATOR_MOUNTS]
    candidates += ["(m.name == 'var-run-argo' && m.mountPath == '/var/run/argo' && !has(m.subPath))",
                   "(m.name == 'input-artifacts' && m.mountPath == '/inputs/snapshot.tar' && m.subPath == 'snapshot')",
                   "(m.name == 'argo-staging' && m.mountPath == '/argo/staging' && !has(m.subPath))"]
    private_names = list(render_policy.HOSTS) + ['cps-gpu-cache'] + list(ISOLATOR_HOSTS)
    rule("object.spec.containers.all(c, !has(c.volumeMounts) || c.volumeMounts.all(m, "
         "!has(m.mountPropagation) && !has(m.subPathExpr) && (!(m.name in " + L(private_names) + ") || c.name == 'main'))) && "
         "object.spec.containers.filter(c, c.name == 'main').all(c, has(c.volumeMounts) && " +
         render_policy.all_of(tests) + ' && c.volumeMounts.all(m, ' + ' || '.join(candidates) + '))',
         'Only the main mounts the exact private runtime and isolator paths; credentialed executors never receive these host paths')
    return bundle

#!/usr/bin/env python3
"""Render an isolated, inactive GPU admission candidate from pinned SDK bytes.

This does not apply resources, change Pod Security, or qualify a GPU runtime.
The owner/creator registry is an operator input, not inferred parent provenance.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

import yaml

from compiled_fixtures import IMAGE, SOURCE, WHEEL_SHA256, DEFAULT_WHEEL, ROOT, generate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'dynamic-cache'))
from mixed_render import compile_plan

HOSTS = {
    'cps-mps-pipe': ('/run/nvidia/mps/nvidia.com/gpu/pipe', 'Directory', '/mps/pipe'),
    'cps-mps-shm': ('/run/nvidia/mps/shm', 'Directory', '/dev/shm'),
}
EXECUTOR_IMAGE_PATTERN = r'[^\s,]+@sha256:[0-9a-f]{64}'
NAMESPACE_PATTERN = r'cps-dynamic-admission-[a-z0-9](?:[a-z0-9-]*[a-z0-9])?'


def literal(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False)


def all_of(parts):
    return ' && '.join('(' + part + ')' for part in parts)


def required_tree(path, value, *, map_fields=()):
    """Build real CEL field comparisons; never evaluate policy in Python."""
    # Quantity's OpenAPI oneOf causes the static checker to omit these maps.
    # Defer only that access; retain exact values and map cardinality checks.
    if path == 'c.resources':
        path = 'dyn(c.resources)'
        map_fields = tuple(field.replace('c.resources', path, 1) for field in map_fields)
    if isinstance(value, dict):
        clauses = []
        for key, child in value.items():
            field = path + '.' + key
            clauses.extend(['has(' + field + ')', required_tree(field, child, map_fields=map_fields)])
        if path in map_fields:
            clauses.append('size(' + path + ') == ' + str(len(value)))
        return all_of(clauses)
    if isinstance(value, list):
        if not value or all(not isinstance(child, (dict, list)) for child in value):
            return path + ' == ' + literal(value)
        return all_of(['size(' + path + ') == ' + str(len(value))] +
                      [required_tree(path + '[' + str(index) + ']', child, map_fields=map_fields)
                       for index, child in enumerate(value)])
    return path + ' == ' + literal(value)


def build(wheel=DEFAULT_WHEEL, *, namespace='cps-dynamic-admission-review',
          executor_image, artifact_secret='cps-artifacts', artifact_ca_secret='cps-artifacts-ca',
          create_creators=(), update_creators=(), owners=()):
    if (not isinstance(namespace, str) or len(namespace) > 63 or
            not re.fullmatch(NAMESPACE_PATTERN, namespace)):
        raise ValueError('Only a new cps-dynamic-admission-* qualification namespace is permitted')
    if not re.fullmatch(EXECUTOR_IMAGE_PATTERN, executor_image):
        raise ValueError('Executor requires an immutable SHA256 image digest')
    for name in (artifact_secret, artifact_ca_secret):
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', name) or len(name) > 253:
            raise ValueError('Canonical secret names required')
    if len(create_creators) > 8 or len(update_creators) > 8 or len(owners) > 32:
        raise ValueError('Bounded qualification registry required')
    for actor in (*create_creators, *update_creators):
        if not isinstance(actor, str) or not re.fullmatch(r'system:serviceaccount:[a-z0-9-]+:[a-z0-9.-]+', actor):
            raise ValueError('Explicit observed service-account request identity required')
    for owner in owners:
        if (set(owner) != {'name', 'uid'} or not isinstance(owner['name'], str) or
                not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', owner['name']) or
                not isinstance(owner['uid'], str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', owner['uid'])):
            raise ValueError('Exact reviewed Workflow name/UID records required')
    if len({owner['uid'] for owner in owners}) != len(owners):
        raise ValueError('Duplicate parent UID is not a qualification registry')
    plans = {gib: compile_plan(Path(wheel), gib) for gib in (5, 10, 20)}
    fixtures = generate(wheel, namespace=namespace)['fixtures']
    init = plans[5]['init_containers'][0]
    if any(plan['init_containers'] != [init] for plan in plans.values()):
        raise ValueError('Initializer differs between fixed profiles')
    policy, binding = list(yaml.safe_load_all((ROOT / 'platform-staging/admission.yaml').read_text()))
    policy = copy.deepcopy(policy); binding = copy.deepcopy(binding)
    group = namespace + '.compute.cps.unileoben.ac.at'
    policy_name = namespace + '-boundary'
    policy['metadata'] = {'name': policy_name, 'annotations': {
        'compute.cps.unileoben.ac.at/qualification-state': 'disabled-offline-candidate',
        'compute.cps.unileoben.ac.at/compiler-source': SOURCE,
        'compute.cps.unileoben.ac.at/compiler-wheel-sha256': WHEEL_SHA256}}
    policy['spec']['paramKind'] = {'apiVersion': group + '/v1alpha1', 'kind': 'DynamicGpuAdmissionPolicy'}
    selector = {'matchLabels': {'kubernetes.io/metadata.name': namespace}}
    policy['spec']['matchConstraints']['namespaceSelector'] = copy.deepcopy(selector)
    policy['spec']['matchConstraints']['resourceRules'][0]['resources'] = ['pods', 'pods/ephemeralcontainers', 'pods/resize']
    policy['spec']['matchConditions'] = [{'name': 'isolated-qualification-namespace',
                                         'expression': 'request.namespace == ' + literal(namespace)}]
    for validation in policy['spec']['validations']:
        expression = validation['expression']
        expression = expression.replace("params.data['approved-images'].split(',')", 'params.approvedImages')
        # Credentials/commands stay executor-only; the cache initializer has its
        # own complete contract below. Arbitrary other init names still fail.
        expression = expression.replace('object.spec.initContainers.all(c,',
            "object.spec.initContainers.filter(c, c.name != 'cps-gpu-cache-init').all(c,")
        validation['expression'] = expression
    policy['spec']['validations'] = [validation for validation in policy['spec']['validations']
        if validation['message'] != 'Host mounts require an explicit trusted GPU injector exception that has not been qualified']
    validations = policy['spec']['validations']
    def rule(expression, message):
        validations.append({'expression': expression, 'message': message})

    # This is a validation, never a creator matchCondition that could skip an
    # unauthorized request. It requires a protected, externally verified table.
    rule("(request.operation == 'CREATE' && request.userInfo.username in params.createCreators) || "
         "(request.operation == 'UPDATE' && request.userInfo.username in params.updateCreators)",
         'Every qualification Pod request requires an explicitly observed and approved creator')
    rule("has(object.metadata.ownerReferences) && size(object.metadata.ownerReferences) == 1 && "
         "object.metadata.ownerReferences.all(o, o.apiVersion == 'argoproj.io/v1alpha1' && o.kind == 'Workflow' && "
         "has(o.controller) && o.controller && params.owners.exists(p, p.name == o.name && p.uid == o.uid))",
         'The exact controller parent Workflow UID must be registered after independent review')
    rule("request.operation != 'UPDATE' || (has(oldObject.metadata) && object.metadata.uid == oldObject.metadata.uid && "
         "object.metadata.ownerReferences == oldObject.metadata.ownerReferences && "
         "object.spec.serviceAccountName == oldObject.spec.serviceAccountName && "
         "object.spec.schedulerName == oldObject.spec.schedulerName && "
         "object.spec.priorityClassName == oldObject.spec.priorityClassName && "
         "object.metadata.annotations['gpu-memory'] == oldObject.metadata.annotations['gpu-memory'])",
         'Updates may not replace the Pod identity, parent, scheduler or approved allocation')
    rule("size(object.spec.containers) <= 2 && object.spec.containers.filter(c, c.name == 'main').size() == 1 && "
         "object.spec.containers.all(c, c.name in ['main','wait']) && "
         "object.spec.containers.filter(c, c.name == 'wait').size() <= 1 && "
         "has(object.spec.initContainers) && size(object.spec.initContainers) <= 2 && "
         "object.spec.initContainers.filter(c, c.name == 'cps-gpu-cache-init').size() == 1 && "
         "object.spec.initContainers.all(c, c.name in ['cps-gpu-cache-init','init'])",
         'Only one main, one private cache initializer and the separately validated Argo executor are allowed')
    blocked_init = ['envFrom', 'ports', 'volumeDevices', 'resizePolicy']
    absent_init = ['workingDir', 'lifecycle', 'livenessProbe', 'readinessProbe', 'startupProbe', 'restartPolicy']
    init_contract = required_tree('c', init, map_fields=('c.resources.requests', 'c.resources.limits'))
    init_contract += ' && ' + all_of(
        ['!has(c.' + field + ') || size(c.' + field + ') == 0' for field in blocked_init] +
        ['!has(c.' + field + ')' for field in absent_init] +
        ['!has(c.' + field + ') || !c.' + field for field in ('stdin', 'stdinOnce', 'tty')] +
        ['!has(c.env[0].valueFrom)', '!has(c.volumeMounts[0].subPath)',
         '!has(c.volumeMounts[0].subPathExpr)', '!has(c.volumeMounts[0].mountPropagation)',
         '!has(c.volumeMounts[0].readOnly) || !c.volumeMounts[0].readOnly'])
    rule("object.spec.initContainers.filter(c, c.name == 'cps-gpu-cache-init').all(c, " + init_contract + ')',
         'The cache initializer must exactly match the verified compiler and receive only its private cache volume')
    security = "has(c.securityContext) && " + required_tree('c.securityContext', plans[5]['container_security_context'])
    security += " && (!has(c.securityContext.privileged) || !c.securityContext.privileged) && "
    security += "(!has(c.securityContext.capabilities.add) || size(c.securityContext.capabilities.add) == 0) && "
    security += "!has(c.securityContext.procMount) && !has(c.securityContext.seLinuxOptions) && "
    security += "!has(c.securityContext.windowsOptions) && !has(c.securityContext.seccompProfile.localhostProfile)"
    rule("object.spec.containers.filter(c, c.name == 'main').all(c, " + security + ')',
         'GPU main processes require the reviewed UID1000/GID100 nonroot runtime security context')
    resource_shapes = []
    for gib in (5, 10, 20):
        fixture = fixtures['batch-shared-' + str(gib)]
        resources = fixture['declaredControllerPod']['object']['spec']['containers'][0]['resources']
        resource_shapes.append("(object.metadata.annotations['gpu-memory'] == " + literal(str(gib * 1024)) +
            ' && ' + required_tree('c.resources', resources,
                                  map_fields=('c.resources.requests', 'c.resources.limits')) + ')')
    rule("object.spec.containers.filter(c, c.name == 'main').all(c, has(c.resources) && (" +
         ' || '.join(resource_shapes) + '))',
         'CPU and memory requests and limits must match the actual fixed-profile compiler output without extra GPU keys')
    rule("object.spec.containers.filter(c, c.name == 'main').all(c, c.image == " + literal(IMAGE) + ") && "
         "has(object.spec.activeDeadlineSeconds) && object.spec.activeDeadlineSeconds > 0 && "
         "object.spec.activeDeadlineSeconds <= 180 && object.spec.restartPolicy == 'Never' && "
         "(request.operation != 'CREATE' || !has(object.spec.nodeName)) && "
         "(!has(object.spec.nodeSelector) || size(object.spec.nodeSelector) == 0) && "
         "!has(object.spec.affinity) && (!has(object.spec.tolerations) || "
         "(size(object.spec.tolerations) <= 2 && object.spec.tolerations.all(t, "
         "t.key in ['node.kubernetes.io/not-ready','node.kubernetes.io/unreachable'] && "
         "t.operator == 'Exists' && t.effect == 'NoExecute' && "
         "has(t.tolerationSeconds) && t.tolerationSeconds == 300 && "
         "(!has(t.value) || t.value == '') && "
         "object.spec.tolerations.filter(other, other.key == t.key).size() == 1)))",
         'The reviewed runtime image, 180-second maximum and scheduler placement cannot be replaced')
    rule("object.spec.initContainers.all(c, has(c.securityContext) && "
         "has(c.securityContext.allowPrivilegeEscalation) && !c.securityContext.allowPrivilegeEscalation && "
         "(!has(c.securityContext.privileged) || !c.securityContext.privileged) && "
         "has(c.securityContext.capabilities) && c.securityContext.capabilities.drop == ['ALL'] && "
         "(!has(c.securityContext.capabilities.add) || size(c.securityContext.capabilities.add) == 0) && "
         "has(c.securityContext.runAsNonRoot) && c.securityContext.runAsNonRoot && "
         "has(c.securityContext.seccompProfile) && c.securityContext.seccompProfile.type == 'RuntimeDefault')",
         'The initializer exception never permits privileged init containers or added capabilities')
    executor_security = copy.deepcopy(plans[5]['container_security_context'])
    executor_security.update(runAsUser=10001, runAsGroup=10001, readOnlyRootFilesystem=True)
    executor_rule = required_tree('c.securityContext', executor_security)
    executor_rule += " && (!has(c.securityContext.privileged) || !c.securityContext.privileged) && "
    executor_rule += "(!has(c.securityContext.capabilities.add) || size(c.securityContext.capabilities.add) == 0)"
    rule("object.spec.containers.filter(c, c.name == 'wait').all(c, has(c.securityContext) && " + executor_rule + ") && "
         "object.spec.initContainers.filter(c, c.name == 'init').all(c, has(c.securityContext) && " + executor_rule + ')',
         'Credentialed executors retain their separate UID10001/GID10001 read-only nonroot security context')
    executor_resources = yaml.safe_load((ROOT / 'platform-staging/argo/values.yaml').read_text())['executor']['resources']
    executor_resource_rule = 'has(c.resources) && ' + required_tree('c.resources', executor_resources,
        map_fields=('c.resources.requests', 'c.resources.limits'))
    rule("object.spec.containers.filter(c, c.name == 'wait').all(c, " + executor_resource_rule + ") && "
         "object.spec.initContainers.filter(c, c.name == 'init').all(c, " + executor_resource_rule + ')',
         'Credentialed executors use the declared Argo CPU and memory limits without additional GPU resources')
    rule("(!has(object.spec.resourceClaims) || size(object.spec.resourceClaims) == 0) && "
         "object.spec.containers.all(c, !has(c.resources) || !has(c.resources.claims) || size(c.resources.claims) == 0) && "
         "object.spec.initContainers.all(c, !has(c.resources) || !has(c.resources.claims) || size(c.resources.claims) == 0)",
         'DRA resource claims are outside the dynamic shared GPU v1 contract')
    rule('has(object.spec.securityContext) && ' + required_tree('object.spec.securityContext', plans[5]['pod_security_context']) +
         " && (!has(object.spec.securityContext.sysctls) || size(object.spec.securityContext.sysctls) == 0) && "
         "(!has(object.spec.securityContext.supplementalGroups) || size(object.spec.securityContext.supplementalGroups) == 0) && "
         "!has(object.spec.securityContext.seLinuxOptions) && !has(object.spec.securityContext.windowsOptions) && "
         "(!has(object.spec.securityContext.appArmorProfile) || "
         "(object.spec.securityContext.appArmorProfile.type == 'RuntimeDefault' && "
         "!has(object.spec.securityContext.appArmorProfile.localhostProfile)))",
         'The reviewed Pod UID, GID, fsGroup and RuntimeDefault seccomp must remain explicit')
    extra_security = "has(c.securityContext) && !has(c.securityContext.seLinuxOptions) && "
    extra_security += "!has(c.securityContext.windowsOptions) && "
    extra_security += "(!has(c.securityContext.procMount) || c.securityContext.procMount == 'Default') && "
    extra_security += "(!has(c.securityContext.appArmorProfile) || "
    extra_security += "(c.securityContext.appArmorProfile.type == 'RuntimeDefault' && "
    extra_security += "!has(c.securityContext.appArmorProfile.localhostProfile))) && "
    extra_security += "(!has(c.securityContext.capabilities.add) || size(c.securityContext.capabilities.add) == 0) && "
    extra_security += "!has(c.securityContext.seccompProfile.localhostProfile)"
    rule('object.spec.containers.all(c, ' + extra_security + ') && object.spec.initContainers.all(c, ' + extra_security + ')',
         'Every executable retains the reviewed AppArmor, proc, SELinux, Windows and capability restrictions')
    rule("has(object.metadata.labels) && object.metadata.labels['kai.scheduler/queue'] == 'cps-batch' && "
         "object.spec.priorityClassName == 'cps-batch' && "
         "has(object.metadata.annotations) && object.metadata.annotations['gpu-fraction-container-name'] == 'main' && "
         "object.metadata.annotations['gpu-memory'] in ['5120','10240','20480'] && "
         "!('gpu-fraction' in object.metadata.annotations) && !('gpu-fraction-num-devices' in object.metadata.annotations)",
         'Only fixed 5/10/20 GiB batch candidates and centrally selected queue and priority are allowed')
    runtime_env = plans[5]['environment']
    env_clauses = []
    for key, value in runtime_env.items():
        expected = "object.metadata.annotations['gpu-memory'] + 'm'" if key == 'CUDA_DEVICE_MEMORY_LIMIT_0' else literal(value)
        env_clauses.append("c.env.filter(e, e.name == " + literal(key) + ").size() == 1 && "
            "c.env.filter(e, e.name == " + literal(key) + ").all(e, has(e.value) && e.value == " + expected + " && !has(e.valueFrom))")
    rule("object.spec.containers.filter(c, c.name == 'main').all(c, has(c.env) && size(c.env) <= 64 && " +
         all_of(env_clauses) + " && (!has(c.envFrom) || size(c.envFrom) == 0) && "
         "c.env.all(e, c.env.filter(other, other.name == e.name).size() == 1 && "
         "(e.name in ['CUDA_DEVICE_MEMORY_LIMIT_0','CUDA_DEVICE_MEMORY_SHARED_CACHE','CUDA_MPS_PIPE_DIRECTORY'] || "
         "!e.name.matches('(?i)^(CUDA_|NVIDIA_|GPU_|LD_|HAMI_|VGPU_|MPS_)')) && "
         "!e.name.matches('(?i)^PYTHONPATH$')))",
         'The pre-injection shape requires exact indexed quota, private cache and MPS environment without loader or device overrides')
    # Deliberately admit ONLY the pre-injection runtime shape at this stage.
    # KAI host volumes cannot be trusted merely by copied names. The complete
    # post-injection transition/ConfigMap-owner contract remains a later gate.
    expected_hosts = []
    for name, (path, kind, _) in list(HOSTS.items())[:2]:
        expected_hosts.append("(v.name == " + literal(name) + " && v.hostPath.path == " + literal(path) +
            " && has(v.hostPath.type) && v.hostPath.type == " + literal(kind) + ')')
    rule("has(object.spec.volumes) && size(object.spec.volumes) <= 16 && "
         "object.spec.volumes.all(v, object.spec.volumes.filter(other, other.name == v.name).size() == 1 && "
         "((has(v.hostPath) && (" + ' || '.join(expected_hosts) + ")) || "
         "(has(v.emptyDir) && v.name in ['cps-gpu-cache','var-run-argo','tmp-dir-argo','input-artifacts','argo-staging']) || "
         "(has(v.secret) && (v.secret.secretName == params.data['artifact-secret'] || "
         "v.secret.secretName == params.data['artifact-ca-secret'] || "
         "v.secret.secretName == 'cps-workflow-executor.service-account-token')))) && "
         "object.spec.volumes.filter(v, v.name == 'cps-gpu-cache').size() == 1 && "
         "object.spec.volumes.filter(v, v.name == 'cps-gpu-cache').all(v, has(v.emptyDir) && "
         "has(dyn(v.emptyDir).sizeLimit) && dyn(v.emptyDir).sizeLimit == '64Mi' && !has(v.emptyDir.medium)) && " +
         all_of(["object.spec.volumes.filter(v, v.name == " + literal(name) + ").size() == 1" for name in list(HOSTS)[:2]]),
         'Only the two exact compiler MPS hostPaths and one private 64Mi cache are allowed; KAI injection is not yet qualified')
    mounts = plans[5]['volume_mounts']
    mount_tests = []
    for mount in mounts:
        mount_tests.append("c.volumeMounts.filter(m, m.name == " + literal(mount['name']) + ").size() == 1 && "
            "c.volumeMounts.filter(m, m.name == " + literal(mount['name']) + ").all(m, " +
            required_tree('m', mount) + ' && !has(m.subPathExpr) && !has(m.mountPropagation)' +
            ' && (!has(m.readOnly) || !m.readOnly)' +
            ('' if 'subPath' in mount else ' && !has(m.subPath)') + ')')
    rule("object.spec.containers.all(c, (!has(c.volumeMounts) || c.volumeMounts.all(m, "
         "!has(m.mountPropagation) && !has(m.subPathExpr) && "
         "(!(m.name in ['cps-gpu-cache','cps-mps-pipe','cps-mps-shm']) || c.name == 'main')))) && "
         "object.spec.containers.filter(c, c.name == 'main').all(c, has(c.volumeMounts) && " +
         all_of(mount_tests) + " && c.volumeMounts.all(m, "
         "m.name in ['cps-gpu-cache','cps-mps-pipe','cps-mps-shm'] || "
         "(m.name == 'var-run-argo' && m.mountPath == '/var/run/argo' && !has(m.subPath)) || "
         "(m.name == 'input-artifacts' && m.mountPath == '/inputs/snapshot.tar') || "
         "(m.name == 'argo-staging' && m.mountPath == '/argo/staging' && !has(m.subPath))))",
         'Only the main runtime may mount its private cache file and MPS sockets; alternate roots and binary shadow mounts are denied')
    rule("object.spec.containers.all(c, !has(c.lifecycle) && !has(c.livenessProbe) && !has(c.readinessProbe) && "
         "!has(c.startupProbe) && (!has(c.volumeDevices) || size(c.volumeDevices) == 0)) && "
         "object.spec.initContainers.all(c, !has(c.lifecycle) && !has(c.livenessProbe) && !has(c.readinessProbe) && "
         "!has(c.startupProbe) && (!has(c.volumeDevices) || size(c.volumeDevices) == 0)) && "
         "object.spec.containers.all(c, !has(c.ports) || c.ports.all(p, !has(p.hostPort) || p.hostPort == 0)) && "
         "(!has(object.spec.runtimeClassName) || object.spec.runtimeClassName == 'nvidia') && "
         "(!has(object.spec.os) || object.spec.os.name == 'linux')",
         'Unreviewed executable hooks, block devices and runtime classes require a separate qualification')
    # A separate API group avoids extending/reinterpreting the production four-
    # string schema. Empty tables intentionally deny requests until reviewed.
    def strings(maximum):
        return {'type': 'array', 'maxItems': maximum, 'items': {'type': 'string'}, 'x-kubernetes-list-type': 'set'}
    properties = {
        'data': {'type': 'object', 'required': ['executor-image', 'artifact-secret', 'artifact-ca-secret'],
                 'additionalProperties': {'type': 'string'}, 'x-kubernetes-validations': [
                     {'rule': 'self.size() == 3', 'message': 'Exactly the three declared executor parameters are required'}]},
        'approvedImages': strings(8), 'createCreators': strings(8), 'updateCreators': strings(8),
        'owners': {'type': 'array', 'maxItems': 32, 'x-kubernetes-list-type': 'map', 'x-kubernetes-list-map-keys': ['uid'],
                   'items': {'type': 'object', 'required': ['name', 'uid'],
                             'properties': {'name': {'type': 'string'}, 'uid': {'type': 'string'}}}}}
    crd = {'apiVersion': 'apiextensions.k8s.io/v1', 'kind': 'CustomResourceDefinition',
        'metadata': {'name': 'dynamicgpuadmissionpolicies.' + group}, 'spec': {'group': group, 'scope': 'Namespaced',
        'names': {'kind': 'DynamicGpuAdmissionPolicy', 'plural': 'dynamicgpuadmissionpolicies', 'singular': 'dynamicgpuadmissionpolicy'},
        'versions': [{'name': 'v1alpha1', 'served': True, 'storage': True, 'schema': {'openAPIV3Schema': {
            'type': 'object', 'required': list(properties), 'properties': properties}}}]}}
    params = {'apiVersion': group + '/v1alpha1', 'kind': 'DynamicGpuAdmissionPolicy',
        'metadata': {'name': 'reviewed-runtime', 'namespace': namespace},
        'data': {'executor-image': executor_image, 'artifact-secret': artifact_secret, 'artifact-ca-secret': artifact_ca_secret},
        'approvedImages': list(dict.fromkeys([IMAGE, executor_image])),
        'createCreators': list(dict.fromkeys(create_creators)), 'updateCreators': list(dict.fromkeys(update_creators)),
        'owners': copy.deepcopy(list(owners))}
    binding['metadata']['name'] = policy_name
    binding['spec']['policyName'] = policy_name
    binding['spec']['matchResources']['namespaceSelector'] = copy.deepcopy(selector)
    binding['spec']['paramRef'] = {'name': 'reviewed-runtime', 'namespace': namespace, 'parameterNotFoundAction': 'Deny'}
    return {'apiVersion': 'v1', 'kind': 'List', 'items': [crd, params, policy, binding]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, default=DEFAULT_WHEEL)
    parser.add_argument('--namespace', default='cps-dynamic-admission-review')
    parser.add_argument('--executor-image', required=True)
    parser.add_argument('--registry', type=Path, help='Operator-reviewed JSON createCreators/updateCreators/owners; defaults deny all')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text()) if args.registry else {}
    if set(registry) - {'createCreators', 'updateCreators', 'owners'}:
        parser.error('Unknown registry fields')
    result = build(args.wheel, namespace=args.namespace, executor_image=args.executor_image,
        create_creators=registry.get('createCreators', []), update_creators=registry.get('updateCreators', []),
        owners=registry.get('owners', []))
    with args.output.open('x') as output:
        yaml.safe_dump_all(result['items'], output, sort_keys=False)
    print(json.dumps({'rendered': True, 'applied': False, 'productionQualified': False,
        'postInjectionQualified': False, 'sourceCommit': SOURCE, 'wheelSha256': WHEEL_SHA256,
        'manifestSha256': hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()}))

#!/usr/bin/env python3
"""Render a closed, default-disabled CPU node authority deployment; no API calls."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import node_agent as agent

HERE = Path(__file__).resolve().parent
DEFAULT_IMAGE = 'ghcr.io/bjoernellens1/cps-native-node-agent@sha256:' + '0' * 64
ACCOUNT = 'cps-native-node-agent'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def item(kind, name, namespace=None, **fields):
    value = {'apiVersion': 'v1' if kind in ('Namespace', 'ServiceAccount', 'ConfigMap') else
             'apps/v1' if kind == 'Deployment' else 'admissionregistration.k8s.io/v1' if
             kind in ('ValidatingAdmissionPolicy', 'ValidatingAdmissionPolicyBinding') else 'rbac.authorization.k8s.io/v1',
             'kind': kind, 'metadata': {'name': name}}
    if namespace: value['metadata']['namespace'] = namespace
    value.update(fields)
    return value


def render(config=None, *, image=DEFAULT_IMAGE, enable=False):
    config = agent.validate_config(config if config is not None else agent.parse((HERE / 'config.example.json').read_bytes()))
    agent.require(isinstance(image, str) and re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}', image),
                  'Immutable CPU service image digest required')
    agent.require(not enable or (config['enabled'] and not image.endswith('0' * 64)
                  and config['policy_hash'] != 'sha256:' + '0' * 64),
                  'Activation requires enabled operator config, actual policy and built digest image')
    namespace, node = config['authority_namespace'], config['pool']['node']
    sources = agent.snapshot_sources()
    sources.update({name: (HERE / name).read_text() for name in ('node_agent.py', 'driver_loader.py')})
    sources['source-snapshot.json'] = (HERE / 'source-snapshot.json').read_text()
    code_name = 'cps-native-node-code-' + digest(sources)[:16]
    config_name = 'cps-native-node-config-' + digest(config)[:16]
    subject = [{'kind': 'ServiceAccount', 'name': ACCOUNT, 'namespace': namespace}]
    objects = [item('Namespace', namespace), item('ServiceAccount', ACCOUNT, namespace, automountServiceAccountToken=True),
        item('ConfigMap', code_name, namespace, immutable=True, data=sources),
        item('ConfigMap', config_name, namespace, immutable=True,
             data={'config.json': json.dumps(config, sort_keys=True, separators=(',', ':'))}),
        item('Role', ACCOUNT + '-authority', namespace,
             rules=[{'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get', 'list', 'create']}]),
        item('RoleBinding', ACCOUNT + '-authority', namespace, subjects=subject,
             roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': ACCOUNT + '-authority'}),
        item('ClusterRole', ACCOUNT + '-node', rules=[{'apiGroups': [''], 'resources': ['nodes'],
             'resourceNames': [node], 'verbs': ['get']}]),
        item('ClusterRoleBinding', ACCOUNT + '-node', subjects=subject,
             roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole', 'name': ACCOUNT + '-node'})]
    for hub_namespace in ('jupyterhub', 'cit-jhub'):
        objects.extend([item('Role', ACCOUNT + '-pods', hub_namespace,
            rules=[{'apiGroups': [''], 'resources': ['pods'], 'verbs': ['get', 'delete']}]),
            item('RoleBinding', ACCOUNT + '-pods', hub_namespace, subjects=subject,
                 roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': ACCOUNT + '-pods'})])
    # RBAC cannot restrict create by resourceName. This admission policy closes
    # that gap: node credentials can publish cleanup, never enrollment/ledger.
    policy_name = ACCOUNT + '-cleanup-only'
    username = 'system:serviceaccount:' + namespace + ':' + ACCOUNT
    # CEL does not decode JSON strings: these are bounded wire discriminators,
    # not substitutes for the SDK/Node's exact claim, hash and custody validation.
    binding = "object.metadata.labels['cps.compute/native-binding']"
    proof_text = "object.data['abort.json']"
    proof_wire = ("size(" + proof_text + ") <= 65536 && " + proof_text + ".startsWith('{\"attempt\":') && "
        + proof_text + ".contains('\"cleanup_confirmed\":true,') && has(object.metadata.labels) && "
        "'cps.compute/native-binding' in object.metadata.labels && " + proof_text + ".contains('\"binding_id\":\"' + " + binding + " + '\",') && ("
        + proof_text + ".endsWith(',\"outcome\":\"enrollment-never-published\",\"slot_kind\":\"abort-barrier\",\"version\":2}') || "
        + proof_text + ".endsWith(',\"outcome\":\"enrollment-never-programmed\",\"slot_kind\":\"enrollment\",\"version\":2}'))")
    expressions = [
        ("request.namespace == " + json.dumps(namespace), 'Cleanup publication stays in the authority namespace.'),
        ("(object.metadata.name.matches('^cps-native-cleanup-[a-f0-9]{40}$') || object.metadata.name.matches('^cps-native-abort-[a-f0-9]{40}$')) && has(object.immutable) && object.immutable == true",
         'The node agent may create only immutable native cleanup or terminal abort ConfigMaps.'),
        ("has(object.data) && size(object.data) == 1 && !has(object.binaryData) && (("
         "object.metadata.name.matches('^cps-native-cleanup-[a-f0-9]{40}$') && 'receipt.json' in object.data) || ("
         "object.metadata.name.matches('^cps-native-abort-[a-f0-9]{40}$') && 'abort.json' in object.data && " + proof_wire + "))",
         'Exactly one name-bound cleanup receipt or terminal v2 abort proof is required.'),
        ("has(object.metadata.labels) && size(object.metadata.labels) == 1 && 'cps.compute/native-binding' in object.metadata.labels && "
         "object.metadata.labels['cps.compute/native-binding'].matches('^[a-f0-9]{60}$') && "
         "(('cps-native-cleanup-' + object.metadata.labels['cps.compute/native-binding']).startsWith(object.metadata.name) || "
         "('cps-native-abort-' + object.metadata.labels['cps.compute/native-binding']).startsWith(object.metadata.name))",
         'Cleanup names and labels carry one exact binding identity.'),
        ("!has(object.metadata.ownerReferences) || size(object.metadata.ownerReferences) == 0",
         'Cleanup tombstones must not be garbage-collected through Pod ownership.'),
    ]
    objects.extend([item('ValidatingAdmissionPolicy', policy_name,
        spec={'failurePolicy': 'Fail', 'matchConstraints': {'resourceRules': [{'apiGroups': [''],
            'apiVersions': ['v1'], 'operations': ['CREATE'], 'resources': ['configmaps'], 'scope': 'Namespaced'}]},
            'matchConditions': [{'name': 'node-agent-credential', 'expression': 'request.userInfo.username == ' + json.dumps(username)}],
            'validations': [{'expression': expression, 'message': message} for expression, message in expressions]}),
        item('ValidatingAdmissionPolicyBinding', policy_name,
             spec={'policyName': policy_name, 'validationActions': ['Deny']})])
    # The gateway owns allocation CAS and enrollment, independently of the node
    # credential. Restrict create through admission because RBAC resourceNames
    # cannot constrain POST; cleanup remains exclusively node-controlled.
    gateway_name = 'cps-native-gateway-authority'
    gateway_subject = [{'kind': 'ServiceAccount', 'name': 'cps-compute-controller', 'namespace': 'cps-compute'}]
    gateway_username = 'system:serviceaccount:cps-compute:cps-compute-controller'
    barrier_text = "object.data['abort-barrier.json']"
    barrier_pattern = r'^\{"claim":\{[^\r\n]*\},"claim_sha256":"sha256:[a-f0-9]{64}","kind":"enrollment-abort-barrier","version":2\}$'
    barrier_wire = ("size(" + barrier_text + ") <= 65536 && " + barrier_text + ".matches(" + json.dumps(barrier_pattern) + ") && "
        + barrier_text + ".contains('\"binding_id\":\"' + " + binding + " + '\",')")
    enrollment = ("object.metadata.name.matches('^cps-native-enrollment-[a-f0-9]{40}$') && "
        "has(object.immutable) && object.immutable == true && has(object.data) && size(object.data) == 1 && "
        "has(object.metadata.labels) && size(object.metadata.labels) == 1 && "
        "'cps.compute/native-binding' in object.metadata.labels && "
        "object.metadata.labels['cps.compute/native-binding'].matches('^[a-f0-9]{60}$') && "
        "('cps-native-enrollment-' + object.metadata.labels['cps.compute/native-binding']).startsWith(object.metadata.name) && "
        "('enrollment.json' in object.data || ('abort-barrier.json' in object.data && " + barrier_wire + "))")
    ledger = ("object.metadata.name == 'cps-native-gpu-allocations' && "
        "(!has(object.immutable) || object.immutable == false) && has(object.data) && size(object.data) == 1 && "
        "'state.json' in object.data && object.data['state.json'] == '{\"allocations\":{},\"version\":1}'")
    objects.extend([
        item('ClusterRole', gateway_name + '-node', rules=[
            {'apiGroups': [''], 'resources': ['nodes'], 'resourceNames': [node], 'verbs': ['get']}]),
        item('ClusterRoleBinding', gateway_name + '-node', subjects=gateway_subject,
            roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole', 'name': gateway_name + '-node'}),
        item('Role', gateway_name, namespace, rules=[
            {'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get', 'create']},
            {'apiGroups': [''], 'resources': ['configmaps'], 'resourceNames': ['cps-native-gpu-allocations'], 'verbs': ['patch']}]),
        item('RoleBinding', gateway_name, namespace, subjects=gateway_subject,
            roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': gateway_name}),
        item('ValidatingAdmissionPolicy', gateway_name + '-create-only', spec={
            'failurePolicy': 'Fail', 'matchConstraints': {'resourceRules': [{'apiGroups': [''],
                'apiVersions': ['v1'], 'operations': ['CREATE'], 'resources': ['configmaps'], 'scope': 'Namespaced'}]},
            'matchConditions': [{'name': 'gateway-authority-create', 'expression':
                'request.namespace == ' + json.dumps(namespace) + ' && request.userInfo.username == ' + json.dumps(gateway_username)}],
            'validations': [
                {'expression': '(' + ledger + ') || (' + enrollment + ')',
                 'message': 'The gateway may create only an empty native ledger or one immutable enrollment/terminal v2 abort-barrier slot.'},
                {'expression': '!has(object.binaryData)', 'message': 'Authority records must use text data.'},
                {'expression': '!has(object.metadata.ownerReferences) || size(object.metadata.ownerReferences) == 0',
                 'message': 'Native authority records cannot have garbage-collection owners.'}]}),
        item('ValidatingAdmissionPolicyBinding', gateway_name + '-create-only',
             spec={'policyName': gateway_name + '-create-only', 'validationActions': ['Deny']})])
    volumes = [{'name': 'code', 'configMap': {'name': code_name, 'defaultMode': 0o444}},
        {'name': 'config', 'configMap': {'name': config_name, 'defaultMode': 0o400}},
        {'name': 'state', 'hostPath': {'path': '/run/cps-native-gpu', 'type': 'Directory'}},
        {'name': 'host', 'hostPath': {'path': '/', 'type': 'Directory'}},
        {'name': 'cgroups', 'hostPath': {'path': '/sys/fs/cgroup', 'type': 'Directory'}},
        {'name': 'modules', 'hostPath': {'path': '/sys/module', 'type': 'Directory'}},
        {'name': 'devices', 'hostPath': {'path': '/dev', 'type': 'Directory'}}]
    mounts = [{'name': 'code', 'mountPath': '/opt/native', 'readOnly': True},
        {'name': 'config', 'mountPath': '/config/config.json', 'subPath': 'config.json', 'readOnly': True},
        {'name': 'state', 'mountPath': '/run/cps-native-gpu'}, {'name': 'host', 'mountPath': '/host', 'readOnly': True},
        {'name': 'cgroups', 'mountPath': '/sys/fs/cgroup', 'readOnly': True},
        {'name': 'modules', 'mountPath': '/sys/module', 'readOnly': True},
        {'name': 'devices', 'mountPath': '/dev', 'readOnly': True}]
    labels = {'app.kubernetes.io/name': ACCOUNT}
    objects.append(item('Deployment', ACCOUNT, namespace, spec={'replicas': 1 if enable else 0,
        'strategy': {'type': 'Recreate'}, 'selector': {'matchLabels': labels},
        'template': {'metadata': {'labels': labels}, 'spec': {'serviceAccountName': ACCOUNT,
            'nodeName': node, 'hostPID': True, 'terminationGracePeriodSeconds': 15,
            'securityContext': {'runAsUser': 0, 'runAsGroup': 0},
            'volumes': volumes, 'containers': [{'name': 'node-agent', 'image': image, 'imagePullPolicy': 'IfNotPresent',
                'command': ['python3', '/opt/native/node_agent.py'],
                'args': ['--execute', '--config', '/config/config.json', '--bundle', '/opt/native',
                         '--iterations', '10000' if enable else '60', '--interval', '2'],
                'securityContext': {'privileged': True, 'readOnlyRootFilesystem': True},
                'resources': {'requests': {'cpu': '100m', 'memory': '128Mi'},
                              'limits': {'cpu': '500m', 'memory': '512Mi'}},
                'env': [{'name': 'PYTHONDONTWRITEBYTECODE', 'value': '1'}], 'volumeMounts': mounts}]}}}))
    return {'apiVersion': 'v1', 'kind': 'List', 'items': objects}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--image', default=DEFAULT_IMAGE)
    parser.add_argument('--enable', action='store_true')
    args = parser.parse_args(argv)
    config = agent.parse(args.config.read_bytes()) if args.config else None
    print(json.dumps(render(config, image=args.image, enable=args.enable), sort_keys=True, indent=2))

if __name__ == '__main__': main()

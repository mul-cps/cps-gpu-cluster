"""Render inactive QA service/fence/transition artifacts; never apply them."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re

import yaml

import fence
import quota_transition


def build(*, image, ca_bundle, registry=None, namespace='cps-dynamic-admission-coordination',
          service_namespace='cps-dynamic-coordination-review', node_names=(), sealer_rbac=False,
          quota_writers=()):
    if not re.fullmatch(r'[a-z0-9./:_-]+@sha256:[0-9a-f]{64}', image):
        raise ValueError('An independently built/reviewed immutable image required')
    if not re.fullmatch(r'cps-dynamic-coordination-[a-z0-9-]+', service_namespace) or len(service_namespace) > 63:
        raise ValueError('Separate QA service namespace required')
    if not ca_bundle or len(ca_bundle) > 32768:
        raise ValueError('Bounded reviewed TLS CA bundle required')
    actor = 'system:serviceaccount:' + service_namespace + ':trusted-sealer'
    if registry is None:
        registry = dict(schemaVersion=1, namespace=namespace, bindingWriters=[], cleanupWriters=[], sealWriter=actor, records=[])
    fence.validate_registry(registry)
    if registry['namespace'] != namespace: raise ValueError('Registry namespace disagrees')
    registry_name = 'reviewed-generations-' + hashlib.sha256(fence.canonical(registry)).hexdigest()[:16]
    approved_nodes = {r['node']['metadata']['name'] for r in registry['records']}
    if set(node_names) - approved_nodes or len(set(node_names)) != len(node_names):
        raise ValueError('Node GET/protection must name only distinct reviewed fixed Nodes')
    if sealer_rbac and registry['sealWriter'] != actor: raise ValueError('Exact trusted-sealer service-account identity required')
    labels = {'app': 'dynamic-generation-fence'}
    annotations = {'compute.cps.unileoben.ac.at/qualification-state': 'qa-only-inactive-candidate'}
    items = [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': service_namespace, 'annotations': annotations}},
             {'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': {'name': 'generation-fence', 'namespace': service_namespace}},
             {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': registry_name, 'namespace': service_namespace},
              'immutable': True, 'data': {'registry.json': fence.canonical(registry).decode()}},
             {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': {'name': 'generation-fence-reader', 'namespace': namespace},
              'rules': [{'apiGroups': [''], 'resources': ['pods', 'configmaps'], 'verbs': ['get']},
                        {'apiGroups': ['argoproj.io'], 'resources': ['workflows'], 'verbs': ['get']}]},
             {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': {'name': 'generation-fence-reader', 'namespace': namespace},
              'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'generation-fence-reader'},
              'subjects': [{'kind': 'ServiceAccount', 'namespace': service_namespace, 'name': 'generation-fence'}]},
             {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'generation-fence', 'namespace': service_namespace},
              'spec': {'selector': labels, 'ports': [{'port': 443, 'targetPort': 8443}]}},
             {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'generation-fence', 'namespace': service_namespace, 'annotations': annotations},
              'spec': {'replicas': 0, 'selector': {'matchLabels': labels}, 'template': {'metadata': {'labels': labels}, 'spec': {
                  'serviceAccountName': 'generation-fence', 'securityContext': {'runAsNonRoot': True, 'runAsUser': 65532, 'seccompProfile': {'type': 'RuntimeDefault'}},
                  'containers': [{'name': 'webhook', 'image': image, 'args': ['--registry=/registry/registry.json', '--tls-cert=/tls/tls.crt', '--tls-key=/tls/tls.key', '--api-server=https://kubernetes.default.svc'],
                     'ports': [{'containerPort': 8443}], 'resources': {'requests': {'cpu': '100m', 'memory': '64Mi'}, 'limits': {'cpu': '1', 'memory': '256Mi'}},
                     'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}},
                     'readinessProbe': {'httpGet': {'scheme': 'HTTPS', 'path': '/healthz', 'port': 8443}},
                     'volumeMounts': [{'name': 'registry', 'mountPath': '/registry', 'readOnly': True}, {'name': 'tls', 'mountPath': '/tls', 'readOnly': True}]}],
                  'volumes': [{'name': 'registry', 'configMap': {'name': registry_name}}, {'name': 'tls', 'secret': {'secretName': 'generation-fence-tls'}}]}}}},
    ]
    rules = [{'apiGroups': [''], 'apiVersions': ['v1'], 'operations': ['CREATE'], 'resources': ['pods/binding'], 'scope': 'Namespaced'},
             {'apiGroups': [''], 'apiVersions': ['v1'], 'operations': ['CREATE', 'UPDATE', 'DELETE'], 'resources': ['configmaps'], 'scope': 'Namespaced'}]
    webhook = dict(name='generation-fence.qa.compute.cps.unileoben.ac.at', admissionReviewVersions=['v1'],
        sideEffects='None', failurePolicy='Fail', matchPolicy='Exact', timeoutSeconds=5,
        namespaceSelector={'matchLabels': {'kubernetes.io/metadata.name': namespace}}, rules=rules,
        clientConfig={'caBundle': base64.b64encode(ca_bundle).decode(), 'service': {'namespace': service_namespace, 'name': 'generation-fence', 'path': '/validate', 'port': 443}})
    webhooks = [webhook]
    if node_names:
        role = {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRole', 'metadata': {'name': service_namespace + '-nodes'},
                'rules': [{'apiGroups': [''], 'resources': ['nodes'], 'resourceNames': list(node_names), 'verbs': ['get']}]}
        items.extend([role, {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRoleBinding', 'metadata': {'name': role['metadata']['name']},
            'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole', 'name': role['metadata']['name']},
            'subjects': [{'kind': 'ServiceAccount', 'namespace': service_namespace, 'name': 'generation-fence'}]}])
        node_webhook = dict(webhook, name='fixed-node-window.qa.compute.cps.unileoben.ac.at', namespaceSelector={},
            matchConditions=[{'name': 'exact-reviewed-nodes', 'expression': 'request.name in ' + json.dumps(list(node_names))}],
            rules=[{'apiGroups': [''], 'apiVersions': ['v1'], 'operations': ['UPDATE', 'DELETE'], 'resources': ['nodes', 'nodes/status'], 'scope': 'Cluster'}])
        webhooks.append(node_webhook)
    if sealer_rbac:
        names = sorted(cm['metadata']['name'] for r in registry['records'] for cm in r['configMaps'])
        if not names: raise ValueError('Exact reviewed map names required before sealer PATCH RBAC')
        items.extend([{'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': {'name': 'trusted-sealer', 'namespace': service_namespace}},
            {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': {'name': 'trusted-sealer', 'namespace': namespace},
             'rules': [{'apiGroups': [''], 'resources': ['configmaps'], 'resourceNames': names, 'verbs': ['get', 'patch']},
                       {'apiGroups': [''], 'resources': ['pods'], 'resourceNames': [r['pod']['metadata']['name'] for r in registry['records']], 'verbs': ['get']},
                       {'apiGroups': ['argoproj.io'], 'resources': ['workflows'], 'resourceNames': list({r['workflow']['metadata']['name'] for r in registry['records']}), 'verbs': ['get']}]},
            {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': {'name': 'trusted-sealer', 'namespace': namespace},
             'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'trusted-sealer'},
             'subjects': [{'kind': 'ServiceAccount', 'namespace': service_namespace, 'name': 'trusted-sealer'}]}])
        # Sealer requires the same explicit Node GET capability, never Node edits.
        if node_names:
            items.append({'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRoleBinding', 'metadata': {'name': service_namespace + '-sealer-nodes'},
                'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole', 'name': service_namespace + '-nodes'},
                'subjects': [{'kind': 'ServiceAccount', 'namespace': service_namespace, 'name': 'trusted-sealer'}]})
    items.extend(quota_transition.build(registry, quota_writers=quota_writers)['items'])
    items.append({'apiVersion': 'admissionregistration.k8s.io/v1', 'kind': 'ValidatingWebhookConfiguration',
                  'metadata': {'name': service_namespace, 'annotations': annotations}, 'webhooks': webhooks})
    return {'apiVersion': 'v1', 'kind': 'List', 'items': items}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--ca-bundle', type=Path, required=True)
    parser.add_argument('--registry', type=Path)
    parser.add_argument('--namespace', default='cps-dynamic-admission-coordination')
    parser.add_argument('--service-namespace', default='cps-dynamic-coordination-review')
    parser.add_argument('--node-name', action='append', default=[])
    parser.add_argument('--sealer-rbac', action='store_true')
    parser.add_argument('--quota-writer', action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text()) if args.registry else None
    manifest = build(image=args.image, ca_bundle=args.ca_bundle.read_bytes(), registry=registry,
                     namespace=args.namespace, service_namespace=args.service_namespace,
                     node_names=args.node_name, sealer_rbac=args.sealer_rbac, quota_writers=args.quota_writer)
    with args.output.open('x') as output: yaml.safe_dump_all(manifest['items'], output, sort_keys=False)
    print(json.dumps({'applied': False, 'productionAtomicity': False, 'resources': len(manifest['items'])}))


if __name__ == '__main__': main()

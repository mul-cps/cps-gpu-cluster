"""Render the optional visitor boundary; fixture digests never qualify a release."""
import copy
import json
import pathlib
import subprocess
import tempfile
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
IMAGE = 'registry.invalid/compute-visitor@sha256:' + '2' * 64


def enabled_values():
    policy = json.loads((ROOT / 'compute-policy/generated/policy.json').read_text())
    return {'enabled': True, 'policyJson': json.dumps(policy), 'policyHash': policy['policyHash'],
        'gateway': {'image': IMAGE},
        'consoles': {'cps': {'image': IMAGE}, 'cit': {'image': IMAGE,
            'publicCallbackUrl': 'https://cit.example.invalid/services/cit-admin/oauth_callback'}},
        'computeVisitor': {'enabled': True, 'image': IMAGE,
            'gatewayCaConfigMapRef': 'cps-compute-gateway-ca',
            'sources': {
                'cps': {'enabled': True, 'publicOrigin': 'https://cps.example.invalid',
                    'hubApiUrl': 'https://cps.example.invalid/hub/api',
                    'secretRef': 'cps-compute-ui-oauth', 'hubCaConfigMapRef': 'cps-hub-public-ca',
                    'hubHttpsCidrs': ['192.0.2.10/32']},
                'cit': {'enabled': True, 'publicOrigin': 'https://cit.example.invalid',
                    'hubApiUrl': 'https://cit.example.invalid/hub/api',
                    'secretRef': 'cit-compute-ui-oauth', 'hubCaConfigMapRef': 'cit-hub-public-ca',
                    'hubHttpsCidrs': ['2001:db8::10/128']}}}}


class ComputeVisitorChart(unittest.TestCase):
    def render(self, values):
        with tempfile.NamedTemporaryFile('w', suffix='.yaml') as file:
            yaml.safe_dump(values, file)
            file.flush()
            return subprocess.run(['helm', 'template', 'compute', str(ROOT / 'platform-staging/chart'),
                '-f', file.name], text=True, capture_output=True)

    def documents(self, values):
        result = self.render(values)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [doc for doc in yaml.safe_load_all(result.stdout) if doc]

    def test_default_and_outer_disabled_render_no_visitor_components(self):
        self.assertEqual(self.documents({}), [])
        values = enabled_values()
        values['enabled'] = False
        self.assertEqual(self.documents(values), [])
        values['enabled'] = True
        values['computeVisitor']['enabled'] = False
        self.assertFalse(any('-compute-ui' in doc['metadata']['name'] for doc in self.documents(values)))

    def test_two_dedicated_frontends_use_exact_api_configuration_and_no_control_credentials(self):
        docs = self.documents(enabled_values())
        for source, hub_namespace in (('cps', 'jupyterhub'), ('cit', 'cit-jhub')):
            name = source + '-compute-ui'
            deployment = next(doc for doc in docs if doc['kind'] == 'Deployment' and doc['metadata']['name'] == name)
            self.assertEqual(deployment['metadata']['namespace'], 'cps-compute')
            self.assertEqual(deployment['spec']['replicas'], 1)
            self.assertEqual(deployment['spec']['strategy']['type'], 'Recreate')
            pod = deployment['spec']['template']['spec']
            self.assertFalse(pod['automountServiceAccountToken'])
            self.assertNotIn('serviceAccountName', pod)
            self.assertEqual(pod['securityContext']['runAsUser'], 10001)
            container = pod['containers'][0]
            self.assertEqual(container['image'], IMAGE)
            self.assertEqual(container['command'], ['cps-compute-visitor'])
            self.assertEqual(container['args'], ['--bind', '0.0.0.0', '--port', '8080'])
            self.assertEqual(container['resources']['requests']['memory'], '2Gi')
            self.assertEqual(container['resources']['limits']['memory'], '4Gi')
            self.assertTrue(container['securityContext']['readOnlyRootFilesystem'])
            self.assertFalse(container['securityContext']['allowPrivilegeEscalation'])
            self.assertNotIn('envFrom', container)
            env = {row['name']: row for row in container['env']}
            expected = {'SOURCE': source, 'OAUTH_CLIENT_ID': 'service-' + name,
                'PUBLIC_ORIGIN': 'https://' + source + '.example.invalid',
                'HUB_API_URL': 'https://' + source + '.example.invalid/hub/api',
                'HUB_AUTHORIZATION_URL': 'https://' + source + '.example.invalid/hub/api/oauth2/authorize',
                'COMPUTE_URL': 'https://compute-gateway.cps-compute.svc.cluster.local:8000',
                'HUB_CA_FILE': '/trust/hub/ca.crt', 'COMPUTE_CA_FILE': '/trust/gateway/ca.crt'}
            for key, value in expected.items():
                self.assertEqual(env['COMPUTE_VISITOR_' + key]['value'], value)
            for suffix, key in (('OAUTH_CLIENT_SECRET', 'oauth-client-secret'), ('COOKIE_SECRET', 'cookie-secret')):
                self.assertEqual(env['COMPUTE_VISITOR_' + suffix]['valueFrom'], {
                    'secretKeyRef': {'name': name + '-oauth', 'key': key}})
            self.assertFalse(any(row.startswith(('JUPYTERHUB_', 'KUBERNETES_', 'CPS_WORKSPACE_')) for row in env))
            self.assertFalse(any('secret' in volume or 'projected' in volume or 'persistentVolumeClaim' in volume
                                 for volume in pod['volumes']))
            trust = {volume['name']: volume['configMap'] for volume in pod['volumes'] if 'configMap' in volume}
            self.assertEqual(trust, {'hub-ca': {'name': source + '-hub-public-ca', 'items': [{'key': 'ca.crt', 'path': 'ca.crt'}]},
                'gateway-ca': {'name': 'cps-compute-gateway-ca', 'items': [{'key': 'ca.crt', 'path': 'ca.crt'}]}})
            service = next(doc for doc in docs if doc['kind'] == 'Service' and doc['metadata']['name'] == name)
            self.assertEqual(service['metadata']['namespace'], 'cps-compute')
            self.assertEqual(service['spec'].get('type', 'ClusterIP'), 'ClusterIP')
            self.assertEqual(service['spec']['selector'], {'app': name})
            self.assertEqual(service['spec']['ports'], [{'name': 'http', 'port': 8080, 'targetPort': 'http'}])
        self.assertFalse(any(doc['kind'] in ('Ingress', 'Role', 'RoleBinding', 'ServiceAccount', 'Secret')
            and '-compute-ui' in doc['metadata']['name'] for doc in docs))

    def test_network_boundary_permits_only_own_hub_proxy_dns_https_hub_and_gateway(self):
        docs = self.documents(enabled_values())
        for source, hub_namespace, cidr in (('cps', 'jupyterhub', '192.0.2.10/32'),
                                            ('cit', 'cit-jhub', '2001:db8::10/128')):
            name = source + '-compute-ui'
            boundary = next(doc for doc in docs if doc['kind'] == 'NetworkPolicy' and doc['metadata']['name'] == name)
            self.assertEqual(boundary['metadata']['namespace'], 'cps-compute')
            self.assertEqual(boundary['spec']['podSelector'], {'matchLabels': {'app': name}})
            self.assertEqual(boundary['spec']['policyTypes'], ['Ingress', 'Egress'])
            self.assertEqual(boundary['spec']['ingress'], [{'from': [{
                'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': hub_namespace}},
                'podSelector': {'matchLabels': {'app': 'jupyterhub', 'component': 'proxy'}}}],
                'ports': [{'protocol': 'TCP', 'port': 8080}]}])
            self.assertEqual(boundary['spec']['egress'], [
                {'to': [{'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': 'kube-system'}},
                    'podSelector': {'matchLabels': {'k8s-app': 'kube-dns'}}}],
                    'ports': [{'protocol': 'UDP', 'port': 53}, {'protocol': 'TCP', 'port': 53}]},
                {'to': [{'podSelector': {'matchLabels': {'app': 'compute-gateway'}}}],
                    'ports': [{'protocol': 'TCP', 'port': 8000}]},
                {'to': [{'ipBlock': {'cidr': cidr}}], 'ports': [{'protocol': 'TCP', 'port': 443}]}])
            gateway = next(doc for doc in docs if doc['kind'] == 'NetworkPolicy'
                and doc['metadata']['name'] == name + '-gateway')
            self.assertEqual(gateway['spec'], {'podSelector': {'matchLabels': {'app': 'compute-gateway'}},
                'policyTypes': ['Ingress'], 'ingress': [{'from': [{'podSelector': {'matchLabels': {'app': name}}}],
                    'ports': [{'protocol': 'TCP', 'port': 8000}]}]})

    def test_source_disable_does_not_create_that_sources_workload_or_network_permissions(self):
        values = enabled_values()
        values['computeVisitor']['sources']['cit'] = {'enabled': False}
        docs = self.documents(values)
        names = {doc['metadata']['name'] for doc in docs}
        self.assertIn('cps-compute-ui', names)
        self.assertFalse(any(name.startswith('cit-compute-ui') for name in names))

    def test_incomplete_or_cross_wired_configuration_is_rejected(self):
        cases = {
            'missing-image': lambda v: v['computeVisitor'].update(image=''),
            'mutable-image': lambda v: v['computeVisitor'].update(image='registry.invalid/visitor:latest'),
            'string-enabled': lambda v: v['computeVisitor'].update(enabled='false'),
            'missing-oauth-secret': lambda v: v['computeVisitor']['sources']['cps'].update(secretRef=''),
            'reused-secret': lambda v: v['computeVisitor']['sources']['cit'].update(secretRef='cps-compute-ui-oauth'),
            'admin-secret': lambda v: v['computeVisitor']['sources']['cps'].update(secretRef='cps-admin-oauth'),
            'missing-gateway-ca': lambda v: v['computeVisitor'].update(gatewayCaConfigMapRef=''),
            'foreign-gateway-ca': lambda v: v['computeVisitor'].update(gatewayCaConfigMapRef='unreviewed-ca'),
            'missing-hub-ca': lambda v: v['computeVisitor']['sources']['cps'].update(hubCaConfigMapRef=''),
            'plaintext-hub': lambda v: v['computeVisitor']['sources']['cps'].update(hubApiUrl='http://hub:8081/hub/api'),
            'foreign-hub': lambda v: v['computeVisitor']['sources']['cps'].update(hubApiUrl='https://cit.example.invalid/hub/api'),
            'origin-path': lambda v: v['computeVisitor']['sources']['cps'].update(publicOrigin='https://cps.example.invalid/path'),
            'missing-hub-egress': lambda v: v['computeVisitor']['sources']['cps'].update(hubHttpsCidrs=[]),
            'broad-hub-egress': lambda v: v['computeVisitor']['sources']['cps'].update(hubHttpsCidrs=['0.0.0.0/0']),
            'admin-port': lambda v: v['computeVisitor'].update(port=10101),
            'gateway-port': lambda v: v['computeVisitor'].update(port=8000),
            'gateway-collision': lambda v: v['gateway'].update(port=8080,
                url='https://compute-gateway.cps-compute.svc.cluster.local:8080'),
            'foreign-namespace': lambda v: v.update(namespace='other-namespace'),
        }
        for name, change in cases.items():
            with self.subTest(name=name):
                values = copy.deepcopy(enabled_values())
                change(values)
                result = self.render(values)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('Compute visitor', result.stderr)


if __name__ == '__main__':
    unittest.main()

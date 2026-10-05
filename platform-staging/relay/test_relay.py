import pathlib
import unittest

import yaml


class RelayTests(unittest.TestCase):
    def test_private_persistent_credential_free_gateway(self):
        root = pathlib.Path(__file__).parent
        objects = list(yaml.safe_load_all((root / 'deployment.yaml').read_text()))
        deployment = next(x for x in objects if x['kind'] == 'Deployment')
        spec = deployment['spec']['template']['spec']
        self.assertFalse(spec['automountServiceAccountToken'])
        self.assertFalse(spec.get('hostNetwork', False))
        self.assertEqual(deployment['spec']['replicas'], 1)
        self.assertEqual(deployment['spec']['strategy']['type'], 'Recreate')
        state = next(v for v in spec['volumes'] if v['name'] == 'state')
        self.assertIn('persistentVolumeClaim', state)
        for container in spec['containers'] + spec['initContainers']:
            self.assertIn('@sha256:', container['image'])
            self.assertNotIn('NB_SETUP_KEY', str(container))
            self.assertNotIn('hostPort', str(container))
        service = next(x for x in objects if x['kind'] == 'Service')
        self.assertEqual(service['spec']['type'], 'ClusterIP')
        proxy = next(c for c in spec['containers'] if c['name'] == 'proxy')
        self.assertTrue(proxy['securityContext']['runAsNonRoot'])
        self.assertTrue(proxy['securityContext']['readOnlyRootFilesystem'])
        config = (root / 'haproxy.cfg').read_text()
        self.assertIn('verify required', config)
        self.assertIn('verifyhost truenas.local', config)
        self.assertIn('ssl crt /tls/server.pem', config)
        policy = next(x for x in objects if x['kind'] == 'NetworkPolicy')
        self.assertEqual(policy['spec']['ingress'][0]['ports'], [{'protocol': 'TCP', 'port': 8333}])


if __name__ == '__main__':
    unittest.main()

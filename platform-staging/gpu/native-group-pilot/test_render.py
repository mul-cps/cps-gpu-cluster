import importlib
import json
from pathlib import Path
import unittest
from test_node_agent import fixtures

HERE = Path(__file__).resolve().parent

class RenderTest(unittest.TestCase):
    def setUp(self):
        if not (HERE / 'render.py').exists(): self.fail('Disabled deployment renderer is missing')
        self.render = importlib.import_module('render')

    def test_default_deployment_is_zero_replicas_with_cpu_resources_and_pinned_code(self):
        result = self.render.render()
        deployment = next(v for v in result['items'] if v['kind'] == 'Deployment')
        self.assertEqual(deployment['spec']['replicas'], 0)
        spec = deployment['spec']['template']['spec']
        self.assertEqual(spec['nodeName'], 'k3s-wk-gpu2')
        self.assertTrue(spec['hostPID'])
        container = spec['containers'][0]
        self.assertEqual(set(container['resources']['requests']), {'cpu', 'memory'})
        self.assertTrue(container['securityContext']['privileged'])
        maps = [v for v in result['items'] if v['kind'] == 'ConfigMap']
        self.assertTrue(all(v['immutable'] for v in maps))
        code = next(v for v in maps if 'node_agent.py' in v['data'])
        self.assertIn('native_gpu_health.py', code['data'])
        self.assertIn('source-snapshot.json', code['data'])

    def test_enable_requires_explicit_enabled_config_and_real_digest_image(self):
        config, _, _ = fixtures()
        with self.assertRaises(ValueError): self.render.render(config=config, enable=True)
        disabled = dict(config, enabled=False)
        with self.assertRaises(ValueError): self.render.render(config=disabled, enable=True, image='ghcr.io/cps/native@sha256:' + 'd' * 64)
        result = self.render.render(config=config, enable=True, image='ghcr.io/cps/native@sha256:' + 'd' * 64)
        deployment = next(v for v in result['items'] if v['kind'] == 'Deployment')
        self.assertEqual(deployment['spec']['replicas'], 1)
        with self.assertRaises(ValueError): self.render.render(config=config, enable=True, image='latest')

    def test_rbac_limits_pods_nodes_and_authority_configmaps(self):
        result = self.render.render()
        pod_roles = [v for v in result['items'] if v['kind'] == 'Role' and v['metadata']['namespace'] in ('jupyterhub', 'cit-jhub')]
        self.assertEqual(len(pod_roles), 2)
        self.assertTrue(all(v['rules'] == [{'apiGroups': [''], 'resources': ['pods'], 'verbs': ['get', 'delete']}] for v in pod_roles))
        cluster = next(v for v in result['items'] if v['kind'] == 'ClusterRole')
        self.assertEqual(cluster['rules'], [{'apiGroups': [''], 'resources': ['nodes'], 'resourceNames': ['k3s-wk-gpu2'], 'verbs': ['get']}])
        authority = next(v for v in result['items'] if v['kind'] == 'Role' and v['metadata']['namespace'] == 'cps-native-authority')
        self.assertEqual(authority['rules'], [{'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get', 'list', 'create']}])
        policy = next(v for v in result['items'] if v['kind'] == 'ValidatingAdmissionPolicy')
        expressions = '\n'.join(v['expression'] for v in policy['spec']['validations'])
        self.assertIn('cps-native-cleanup-', expressions)
        self.assertIn('object.immutable', expressions)
        self.assertIn('receipt.json', expressions)
        self.assertIn('system:serviceaccount:cps-native-authority:cps-native-node-agent', policy['spec']['matchConditions'][0]['expression'])

if __name__ == '__main__': unittest.main()

"""Render the optional personal Argo boundary without live credentials."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
IMAGE = 'registry.invalid/fixture@sha256:' + '1' * 64


class PersonalArgoChart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        policy = json.loads((ROOT / 'compute-policy/generated/policy.json').read_text())
        cls.values = {
            'enabled': True, 'policyJson': json.dumps(policy), 'policyHash': policy['policyHash'],
            'gateway': {'image': IMAGE, 'argoUi': {'enabled': True}},
            'consoles': {source: {'image': IMAGE, 'publicCallbackUrl': f'https://{source}.invalid/services/{source}-admin/oauth_callback'} for source in ('cps', 'cit')},
            'personalArgo': {'enabled': True, 'image': IMAGE, 'nativeUrl': 'https://native.invalid:2746/argo',
                'sources': {source: {'enabled': True, 'publicOrigin': f'https://{source}.invalid',
                    'hubApiUrl': f'https://hub-{source}.invalid/hub/api',
                    'ingress': {'enabled': True, 'host': f'{source}.invalid', 'tlsSecretRef': f'{source}-tls'}} for source in ('cps', 'cit')}}}

    def render(self, values=None):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml') as stream:
            yaml.safe_dump(self.values if values is None else values, stream)
            stream.flush()
            result = subprocess.run(['helm', 'template', 'fixture', str(ROOT / 'platform-staging/chart'), '-f', stream.name], capture_output=True, text=True)
        return result, list(yaml.safe_load_all(result.stdout)) if result.returncode == 0 else []

    def test_disabled_defaults_emit_no_resources(self):
        result, objects = self.render({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(objects, [])

    def test_each_source_has_independent_oauth_and_no_kubernetes_identity(self):
        result, objects = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        for source in ('cps', 'cit'):
            deployment = next(o for o in objects if o and o['kind'] == 'Deployment' and o['metadata']['name'] == f'{source}-argo-ui')
            pod = deployment['spec']['template']['spec']; container = pod['containers'][0]
            self.assertFalse(pod['automountServiceAccountToken'])
            self.assertTrue(container['securityContext']['readOnlyRootFilesystem'])
            env = {e['name']: e for e in container['env']}
            self.assertEqual(env['ARGO_USER_OAUTH_CLIENT_ID']['value'], f'service-{source}-argo-ui')
            self.assertEqual(env['ARGO_USER_OAUTH_CLIENT_SECRET']['valueFrom']['secretKeyRef']['name'], f'{source}-argo-ui-oauth')
            self.assertNotIn('JUPYTERHUB_API_TOKEN', env)

    def test_reader_rotator_can_only_request_named_reader_and_patch_named_secret(self):
        result, objects = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        roles = {o['metadata']['name']: o for o in objects if o and o['kind'] == 'Role'}
        request = roles['cps-argo-ui-token-request']['rules']
        publish = roles['cps-argo-ui-token-publish']['rules']
        self.assertEqual(request, [{'apiGroups': [''], 'resources': ['serviceaccounts/token'], 'resourceNames': ['argo-artifact-reader'], 'verbs': ['create']}])
        self.assertEqual(publish, [{'apiGroups': [''], 'resources': ['secrets'], 'resourceNames': ['cps-argo-ui-reader'], 'verbs': ['patch']}])
        gateway = next(o for o in objects if o and o['kind'] == 'Deployment' and o['metadata']['name'] == 'compute-gateway')
        volumes = gateway['spec']['template']['spec']['volumes']
        self.assertEqual(next(v for v in volumes if v['name'] == 'argo-ui-reader')['secret']['items'], [{'key': 'token', 'path': 'token'}])

    def test_gateway_owner_adapter_must_be_explicitly_enabled(self):
        values = copy.deepcopy(self.values); values['gateway']['argoUi']['enabled'] = False
        result, _ = self.render(values)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('owner-filtering gateway adapter', result.stderr)

    def test_public_ingress_cannot_change_callback_origin(self):
        values = copy.deepcopy(self.values); values['personalArgo']['sources']['cps']['ingress']['host'] = 'foreign.invalid'
        result, _ = self.render(values)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('match exactly', result.stderr)

    def test_native_backend_rejects_plaintext_and_unknown_base_path(self):
        for url in ('http://native.invalid/argo', 'https://native.invalid', 'https://native.invalid/foreign'):
            with self.subTest(url=url):
                values = copy.deepcopy(self.values); values['personalArgo']['nativeUrl'] = url
                result, _ = self.render(values)
                self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()

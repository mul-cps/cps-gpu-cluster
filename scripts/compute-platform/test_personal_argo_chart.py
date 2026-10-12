"""Render the optional personal Argo boundary without live credentials."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

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
            self.assertGreater(pod['terminationGracePeriodSeconds'], 30)
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

    def test_reader_rotation_waits_for_explicit_activation(self):
        result, objects = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        cron = next(o for o in objects if o and o['kind'] == 'CronJob' and o['metadata']['name'] == 'argo-ui-token-rotator')
        self.assertIs(cron['spec'].get('suspend'), True)
        values = copy.deepcopy(self.values)
        values['gateway']['argoUi']['rotationSuspended'] = False
        result, objects = self.render(values)
        self.assertEqual(result.returncode, 0, result.stderr)
        cron = next(o for o in objects if o and o['kind'] == 'CronJob' and o['metadata']['name'] == 'argo-ui-token-rotator')
        self.assertIs(cron['spec']['suspend'], False)

    def test_prepared_activation_pins_privacy_frontend_and_keeps_both_sources_private(self):
        directory = ROOT / 'platform-staging/argo/personal-activation-20261012'
        values = yaml.safe_load((directory / 'values.yaml').read_text())
        values.update({key: self.values[key] for key in ('policyJson', 'policyHash')})
        frontend_image = 'ghcr.io/mul-cps/e2x-course-hub@sha256:7e1509969062bc3b0855671c12f181548494cb6095669b949e0426a5e74c2b2e'
        self.assertEqual(values['personalArgo']['image'], frontend_image)
        result, objects = self.render(values)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(o and o['kind'] == 'Ingress' and o['metadata']['name'].endswith('-argo-ui') for o in objects))
        for source in ('cps', 'cit'):
            deployment = next(o for o in objects if o and o['kind'] == 'Deployment' and o['metadata']['name'] == source + '-argo-ui')
            self.assertEqual(deployment['spec']['template']['spec']['containers'][0]['image'], frontend_image)
            env = {e['name']: e for e in deployment['spec']['template']['spec']['containers'][0]['env']}
            self.assertEqual(env['ARGO_USER_NATIVE_ARGO_URL']['value'], 'https://cps-argo-argo-workflows-server.cps-argo.svc.cluster.local:2746')
            self.assertEqual(env['ARGO_USER_OAUTH_CLIENT_ID']['value'], 'service-' + source + '-argo-ui')

    def test_prepared_activation_still_rejects_missing_frontend_image(self):
        directory = ROOT / 'platform-staging/argo/personal-activation-20261012'
        values = yaml.safe_load((directory / 'values.yaml').read_text())
        values.update({key: self.values[key] for key in ('policyJson', 'policyHash')})
        values['personalArgo']['image'] = ''
        result, _ = self.render(values)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('released service image digest', result.stderr)

    def test_persistent_hub_fragments_preserve_existing_roles_and_register_own_source(self):
        directory = ROOT / 'platform-staging/argo/personal-activation-20261012'
        for source, origin in (('cps', 'https://jupyterhub.dshl.unileoben.ac.at'), ('cit', 'https://jhub.dshl.unileoben.ac.at')):
            values = yaml.safe_load((directory / (source + '-hub-values-fragment.yaml')).read_text())
            env = values['hub']['extraEnv']
            self.assertEqual(env, [{'name': 'PERSONAL_ARGO_OAUTH_CLIENT_SECRET', 'valueFrom': {'secretKeyRef': {'name': 'personal-argo-oauth', 'key': 'oauth-client-secret'}}}])
            original = [{'name': 'user', 'scopes': ['self', 'access:services!service=existing']}, {'name': 'operator', 'scopes': ['read:users']}]
            c = SimpleNamespace(JupyterHub=SimpleNamespace(services=[{'name': 'existing'}], load_roles=copy.deepcopy(original)))
            with patch.dict(os.environ, {'PERSONAL_ARGO_OAUTH_CLIENT_SECRET': 'synthetic-' + source}, clear=True):
                exec(values['hub']['extraConfig']['99-personal-argo-service'], {'c': c})
            self.assertEqual(c.JupyterHub.services[0], {'name': 'existing'})
            self.assertEqual(c.JupyterHub.services[1], {'name': source + '-argo-ui', 'api_token': 'synthetic-' + source, 'oauth_client_id': 'service-' + source + '-argo-ui', 'oauth_redirect_uri': origin + '/argo/oauth_callback', 'oauth_client_allowed_scopes': [], 'display': False})
            self.assertEqual(c.JupyterHub.load_roles, [{'name': 'user', 'scopes': ['self', 'access:services!service=existing', 'access:services!service=' + source + '-argo-ui']}, original[1]])

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
        for url in ('http://native.invalid/argo', 'http://native.invalid/', 'https://native.invalid/foreign',
                    'https://native.invalid//', 'https://native.invalid/argo//', 'https://native.invalid/argo/api'):
            with self.subTest(url=url):
                values = copy.deepcopy(self.values); values['personalArgo']['nativeUrl'] = url
                result, _ = self.render(values)
                self.assertNotEqual(result.returncode, 0)

    def test_native_backend_accepts_explicit_https_root_or_argo(self):
        for url in ('https://native.invalid', 'https://native.invalid/', 'https://native.invalid/argo', 'https://native.invalid/argo/'):
            with self.subTest(url=url):
                values = copy.deepcopy(self.values); values['personalArgo']['nativeUrl'] = url
                result, objects = self.render(values)
                self.assertEqual(result.returncode, 0, result.stderr)
                deployment = next(o for o in objects if o and o['kind'] == 'Deployment' and o['metadata']['name'] == 'cps-argo-ui')
                env = {e['name']: e for e in deployment['spec']['template']['spec']['containers'][0]['env']}
                self.assertEqual(env['ARGO_USER_NATIVE_ARGO_URL']['value'], url)


if __name__ == '__main__':
    unittest.main()

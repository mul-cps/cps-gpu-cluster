"""Offline preservation checks using synthetic, non-production captures."""
import base64
import copy
import json
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import unittest

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PIN = 'ghcr.io/mul-cps/e2x-course-hub@sha256:fd8ba6c022497f06b6f4b42fc0b37b9cf164f3136ac204d753d82a20fdef3a7a'


def apply_patch(original, operations):
    result = copy.deepcopy(original)
    for operation in operations:
        keys = operation['path'].strip('/').split('/')
        parent = result
        for key in keys[:-1]:
            parent = parent[int(key)] if isinstance(parent, list) else parent[key]
        key = keys[-1]
        if operation['op'] == 'test':
            assert parent[key] == operation['value']
        elif isinstance(parent, list):
            assert operation['op'] == 'add' and key == '-'
            parent.append(operation['value'])
        else:
            parent[key] = operation['value']
    return result


class Prepare(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.output = self.directory / 'prepared'
        self.inputs = {}
        self.objects = {}
        policy = json.loads((ROOT / 'compute-policy/generated/policy.json').read_text())
        self.capture('policy_configmap', 'ConfigMap', 'compute-policy', 'cps-compute', data={'policy.json': json.dumps(policy)})
        self.runtime = {'artifacts': {'secret': 'synthetic-private-value'}, 'argo_ca_file': '/trust/ca.crt',
                        'nativeGpuGroups': {'enabled': False}, 'nativeGpuQualification': {'enabled': True},
                        'unknownConcurrentSetting': [1, {'keep': True}], 'argoUi': {'enabled': False}}
        self.capture('gateway_runtime_secret', 'Secret', 'cps-compute-runtime', 'cps-compute',
                     data={'runtime.json': self.encode(json.dumps(self.runtime)), 'other': 'cHJlc2VydmU='})
        gateway_pod = {'containers': [{'name': 'sidecar', 'image': 'unchanged'}, {'name': 'gateway',
            'image': 'registry.invalid/gateway@sha256:' + '2' * 64, 'env': [{'name': 'KEEP', 'value': 'yes'}],
            'volumeMounts': [{'name': 'config', 'mountPath': '/config'}]}],
            'volumes': [{'name': 'config', 'secret': {'secretName': 'cps-compute-runtime'}},
                        {'name': 'policy', 'configMap': {'name': 'compute-policy'}}, {'name': 'native', 'emptyDir': {}}]}
        self.capture('gateway_deployment', 'Deployment', 'compute-gateway', 'cps-compute', spec={'template': {'spec': gateway_pod}})
        self.original_values = {}
        for source, namespace in (('cps', 'jupyterhub'), ('cit', 'cit-jhub')):
            env = [{'name': 'KEEP', 'value': 'synthetic-private-value'}] if source == 'cps' else {'KEEP': 'synthetic-private-value'}
            values = {'hub': {'extraEnv': env, 'extraConfig': {'zy-native-group-access': 'native access',
                'zz-native-group-pilot': 'native pilot'}, 'config': {'JupyterHub': {'services': [{'name': 'existing'}]}}},
                'singleuser': {'extraEnv': {'NATIVE': 'preserved'}}}
            self.original_values[source] = copy.deepcopy(values)
            self.capture(source + '_hub_secret', 'Secret', 'hub', namespace,
                data={'values.yaml': self.encode(yaml.safe_dump(values)), 'other': 'cHJlc2VydmU='})
            pod = {'containers': [{'name': 'hub', 'image': 'unchanged', 'env': [{'name': 'KEEP', 'value': 'yes'}],
                'volumeMounts': [{'name': 'native', 'mountPath': '/etc/cps-native-hub'}]}],
                'volumes': [{'name': 'native', 'configMap': {'name': 'cps-native-hub-config'}}]}
            if source == 'cit':
                pod['volumes'].append({'name': 'existing-secret', 'secret': {'secretName': 'jupyterhub-secrets'}})
            self.capture(source + '_hub_deployment', 'Deployment', 'hub', namespace, spec={'template': {'spec': pod}})
        self.capture('cit_existing_secret', 'Secret', 'jupyterhub-secrets', 'cit-jhub', data={'other': 'cHJlc2VydmU='})
        self.inputs['ca_files'] = [ssl.get_default_verify_paths().cafile]
        self.manifest = self.directory / 'inputs.json'

    @staticmethod
    def encode(value):
        return base64.b64encode(value.encode()).decode()

    def capture(self, key, kind, name, namespace, **fields):
        value = {'apiVersion': 'v1', 'kind': kind, 'metadata': {'name': name, 'namespace': namespace,
                 'uid': key, 'resourceVersion': '123'}, **fields}
        self.objects[key] = value
        path = self.directory / (key + '.json')
        path.write_text(json.dumps(value)); path.chmod(0o600)
        self.inputs[key] = str(path)

    def run_prepare(self):
        for key, value in self.objects.items():
            Path(self.inputs[key]).write_text(json.dumps(value))
        self.manifest.write_text(json.dumps(self.inputs)); self.manifest.chmod(0o600)
        return subprocess.run([sys.executable, str(HERE / 'prepare.py'), '--inputs', str(self.manifest),
            '--output', str(self.output)], capture_output=True, text=True)

    def patch(self, name, key):
        return apply_patch(self.objects[key], json.loads((self.output / name).read_text()))

    def test_preparation_preserves_every_unowned_setting_and_cas(self):
        result = self.run_prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        for source in ('cps', 'cit'):
            patched = self.patch(source + '-hub-secret.patch.json', source + '_hub_secret')
            merged = yaml.safe_load(base64.b64decode(patched['data']['values.yaml']))
            original = copy.deepcopy(self.original_values[source])
            config = merged['hub']['extraConfig'].pop('99-personal-argo-service')
            self.assertIn("_personal_name = '" + source + "-argo-ui'", config)
            if source == 'cps':
                self.assertEqual(merged['hub']['extraEnv'].pop()['name'], 'PERSONAL_ARGO_OAUTH_CLIENT_SECRET')
            else:
                self.assertEqual(merged['hub']['extraEnv'].pop('PERSONAL_ARGO_OAUTH_CLIENT_SECRET'),
                    {'valueFrom': {'secretKeyRef': {'name': 'personal-argo-oauth', 'key': 'oauth-client-secret'}}})
            self.assertEqual(merged, original)
            self.assertEqual(patched['data']['other'], self.objects[source + '_hub_secret']['data']['other'])
            pod = self.patch(source + '-hub-deployment.patch.json', source + '_hub_deployment')
            entry = pod['spec']['template']['spec']['containers'][0]['env'].pop()
            self.assertEqual(entry['name'], 'PERSONAL_ARGO_OAUTH_CLIENT_SECRET')
            self.assertEqual(pod, self.objects[source + '_hub_deployment'])
        patched = self.patch('gateway-runtime.patch.json', 'gateway_runtime_secret')
        runtime = json.loads(base64.b64decode(patched['data']['runtime.json']))
        self.assertEqual(runtime.pop('argoUi'), {'enabled': True, 'readerTokenFile': '/argo-reader/token', 'temporaryDirectory': '/tmp'})
        original = copy.deepcopy(self.runtime); original.pop('argoUi')
        self.assertEqual(runtime, original)
        gateway = self.patch('gateway-deployment.patch.json', 'gateway_deployment')
        pod = gateway['spec']['template']['spec']
        self.assertEqual(pod['volumes'].pop()['name'], 'argo-ui-reader')
        self.assertEqual(pod['containers'][1]['volumeMounts'].pop()['mountPath'], '/argo-reader')
        self.assertEqual(gateway, self.objects['gateway_deployment'])
        for path in self.output.glob('*.patch.json'):
            operations = json.loads(path.read_text())
            self.assertEqual([o['path'] for o in operations[:2]], ['/metadata/uid', '/metadata/resourceVersion'])
            stale = copy.deepcopy(self.objects[next(k for k in self.objects if self.objects[k]['metadata']['uid'] == operations[0]['value'])])
            stale['metadata']['resourceVersion'] = '124'
            with self.assertRaises(AssertionError): apply_patch(stale, operations)

    def test_private_outputs_pinned_frontends_and_separate_ca_reader(self):
        result = self.run_prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('synthetic-private-value', result.stdout + result.stderr)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        for path in self.output.iterdir(): self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        objects = [o for o in yaml.safe_load_all((self.output / 'resources.yaml').read_text()) if o]
        self.assertFalse(any(o['kind'] == 'Ingress' for o in objects))
        frontends = [o for o in objects if o['kind'] == 'Deployment']
        self.assertEqual(len(frontends), 2)
        for deployment in frontends:
            pod = deployment['spec']['template']['spec']; container = pod['containers'][0]
            self.assertEqual(container['image'], PIN)
            env = {e['name']: e.get('value') for e in container['env']}
            for upstream in ('HUB', 'COMPUTE', 'NATIVE_ARGO'):
                self.assertEqual(env['ARGO_USER_' + upstream + '_CA_FILE'], '/trust/ca.crt')
            self.assertEqual(pod['volumes'][0]['configMap']['name'], 'cps-personal-argo-upstream-ca')
        cron = next(o for o in objects if o['kind'] == 'CronJob')
        self.assertIs(cron['spec']['suspend'], True)
        self.assertIn("'cps-personal-argo-reader', 'cps-argo'", cron['spec']['jobTemplate']['spec']['template']['spec']['containers'][0]['args'][0])
        reader = list(yaml.safe_load_all((self.output / 'reader-rbac.yaml').read_text()))
        role = next(o for o in reader if o['kind'] == 'Role')
        self.assertEqual(role['metadata']['namespace'], 'cps-workflows')
        self.assertEqual(role['rules'], [
            {'apiGroups': ['argoproj.io'], 'resources': ['workflows'], 'verbs': ['get', 'list', 'watch']},
            {'apiGroups': [''], 'resources': ['pods'], 'verbs': ['get', 'list']},
            {'apiGroups': [''], 'resources': ['pods/log'], 'verbs': ['get']}])

    def test_policy_binding_conflict_rejected(self):
        self.objects['gateway_deployment']['spec']['template']['spec']['volumes'][1]['configMap']['name'] = 'wrong'
        result = self.run_prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('policy capture does not match gateway', result.stderr)
        self.assertFalse(self.output.exists())

    def test_existing_secret_override_rejected(self):
        self.objects['cit_existing_secret']['data']['values.yaml'] = self.encode('synthetic-private-value')
        result = self.run_prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('synthetic-private-value', result.stderr)
        self.assertIn('existing-secret values override', result.stderr)

    def test_conflicting_owned_fields_rejected(self):
        cases = [('hub', lambda: self.objects['cps_hub_deployment']['spec']['template']['spec']['containers'][0]['env'].append({'name': 'PERSONAL_ARGO_OAUTH_CLIENT_SECRET', 'value': 'synthetic-private-value'})),
                 ('runtime', lambda: self.runtime.update(argoUi={'enabled': True})),
                 ('volume', lambda: self.objects['gateway_deployment']['spec']['template']['spec']['volumes'].append({'name': 'argo-ui-reader'}))]
        for label, mutate in cases:
            with self.subTest(label=label):
                saved = copy.deepcopy(self.objects); saved_runtime = copy.deepcopy(self.runtime)
                mutate()
                self.objects['gateway_runtime_secret']['data']['runtime.json'] = self.encode(json.dumps(self.runtime))
                result = self.run_prepare()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('synthetic-private-value', result.stderr + result.stdout)
                self.assertFalse(self.output.exists())
                self.objects = saved; self.runtime = saved_runtime

    def test_fresh_private_inputs_and_output_required(self):
        self.output.mkdir(mode=0o700)
        result = self.run_prepare()
        self.assertNotEqual(result.returncode, 0)
        self.output.rmdir()
        Path(self.inputs['cps_hub_secret']).chmod(0o644)
        result = self.run_prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('private regular file required', result.stderr)

    def test_malformed_private_input_never_prints_parser_contents(self):
        self.objects['cps_hub_secret']['data']['values.yaml'] = self.encode('hub: [synthetic-private-value')
        result = self.run_prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('synthetic-private-value', result.stdout + result.stderr)
        self.assertFalse(self.output.exists())

    def test_list_capture_selects_exact_identity(self):
        selected = copy.deepcopy(self.objects['policy_configmap'])
        self.objects['policy_configmap'] = {'kind': 'List', 'items': [selected, {'kind': 'ConfigMap', 'metadata': {'name': 'unrelated'}}]}
        result = self.run_prepare()
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()

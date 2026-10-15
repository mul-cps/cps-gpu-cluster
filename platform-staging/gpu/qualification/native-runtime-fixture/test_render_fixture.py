"""CPU tests for the operator-only native cap fixture and byte ownership."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent


def builder():
    if not (HERE / 'render_fixture.py').exists():
        raise AssertionError('Native runtime fixture builder is missing')
    spec = importlib.util.spec_from_file_location('native_fixture_builder', HERE / 'render_fixture.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FixtureTests(unittest.TestCase):
    def test_sources_and_exceptions_are_immutable_and_complete(self):
        module = builder()
        proposal = module.render()
        self.assertEqual(proposal, json.loads((HERE / 'proposal.json').read_text()))
        items = proposal['items']
        cm = next(item for item in items if item['kind'] == 'ConfigMap')
        digest = hashlib.sha256(json.dumps({'data': cm['data'], 'binaryData': cm['binaryData']},
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertTrue(cm['immutable'])
        self.assertEqual(cm['metadata']['annotations']['source.payload.sha256'], digest)
        self.assertEqual(cm['metadata']['name'], 'native-runtime-' + digest[:12])
        self.assertEqual(hashlib.sha256(base64.b64decode(cm['binaryData']['native-imports'])).hexdigest(),
                         module.BINARY_SHA)
        self.assertEqual(hashlib.sha256(cm['data']['native_gpu_runtime.py'].encode()).hexdigest(), module.RUNTIME_SHA)
        self.assertEqual(hashlib.sha256(cm['data']['cuda_probe.py'].encode()).hexdigest(), module.CUDA_SHA)
        self.assertEqual({p['metadata']['name'] for p in items if p['kind'] == 'Pod'},
                         {'native-cap-main', 'native-cap-peer'})
        for pod in (item for item in items if item['kind'] == 'Pod'):
            gate = pod['spec']['initContainers'][0]
            main = pod['spec']['containers'][0]
            self.assertEqual(gate['name'], 'cps-native-cap-gate')
            self.assertIn({'name': 'NVIDIA_VISIBLE_DEVICES', 'value': 'void'}, gate['env'])
            self.assertIn({'name': 'NVIDIA_VISIBLE_DEVICES', 'value': module.GPU}, main['env'])
            self.assertEqual(pod['spec']['nodeName'], module.NODE)
            self.assertEqual(pod['spec']['runtimeClassName'], 'nvidia')
            self.assertEqual(gate['imagePullPolicy'], 'Never')
            self.assertEqual(main['imagePullPolicy'], 'Never')
            self.assertFalse(pod['spec']['automountServiceAccountToken'])
            self.assertEqual(main['securityContext']['runAsUser'], 1000)
            self.assertEqual(main['securityContext']['runAsGroup'], 100)
            mounts = {m['name'] for m in main['volumeMounts']}
            self.assertFalse(mounts.intersection({'cps-native-receipts', 'cps-native-authority',
                                                 'cps-native-driver-metadata'}))
            self.assertEqual(pod['metadata']['annotations']['qualification.production'], 'false')
            self.assertEqual(module.runtime().native_spec_sha256(pod),
                             pod['metadata']['annotations']['cps.compute/native-spec-sha256'])

    def test_changed_binary_or_runtime_source_is_rejected(self):
        module = builder()
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / 'modified'
            bad.write_bytes(b'not-reviewed')
            with self.assertRaises(ValueError):
                module.render(binary_path=bad)
            with self.assertRaises(ValueError):
                module.render(runtime_path=bad)

    def test_dryrun_finalization_preserves_only_the_bound_operator_exceptions(self):
        module = builder()
        result = module.render()
        pod = next(i for i in result['items'] if i['kind'] == 'Pod')
        admitted = copy.deepcopy(pod)
        admitted['spec'].update({'dnsPolicy': 'ClusterFirst', 'serviceAccountName': 'default',
                                 'schedulerName': 'default-scheduler'})
        finalized, intent = module.finalize(pod, admitted, pod_uid='11111111-1111-4111-8111-111111111111')
        self.assertEqual(intent['spec_sha256'], module.runtime().native_spec_sha256(finalized))
        self.assertEqual(intent['cap_mib'], 5120)
        self.assertEqual(intent['node_uid'], module.NODE_UID)
        self.assertEqual(intent['gpu_uuid'], module.GPU)
        admitted['spec']['containers'][0]['env'].append({'name': 'LD_PRELOAD', 'value': 'hami.so'})
        with self.assertRaises(ValueError):
            module.finalize(pod, admitted, pod_uid='11111111-1111-4111-8111-111111111111')

    def test_idle_window_changes_immutable_payload_and_trusted_spec_binding(self):
        module = builder()
        default = module.render()
        default_cm = next(i for i in default['items'] if i['kind'] == 'ConfigMap')
        default_pod = next(i for i in default['items'] if i['kind'] == 'Pod')
        for seconds in (60, 1800, 3600):
            with self.subTest(seconds=seconds):
                result = module.render(idle_seconds=seconds)
                cm = next(i for i in result['items'] if i['kind'] == 'ConfigMap')
                pod = next(i for i in result['items'] if i['kind'] == 'Pod')
                self.assertTrue(cm['immutable'])
                self.assertNotEqual(cm['metadata']['name'], default_cm['metadata']['name'])
                self.assertIn(f'time.sleep({seconds})', cm['data']['main_idle.py'])
                self.assertIn(f"'idle_seconds':{seconds}", cm['data']['main_idle.py'])
                self.assertIn(f'main{seconds}s idle', pod['metadata']['annotations']['qualification.operator-exceptions'])
                self.assertNotEqual(pod['metadata']['annotations']['cps.compute/native-spec-sha256'],
                                    default_pod['metadata']['annotations']['cps.compute/native-spec-sha256'])
                finalized, intent = module.finalize(pod, copy.deepcopy(pod), idle_seconds=seconds,
                    pod_uid='11111111-1111-4111-8111-111111111111')
                self.assertEqual(intent['spec_sha256'], module.runtime().native_spec_sha256(finalized))
                self.assertEqual(intent['policy_hash'], pod['metadata']['annotations']['qualification.policy-hash'])
                self.assertNotEqual(intent['policy_hash'], module.POLICY_HASH)
                with self.assertRaisesRegex(ValueError, 'Trusted proposal changed'):
                    module.finalize(pod, copy.deepcopy(pod))

    def test_invalid_idle_window_is_rejected_before_source_reads(self):
        module = builder()
        for seconds in (59, 3601, 0, -1, True, False, 900.0, '900', None):
            with self.subTest(seconds=seconds), mock.patch.object(module, '_pinned') as pinned:
                with self.assertRaisesRegex(ValueError, 'idle_seconds'):
                    module.render(idle_seconds=seconds)
                pinned.assert_not_called()
        pod = next(i for i in module.render()['items'] if i['kind'] == 'Pod')
        with mock.patch.object(module, 'runtime') as runtime:
            with self.assertRaisesRegex(ValueError, 'idle_seconds'):
                module.finalize(pod, pod, idle_seconds=True)
            runtime.assert_not_called()


if __name__ == '__main__':
    unittest.main()

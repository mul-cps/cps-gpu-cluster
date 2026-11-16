import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[2] / 'platform-staging/gpu/upstream-sharing/prepare.py'


class PrepareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.available = SOURCE.exists()
        if cls.available:
            spec = importlib.util.spec_from_file_location('prepare', SOURCE)
            cls.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.module)

    def setUp(self):
        self.assertTrue(self.available, 'candidate preparation is not implemented')

    def test_os_plan_selects_one_nominated_host_and_never_uncordons(self):
        plan = self.module.os_plan('k3s-wk-gpu2', 'pilot-1', 'registry.example/upgrade@sha256:' + 'a' * 64)
        spec = plan['spec']
        self.assertEqual(spec['concurrency'], 1)
        self.assertTrue(spec['exclusive'])
        self.assertFalse(spec['cordon'])
        self.assertNotIn('drain', spec)
        self.assertEqual(spec['nodeSelector']['matchLabels'], {
            'kubernetes.io/hostname': 'k3s-wk-gpu2',
            'cps.unileoben.ac.at/os-upgrade': 'pilot-1',
        })
        self.assertEqual(spec['upgrade']['args'], ['pilot-1', 'k3s-wk-gpu2'])

    def test_plan_refuses_control_planes_mutable_images_and_bad_identity(self):
        for node, operation, image in [
            ('k3s-cp1', 'pilot-1', 'r/x@sha256:' + 'a' * 64),
            ('k3s-wk-gpu2', '../escape', 'r/x@sha256:' + 'a' * 64),
            ('k3s-wk-gpu2', 'pilot-1', 'r/x:latest'),
        ]:
            with self.assertRaises(ValueError):
                self.module.os_plan(node, operation, image)

    def test_fraction_postrender_limits_only_selected_worker_and_fails_closed(self):
        docs = [{'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': {'name': 'controller'}},
                {'apiVersion': 'gpu-fractioning.kai.scheduler/v1alpha1', 'kind': 'GpuFractioningConfig',
                 'metadata': {'name': 'default'}, 'spec': {'nodeSelector': {'nvidia.com/gpu.present': 'true'},
                    'fractioningAgent': {'criSocketPath': '/run/containerd/containerd.sock'}}}]
        rendered = self.module.fraction_config(docs)
        self.assertEqual(rendered[0], docs[0])
        config = rendered[1]['spec']
        self.assertEqual(config['nodeSelector'], {'kubernetes.io/hostname': 'k3s-wk-gpu2',
            'cps.unileoben.ac.at/fractioning-runtime': 'upstream'})
        self.assertFalse(config['fractioningAgent']['failOpen'])
        self.assertTrue(config['fractioningAgent']['retroactiveEnforcement'])
        self.assertEqual(config['fractioningAgent']['criSocketPath'], '/run/k3s/containerd/containerd.sock')

    def test_chart_schema_drift_or_duplicate_configs_prevent_output(self):
        for docs in [[], [{'kind': 'GpuFractioningConfig', 'metadata': {'name': 'unexpected'}}],
                     [{'kind': 'GpuFractioningConfig', 'metadata': {'name': 'default'}}] * 2]:
            with self.assertRaises(ValueError):
                self.module.fraction_config(docs)


if __name__ == '__main__':
    unittest.main()

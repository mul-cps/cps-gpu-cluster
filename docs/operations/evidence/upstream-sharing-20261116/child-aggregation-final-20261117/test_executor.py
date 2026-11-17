import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

PATH = Path(__file__).with_name('executor.py')
spec = importlib.util.spec_from_file_location('child_final_executor', PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Safety(unittest.TestCase):
    def test_exact_payload_and_two_bounded_manifests(self):
        cm, pods = m.render('child-final-test')
        self.assertTrue(cm['immutable'])
        self.assertEqual(m.hashlib.sha256(cm['data']['probe.py'].encode()).hexdigest(), m.PROBE_SHA)
        self.assertEqual(len(pods), 2)
        for pod, gpu in zip(pods, m.GPUS):
            self.assertEqual(pod['spec']['nodeName'], 'k3s-wk-gpu2')
            self.assertEqual(pod['spec']['activeDeadlineSeconds'], 240)
            self.assertEqual(pod['spec']['containers'][0]['image'], m.IMAGE)
            annotations = pod['metadata']['annotations']
            self.assertEqual(annotations['required-plugins.noderesource.dev/container.main'], '["gpu-fractioning"]')
            self.assertTrue(annotations['nvidia.com/container.main.gpus.devices'].endswith(gpu))
    def test_driver_limit_readback_rejects_wrong_limit_or_leaf(self):
        good = f"GPU 0 (UUID: {m.GPUS[0]})\n namespace: /sys/fs/cgroup/owned\n soft limit: 5120 MiB\n hard limit: 5120 MiB\n"
        m.validate_limits(good, '/owned', m.GPUS[0])
        for bad in [good.replace('hard limit: 5120', 'hard limit: 10240'), good.replace('/owned', '/other')]:
            with self.assertRaises(RuntimeError): m.validate_limits(bad, '/owned', m.GPUS[0])
    def test_replacement_is_never_deleted(self):
        calls = []
        def call(args, **kw):
            calls.append(args)
            return json.dumps({'metadata':{'uid':'replacement','resourceVersion':'9'}})
        with self.assertRaisesRegex(RuntimeError, 'replacement'):
            m.delete_owned('pods', 'fixture', 'original', call)
        self.assertEqual(len(calls), 1)
    def test_cleanup_has_exact_preconditions_and_grace(self):
        calls = []
        def call(args, **kw):
            calls.append((args, kw))
            return json.dumps({'metadata':{'uid':'original','resourceVersion':'9'}})
        m.delete_owned('pods', 'fixture', 'original', call)
        body = json.loads(calls[1][1]['data'])
        self.assertEqual(body['preconditions'], {'uid':'original','resourceVersion':'9'})
        self.assertEqual(body['gracePeriodSeconds'], 15)
        self.assertIn('--timeout=45s', calls[2][0])
    def test_unknown_create_uid_never_adopted(self):
        def forbidden(*a, **kw): self.fail('must not call Kubernetes')
        with self.assertRaisesRegex(RuntimeError, 'unknown'):
            m.delete_owned('pods', 'fixture', None, forbidden)

if __name__ == '__main__': unittest.main()

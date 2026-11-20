import pathlib
import subprocess
import unittest
import yaml


class IsolatorScopeTests(unittest.TestCase):
    def run_renderer(self, document):
        return subprocess.run(['python3', str(pathlib.Path(__file__).with_name('isolator-post-render.py'))], input=yaml.safe_dump(document), capture_output=True, text=True)

    def test_scope_is_namespace_owned_and_scheduler_specific(self):
        document = {'apiVersion': 'admissionregistration.k8s.io/v1', 'kind': 'MutatingWebhookConfiguration', 'metadata': {'name': 'kai-resource-isolator-mutating'}, 'webhooks': [{'name': 'vgpu.lib.kai-resource-isolator.io', 'objectSelector': {'matchLabels': {'skip': 'false'}}}]}
        result = self.run_renderer(document)
        self.assertEqual(result.returncode, 0, result.stderr)
        webhook = yaml.safe_load(result.stdout)['webhooks'][0]
        self.assertNotIn('objectSelector', webhook)
        self.assertEqual(webhook['namespaceSelector'], {'matchLabels': {'compute.cps.unileoben.ac.at/isolation': 'required'}})
        self.assertEqual(webhook['matchConditions'][0]['expression'], "object.spec.schedulerName == 'kai-scheduler'")

    def test_changed_upstream_shape_fails_before_activation(self):
        for document in ({'kind': 'ConfigMap'}, {'kind': 'MutatingWebhookConfiguration', 'metadata': {'name': 'unreviewed'}}):
            self.assertNotEqual(self.run_renderer(document).returncode, 0)


if __name__ == '__main__':
    unittest.main()

import pathlib
import subprocess
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


class LegacyDaskBoundaryTests(unittest.TestCase):
    def render(self, enabled):
        result = subprocess.run(['helm', 'template', 'qualification', str(ROOT / 'platform-staging/chart'),
                                 '--set', f'legacyDaskBoundary.enabled={str(enabled).lower()}'],
                                capture_output=True, text=True, check=True)
        return [d for d in yaml.safe_load_all(result.stdout) if d and
                d['metadata']['name'] == 'cps-compute-legacy-dask-boundary']

    def test_disabled_by_default(self):
        self.assertEqual(self.render(False), [])

    def test_all_mutations_all_namespaces_and_no_object_dependency(self):
        policy, binding = self.render(True)
        self.assertEqual(policy['spec']['failurePolicy'], 'Fail')
        rule = policy['spec']['matchConstraints']['resourceRules'][0]
        self.assertEqual(rule['operations'], ['CREATE', 'UPDATE', 'DELETE'])
        self.assertEqual(rule['apiVersions'], ['*'])
        self.assertIn('daskworkergroups/scale', rule['resources'])
        expression = policy['spec']['validations'][0]['expression']
        self.assertIn('system:serviceaccount:jupyterhub:dask-sa', expression)
        self.assertIn('system:serviceaccount:cit-jhub:dask-sa', expression)
        self.assertNotIn('object.', expression)
        self.assertEqual(binding['spec']['validationActions'], ['Deny'])
        self.assertNotIn('matchResources', binding['spec'])

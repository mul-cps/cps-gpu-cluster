from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]


class ExecutorBoundary(unittest.TestCase):
    def test_main_principal_has_no_executor_rbac_or_automatic_token(self):
        objects = list(yaml.safe_load_all((ROOT / 'platform-staging/workload-rbac.yaml').read_text()))
        accounts = {item['metadata']['name']:item for item in objects if item['kind']=='ServiceAccount'}
        self.assertFalse(accounts['cps-workflow']['automountServiceAccountToken'])
        subjects = [subject for item in objects if item['kind']=='RoleBinding' for subject in item['subjects']]
        self.assertTrue(subjects)
        self.assertTrue(all(subject['name']=='cps-workflow-executor' for subject in subjects))
        token = next(item for item in objects if item['kind']=='Secret')
        self.assertEqual(token['type'],'kubernetes.io/service-account-token')
        self.assertEqual(token['metadata']['annotations']['kubernetes.io/service-account.name'],'cps-workflow-executor')
        self.assertNotIn('data',token)

    def test_parameter_failure_cannot_affect_other_namespaces(self):
        policy,binding = list(yaml.safe_load_all((ROOT / 'platform-staging/admission.yaml').read_text()))
        expected = {'matchLabels':{'kubernetes.io/metadata.name':'cps-workflows'}}
        self.assertEqual(policy['spec']['matchConstraints']['namespaceSelector'],expected)
        self.assertEqual(binding['spec']['matchResources']['namespaceSelector'],expected)
        self.assertEqual(binding['spec']['paramRef']['parameterNotFoundAction'],'Deny')

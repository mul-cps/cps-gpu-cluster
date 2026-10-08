import copy
import importlib.util
from pathlib import Path
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('live_admission',ROOT/'scripts/compute-platform/qualify-live-admission.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class NormalizedPolicy(unittest.TestCase):
    def setUp(self):
        self.policy,self.binding=list(yaml.safe_load_all((ROOT/'platform-staging/admission.yaml').read_text()))

    def test_only_documented_api_defaults_match_without_mutating_input(self):
        original=copy.deepcopy(self.policy['spec']);server=copy.deepcopy(original)
        server['matchConstraints']['matchPolicy']='Equivalent'
        server['matchConstraints']['objectSelector']={}
        for rule in server['matchConstraints']['resourceRules']:rule['scope']='*'
        self.assertEqual(module.normalized(original),module.normalized(server))
        self.assertEqual(original,self.policy['spec'])

    def test_changed_namespace_or_scope_cannot_be_normalized_away(self):
        for key in ['namespace','scope']:
            changed=copy.deepcopy(self.policy['spec'])
            if key=='namespace':changed['matchConstraints']['namespaceSelector']['matchLabels']['kubernetes.io/metadata.name']='other'
            else:changed['matchConstraints']['resourceRules'][0]['scope']='Cluster'
            self.assertNotEqual(module.normalized(changed),module.normalized(self.policy['spec']))

    def test_changed_validations_and_binding_actions_are_not_defaults(self):
        changed=copy.deepcopy(self.policy['spec']);changed['validations']=[]
        self.assertNotEqual(module.normalized(changed),module.normalized(self.policy['spec']))
        changed=copy.deepcopy(self.binding['spec']);changed['validationActions']=['Warn']
        self.assertNotEqual(module.normalized(changed),module.normalized(self.binding['spec']))

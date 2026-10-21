"""Check the operator-owned CPU image used by the released Hub resolver."""
import ast
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
VALUES = ROOT / 'cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml'
CPU_IMAGE = ('ghcr.io/mul-cps/cps-jupyter-notebook@sha256:'
             '16ed0a2c9c3d8e6d3942b515fc3a32ec750b3c506323326c050370566b595497')


def profiles():
    config = yaml.safe_load(VALUES.read_text())['hub']['extraConfig']['02-profiles']
    assignments = [node for node in ast.parse(config).body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'PROFILE_CONFIGS'
                           for target in node.targets)]
    if len(assignments) != 1:
        raise AssertionError('One operator-owned PROFILE_CONFIGS table required')
    return ast.literal_eval(assignments[0].value)


class NotebookCPURuntimeTests(unittest.TestCase):
    def test_effective_cpu_default_uses_published_addon_overlay(self):
        cpu = profiles()['cpu-default']
        self.assertEqual(cpu['image'], CPU_IMAGE)
        self.assertEqual(cpu['gpu'], 0)
        self.assertIsNone(cpu['runtime_class'])

    def test_timer_overlay_is_not_selected_for_any_other_profile(self):
        table = profiles()
        self.assertEqual([name for name, profile in table.items()
                          if profile.get('image') == CPU_IMAGE], ['cpu-default'])

    def test_cpu_prepuller_pins_the_same_immutable_bytes(self):
        pull = yaml.safe_load(VALUES.read_text())['prePuller']['extraImages']['datascience']
        self.assertEqual(pull['name'] + '@' + pull['tag'].split('@', 1)[-1], CPU_IMAGE)


if __name__ == '__main__':
    unittest.main()

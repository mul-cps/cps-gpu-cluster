import pathlib
import unittest
import yaml
ROOT = pathlib.Path(__file__).resolve().parents[2]
class DeschedulerScope(unittest.TestCase):
    def test_restartable_opt_in_and_no_gangs(self):
        v = yaml.safe_load((ROOT/'cluster-maintenance/clusters/cit-cps-gpu/system/descheduler/values.yaml').read_text())
        args = v['deschedulerPolicy']['profiles'][0]['pluginConfig'][0]['args']
        self.assertEqual(args['priorityThreshold']['value'], 11)
        selector = args.get('labelSelector', {})
        self.assertEqual(selector.get('matchLabels', {}).get('compute.cps.unileoben.ac.at/descheduler-eligible'), 'true')
        self.assertIn({'key': 'pod-group-name', 'operator': 'DoesNotExist'}, selector.get('matchExpressions', []))
if __name__ == '__main__':unittest.main()

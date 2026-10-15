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

    def test_unqualified_fallback_stays_suspended_and_excludes_all_known_gangs(self):
        v = yaml.safe_load((ROOT/'cluster-maintenance/clusters/cit-cps-gpu/system/descheduler/values.yaml').read_text())
        self.assertEqual(v['kind'], 'CronJob')
        self.assertTrue(v['suspend'])
        self.assertEqual(v['image']['tag'], 'v0.34.0@sha256:18ecceedd6096627d9e496f5332e9d2431587f53699802d35393f40a5a7b7239')
        expressions=v['deschedulerPolicy']['profiles'][0]['pluginConfig'][0]['args']['labelSelector']['matchExpressions']
        self.assertEqual({entry['key'] for entry in expressions}, {'pod-group-name','scheduling.k8s.io/group-name','kai.scheduler/podgroup','jobset.sigs.k8s.io/jobset-name'})
        self.assertTrue(all(entry['operator']=='DoesNotExist' for entry in expressions))

if __name__ == '__main__':unittest.main()

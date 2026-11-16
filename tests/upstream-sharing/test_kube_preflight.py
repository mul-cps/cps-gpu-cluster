import copy
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[2] / 'platform-staging/gpu/upstream-sharing/os-upgrade/kube_preflight.py'


class PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.available = SOURCE.exists()
        if cls.available:
            spec = importlib.util.spec_from_file_location('kube_preflight', SOURCE)
            cls.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.module)

    def setUp(self):
        self.assertTrue(self.available, 'live preflight not implemented')
        self.nodes = [{'metadata': {'name': f'k3s-wk-gpu{i}', 'labels': {}}, 'spec': {},
                       'status': {'allocatable': {'nvidia.com/gpu': '2'},
                                  'conditions': [{'type': 'Ready', 'status': 'True'}]}} for i in range(1, 5)]
        self.nodes[1]['metadata']['labels']['cps.unileoben.ac.at/os-upgrade'] = 'pilot-1'
        self.nodes[1]['spec']['unschedulable'] = True
        self.pods = [{'metadata': {'uid': 'suc-job'}, 'status': {'phase': 'Running'}}]

    def check(self):
        self.module.check(self.nodes, self.pods, 'k3s-wk-gpu2', 'pilot-1', 'suc-job')

    def test_precordoned_drained_worker_with_three_peers_passes(self):
        self.check()

    def test_any_live_non_daemon_workload_blocks_upgrade(self):
        self.pods.append({'metadata': {'uid': 'user-job', 'ownerReferences': [{'kind': 'Job'}]},
                          'status': {'phase': 'Running'}})
        with self.assertRaisesRegex(RuntimeError, 'live workload'):
            self.check()

    def test_completed_pods_and_daemonsets_do_not_block(self):
        self.pods.extend([{'metadata': {'uid': 'old-job'}, 'status': {'phase': 'Succeeded'}},
                          {'metadata': {'uid': 'ds', 'ownerReferences': [{'kind': 'DaemonSet', 'controller': True}]},
                           'status': {'phase': 'Running'}}])
        self.check()

    def test_missing_peer_capacity_or_second_maintenance_blocks(self):
        for change in ['capacity', 'maintenance', 'uncordoned', 'nomination']:
            with self.subTest(change=change):
                original = copy.deepcopy(self.nodes)
                if change == 'capacity':
                    self.nodes[0]['status']['allocatable']['nvidia.com/gpu'] = '0'
                elif change == 'maintenance':
                    self.nodes[0]['metadata']['labels']['cps.unileoben.ac.at/os-upgrade'] = 'other-op'
                elif change == 'uncordoned':
                    self.nodes[1]['spec']['unschedulable'] = False
                else:
                    self.nodes[1]['metadata']['labels'].clear()
                with self.assertRaises(RuntimeError):
                    self.check()
                self.nodes = original


if __name__ == '__main__':
    unittest.main()

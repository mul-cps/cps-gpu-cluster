import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import node_journal as journal


class RestoreGateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        (self.directory / 'preflight.json').write_text(json.dumps({'protectedGpuDriverPods': [], 'protectedPvcPods': []}))
        self.node = {'metadata': {'uid': journal.UID, 'resourceVersion': 'fresh-rv',
                                 'labels': {journal.DRIVER_KEY: 'true', 'nvidia.com/gpu.deploy.mig-manager': 'true'}},
                     'spec': {'unschedulable': True}}
        before = {'uid': journal.UID, 'node': journal.NODE, 'untouchedMigManagerLabel': 'true',
                  'labels': {journal.DRIVER_KEY: 'true'}, 'unschedulable': False}
        (self.directory / 'before.json').write_text(json.dumps(before))
        self.legacy = {'metadata': {'namespace': 'gpu-operator', 'name': 'nvidia-driver-daemonset-new',
                                    'labels': {'app': 'nvidia-driver-daemonset'}},
                       'spec': {'nodeName': journal.NODE},
                       'status': {'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'True'}],
                                  'containerStatuses': [{'imageID': 'nvcr.io/nvidia/driver@sha256:41515698692bd5e192186e620b65717af960a66d22dbb5a06e3656575a5d9148'}]}}

    def tearDown(self):
        self.temp.cleanup()

    def run_prepare(self, pods, versions):
        with patch.object(journal, 'HERE', self.directory), patch.object(journal, 'get', side_effect=[self.node, {'items': pods}]), \
             patch.object(journal.subprocess, 'check_output', return_value=versions):
            return journal.prepare('restore', self.directory)

    def test_live_canary_blocks_restore_and_uncordon(self):
        canary = {'metadata': {'namespace': 'gpu-operator', 'name': 'canary', 'labels': {'app': 'gpu2-r615-driver-canary'}},
                  'spec': {'nodeName': journal.NODE}, 'status': {'phase': 'Running'}}
        with self.assertRaises(AssertionError):
            self.run_prepare([self.legacy, canary], '580.95.05, Disabled, Disabled\n' * 2)
        self.assertFalse((self.directory / 'restore.patch.json').exists())

    def test_r615_loaded_version_blocks_restore(self):
        with self.assertRaises(AssertionError):
            self.run_prepare([self.legacy], '615.71.09, Disabled, Disabled\n' * 2)
        self.assertFalse((self.directory / 'restore.patch.json').exists())

    def test_actual_r580_recovery_emits_only_private_cas_patch(self):
        output = self.run_prepare([self.legacy], '580.95.05, Disabled, Disabled\n' * 2)
        data = json.loads(output.read_text())
        self.assertEqual(data[:2], [{'op': 'test', 'path': '/metadata/uid', 'value': journal.UID},
                                   {'op': 'test', 'path': '/metadata/resourceVersion', 'value': 'fresh-rv'}])
        self.assertEqual(data[-1], {'op': 'add', 'path': '/spec/unschedulable', 'value': False})
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)

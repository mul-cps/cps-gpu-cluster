"""CPU-only qualification adapter tests; pinned SDK supplied explicitly."""
import copy
from dataclasses import asdict, replace
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from node_backend import QualificationNodeBackend, private_read, private_write
from poll import CORE_SHA256, MANUAL_SHA256, Kubernetes, health, load_pinned, main


UID = 'd3a1659e-6345-43cc-9ca5-7b8ef1aa5378'
NODE_UID = 'ceabb702-aa07-40b3-9015-7d473f3cf141'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
BOOT = '209f8bc9-a478-48e4-925a-6e07ffa56f7a'
EPOCH = 'e148263b-805d-4ccd-857c-84a03d4f4229'
CID = 'c' * 64


class Crash(BaseException): pass


class Driver:
    version = '615.71.09'
    def __init__(self, parent):
        self.parent, self.value, self.children = str(parent), {'nvml_result': 3, 'state': 'unset-or-unsupported'}, {}
        self.writes = []
        self.after_set = None
    def get(self, gpu, path):
        assert gpu == GPU
        return self.value if str(path) == self.parent else self.children.get(str(path))
    def set(self, gpu, path, soft, hard):
        assert gpu == GPU and str(path) == self.parent
        self.writes.append((soft, hard))
        self.value = {'soft': soft, 'hard': hard, 'used': 0}
        if self.after_set: self.after_set()


class NodeBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = os.environ.get('CPS_NATIVE_CONTROLLER_SOURCE')
        if not source:
            raise RuntimeError('Set CPS_NATIVE_CONTROLLER_SOURCE to the pinned SDK module; tests do not silently skip')
        cls.m = load_pinned('_qualification_test_models', source, CORE_SHA256)
        manual = Path(__file__).resolve().parents[3] / 'scheduler/qualification/r615-pod-cap/pod_cap.py'
        cls.manual = load_pinned('_qualification_test_manual', manual, MANUAL_SHA256)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); self.proc = self.root / 'proc'; self.cg = self.root / 'cg'
        (self.proc / '211').mkdir(parents=True)
        (self.proc / 'sys/kernel/random').mkdir(parents=True)
        (self.proc / 'sys/kernel/random/boot_id').write_text(BOOT)
        (self.proc / '211/stat').write_text('211 (gate spaced ) process) ' + ' '.join(['S'] + ['0'] * 18 + ['345']))
        self.relative = '/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod' + UID.replace('-', '_') + '.slice'
        self.group = self.cg / self.relative.lstrip('/')
        self.leaf = self.group / ('cri-containerd-' + CID + '.scope')
        self.leaf.mkdir(parents=True)
        (self.cg / 'cgroup.controllers').write_text('cpu memory misc')
        (self.proc / '211/cgroup').write_text('0::' + self.relative + '/' + self.leaf.name + '\n')
        for group in (self.group, self.leaf):
            (group / 'cgroup.procs').write_text('211\n')
            (group / 'cgroup.threads').write_text('211\n')
        (self.group / 'cgroup.events').write_text('populated 1\n')
        self.state = self.root / 'state'
        for part in ('', 'authority', 'receipts', 'bootstrap', 'journal'):
            (self.state / part).mkdir(mode=0o700)
        self.uid = os.getuid()
        epochfile = self.state / 'authority/driver-generation'
        epochfile.write_text(EPOCH); epochfile.chmod(0o600)
        self.pod = {'metadata': {'uid': UID, 'name': 'notebook', 'namespace': 'qualification', 'resourceVersion': '1'},
            'spec': {'nodeName': 'k3s-wk-gpu2', 'initContainers': [{'name': 'cps-native-cap-gate'}],
                     'containers': [{'name': 'main'}]}, 'status': {'containerStatuses': [], 'phase': 'Pending'}}
        spec = __import__('hashlib').sha256(json.dumps(self.pod['spec'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.intent = self.m.CapIntent('qualification', 'notebook', UID, 'k3s-wk-gpu2', NODE_UID,
                                      spec, GPU, 5120, 'sha256:' + 'a' * 64)
        self.node = {'metadata': {'uid': NODE_UID, 'name': 'k3s-wk-gpu2'}}
        self.cri = {'status': {'id': CID, 'state': 'CONTAINER_RUNNING', 'labels': {
            'io.kubernetes.pod.uid': UID, 'io.kubernetes.pod.namespace': 'qualification',
            'io.kubernetes.pod.name': 'notebook', 'io.kubernetes.container.name': 'cps-native-cap-gate'}},
            'info': {'pid': 211}}
        self.driver = Driver(self.group)
        self.healthy, self.clients, self.deleted = True, set(), []
        self.backend = QualificationNodeBackend(self.m, self.manual, intents=[self.intent], driver=self.driver,
            get_pod=lambda _: self.pod, get_node=lambda _: self.node, get_cri=lambda _: self.cri,
            delete_pod=lambda intent: self.deleted.append(intent.pod_uid), gpu_clients=lambda _: self.clients,
            health=lambda: self.healthy, proc_root=self.proc, cgroup_root=self.cg,
            state_root=self.state, trusted_uid=self.uid)
        self.journal = self.m.PrivateJournal(self.state / 'journal')
        self.controller = self.m.NativeCapController(self.backend, self.journal, enabled=True)

    def stop(self):
        self.pod['status']['phase'] = 'Succeeded'
        (self.group / 'cgroup.events').write_text('populated 0\n')
        for group in (self.group, self.leaf):
            (group / 'cgroup.procs').write_text('')
            (group / 'cgroup.threads').write_text('')

    def test_inert_cli_needs_no_modules_credentials_or_driver(self):
        main([])

    def test_poll_cleaned_uid_is_a_tombstone_before_same_name_pod_lookup(self):
        # Complete a real controller transaction in the CPU backend/journal,
        # then restart the actual CLI loop against its durable cleaned record.
        self.controller.reconcile(self.intent)
        self.stop()
        self.assertEqual(self.controller.cleanup(self.intent).state, 'cleaned')
        enrolled = self.state / 'intents'
        enrolled.mkdir(mode=0o700)
        private_write(enrolled / (UID + '.json'), asdict(self.intent), self.uid, create=True)
        writes = list(self.driver.writes)
        replacement = copy.deepcopy(self.pod)
        replacement['metadata']['uid'] = '11111111-1111-4111-8111-111111111111'
        replacement['status']['phase'] = 'Running'
        kube = Mock()
        kube.pod.return_value = replacement
        driver = SimpleNamespace(close=Mock())
        output = io.StringIO()
        # These are injected CPU dependencies, not a live driver or Kube API.
        with patch('poll.load_pinned', side_effect=[self.m, SimpleNamespace(Nvml=lambda: driver)]), \
                patch('poll.os', SimpleNamespace(geteuid=lambda: 0)), \
                patch('poll.private_directory', side_effect=lambda path:
                      __import__('node_backend').private_directory(path, self.uid)), \
                patch('poll.private_read', side_effect=lambda path: private_read(path, self.uid)), \
                patch('poll.Kubernetes', return_value=kube), \
                patch('poll.QualificationNodeBackend', return_value=self.backend), \
                patch.object(self.backend, 'check_cleanup', side_effect=AssertionError('tombstone must skip cleanup')) as cleanup, \
                patch('poll.time.sleep'), patch('sys.stdout', output):
            main(['--execute', '--qualification', '--controller-module', 'cpu-models',
                  '--manual-helper', 'cpu-manual', '--state-root', str(self.state), '--iterations', '2'])
        observed = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(observed, [{'pod_uid': UID, 'state': 'cleaned', 'iteration': iteration,
                                    'production_qualified': False} for iteration in (0, 1)])
        kube.pod.assert_not_called()
        kube.delete.assert_not_called()
        cleanup.assert_not_called()
        driver.close.assert_called_once_with()
        self.assertEqual(self.driver.writes, writes)
        self.assertEqual(self.journal.read(UID).state, 'cleaned')

    def test_exact_proc_cri_boot_cgroup_and_epoch_identity(self):
        observation = self.backend.observe(self.intent)
        self.assertEqual(observation.identity.driver_generation, EPOCH)
        self.assertEqual(observation.identity.cgroup_inode, self.group.stat().st_ino)
        self.assertEqual(observation.identity.cgroup_path, '/sys/fs/cgroup' + self.relative)
        self.assertEqual(observation.identity.host_pid, 211)
        self.assertTrue(observation.descendants_unlimited)

    def test_code3_bootstraps_durably_before_cap_and_seal(self):
        def at_write():
            bootstrap = private_read(self.state / 'bootstrap' / (UID + '.json'), self.uid)
            if len(self.driver.writes) == 1:
                self.assertEqual(bootstrap['state'], 'prepared')
                self.assertIsNone(self.journal.read(UID))
        self.driver.after_set = at_write
        record = self.controller.reconcile(self.intent)
        self.assertEqual(record.state, 'sealed')
        self.assertEqual(self.driver.writes, [(0, self.m.MAX_LIMIT), (5120 * 1048576, 5120 * 1048576)])
        bootstrap = private_read(self.state / 'bootstrap' / (UID + '.json'), self.uid)
        self.assertEqual(bootstrap['state'], 'applied')
        self.assertEqual(bootstrap['readback']['used'], 0)
        self.assertEqual(self.backend.read_gate(record.identity), record.receipt())

    def test_known_finite_parent_cap_is_never_bootstrapped_or_adopted(self):
        self.driver.value = {'soft': 1, 'hard': 2, 'used': 0}
        with self.assertRaisesRegex(ValueError, 'unowned'):
            self.controller.reconcile(self.intent)
        self.assertEqual(self.driver.writes, [])
        self.assertEqual(list((self.state / 'bootstrap').iterdir()), [])

    def test_unsupported_after_unlimited_set_retains_bootstrap_and_no_public_receipt(self):
        def unsupported(): self.driver.value = {'nvml_result': 3, 'state': 'unset-or-unsupported'}
        self.driver.after_set = unsupported
        with self.assertRaisesRegex(ValueError, 'readback'):
            self.controller.reconcile(self.intent)
        self.assertEqual(private_read(self.state / 'bootstrap' / (UID + '.json'), self.uid)['state'], 'prepared')
        self.assertIsNone(self.journal.read(UID))
        self.assertEqual(list((self.state / 'receipts').iterdir()), [])

    def test_bootstrap_set_crash_resumes_before_any_cap_transaction(self):
        self.driver.after_set = lambda: (_ for _ in ()).throw(Crash())
        with self.assertRaises(Crash): self.controller.reconcile(self.intent)
        self.driver.after_set = None
        self.assertIsNone(self.journal.read(UID))
        self.assertEqual(self.controller.reconcile(self.intent).state, 'sealed')
        self.assertEqual(private_read(self.state / 'bootstrap' / (UID + '.json'), self.uid)['state'], 'applied')

    def test_bootstrap_cannot_follow_user_init_or_main(self):
        for key in ('containerStatuses', 'initContainerStatuses'):
            with self.subTest(key=key):
                self.pod['status'][key] = [{'name': 'untrusted', 'containerID': 'containerd://' + 'd' * 64}]
                with self.assertRaises(ValueError): self.controller.reconcile(self.intent)
                self.pod['status'][key] = []
        self.assertEqual(self.driver.writes, [])

    def test_bootstrap_refuses_existing_own_gpu_client(self):
        self.clients = {211}
        with self.assertRaisesRegex(ValueError, 'CUDA client'):
            self.controller.reconcile(self.intent)
        self.assertEqual(self.driver.writes, [])

    def test_foreign_cri_uid_or_pid_start_change_refuses_seal(self):
        self.cri['status']['labels']['io.kubernetes.pod.uid'] = NODE_UID
        with self.assertRaises(ValueError): self.controller.reconcile(self.intent)
        self.assertEqual(self.driver.writes, [])

    def test_foreign_descendant_limit_refuses_parent_write(self):
        self.driver.children[str(self.leaf)] = {'soft': 3, 'hard': 4, 'used': 0}
        with self.assertRaisesRegex(ValueError, 'descendant'): self.controller.reconcile(self.intent)
        self.assertEqual(self.driver.writes, [])

    def test_controlled_inherited_same_parent_cap_is_permitted(self):
        self.controller.reconcile(self.intent)
        self.driver.children[str(self.leaf)] = copy.deepcopy(self.driver.value)
        self.assertEqual(self.controller.reconcile(self.intent).state, 'sealed')

    def test_sameboot_epoch_changed_quarantines_uid_and_retains_native_cap(self):
        record = self.controller.reconcile(self.intent)
        path = self.state / 'authority/driver-generation'
        path.write_text(NODE_UID)
        with self.assertRaisesRegex(ValueError, 'epoch'): self.controller.reconcile(self.intent)
        self.assertEqual(self.deleted, [UID])
        self.assertIsNone(self.backend.read_gate(record.identity))
        self.assertEqual(len(self.driver.writes), 2)

    def test_health_failure_quarantine_still_works_without_health_or_epoch(self):
        record = self.controller.reconcile(self.intent)
        self.healthy = False
        (self.state / 'authority/driver-generation').unlink()
        with self.assertRaises(ValueError): self.controller.reconcile(self.intent)
        self.assertEqual(self.deleted, [UID])
        self.assertIsNone(self.backend.read_gate(record.identity))
        self.assertEqual(len(self.driver.writes), 2)

    def test_quarantine_never_deletes_replacement_uid(self):
        record = self.controller.reconcile(self.intent)
        self.pod['metadata']['uid'] = NODE_UID
        with self.assertRaises(ValueError): self.controller.reconcile(self.intent)
        self.assertEqual(self.deleted, [])
        self.assertEqual(len(self.driver.writes), 2)

    def test_cleanup_requires_all_tasks_and_native_usage_and_clients_gone(self):
        self.controller.reconcile(self.intent)
        self.pod['status']['phase'] = 'Succeeded'
        with self.assertRaisesRegex(ValueError, 'tasks'): self.controller.cleanup(self.intent)
        self.stop()
        self.driver.value['used'] = 1
        with self.assertRaisesRegex(ValueError, 'clients'): self.controller.cleanup(self.intent)
        self.driver.value['used'] = 0; self.clients = {999}
        with self.assertRaisesRegex(ValueError, 'clients'): self.controller.cleanup(self.intent)
        self.clients = set()
        self.assertEqual(self.controller.cleanup(self.intent).state, 'cleaned')
        self.assertEqual(self.driver.writes[-1], (0, self.m.MAX_LIMIT))

    def test_removed_cgroup_never_gets_native_reset(self):
        self.controller.reconcile(self.intent)
        self.stop(); self.pod = None; shutil.rmtree(self.group)
        self.assertEqual(self.controller.cleanup(self.intent).state, 'cleaned')
        self.assertEqual(len(self.driver.writes), 2)

    def test_foreign_receipt_is_preserved_and_main_not_released(self):
        path = self.state / 'receipts' / (UID + '.json')
        private_write(path, {'foreign': True}, self.uid, create=True)
        with self.assertRaisesRegex(ValueError, 'receipt'): self.controller.reconcile(self.intent)
        self.assertEqual(private_read(path, self.uid), {'foreign': True})
        self.assertEqual(self.driver.writes, [])

    def test_missing_or_unsafe_epoch_and_unsafe_receipt_are_denied(self):
        path = self.state / 'authority/driver-generation'
        path.chmod(0o644)
        with self.assertRaises(ValueError): self.controller.reconcile(self.intent)
        path.chmod(0o600); path.write_text('615.71.09')
        with self.assertRaises(ValueError): self.controller.reconcile(self.intent)
        self.assertEqual(self.driver.writes, [])

    def test_unknown_nvml_readback_never_becomes_unset(self):
        self.driver.value = {'nvml_result': 999}
        with self.assertRaisesRegex(ValueError, 'Unknown'): self.controller.reconcile(self.intent)
        self.assertEqual(self.driver.writes, [])

    def test_health_change_at_bootstrap_set_retains_authority_without_cap(self):
        self.driver.after_set = lambda: setattr(self, 'healthy', False)
        with self.assertRaisesRegex(ValueError, 'health'):
            self.controller.reconcile(self.intent)
        self.assertEqual(self.driver.writes, [(0, self.m.MAX_LIMIT)])
        self.assertEqual(private_read(self.state / 'bootstrap' / (UID + '.json'), self.uid)['state'], 'prepared')
        self.assertIsNone(self.journal.read(UID))

    def test_receipt_publication_never_overwrites_even_owned_existing_content(self):
        path = self.state / 'receipts' / (UID + '.json')
        private_write(path, {'original': True}, self.uid, create=True)
        with self.assertRaises(FileExistsError):
            private_write(path, {'replacement': True}, self.uid, create=True)
        self.assertEqual(private_read(path, self.uid), {'original': True})
        self.assertEqual(path.stat().st_nlink, 1)

    def test_actual_api_delete_contract_uses_uid_precondition(self):
        calls = []
        api = Kubernetes.__new__(Kubernetes)
        api.call = lambda *args: calls.append(args)
        api.delete(self.intent)
        self.assertEqual(calls[0][0], 'DELETE')
        self.assertEqual(calls[0][2]['preconditions'], {'uid': UID})
        self.assertEqual(calls[0][1], '/api/v1/namespaces/qualification/pods/notebook')

    def test_gate_authority_directory_never_contains_private_controller_records(self):
        self.controller.reconcile(self.intent)
        self.assertEqual([file.name for file in (self.state / 'authority').iterdir()], ['driver-generation'])
        self.assertTrue((self.state / 'bootstrap' / (UID + '.json')).exists())
        self.assertTrue((self.state / 'journal' / (UID + '.json')).exists())

    def test_cli_health_pins_exact_driver_and_all_guard_parameters(self):
        params = {'uvm_deny_managed_mmap': 'Y', 'uvm_disable_hmm': 'Y',
                  'uvm_ats_mode': '0', 'uvm_enable_builtin_tests': '0', 'uvm_disable_sam_migration': 'Y'}
        healthroot = self.root / 'health'
        for path, text in [('/sys/module/nvidia/version', self.driver.version),
                           *[('/sys/module/nvidia_uvm/parameters/' + key, value) for key, value in params.items()]]:
            file = healthroot / path.lstrip('/'); file.parent.mkdir(parents=True, exist_ok=True); file.write_text(text)
        with patch('poll.Path', side_effect=lambda path: healthroot / str(path).lstrip('/')):
            self.assertTrue(health(self.driver))
            self.driver.version = '615.71.10'
            with self.assertRaisesRegex(ValueError, '615.71.09'): health(self.driver)
            self.driver.version = '615.71.09'
            sam = healthroot / 'sys/module/nvidia_uvm/parameters/uvm_disable_sam_migration'
            sam.write_text('N')
            with self.assertRaisesRegex(ValueError, 'guard'): health(self.driver)
            sam.unlink()
            with self.assertRaises(FileNotFoundError): health(self.driver)


if __name__ == '__main__': unittest.main()

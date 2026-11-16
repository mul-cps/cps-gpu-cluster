"""Safety contracts for the host release upgrade integration."""
import hashlib
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / 'platform-staging/gpu/upstream-sharing/os-upgrade/host_upgrade.py'


class UpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.available = SOURCE.exists()
        if cls.available:
            spec = importlib.util.spec_from_file_location('host_upgrade', SOURCE)
            cls.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.module)

    def setUp(self):
        self.assertTrue(self.available, 'host upgrade integration has not been implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, value in {
            'etc/os-release': 'ID=ubuntu\nVERSION_ID="24.04"\nPRETTY_NAME="Ubuntu 24.04.5 LTS"\n',
            'etc/hostname': 'k3s-wk-gpu2\n',
            'proc/sys/kernel/random/boot_id': 'boot-before\n',
            'etc/update-manager/release-upgrades': '[DEFAULT]\nPrompt=lts\n',
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        auth = self.root / "var/lib/cps-os-upgrade/authorization/pilot-1.json"
        auth.parent.mkdir(parents=True)
        auth.write_text(json.dumps({"node": "k3s-wk-gpu2", "target": "26.04.1",
            "payload_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "evidence": {key: "reviewed-artifact#sha256" for key in self.module.GATES}}))
        auth.chmod(0o600)

    def test_launch_is_durable_before_systemd_and_duplicate_never_resubmits(self):
        seen = []
        def submit(args, **kwargs):
            seen.append(self.module.read_state(self.root, 'pilot-1')['status'])
        with patch.object(self.module.subprocess, 'run', side_effect=submit) as run:
            self.module.launch(self.root, 'pilot-1', 'k3s-wk-gpu2')
            with self.assertRaisesRegex(RuntimeError, 'reconcile'):
                self.module.launch(self.root, 'pilot-1', 'k3s-wk-gpu2')
        self.assertEqual(seen, ['submitted'])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(self.module.read_state(self.root, 'pilot-1')['status'], 'submitted')

    def test_missing_or_mismatched_authorization_does_not_submit(self):
        auth = self.root / "var/lib/cps-os-upgrade/authorization/pilot-1.json"
        receipt = json.loads(auth.read_text())
        receipt['payload_sha256'] = 'stale-payload'
        auth.write_text(json.dumps(receipt))
        with patch.object(self.module.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'authorization'):
                self.module.launch(self.root, 'pilot-1', 'k3s-wk-gpu2')
            auth.unlink()
            with self.assertRaisesRegex(RuntimeError, 'authorization'):
                self.module.launch(self.root, 'pilot-1', 'k3s-wk-gpu2')
            run.assert_not_called()

    def test_wrong_host_and_path_traversal_do_not_submit(self):
        with patch.object(self.module.subprocess, 'run') as run:
            for operation, node in [('pilot-1', 'k3s-wk-gpu3'), ('../escape', 'k3s-wk-gpu2')]:
                with self.assertRaises(ValueError):
                    self.module.launch(self.root, operation, node)
            run.assert_not_called()

    def test_failed_systemd_submission_is_unknown_and_not_retryable(self):
        with patch.object(self.module.subprocess, 'run', side_effect=OSError('connection lost')):
            with self.assertRaises(OSError):
                self.module.launch(self.root, 'pilot-1', 'k3s-wk-gpu2')
        self.assertEqual(self.module.read_state(self.root, 'pilot-1')['status'], 'unknown')
        with self.assertRaisesRegex(RuntimeError, 'reconcile'):
            self.module.launch(self.root, 'pilot-1', 'k3s-wk-gpu2')

    def test_release_runs_canonical_upgrader_once_and_preserves_logs(self):
        with patch.object(self.module.subprocess, 'run'):
            self.module.launch(self.root, 'pilot-1', 'k3s-wk-gpu2')
        calls = []
        def command(args, **kwargs):
            calls.append(args)
            if args == ['dpkg', '--audit']:
                return self.module.subprocess.CompletedProcess(args, 0, stdout='')
            kwargs['stdout'].write('upgrade output\n')
            return self.module.subprocess.CompletedProcess(args, 0)
        with patch.object(self.module.subprocess, 'run', side_effect=command):
            self.module.execute(self.root, 'pilot-1')
            with self.assertRaisesRegex(RuntimeError, 'reconcile'):
                self.module.execute(self.root, 'pilot-1')
        self.assertEqual(calls, [['dpkg', '--audit'], ['do-release-upgrade', '-f', 'DistUpgradeViewNonInteractive']])
        self.assertEqual(self.module.read_state(self.root, 'pilot-1')['status'], 'reboot-required')
        self.assertIn('upgrade output', (self.root / 'var/lib/cps-os-upgrade/pilot-1/upgrade.log').read_text())

    def test_reboot_mid_upgrade_remains_unknown_and_is_never_success(self):
        with patch.object(self.module.subprocess, 'run'):
            self.module.launch(self.root, 'pilot-1', 'k3s-wk-gpu2')
        self.module.write_state(self.root, 'pilot-1', {'status': 'running', 'boot_id': 'boot-before'})
        (self.root / 'proc/sys/kernel/random/boot_id').write_text('boot-after')
        self.assertEqual(self.module.reconcile(self.root, 'pilot-1')['status'], 'unknown')

    def test_only_clean_exact_target_after_reboot_is_os_verified(self):
        with patch.object(self.module.subprocess, 'run'):
            self.module.launch(self.root, 'pilot-1', 'k3s-wk-gpu2')
        self.module.write_state(self.root, 'pilot-1', {'status': 'reboot-required', 'boot_id': 'boot-before'})
        (self.root / 'proc/sys/kernel/random/boot_id').write_text('boot-after')
        release = self.root / 'etc/os-release'
        release.write_text('ID=ubuntu\nVERSION_ID="26.04"\nPRETTY_NAME="Ubuntu 26.04.1 LTS"\n')
        with patch.object(self.module.subprocess, 'run', return_value=self.module.subprocess.CompletedProcess([], 0, stdout='')):
            state = self.module.reconcile(self.root, 'pilot-1')
        self.assertEqual(state['status'], 'os-verified')
        self.assertNotIn('accepted', state)

    def test_dead_unit_on_same_boot_becomes_unknown(self):
        with patch.object(self.module.subprocess, 'run'):
            self.module.launch(self.root, 'pilot-1', 'k3s-wk-gpu2')
        with patch.object(self.module.subprocess, 'run', return_value=self.module.subprocess.CompletedProcess([], 0, stdout='failed\n')):
            state = self.module.reconcile(self.root, 'pilot-1')
        self.assertEqual(state['status'], 'unknown')
        with self.assertRaisesRegex(RuntimeError, 'reconcile'):
            self.module.launch(self.root, 'pilot-1', 'k3s-wk-gpu2')

    def test_missing_prerequisites_do_not_run_upgrader(self):
        with patch.object(self.module.subprocess, 'run'):
            self.module.launch(self.root, 'pilot-1', 'k3s-wk-gpu2')
        (self.root / 'var/run').mkdir(parents=True)
        (self.root / 'var/run/reboot-required').touch()
        with patch.object(self.module.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'prerequisite'):
                self.module.execute(self.root, 'pilot-1')
            run.assert_not_called()
        self.assertEqual(self.module.read_state(self.root, 'pilot-1')['status'], 'failed')


if __name__ == '__main__':
    unittest.main()

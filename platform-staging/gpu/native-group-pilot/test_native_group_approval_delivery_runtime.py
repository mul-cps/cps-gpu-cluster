"""Execute the rendered init command against real, private journal fixtures."""
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import native_group_approval_delivery as delivery
import native_group_approval_delivery_runtime as runtime
import test_native_group_approval_delivery as delivery_tests


class JournalInitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.seed = self.root / 'seed'
        self.inputs = self.root / 'inputs'
        self.mount = self.root / 'journal'
        for directory in (self.seed, self.inputs, self.mount):
            directory.mkdir(mode=0o700)
        self.journal = self.mount / 'delivery'
        self.journal.mkdir(mode=0o700)
        self.contents = {'state.json': b'{"version":1,"transition":{"owned":"retained"}}\n',
            'lock': b''}
        for name, data in self.contents.items():
            path = self.journal / name
            path.write_bytes(data)
            path.chmod(0o600)
        fixture = delivery_tests.DeliveryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.config = fixture.config
        self.spec = next(obj for obj in runtime.render(self.config,
            image='ghcr.io/example/delivery@sha256:' + 'a' * 64,
            config_secret='operator-delivery-input', journal_pvc='operator-delivery-journal',
            context='reviewed-context') if obj['kind'] == 'Deployment')['spec']['template']['spec']
        for name in ('config.json', 'source-command.json', 'epoch-command.json', 'kubeconfig'):
            (self.seed / name).write_bytes(b'private-input-fixture')
        self.attempt = 0

    def command(self):
        command = list(self.spec['initContainers'][0]['command'])
        command[0] = sys.executable
        self.attempt += 1
        command[-1] = command[-1].replace("'/inputs/delivery'", repr(str(self.inputs / ('delivery-' + str(self.attempt)))))
        command[-1] = command[-1].replace("'/seed'", repr(str(self.seed)))
        command[-1] = command[-1].replace("'/journal'", repr(str(self.mount)))
        return command

    def run_init(self):
        return subprocess.run(self.command(), capture_output=True, text=True, check=False)

    def test_restart_repairs_only_fsgroup_widened_owned_journal_modes(self):
        self.journal.chmod(0o2770)
        for name in self.contents:
            (self.journal / name).chmod(0o660)
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(self.journal.stat().st_mode & 0o7777, 0o700)
        for name, data in self.contents.items():
            path = self.journal / name
            self.assertEqual(path.stat().st_mode & 0o7777, 0o600)
            self.assertEqual(path.read_bytes(), data)
        delivery.private_directory(self.journal)

    def test_fresh_empty_journal_is_created_private_without_state_creation(self):
        for name in self.contents:
            (self.journal / name).unlink()
        self.journal.rmdir()
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.journal.stat().st_mode & 0o7777, 0o700)
        self.assertEqual(list(self.journal.iterdir()), [])

    def assert_rejected_unchanged(self):
        before_mode = self.journal.lstat().st_mode
        result = self.run_init()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertEqual(self.journal.lstat().st_mode, before_mode)

    def test_unknown_file_fails_before_any_journal_mode_changes(self):
        self.journal.chmod(0o770)
        (self.journal / 'state.json').chmod(0o660)
        (self.journal / 'foreign').write_bytes(b'untouched')
        self.assert_rejected_unchanged()
        self.assertEqual((self.journal / 'state.json').stat().st_mode & 0o7777, 0o660)
        self.assertEqual((self.journal / 'foreign').read_bytes(), b'untouched')

    def test_state_symlink_cannot_change_the_external_target(self):
        target = self.root / 'external'
        target.write_bytes(b'untouched')
        target.chmod(0o660)
        (self.journal / 'state.json').unlink()
        (self.journal / 'state.json').symlink_to(target)
        self.assert_rejected_unchanged()
        self.assertEqual(target.stat().st_mode & 0o7777, 0o660)
        self.assertEqual(target.read_bytes(), b'untouched')

    def test_journal_symlink_cannot_change_the_external_directory(self):
        target = self.root / 'external-directory'
        self.journal.rename(target)
        target.chmod(0o770)
        self.journal.symlink_to(target, target_is_directory=True)
        self.assert_rejected_unchanged()
        self.assertEqual(target.stat().st_mode & 0o7777, 0o770)

    def test_hard_linked_state_is_rejected_without_changing_either_name(self):
        target = self.root / 'external-link'
        os.link(self.journal / 'state.json', target)
        target.chmod(0o660)
        self.assert_rejected_unchanged()
        self.assertEqual(target.stat().st_mode & 0o7777, 0o660)
        self.assertEqual(target.read_bytes(), self.contents['state.json'])

    def test_foreign_owner_identity_is_rejected_before_modes_change(self):
        # No privileged chown is available: keep real inode metadata and supply
        # a different process UID to exercise the same ownership boundary.
        command = self.command()[-1]
        self.journal.chmod(0o770)
        with patch('os.getuid', return_value=os.getuid() + 1):
            with self.assertRaises(ValueError):
                exec(command, {})
        self.assertEqual(self.journal.stat().st_mode & 0o7777, 0o770)

    def test_foreign_file_owner_identity_is_rejected_before_modes_change(self):
        command = self.command()[-1]
        self.journal.chmod(0o770)
        owner = os.getuid()
        with patch('os.getuid', side_effect=[owner, owner + 1]):
            with self.assertRaises(ValueError):
                exec(command, {})
        self.assertEqual(self.journal.stat().st_mode & 0o7777, 0o770)
        self.assertEqual((self.journal / 'state.json').read_bytes(), self.contents['state.json'])

    def test_an_active_journal_lock_prevents_mode_repair(self):
        self.journal.chmod(0o770)
        with (self.journal / 'lock').open('r+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assert_rejected_unchanged()
        self.assertEqual((self.journal / 'state.json').read_bytes(), self.contents['state.json'])

    def test_world_access_or_executable_state_is_not_treated_as_fsgroup_widening(self):
        for mode in (0o664, 0o760, 0o4660):
            with self.subTest(mode=mode):
                (self.journal / 'state.json').chmod(mode)
                self.assert_rejected_unchanged()
                self.assertEqual((self.journal / 'state.json').stat().st_mode & 0o7777, mode)

    def test_init_mounts_the_same_journal_before_strict_delivery_validation(self):
        mount = {'name': 'journal', 'mountPath': '/journal'}
        self.assertIn(mount, self.spec['initContainers'][0]['volumeMounts'])
        self.assertIn(mount, self.spec['containers'][0]['volumeMounts'])
        self.assertEqual(self.spec['securityContext']['fsGroupChangePolicy'], 'OnRootMismatch')
        self.assertEqual(self.spec['initContainers'][0]['securityContext']['runAsUser'], 1000)


if __name__ == '__main__':
    unittest.main()

"""CPU-only fence regressions: temporary files, pipes, and fake host observations.

No test invokes NVIDIA, module maintenance, Kubernetes, or the live state root.
Root ownership is simulated only for files inside a test-owned temporary tree.
"""
from contextlib import ExitStack, redirect_stdout
import errno
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SPEC = importlib.util.spec_from_file_location(
    'reviewed_teardown_fence', Path(__file__).with_name('teardown_fence.py'))
fence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fence)


def root_stat(info):
    fields = {key: getattr(info, key) for key in dir(info) if key.startswith('st_')}
    return SimpleNamespace(**{**fields, 'st_uid': 0})


class FenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        for name in ('journal', 'authority', 'operator', 'receipts', 'driver-inputs', 'published-cleanup'):
            (self.root / name).mkdir(mode=0o700)
        self.addCleanup(patch.stopall)
        patch.object(fence, 'ROOT', self.root).start()
        fence.DEVICE_IDS.clear()
        fence.RPC_BUFFER = b''
        self.addCleanup(fence.DEVICE_IDS.clear)
        self.addCleanup(setattr, fence, 'RPC_BUFFER', b'')
        self.raw_sha = lambda raw: 'sha256:' + hashlib.sha256(raw).hexdigest()
        self.recovery = SimpleNamespace(raw_sha256=self.raw_sha,
            validate_before=Mock(), validate_teardown=Mock())

    def root_files(self):
        """Preserve actual modes/inodes/flock; simulate owner for private fixtures."""
        real_fstat = os.fstat
        stack = ExitStack()
        stack.enter_context(patch.object(fence, 'directory', side_effect=lambda p: root_stat(p.lstat())))
        stack.enter_context(patch.object(fence.os, 'fstat', side_effect=lambda fd: root_stat(real_fstat(fd))))
        return stack

    def file(self, relative, raw=b'protected\n', mode=0o600):
        path = self.root / relative
        path.write_bytes(raw)
        path.chmod(mode)
        return path

    def rpc(self, data, *, close_writer=True, timeout=0.1):
        reader, writer = os.pipe()
        try:
            if data:
                # A fake read avoids pipe-capacity stalls for oversized frames.
                chunks = [data[i:i + 65536] for i in range(0, len(data), 65536)]
                with patch.object(fence.sys, 'stdin', SimpleNamespace(fileno=lambda: reader)), \
                     patch.object(fence.select, 'select', return_value=([reader], [], [])), \
                     patch.object(fence.os, 'read', side_effect=[*chunks, b'']):
                    return fence.read_rpc(timeout)
            if close_writer:
                os.close(writer)
                writer = None
            with patch.object(fence.sys, 'stdin', SimpleNamespace(fileno=lambda: reader)):
                return fence.read_rpc(timeout)
        finally:
            os.close(reader)
            if writer is not None:
                os.close(writer)

    def proof_fixture(self):
        scope = {'node': 'k3s-wk-gpu2', 'node_uid': fence.NODE_UID,
            'boot_id': fence.BOOT_ID, 'driver_generation': fence.OLD_GENERATION,
            'loaded_modules': ['nvidia', 'nvidia_uvm'],
            'module_sha256': {key: 'sha256:' + value for key, value in fence.OLD_MODULES.items()},
            'nvidia_gpus': [{'gpu_uuid': 'GPU-one', 'pci_bdf': '0000:06:10.0'},
                            {'gpu_uuid': 'GPU-two', 'pci_bdf': '0000:06:11.0'}],
            'pilot_pods': [{'namespace': 'jupyterhub', 'name': 'pilot', 'pod_uid': fence.LEGACY_UID}],
            'journal_directory': {'device': 9, 'inode': 10}}
        plan = {'scope': scope, 'operation_id': 'reviewed-operation',
            'journal': {'sha256': 'sha256:' + 'a' * 64,
                        'record': {'intent': {'pod_uid': fence.LEGACY_UID}}},
            'review': {'load_manifest_sha256': self.raw_sha(b'manifest'),
                       'old_module_source_sha256': 'sha256:' + fence.OLD_HEALTH_SHA}}
        locks = {key: {'device': 7, 'inode': index + 20}
            for index, key in enumerate(('journal', 'driver', 'maintenance'))}
        return plan, 'sha256:' + 'b' * 64, locks

    def teardown(self, *, inventory=None, bound=None, modules=([], []), gate=None, final=False):
        plan, digest, locks = self.proof_fixture()
        inventory = inventory if inventory is not None else [g['pci_bdf'] for g in plan['scope']['nvidia_gpus']]
        before = {'locks': locks, 'gate_sha256': gate}
        with patch.object(fence, 'stable_base', return_value=(plan['journal']['sha256'], True, 0, locks)), \
             patch.object(fence, 'modules', return_value=modules), \
             patch.object(fence, 'pci_inventory', return_value=inventory), \
             patch.object(fence.os.path, 'lexists', side_effect=lambda p: str(p) == bound), \
             patch.object(fence, 'gpu_fd_clients', return_value=0), \
             patch.object(fence, 'gate_hash', return_value=gate), \
             patch.object(fence.subprocess, 'run', side_effect=AssertionError('No post-unload NVIDIA command')):
            proof = fence.teardown_proof(plan, digest, {}, self.recovery, before, final=final)
        return plan, digest, before, proof

    def test_default_is_inert_before_any_host_or_private_file_observation(self):
        with ExitStack() as stack, redirect_stdout(io.StringIO()) as output:
            for name in ('directory', 'read_protected', 'load_protected', 'acquire_lock',
                         'before_proof', 'modules', 'gpu_fd_clients', 'read_rpc'):
                stack.enter_context(patch.object(fence, name, side_effect=AssertionError(name)))
            stack.enter_context(patch.object(fence.subprocess, 'run', side_effect=AssertionError('command')))
            fence.main([])
        self.assertEqual(json.loads(output.getvalue()),
            {'state': 'inert', 'module_actions': False, 'cap_actions': False})

    def test_execute_requires_root_and_explicit_qualification_before_file_access(self):
        for uid, argv in ((1000, ['--execute', '--qualification']), (0, ['--execute'])):
            with self.subTest(uid=uid), patch.object(fence.os, 'geteuid', return_value=uid), \
                 patch.object(fence, 'directory', side_effect=AssertionError('premature private access')):
                with self.assertRaisesRegex(ValueError, 'Explicit Root qualification'):
                    fence.main(argv)

    def test_missing_existing_lock_is_not_created(self):
        path = self.root / 'journal/.writer.lock'
        with self.root_files(), self.assertRaises(FileNotFoundError):
            fence.acquire_lock(path)
        self.assertFalse(path.exists())

    def test_symlink_wrong_mode_and_foreign_owner_lock_are_rejected(self):
        target = self.file('journal/target')
        link = self.root / 'journal/.writer.lock'
        link.symlink_to(target)
        with self.root_files(), self.assertRaises(OSError):
            fence.acquire_lock(link)
        link.unlink()
        self.file('journal/.writer.lock', mode=0o644)
        with self.root_files(), self.assertRaisesRegex(ValueError, 'Private root lock'):
            fence.acquire_lock(link)
        link.chmod(0o600)
        with patch.object(fence, 'directory', return_value=None), \
             patch.object(fence.os, 'fstat', return_value=SimpleNamespace(
                 st_mode=stat.S_IFREG | 0o600, st_uid=1000, st_nlink=1)), \
             self.assertRaisesRegex(ValueError, 'Private root lock'):
            fence.acquire_lock(link)

    def test_competing_lock_and_inode_replacement_cannot_claim_continuity(self):
        path = self.file('journal/.writer.lock')
        with self.root_files():
            fd = fence.acquire_lock(path)
            try:
                with self.assertRaises(BlockingIOError):
                    fence.acquire_lock(path)
                old_inode = os.fstat(fd).st_ino
                path.unlink()
                self.file('journal/.writer.lock')
                self.assertNotEqual(path.stat().st_ino, old_inode)
                with self.assertRaisesRegex(ValueError, 'Unchanged private lock inode'):
                    fence.lock_proof({'journal': fd})
            finally:
                os.close(fd)

    def test_optional_receipt_is_absent_only_for_missing_entry_not_dangling_symlink(self):
        with self.root_files():
            self.assertIsNone(fence.gate_hash({}, self.recovery))
            path = self.root / 'receipts' / (fence.LEGACY_UID + '.json')
            path.symlink_to(self.root / 'missing-target')
            with self.assertRaises(OSError) as error:
                fence.gate_hash({}, self.recovery)
            self.assertEqual(error.exception.errno, errno.ELOOP)

    def test_receipt_hashes_exact_bytes_and_rejects_unsafe_mode_and_hardlink(self):
        path = self.file('receipts/' + fence.LEGACY_UID + '.json', b'{"gate":true}\n')
        with self.root_files():
            self.assertEqual(fence.gate_hash({}, self.recovery), self.raw_sha(path.read_bytes()))
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, 'Protected exact-mode'):
                fence.gate_hash({}, self.recovery)
            path.chmod(0o600)
            os.link(path, self.root / 'receipts/alias')
            with self.assertRaisesRegex(ValueError, 'Protected exact-mode'):
                fence.gate_hash({}, self.recovery)

    def test_rpc_preserves_separate_buffered_frames_and_rejects_nested_duplicates(self):
        self.assertEqual(self.rpc(b'{"op":"one"}\n{"op":"two"}\n'), {'op': 'one'})
        # Buffered second frame must not read unrelated new bytes.
        with patch.object(fence.os, 'read', side_effect=AssertionError('unexpected read')):
            self.assertEqual(fence.read_rpc(), {'op': 'two'})
        with self.assertRaisesRegex(ValueError, 'Duplicate Root RPC field'):
            self.rpc(b'{"plan":{"binding":"one","binding":"two"}}\n')

    def test_rpc_eof_partial_frame_deadline_and_oversize_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'EOF or size bound'):
            self.rpc(b'')
        with self.assertRaisesRegex(ValueError, 'EOF or size bound'):
            self.rpc(b'{"op":')
        with self.assertRaisesRegex(ValueError, 'deadline exceeded'):
            self.rpc(b'', close_writer=False, timeout=0.01)
        with self.assertRaisesRegex(ValueError, 'EOF or size bound'):
            self.rpc(b' ' * 262145 + b'\n')

    def test_device_ids_survive_device_node_removal_and_detect_existing_fd(self):
        device = SimpleNamespace(is_char_device=lambda: True,
            stat=lambda: SimpleNamespace(st_rdev=os.makedev(195, 0)))
        handle = SimpleNamespace(stat=lambda: SimpleNamespace(
            st_mode=stat.S_IFCHR | 0o600, st_rdev=os.makedev(195, 0)))
        active = {'devices': [device], 'fds': []}
        class Process:
            name = '123'
            def __truediv__(self, name):
                return SimpleNamespace(iterdir=lambda: iter(active['fds']))
        paths = {'/dev': SimpleNamespace(glob=lambda pattern: active['devices']),
                 '/dev/nvidia-caps': SimpleNamespace(glob=lambda pattern: []),
                 '/proc': SimpleNamespace(iterdir=lambda: [Process()])}
        with patch.object(fence, 'Path', side_effect=lambda p: paths[str(p)]):
            self.assertEqual(fence.gpu_fd_clients(), 0)
            active['devices'] = []
            active['fds'] = [handle]
            self.assertEqual(fence.gpu_fd_clients(), 1)
            active['fds'] = []
            self.assertEqual(fence.gpu_fd_clients(), 0)
        self.assertEqual(fence.DEVICE_IDS, {os.makedev(195, 0)})

    def test_unreadable_process_fds_are_not_silently_zero_clients(self):
        class Process:
            name = '123'
            def __truediv__(self, name):
                return SimpleNamespace(iterdir=Mock(side_effect=PermissionError('fd inventory denied')))
        fence.DEVICE_IDS.add(os.makedev(195, 0))
        paths = {'/dev': SimpleNamespace(glob=lambda pattern: []),
                 '/dev/nvidia-caps': SimpleNamespace(glob=lambda pattern: []),
                 '/proc': SimpleNamespace(iterdir=lambda: [Process()])}
        with patch.object(fence, 'Path', side_effect=lambda p: paths[str(p)]), \
             self.assertRaises(PermissionError):
            fence.gpu_fd_clients()

    def test_teardown_independently_requires_sysfs_and_proc_module_absence(self):
        for modules in ((['nvidia_uvm'], []), ([], ['nvidia']), (['nvidia_drm'], ['nvidia_drm'])):
            with self.subTest(modules=modules), self.assertRaisesRegex(ValueError, 'Every NVIDIA module'):
                self.teardown(modules=modules)
        self.recovery.validate_teardown.assert_not_called()

    def test_bound_prior_pci_function_or_replacement_authority_blocks_teardown(self):
        paths = [str(Path('/sys/bus/pci/devices/0000:06:10.0/driver')),
                 str(self.root / 'authority/driver-generation'),
                 str(self.root / 'authority/driver-load-manifest.json')]
        for path in paths:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.teardown(bound=path)
        self.recovery.validate_teardown.assert_not_called()

    def test_teardown_proof_contains_fresh_observations_without_nvml_or_commands(self):
        plan, digest, before, proof = self.teardown()
        self.assertEqual(proof['pci_unbound'], [g['pci_bdf'] for g in plan['scope']['nvidia_gpus']])
        self.assertEqual((proof['sysfs_modules'], proof['proc_modules']), ([], []))
        self.assertEqual((proof['gpu_fd_clients'], proof['pod_runtime_tasks']), (0, 0))
        self.assertEqual(proof['journal_sha256'], plan['journal']['sha256'])
        self.assertEqual(proof['locks'], before['locks'])
        self.recovery.validate_teardown.assert_called_once_with(proof, plan, digest, before)

    def test_completion_requires_null_gate_and_current_journal_validation(self):
        plan, digest, before, proof = self.teardown(final=True)
        self.recovery.validate_teardown.assert_called_once_with(proof, plan, digest, before,
            journal_sha256=proof['journal_sha256'], gate_sha256=None)

    def main_transaction(self, *, changed_teardown=False, operation='release', nonce=None,
                         invalid_bootstrap=None):
        """Fake every host/API input; retain real temporary lock lifecycle."""
        plan, digest, _ = self.proof_fixture()
        expected_nonce = '11111111-2222-4333-8444-555555555555'
        before = {'original': 'before-observation'}
        teardown = {'original': 'positive-teardown-observation'}
        final_teardown = {'current': 'post-completion-teardown-observation'}
        audit = {'immutable': True, 'metadata': {'uid': 'actual-audit'}}
        cleanup = {'immutable': True, 'metadata': {'uid': 'actual-cleanup'}}
        completion = {'journal_record': {'state': 'cleaned'},
            'journal_raw_sha256': 'sha256:' + 'c' * 64, 'archive_sha256': 'sha256:' + 'a' * 64,
            'tombstone': {'cleanup_uid': 'actual-cleanup'}, 'gate_absent': True}
        requests = [
            {'op': 'acquire', 'nonce': expected_nonce, 'plan': plan, 'plan_sha256': digest},
            {'op': 'verify-teardown', 'nonce': expected_nonce},
            {'op': 'publish-local', 'nonce': expected_nonce, 'plan_sha256': digest,
             'audit': audit, 'cleanup': cleanup},
            {'op': 'verify-completion', 'nonce': expected_nonce},
            {'op': operation, 'nonce': nonce or expected_nonce}]
        acquired = {}
        real_acquire = fence.acquire_lock
        for path in ('journal/.writer.lock', 'authority/.driver-loader.lock', 'operator/.teardown.lock'):
            self.file(path)

        def acquiring(path):
            fd = real_acquire(path)
            acquired[path] = fd
            return fd

        def assert_locks_held():
            self.assertEqual(len(acquired), 3)
            for path, fd in acquired.items():
                self.assertEqual(os.fstat(fd).st_ino, path.stat().st_ino)
                competing = os.open(path, os.O_RDWR)
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
                finally:
                    os.close(competing)

        def publish(root, actual_plan, actual_audit, actual_cleanup, **kwargs):
            assert_locks_held()
            self.assertEqual((root, actual_plan, actual_audit, actual_cleanup),
                             (self.root, plan, audit, cleanup))
            self.assertEqual(kwargs, {'before': before, 'teardown': teardown,
                'lock_fds': dict(zip(('journal', 'driver', 'maintenance'), acquired.values())),
                'trusted_uid': 0})

        def readback(root, actual_plan, actual_audit, actual_cleanup, **kwargs):
            assert_locks_held()
            self.assertEqual((root, actual_plan, actual_audit, actual_cleanup, kwargs),
                (self.root, plan, audit, cleanup, {'trusted_uid': 0}))
            return completion.copy()

        recovery = SimpleNamespace(validate_plan=Mock(), complete_local=Mock(side_effect=publish),
            read_local_completion=Mock(side_effect=readback))
        invalidation = Mock()
        teardown_observations = [teardown,
            {'changed': 'unexpected-writer'} if changed_teardown else teardown,
            final_teardown, final_teardown]
        own_source = Path(fence.__file__).read_bytes()
        protected_bytes = {Path(fence.__file__): own_source}
        dependencies = {}
        for name in ('node_agent.py', 'abort_before_gate.py', 'source-snapshot.json'):
            raw = ('reviewed inert fixture: ' + name).encode()
            protected_bytes[self.root / 'operator' / name] = raw
            dependencies[name] = hashlib.sha256(raw).hexdigest()
        if invalid_bootstrap == 'manifest':
            dependencies.pop('source-snapshot.json')
        manifest_raw = json.dumps(dependencies, sort_keys=True, separators=(',', ':')).encode()
        protected_bytes[self.root / 'operator/dependencies.json'] = manifest_raw
        if invalid_bootstrap == 'dependency':
            protected_bytes[self.root / 'operator/node_agent.py'] = b'tampered dependency'
        loader = Mock(side_effect=[object(), object(), recovery, object()])
        failure = None
        with self.root_files(), redirect_stdout(io.StringIO()) as output, \
             patch.object(fence.os, 'geteuid', return_value=0), \
             patch.object(fence, 'read_protected', side_effect=lambda path: protected_bytes[path]), \
             patch.object(fence, 'load_protected', loader), \
             patch.object(fence, 'read_rpc', side_effect=requests), \
             patch.object(fence, 'acquire_lock', side_effect=acquiring), \
             patch.object(fence, 'before_proof', return_value=before), \
             patch.object(fence, 'invalidate_old_authority', invalidation), \
             patch.object(fence, 'modules', return_value=([], [])), \
             patch.object(fence, 'teardown_proof', side_effect=teardown_observations), \
             patch.object(fence.subprocess, 'run', side_effect=AssertionError('No hardware command')):
            try:
                fence.main(['--execute', '--qualification', '--fence-source-sha256',
                    hashlib.sha256(own_source).hexdigest(), '--recovery-source-sha256', 'reviewed-sha',
                    '--dependency-manifest-sha256', hashlib.sha256(manifest_raw).hexdigest()])
            except ValueError as error:
                failure = error
        for fd in acquired.values():
            with self.assertRaises(OSError) as error:
                os.fstat(fd)
            self.assertEqual(error.exception.errno, errno.EBADF)
        if invalid_bootstrap:
            recovery.validate_plan.assert_not_called()
            invalidation.assert_not_called()
            loader.assert_not_called()
            self.assertEqual(acquired, {})
        else:
            recovery.validate_plan.assert_called_once_with(plan, digest)
            invalidation.assert_called_once_with(plan, recovery)
        return recovery, failure, [json.loads(line) for line in output.getvalue().splitlines()]

    def test_main_retains_all_three_real_locks_through_publication_and_fresh_completion(self):
        recovery, failure, events = self.main_transaction()
        self.assertIsNone(failure)
        recovery.complete_local.assert_called_once()
        self.assertEqual(recovery.read_local_completion.call_count, 2)
        self.assertEqual([event['event'] for event in events], [
            'fence-acquired', 'fence-teardown-verified', 'fence-local-published', 'fence-completion-verified'])
        self.assertEqual(events[-2]['proof'], events[-1]['proof'])
        self.assertTrue(all(event['nonce'] == '11111111-2222-4333-8444-555555555555' for event in events))

    def test_main_changed_teardown_never_publishes_or_reads_cached_completion(self):
        recovery, failure, events = self.main_transaction(changed_teardown=True)
        self.assertIsNotNone(failure)
        self.assertIn('Unchanged positive teardown', str(failure))
        recovery.complete_local.assert_not_called()
        recovery.read_local_completion.assert_not_called()
        self.assertEqual([event['event'] for event in events], ['fence-acquired', 'fence-teardown-verified'])

    def test_main_final_release_rejects_wrong_nonce_or_out_of_order_operation(self):
        for kwargs in ({'operation': 'acquire'}, {'nonce': '99999999-2222-4333-8444-555555555555'}):
            with self.subTest(kwargs=kwargs):
                recovery, failure, events = self.main_transaction(**kwargs)
                self.assertIsNotNone(failure)
                self.assertIn('Closed final release', str(failure))
                recovery.complete_local.assert_called_once()
                self.assertEqual(events[-1]['event'], 'fence-completion-verified')

    def test_closed_dependency_manifest_or_changed_bytes_blocks_every_import_and_lock(self):
        for kind, detail in (('manifest', 'Closed exact recovery dependency'),
                             ('dependency', 'Changed protected recovery dependency')):
            with self.subTest(kind=kind):
                recovery, failure, events = self.main_transaction(invalid_bootstrap=kind)
                self.assertIsNotNone(failure)
                self.assertIn(detail, str(failure))
                self.assertEqual(events, [])
                recovery.complete_local.assert_not_called()


if __name__ == '__main__':
    unittest.main()

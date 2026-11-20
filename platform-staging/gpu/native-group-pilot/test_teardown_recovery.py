"""CPU only: fake hardware/API observations, real private files and flock."""
import copy
from datetime import datetime, timedelta, timezone
import fcntl
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid

import teardown_recovery as r


POD = '696bab5d-30c7-4476-bb97-19b300c45302'
BOOT = '209f8bc9-a478-48e4-925a-6e07ffa56f7a'
GEN = '761311d1-755e-4b33-8855-fc2aaff426f4'
OTHER_GPU = 'GPU-06128952-b438-556a-00bb-93039ee24e56'


class Fixture:
    def __init__(self, root, state='cleaned', gate=False):
        self.root = Path(root)
        self.root.chmod(0o700)
        self.fds = {}
        for part in ('journal', 'authority', 'operator', 'receipts'):
            (self.root / part).mkdir(mode=0o700)
        locks = {'journal': 'journal/.writer.lock', 'driver': 'authority/.driver-loader.lock',
                 'maintenance': 'operator/.teardown.lock'}
        for key, relative in locks.items():
            fd = os.open(self.root / relative, os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fds[key] = fd
        m = r._models()
        intent = m.CapIntent('jupyterhub', 'jupyter-cpsnativegroupb--rtc', POD, r.prior.NODE,
            r.prior.NODE_UID, 'a' * 64, r.prior.GPU, 5120, 'sha256:' + 'b' * 64)
        relative = '/kubepods.slice/kubepods-burstable-pod' + POD.replace('-', '_') + '.slice'
        identity = m.CapIdentity(POD, intent.spec_sha256, intent.node_uid, intent.gpu_uuid,
            'c' * 64, 211, 345, BOOT, relative, '/sys/fs/cgroup' + relative, 29, 71, GEN)
        record = m.CapRecord(intent, identity, state, str(uuid.uuid4()), m.CapLimit(intent.cap_bytes, intent.cap_bytes))
        # Preserve formatting as well as semantic content for legacy cleaned journals.
        self.raw = (json.dumps(record.to_dict(), indent=2) + '\n').encode()
        path = self.root / 'journal' / (POD + '.json')
        path.write_bytes(self.raw); path.chmod(0o600)
        enrollment = {'version': 1, 'binding_id': 'a' * 60, 'source': 'cps', 'actor': 'cps',
            'workspace': 'native-group-b', 'principal': 'workspace:cps:native-group-b',
            'members': ['person:one', 'person:two'], 'attempt': 'attempt-696', 'profile': 'native5',
            'policy_hash': intent.policy_hash, 'namespace': intent.namespace, 'name': intent.name,
            'node': intent.node, 'node_uid': intent.node_uid, 'gpu_uuid': intent.gpu_uuid,
            'cap_mib': 5120, 'intent': intent.to_dict()}
        self.enrollment = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
            'metadata': {'name': 'cps-native-enrollment-' + 'a' * 40, 'namespace': r.NAMESPACE,
                'uid': str(uuid.uuid4()), 'labels': {r.LABEL: 'a' * 60}},
            'data': {'enrollment.json': r.canonical(enrollment)}}
        self.ledger = {'apiVersion': 'v1', 'kind': 'ConfigMap',
            'metadata': {'name': r.LEDGER, 'namespace': r.NAMESPACE, 'uid': str(uuid.uuid4()), 'resourceVersion': '1'},
            'data': {'state.json': r.canonical({'version': 1, 'allocations': {'a' * 60: {**enrollment, 'state': 'enrolled'}}})}}
        journal_dir = (self.root / 'journal').stat()
        self.plan = {'version': 1, 'qualification_only': True, 'operation_id': str(uuid.uuid4()),
            'authority_namespace': r.NAMESPACE, 'binding_id': 'a' * 60, 'attempt': enrollment['attempt'],
            'ledger_uid': self.ledger['metadata']['uid'], 'allocation_sha256': r.sha256(enrollment),
            'enrollment_uid': self.enrollment['metadata']['uid'], 'enrollment_sha256': r.sha256(enrollment),
            'fence_command_sha256': r.sha256(['root-fence']), 'tool_sha256': r.raw_sha256(Path(r.__file__).read_bytes()),
            'journal': {'record': record.to_dict(), 'sha256': r.raw_sha256(self.raw)},
            'scope': {'node': intent.node, 'node_uid': intent.node_uid, 'boot_id': BOOT, 'driver_generation': GEN,
                'loaded_modules': ['nvidia', 'nvidia_uvm'],
                'module_sha256': {'nvidia': 'sha256:' + 'd' * 64, 'nvidia_uvm': 'sha256:' + 'e' * 64},
                'nvidia_gpus': [{'gpu_uuid': OTHER_GPU, 'pci_bdf': '0000:06:10.0'},
                                {'gpu_uuid': r.prior.GPU, 'pci_bdf': '0000:06:11.0'}],
                'pilot_pods': [{key: intent.to_dict()[key] for key in ('namespace', 'name', 'pod_uid')}],
                'journal_directory': {'device': journal_dir.st_dev, 'inode': journal_dir.st_ino}},
            'review': {'operator': 'root', 'reason': 'legacy-cap-after-confirmed-driver-teardown',
                'old_module_source_sha256': 'sha256:' + 'f' * 64, 'load_manifest_sha256': 'sha256:' + '0' * 64}}
        gate_raw = None
        if gate:
            from dataclasses import replace
            gate_raw = (r.canonical(replace(record, state='sealed').receipt()) + '\n').encode()
            gate_path = self.root / 'receipts' / (POD + '.json')
            gate_path.write_bytes(gate_raw); gate_path.chmod(0o600)
        self.before = {'stage': 'before', 'operation_id': self.plan['operation_id'], 'plan_sha256': r.sha256(self.plan),
            'scope': copy.deepcopy(self.plan['scope']), 'journal_sha256': self.plan['journal']['sha256'],
            'locks': {key: {'device': os.fstat(fd).st_dev, 'inode': os.fstat(fd).st_ino} for key, fd in self.fds.items()},
            'native_writers_quiesced': True, 'locks_held': True, 'driver_healthy': True,
            'gpu_memory_bytes': {OTHER_GPU: 0, r.prior.GPU: 0}, 'gpu_fd_clients': 0,
            'compute_apps': 0, 'pod_runtime_tasks': 0, 'gate_sha256': None if gate_raw is None else r.raw_sha256(gate_raw)}
        self.after = {'stage': 'teardown', 'operation_id': self.plan['operation_id'], 'plan_sha256': r.sha256(self.plan),
            'node_uid': intent.node_uid, 'boot_id': BOOT, 'old_driver_generation': GEN,
            'old_generation_invalidated': True, 'sysfs_modules': [], 'proc_modules': [],
            'pci_unbound': ['0000:06:10.0', '0000:06:11.0'], 'gpu_fd_clients': 0, 'pod_runtime_tasks': 0,
            'locks': copy.deepcopy(self.before['locks']), 'journal_sha256': self.plan['journal']['sha256'],
            'gate_sha256': self.before['gate_sha256'], 'native_writers_quiesced': True,
            'locks_held': True, 'new_load_absent': True}
        self.calls = []
        self.cms = {r.LEDGER: self.ledger, self.enrollment['metadata']['name']: self.enrollment}
        self.pod = None
        self.node = {'apiVersion': 'v1', 'kind': 'Node', 'metadata': {'name': intent.node, 'uid': intent.node_uid}}
        self.local_completion = None

    def close(self):
        for fd in self.fds.values(): os.close(fd)

    def fence(self, plan):
        self.calls.append('fence')
        self.before['plan_sha256'] = r.sha256(plan)
        self.after['plan_sha256'] = r.sha256(plan)
        return self

    def __enter__(self): return self
    def __exit__(self, *args): self.calls.append('release-fence')
    def get_node(self, name): self.calls.append('node-get'); return copy.deepcopy(self.node)
    def get_pod(self, ns, name): self.calls.append('pod-get'); return copy.deepcopy(self.pod)
    def get_cm(self, name, absent=False): self.calls.append('cm-get:' + name); return copy.deepcopy(self.cms.get(name))
    def create_cm(self, body):
        self.calls.append('cm-create:' + body['metadata']['name'])
        actual = copy.deepcopy(body); actual['metadata']['uid'] = str(uuid.uuid4())
        self.cms[body['metadata']['name']] = actual
        return copy.deepcopy(actual)
    def verify_teardown(self): self.calls.append('teardown-probe'); return copy.deepcopy(self.after)
    def publish_local(self, audit, cleanup):
        self.calls.append('local-publish')
        local = r.complete_local(self.root, self.plan, audit, cleanup, before=self.before,
            teardown=self.after, lock_fds=self.fds, trusted_uid=os.getuid())
        self.actual_audit, self.actual_cleanup = copy.deepcopy(audit), copy.deepcopy(cleanup)
        self.local_completion = local
        return self.verify_completion()
    def verify_completion(self):
        self.calls.append('completion-probe')
        local = r.read_local_completion(self.root, self.plan, self.actual_audit, self.actual_cleanup, trusted_uid=os.getuid())
        fresh = copy.deepcopy(self.after)
        fresh['journal_sha256'] = local['journal_raw_sha256']; fresh['gate_sha256'] = None
        return {'stage': 'complete', 'operation_id': self.plan['operation_id'], 'plan_sha256': r.sha256(self.plan),
                'teardown': fresh, **local}


class TeardownTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

    def fixture(self, **kwargs):
        f = Fixture(self.temporary.name, **kwargs); self.addCleanup(f.close)
        return f

    def execute(self, f):
        return r.execute_recovery(f, f.plan, expected_plan_sha256=r.sha256(f.plan))

    def resume_fixture(self, f=None):
        f = self.fixture() if f is None else f
        f.plan['tool_sha256'] = r.HISTORICAL_TOOL_SHA256
        f.before['plan_sha256'] = r.sha256(f.plan); f.after['plan_sha256'] = r.sha256(f.plan)
        audit = r.audit_body(f.plan, f.before, f.after); audit['metadata']['uid'] = str(uuid.uuid4())
        f.cms[r.names(f.plan)[0]] = copy.deepcopy(audit)
        resume = {'audit_uid': audit['metadata']['uid'], 'audit_sha256': r.sha256(r.parse(audit['data']['teardown.json'])),
            'fence_command_sha256': r.sha256(['root-resume-fence']),
            'publisher_sha256': r.raw_sha256(Path(r.__file__).read_bytes())}
        def fence(plan, actual_resume, actual_audit):
            f.calls.append('resume-fence')
            payload = r.validate_resume(actual_resume, plan, actual_audit)
            f.before = payload['before']; f.resumed = copy.deepcopy(f.after)
            return f
        f.resume_fence = fence
        return f, resume, audit

    def resume(self, f, resume):
        return r.execute_resume(f, f.plan, expected_plan_sha256=r.sha256(f.plan), resume=resume)

    def test_default_is_inert_even_with_irrelevant_paths(self):
        with patch.object(r.subprocess, 'Popen', side_effect=AssertionError), patch.object(r.Path, 'read_bytes', side_effect=AssertionError):
            with patch('sys.stdout', new=io.StringIO()) as out:
                self.assertEqual(r.main(['--plan', '/missing', '--qualification']), 0)
            self.assertEqual(json.loads(out.getvalue())['state'], 'inert')

    def test_cleaned_preserves_actual_original_bytes_and_publishes_normal_uid_tombstone(self):
        f = self.fixture()
        result = self.execute(f)
        self.assertFalse(result['allocation_released'])
        self.assertFalse(result['device_calls'])
        self.assertEqual((f.root / 'journal' / (POD + '.json')).read_bytes(), f.raw)
        cleanup = f.cms[r.names(f.plan)[1]]
        payload = r.parse(cleanup['data']['receipt.json'])
        self.assertEqual(payload, r.receipt(f.plan)); self.assertNotIn('retirement', payload)
        self.assertEqual(f.local_completion['tombstone']['receipt_uid'], cleanup['metadata']['uid'])
        self.assertEqual(f.local_completion['journal_record']['readback']['hard'], 5 * 1024**3)
        self.assertEqual(f.ledger, f.cms[r.LEDGER])
        self.assertGreaterEqual(f.calls.count('node-get'), 4)
        self.assertEqual(f.calls[-1], 'release-fence')

    def test_sealed_transition_keeps_identity_original_archive_and_revokes_only_owned_gate(self):
        f = self.fixture(state='sealed', gate=True)
        original = copy.deepcopy(f.plan['journal']['record'])
        self.execute(f)
        final = r.parse((f.root / 'journal' / (POD + '.json')).read_bytes())
        self.assertEqual(final, {**original, 'state': 'cleaned'})
        archive = f.root / 'operator/teardown-recovery' / f.plan['operation_id'] / 'original-journal.json'
        self.assertEqual(archive.read_bytes(), f.raw)
        self.assertEqual(archive.stat().st_mode & 0o777, 0o400)
        self.assertFalse((f.root / 'receipts' / (POD + '.json')).exists())

    def test_archive_directory_links_are_durable_before_old_journal_transition(self):
        f = self.fixture(state='sealed'); synced = []
        sync, write = r.os.fsync, r._write
        def fsync(fd):
            synced.append(os.fstat(fd).st_ino)
            return sync(fd)
        def writing(path, *args, **kwargs):
            if Path(path).parent == f.root / 'journal':
                archive = f.root / 'operator/teardown-recovery'
                self.assertIn((f.root / 'operator').stat().st_ino, synced)
                self.assertIn(archive.stat().st_ino, synced)
                self.assertIn((archive / f.plan['operation_id']).stat().st_ino, synced)
            return write(path, *args, **kwargs)
        with patch.object(r.os, 'fsync', side_effect=fsync), patch.object(r, '_write', side_effect=writing):
            self.execute(f)
        self.assertIn(f.root.stat().st_ino, synced)

    def test_replay_is_rejected_before_more_teardown_or_publication(self):
        f = self.fixture(); self.execute(f)
        creates = len([c for c in f.calls if c.startswith('cm-create:')])
        with self.assertRaisesRegex(r.RecoveryError, 'replay'):
            self.execute(f)
        self.assertEqual(len([c for c in f.calls if c.startswith('cm-create:')]), creates)

    def test_closed_plan_typed_versions_source_and_exact_review(self):
        f = self.fixture()
        for mutate in (lambda p: p.update(extra=True), lambda p: p.update(version=True),
            lambda p: p.update(qualification_only=1), lambda p: p.update(tool_sha256='sha256:'+'1'*64),
            lambda p: p['review'].update(operator='user'), lambda p: p['journal']['record'].update(state='applied'),
            lambda p: p['scope'].update(driver_generation=BOOT),
            lambda p: p['scope']['module_sha256'].pop('nvidia_uvm'),
            lambda p: p['scope']['nvidia_gpus'].append(p['scope']['nvidia_gpus'][0])):
            with self.subTest(mutate=mutate):
                plan = copy.deepcopy(f.plan); mutate(plan)
                with self.assertRaises((ValueError, TypeError)): r.validate_plan(plan, r.sha256(plan))
        with self.assertRaises(r.RecoveryError): r.validate_plan(f.plan, 'sha256:'+'2'*64)

    def test_self_asserted_or_incomplete_before_fails_before_any_receipt(self):
        f = self.fixture()
        good = copy.deepcopy(f.before)
        for mutate in (lambda p: p.update(locks_held=False), lambda p: p.update(driver_healthy=False),
            lambda p: p.update(gpu_fd_clients=1), lambda p: p.update(pod_runtime_tasks=True),
            lambda p: p['gpu_memory_bytes'].pop(OTHER_GPU),
            lambda p: p['gpu_memory_bytes'].update({OTHER_GPU: 1}), lambda p: p.update(extra=True)):
            f.before = copy.deepcopy(good); mutate(f.before)
            with self.subTest(proof=f.before):
                with self.assertRaises(r.RecoveryError): self.execute(f)
            self.assertFalse(any(c.startswith('cm-create:') for c in f.calls))

    def test_missing_modules_or_bound_device_or_new_generation_never_clean(self):
        f = self.fixture(); good = copy.deepcopy(f.after)
        for change in ({'sysfs_modules': ['nvidia']}, {'proc_modules': ['nvidia_uvm']},
            {'pci_unbound': ['0000:06:11.0']}, {'old_generation_invalidated': False},
            {'new_load_absent': False}, {'boot_id': str(uuid.uuid4())}, {'gpu_fd_clients': 1},
            {'pod_runtime_tasks': 1}, {'journal_sha256': 'sha256:'+'1'*64}):
            f.after = {**good, **change}
            with self.subTest(change=change):
                with self.assertRaises(r.RecoveryError): self.execute(f)
            self.assertEqual((f.root / 'journal' / (POD+'.json')).read_bytes(), f.raw)
            self.assertFalse(any(c.startswith('cm-create:') for c in f.calls))

    def test_wrong_actual_node_enrollment_ledger_attempt_or_pod_stays_held(self):
        for kind in ('node', 'enrollment', 'ledger', 'attempt', 'pod'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                f = Fixture(directory)
                try:
                    if kind == 'node': f.node['metadata']['uid'] = str(uuid.uuid4())
                    if kind == 'enrollment': f.enrollment['metadata']['uid'] = str(uuid.uuid4())
                    if kind == 'ledger': f.ledger['metadata']['uid'] = str(uuid.uuid4())
                    if kind == 'attempt':
                        state = r.parse(f.ledger['data']['state.json']); state['allocations']['a'*60]['attempt'] = 'foreign'
                        f.ledger['data']['state.json'] = r.canonical(state)
                    if kind == 'pod': f.pod = {'metadata': {'uid': 'replacement'}}
                    with self.assertRaises(r.RecoveryError): self.execute(f)
                    self.assertFalse(any(c.startswith('cm-create:') for c in f.calls))
                finally: f.close()

    def test_malformed_peer_outer_alias_cannot_skip_actual_live_intent_pod(self):
        f = self.fixture()
        state = r.parse(f.ledger['data']['state.json'])
        peer = copy.deepcopy(state['allocations']['a'*60]); peer['binding_id'] = 'b'*60
        peer['name'] = 'absent-outer-alias'
        peer['intent']['name'] = 'actual-live-peer'; peer['intent']['pod_uid'] = str(uuid.uuid4())
        state['allocations']['b'*60] = peer; f.ledger['data']['state.json'] = r.canonical(state)
        f.plan['scope']['pilot_pods'].append({key: peer['intent'][key] for key in ('namespace', 'name', 'pod_uid')})
        f.plan['scope']['pilot_pods'].sort(key=lambda p: (p['namespace'], p['name'], p['pod_uid']))
        f.before['scope'] = copy.deepcopy(f.plan['scope'])
        def pod(namespace, name):
            return {'metadata': {'uid': peer['intent']['pod_uid']}} if name == 'actual-live-peer' else None
        f.get_pod = pod
        with self.assertRaisesRegex(r.RecoveryError, 'peer intent'): self.execute(f)
        self.assertFalse(any(c.startswith('cm-create:') for c in f.calls))

    def test_audit_readback_mutation_prevents_consumable_cleanup(self):
        f = self.fixture(); actual = f.get_cm
        def get(name, absent=False):
            result = actual(name, absent=absent)
            if name == r.names(f.plan)[0] and result is not None: result['immutable'] = False
            return result
        f.get_cm = get
        with self.assertRaises(r.RecoveryError): self.execute(f)
        self.assertNotIn(r.names(f.plan)[1], f.cms)

    def test_final_audit_uid_replacement_never_becomes_successful_orphan_provenance(self):
        f = self.fixture(); actual = f.publish_local
        def publish(audit, cleanup):
            result = actual(audit, cleanup)
            f.cms[r.names(f.plan)[0]]['metadata']['uid'] = str(uuid.uuid4())
            return result
        f.publish_local = publish
        with self.assertRaisesRegex(r.RecoveryError, 'Audit authority replaced'): self.execute(f)
        self.assertEqual(f.cms[r.LEDGER], f.ledger)

    def test_late_node_pod_and_physical_module_changes_fail_after_audit_and_before_cleanup(self):
        for change in ('node', 'pod', 'module'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                f = Fixture(directory)
                try:
                    actual = f.create_cm
                    def create(body):
                        created = actual(body)
                        if change == 'node': f.node['metadata']['uid'] = str(uuid.uuid4())
                        if change == 'pod': f.pod = {'metadata': {'uid': 'replacement'}}
                        if change == 'module': f.after['sysfs_modules'] = ['nvidia']
                        return created
                    f.create_cm = create
                    with self.assertRaises(r.RecoveryError): self.execute(f)
                    self.assertIn(r.names(f.plan)[0], f.cms)
                    self.assertNotIn(r.names(f.plan)[1], f.cms)
                    self.assertEqual((f.root / 'journal' / (POD+'.json')).read_bytes(), f.raw)
                finally: f.close()

    def test_journal_changed_or_unowned_lock_prevents_local_publication(self):
        f = self.fixture()
        audit = r.audit_body(f.plan, f.before, f.after); audit['metadata']['uid'] = str(uuid.uuid4())
        cleanup = r.cleanup_body(f.plan, audit); cleanup['metadata']['uid'] = str(uuid.uuid4())
        fcntl.flock(f.fds['driver'], fcntl.LOCK_UN)
        with self.assertRaisesRegex(r.RecoveryError, 'exclusive lock'):
            r.complete_local(f.root, f.plan, audit, cleanup, before=f.before, teardown=f.after,
                lock_fds=f.fds, trusted_uid=os.getuid())
        fcntl.flock(f.fds['driver'], fcntl.LOCK_EX)
        path = f.root / 'journal' / (POD+'.json'); path.write_bytes(f.raw + b' ')
        with self.assertRaisesRegex(r.RecoveryError, 'journal bytes'):
            r.complete_local(f.root, f.plan, audit, cleanup, before=f.before, teardown=f.after,
                lock_fds=f.fds, trusted_uid=os.getuid())
        self.assertFalse((f.root / 'published-cleanup').exists())

    def test_missing_or_replaced_protected_completion_is_not_a_cached_success(self):
        f = self.fixture(); self.execute(f)
        path = f.root / 'published-cleanup' / (POD+'.json')
        mark = r.parse(path.read_bytes()); mark['receipt_uid'] = str(uuid.uuid4()); path.write_text(r.canonical(mark))
        with self.assertRaises(r.RecoveryError): f.verify_completion()

    def test_parse_duplicate_or_nonfinite_rejected(self):
        for raw in ('{"a":1,"a":1}', '{"a":NaN}', 'null-not-json'):
            with self.assertRaises(r.RecoveryError): r.parse(raw)

    def test_rpc_rejects_stale_foreign_nonce_extra_fields_and_unpinned_command(self):
        f = self.fixture()
        with self.assertRaises(r.RecoveryError): r.RootFence(['different'], f.plan)
        rpc = r.RootFence(['root-fence'], f.plan)
        base = {'event': 'fence-acquired', 'nonce': rpc.nonce,
                'observed_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'proof': f.before}
        for change in ({'nonce': str(uuid.uuid4())}, {'event': 'unexpected'}, {'extra': True},
            {'observed_at': (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat().replace('+00:00', 'Z')}):
            rpc.buffer = (r.canonical({**base, **change})+'\n').encode()
            with self.assertRaises(r.RecoveryError): rpc.line('fence-acquired')

    def test_rpc_prequeued_proof_and_early_success_exit_are_rejected(self):
        f = self.fixture(); rpc = r.RootFence(['root-fence'], f.plan)
        value = {'event': 'fence-acquired', 'nonce': rpc.nonce,
            'observed_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'proof': f.before}
        rpc.buffer = (r.canonical(value)+'\n'+r.canonical(value)+'\n').encode()
        with self.assertRaisesRegex(r.RecoveryError, 'prequeued'): rpc.line('fence-acquired')
        rpc.process = Mock(); rpc.process.poll.return_value = 0; rpc.process.returncode = 0
        with self.assertRaisesRegex(r.RecoveryError, 'before requested release'): rpc.__exit__(None, None, None)

    def test_rpc_success_exit_between_alive_checks_requires_actual_release_send(self):
        f = self.fixture(); rpc = r.RootFence(['root-fence'], f.plan)
        rpc.process = Mock(); rpc.process.poll.side_effect = [None, 0]; rpc.process.returncode = 0
        with self.assertRaisesRegex(r.RecoveryError, 'before requested release'): rpc.__exit__(None, None, None)
        rpc.process.stdin.write.assert_not_called()

    def test_resume_uses_actual_immutable_original_proof_and_preserves_every_audit_byte(self):
        f, resume, audit = self.resume_fixture(); before = copy.deepcopy(f.before)
        result = self.resume(f, resume)
        self.assertEqual(result['state'], 'teardown-cleanup-resumed')
        self.assertEqual(f.cms[r.names(f.plan)[0]], audit)
        self.assertEqual(f.before, before)
        self.assertNotIn('cm-create:'+r.names(f.plan)[0], f.calls)
        self.assertIn('resume-fence', f.calls)
        self.assertEqual((f.root/'journal'/(POD+'.json')).read_bytes(), f.raw)
        self.assertEqual(f.local_completion['tombstone']['enrollment_uid'], f.plan['enrollment_uid'])
        self.assertEqual(f.cms[r.LEDGER], f.ledger)

    def test_resume_requires_exact_audit_uid_sha_known_old_source_and_new_source(self):
        f, resume, audit = self.resume_fixture()
        for change in ({'audit_uid': str(uuid.uuid4())}, {'audit_sha256': 'sha256:'+'1'*64},
                       {'publisher_sha256': r.HISTORICAL_TOOL_SHA256}, {'extra': True}):
            with self.subTest(change=change):
                with self.assertRaises(r.RecoveryError): r.validate_resume({**resume, **change}, f.plan, audit)
        foreign = copy.deepcopy(f.plan); foreign['tool_sha256'] = 'sha256:'+'f'*64
        with self.assertRaisesRegex(r.RecoveryError, 'source changed'):
            r.validate_historical_plan(foreign, r.sha256(foreign))
        with self.assertRaisesRegex(r.RecoveryError, 'source changed'):
            r.validate_plan(f.plan, r.sha256(f.plan))

    def test_resume_rejects_existing_cleanup_before_reacquiring_fence(self):
        f, resume, audit = self.resume_fixture()
        f.cms[r.names(f.plan)[1]] = {'already': 'exists'}
        with self.assertRaisesRegex(r.RecoveryError, 'Existing cleanup'): self.resume(f, resume)
        self.assertNotIn('resume-fence', f.calls)
        self.assertFalse(any(c.startswith('cm-create:') for c in f.calls))

    def test_resume_fresh_locks_modules_pod_or_historical_proof_change_never_publish(self):
        for kind in ('locks', 'module', 'pod', 'old-proof'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                # Use a separately isolated fixture for every already-unloaded case.
                f = Fixture(directory)
                try:
                    f, resume, audit = self.resume_fixture(f)
                    if kind == 'locks': f.after['locks']['driver']['inode'] += 1
                    if kind == 'module': f.after['sysfs_modules'] = ['nvidia']
                    if kind == 'pod': f.pod = {'metadata': {'uid': 'foreign'}}
                    if kind == 'old-proof':
                        payload = r.parse(f.cms[r.names(f.plan)[0]]['data']['teardown.json'])
                        payload['before']['driver_healthy'] = False
                        f.cms[r.names(f.plan)[0]]['data']['teardown.json'] = r.canonical(payload)
                    with self.assertRaises(r.RecoveryError): self.resume(f, resume)
                    self.assertFalse(any(c.startswith('cm-create:') for c in f.calls))
                finally:
                    f.close()

    def test_resume_late_actual_audit_uid_replacement_is_rejected(self):
        f, resume, audit = self.resume_fixture(); publish = f.publish_local
        def local(audit, cleanup):
            result = publish(audit, cleanup)
            f.cms[r.names(f.plan)[0]]['metadata']['uid'] = str(uuid.uuid4())
            return result
        f.publish_local = local
        with self.assertRaisesRegex(r.RecoveryError, 'actual UID'): self.resume(f, resume)

    def test_root_rpc_eof_preserves_durable_private_diagnostic_stderr(self):
        f = self.fixture()
        command = [sys.executable, '-c', 'import sys;sys.stdin.readline();sys.stderr.write("protected diagnostic\\n");sys.stderr.flush()']
        f.plan['fence_command_sha256'] = r.sha256(command)
        rpc = r.RootFence(command, f.plan, timeout=2, diagnostics_dir=f.root)
        with self.assertRaises(r.RecoveryError): rpc.__enter__()
        path = Path(rpc.stderr_path)
        self.assertTrue(path.exists()); self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertIn('protected diagnostic', path.read_text())

    def test_kubernetes_backend_never_mutates_without_fence(self):
        backend = r.KubernetesBackend(['root-fence'])
        with patch.object(r.subprocess, 'run', side_effect=AssertionError('Must not call')):
            with self.assertRaisesRegex(r.RecoveryError, 'held Root fence'):
                backend.create_cm({'kind': 'ConfigMap'})

    def test_resume_cli_requires_reviewed_current_source_and_full_pins_before_transport(self):
        f, resume, audit = self.resume_fixture()
        planfile, commandfile = f.root/'plan.json', f.root/'command.json'
        planfile.write_text(r.canonical(f.plan)); commandfile.write_text(r.canonical(['root-resume-fence']))
        argv = ['--execute', '--qualification', '--plan', str(planfile), '--plan-sha256', r.sha256(f.plan),
                '--fence-command-file', str(commandfile), '--output', str(f.root/'result.json'),
                '--resume-audit-uid', resume['audit_uid'], '--resume-audit-sha256', resume['audit_sha256'],
                '--resume-fence-command-sha256', resume['fence_command_sha256']]
        with patch.object(r, 'KubernetesBackend', side_effect=AssertionError('Transport must not initialize')):
            with self.assertRaisesRegex(r.RecoveryError, 'All explicit resume'): r.main(argv)
            with self.assertRaisesRegex(r.RecoveryError, 'publisher SHA mismatch'):
                r.main(argv + ['--resume-publisher-sha256', 'sha256:'+'f'*64])

    def test_real_resume_jsonl_route_preserves_audit_and_supports_repeated_teardown(self):
        f, resume, audit = self.resume_fixture()
        datafile = f.root/'rpc-data.json'
        code = '''import datetime,json,sys,uuid
d=json.load(open(sys.argv[1]))
r=json.loads(sys.stdin.readline())
assert set(r)=={'op','nonce','plan','plan_sha256','audit','resume'}
assert r['op']=='resume-after-audit'
assert str(uuid.UUID(r['nonce']))==r['nonce']
assert r['plan']==d['plan'] and r['plan_sha256']==d['plan_sha256']
assert r['audit']==d['audit'] and r['resume']==d['resume']
nonce=r['nonce']
def emit(event):
 print(json.dumps({'event':event,'nonce':nonce,'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),'proof':d['teardown']}),flush=True)
sys.stderr.write('CPU resume route accepted\\n');sys.stderr.flush()
emit('fence-resumed')
count=0
while True:
 r=json.loads(sys.stdin.readline())
 assert set(r)=={'op','nonce'} and r['nonce']==nonce
 if r['op']=='release':
  assert count==2
  break
 assert r['op']=='verify-teardown'
 count+=1
 emit('fence-teardown-verified')
'''
        command = [sys.executable, '-c', code, str(datafile)]
        resume['fence_command_sha256'] = r.sha256(command)
        datafile.write_text(r.canonical({'plan': f.plan, 'plan_sha256': r.sha256(f.plan),
            'audit': audit, 'resume': resume, 'teardown': f.after}))
        with r.RootFence(command, f.plan, timeout=3, resume=resume, audit=audit, diagnostics_dir=f.root) as rpc:
            self.assertEqual(rpc.before, f.before)
            self.assertEqual(rpc.resumed, f.after)
            self.assertEqual(rpc.verify_teardown(), f.after)
            self.assertEqual(rpc.verify_teardown(), f.after)
        self.assertEqual(rpc.process.returncode, 0)
        self.assertIn('CPU resume route accepted', Path(rpc.stderr_path).read_text())


if __name__ == '__main__': unittest.main()

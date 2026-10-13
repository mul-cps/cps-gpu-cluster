import asyncio
import copy
import importlib.util
from pathlib import Path
import unittest
import tempfile
import os
import stat
from datetime import datetime, timedelta, timezone

BASELINE = Path('/home/bjoern/.local/state/cps-full-project-20261013/normal-source-gpu-acceptance.py')

spec = importlib.util.spec_from_file_location('pair', Path(__file__).with_name('pair.py'))
pair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pair)


def fixture():
    snapshots = {}
    for suffix in ('a', 'b'):
        name = 'native-group-' + suffix
        snapshots[name] = {'members': ['canonical-' + suffix],
            'workspace': {'id': name, 'profile': 'interactive-shared-5', 'state': 'stopped'},
            'approval': {'ready': True, 'revision': 'sha256:832e841b6e7b5885a80de27e8850e8e25087b7a26a08a8270f38869f10bf71ca', 'policy_hash': 'sha256:' + 'd' * 64},
            'reservation': {'active': False, 'attempt': None}}
    capacity = {'pool': {'node': 'k3s-wk-gpu2', 'node_uid': '3336cdd5-d245-436e-b57c-2f66c6dcaa41',
        'gpu_uuid': 'GPU-16128952-b438-556a-00bb-93039ee24e56', 'max_workspaces': 2,
        'memory_budget_mib': 15360, 'headroom_mib': 1024}, 'active_native_entries': 0,
        'native_used_bytes': 0, 'policy_hash': 'sha256:' + 'd' * 64}
    return snapshots, capacity


class AdmissionTests(unittest.TestCase):
    def test_disjoint_existing_members_allow_five_plus_five(self):
        self.assertTrue(pair.check_pair(*fixture()))

    def test_shared_person_is_denied_even_if_two_workspaces_fit(self):
        snapshots, capacity = fixture()
        snapshots['native-group-b']['members'] = snapshots['native-group-a']['members']
        with self.assertRaisesRegex(RuntimeError, 'canonical-member-overlap'):
            pair.check_pair(snapshots, capacity)


class LifecycleTests(unittest.TestCase):
    def test_historical_fsgroup_widened_parent_is_untouched_and_not_reused(self):
        module = pair.load_baseline(BASELINE.read_text(), 'native-group-a', None)
        run_id = 'eba90970-c120-450b-a6de-7afe764238a1'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old = root/'normal-source-gpu-acceptance'
            old.mkdir(mode=0o700); old.chmod(0o2770)
            before = old.stat()
            try:
                created = module.evidence_directory(run_id, data_root=root)
                failure = None
            except module.AcceptanceFailure as error:
                failure = str(error)
            self.assertIsNone(failure, 'pair must use its own fresh private parent')
            self.assertEqual(created.parent.name, 'normal-source-gpu-acceptance-' + run_id)
            self.assertEqual(old.stat().st_ino, before.st_ino)
            self.assertEqual(stat.S_IMODE(old.stat().st_mode), 0o2770)

    def test_new_run_parent_strips_only_its_own_inherited_setgid(self):
        module = pair.load_baseline(BASELINE.read_text(), 'native-group-a', None)
        run_id = 'eba90970-c120-450b-a6de-7afe764238a1'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); root.chmod(0o2770)
            created = module.evidence_directory(run_id, data_root=root)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o2770)
            self.assertEqual(created.parent.name, 'normal-source-gpu-acceptance-' + run_id)
            self.assertEqual(stat.S_IMODE(created.parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(created.stat().st_mode), 0o700)

    def test_preexisting_widened_run_parent_is_refused_not_repaired(self):
        module = pair.load_baseline(BASELINE.read_text(), 'native-group-a', None)
        run_id = 'eba90970-c120-450b-a6de-7afe764238a1'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); parent = root/('normal-source-gpu-acceptance-' + run_id)
            parent.mkdir(mode=0o700); parent.chmod(0o2770)
            with self.assertRaisesRegex(module.AcceptanceFailure, 'private-evidence-directory-required'):
                module.evidence_directory(run_id, data_root=root)
            self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o2770)

    def test_run_parent_symlink_is_refused(self):
        module = pair.load_baseline(BASELINE.read_text(), 'native-group-a', None)
        run_id = 'eba90970-c120-450b-a6de-7afe764238a1'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); target = root/'elsewhere'; target.mkdir()
            (root/('normal-source-gpu-acceptance-' + run_id)).symlink_to(target, target_is_directory=True)
            with self.assertRaises(OSError):
                module.evidence_directory(run_id, data_root=root)
            self.assertEqual(list(target.iterdir()), [])

    def test_early_guard_reason_is_diagnosed_without_public_unexpected_body(self):
        self.assertTrue(callable(getattr(pair, 'failure_diagnostic', None)), 'early failures need a private diagnostic')
        module = pair.load_baseline(BASELINE.read_text(), 'native-group-a', None)
        result = pair.failure_diagnostic('native-group-a', module,
            module.AcceptanceFailure('private-evidence-directory-required'))
        self.assertEqual(result['failure_code'], 'private-evidence-directory-required')
        unexpected = pair.failure_diagnostic('native-group-a', module, ValueError('sensitive-http-body'))
        self.assertEqual(unexpected['failure_code'], 'unexpected-see-private-diagnostic')
        self.assertIn('sensitive-http-body', unexpected['private_diagnostic'])

    def test_changed_original_source_cannot_be_adapted(self):
        with self.assertRaisesRegex(RuntimeError, 'baseline-source-changed'):
            pair.load_baseline(BASELINE.read_text() + '\n', 'native-group-a', None)

    def test_both_ready_gate_never_opens_for_one_workspace(self):
        async def run():
            hold = pair.PairHold(seconds=0, ready_timeout=0.02)
            with self.assertRaisesRegex(RuntimeError, 'peer-start-failed-or-ready-timeout'):
                await hold('native-group-a', {})
            self.assertFalse(hold.gate.is_set())
        asyncio.run(run())

    def test_failed_peer_unblocks_ready_workspace_for_normal_cleanup(self):
        async def run():
            hold = pair.PairHold(seconds=0, ready_timeout=5)
            first = asyncio.create_task(hold('native-group-a', {}))
            await asyncio.sleep(0)
            hold.abort.set()
            with self.assertRaisesRegex(RuntimeError, 'peer-start-failed'):
                await asyncio.wait_for(first, 0.1)
        asyncio.run(run())

    def test_common_hold_requires_both_ordinary_start_readbacks(self):
        async def run():
            hold = pair.PairHold(seconds=0)
            await asyncio.gather(hold('native-group-a', {}), hold('native-group-b', {}))
            self.assertTrue(hold.gate.is_set())
            self.assertEqual(set(hold.ready), set(pair.TARGETS))
        asyncio.run(run())

    def test_unconfirmed_stop_preserves_changed_permission_windows(self):
        module = pair.load_baseline(BASELINE.read_text(), 'native-group-a', None)
        now = datetime.now(timezone.utc)
        old = {'id': 'existing-grant', 'person': 'canonical-a', 'profiles': [module.PROFILE],
               'source': 'cps', 'allowance': 1, 'starts': (now-timedelta(days=2)).isoformat(),
               'expires': (now-timedelta(days=1)).isoformat()}
        target = module.target_windows([old], now, now+timedelta(minutes=30))[0]
        class Compute:
            def __init__(self): self.value, self.writes = old, []
            async def grants(self, person): return [self.value]
            async def put_grant(self, value, actor): self.value=value; self.writes.append(value)
        class Service:
            def __init__(self): self.compute=Compute()
            async def members(self, workspace): return ['canonical-a']
            async def start(self, *args, **kwargs): raise RuntimeError('transport-failed-after-attempt')
            async def close(self, *args, **kwargs): raise RuntimeError('shutdown-unconfirmed')
        before={'workspace':{}, 'members':['canonical-a'], 'memberships':[], 'grants':[old],
                'all_owned_member_grants':[old]}
        async def capture(*args): return before
        module.capture=capture
        plan={'version':1,'actor':'bjoern','workspace':'native-group-a','hold_seconds':180,
              'run_id':'eba90970-c120-450b-a6de-7afe764238a1',
              'execute_before':(now+timedelta(minutes=5)).isoformat(),'before':before,
              'target_memberships':[],'target_grants':[target]}
        service=Service()
        with tempfile.TemporaryDirectory() as td:
            module.evidence_directory=lambda run_id: Path(td)
            self.assertEqual(asyncio.run(module.execute(None,service,plan,module.digest(plan))),1)
        self.assertEqual(service.compute.writes,[target])
        self.assertEqual(service.compute.value,target)

    def test_changed_budget_is_not_silently_accepted(self):
        snapshots, capacity = fixture()
        capacity['pool']['memory_budget_mib'] = 20480
        with self.assertRaisesRegex(RuntimeError, 'exact-reviewed-pool'):
            pair.check_pair(snapshots, capacity)

    def test_active_reservation_is_not_inferred_free_from_zero_charge(self):
        snapshots, capacity = fixture()
        snapshots['native-group-a']['reservation']['active'] = True
        with self.assertRaisesRegex(RuntimeError, 'inactive-reservations'):
            pair.check_pair(snapshots, capacity)

    def test_foreign_native_entry_blocks_the_pair(self):
        snapshots, capacity = fixture()
        capacity['active_native_entries'] = 1
        with self.assertRaisesRegex(RuntimeError, 'empty-native-capacity'):
            pair.check_pair(snapshots, capacity)


if __name__ == '__main__':
    unittest.main()

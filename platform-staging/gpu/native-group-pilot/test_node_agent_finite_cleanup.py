"""CPU regression for preserving each stopped Pod's finite cap until retirement."""
import copy
from contextlib import redirect_stdout
import importlib
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_node_agent import fixtures, GPU, NODE, POD


class FiniteCleanupTest(unittest.TestCase):
    def setUp(self):
        self.agent = importlib.import_module('node_agent')
        self.models = self.agent.load_models_from_snapshot()

    def exercise(self, cap_mib, *, exists, disappear_on_reset=False, fault=None):
        """Keep real enrollment/store/journal/controller/proof code; fake host/API I/O."""
        config, enrollment, cm = fixtures()
        source = 'cps' if cap_mib == 5120 else 'cit'
        profile = 'interactive-native-qualification-' + str(cap_mib // 1024)
        config.update(version=2, mode='operator-qualification',
            workspaces={source + ':pilot': {'profile': profile, 'cap_mib': cap_mib}})
        config['pool'].update(total_memory_mib=40960, free_memory_mib=32768,
            headroom_mib=1024, memory_budget_mib=15360,
            boot_id='209f8bc9-a478-48e4-925a-6e07ffa56f7a',
            driver_generation='e148263b-805d-4ccd-857c-84a03d4f4229')
        enrollment.update(source=source, principal='workspace:' + source + ':pilot',
            namespace=self.agent.NAMESPACES[source], profile=profile, cap_mib=cap_mib)
        enrollment['intent'].update(namespace=enrollment['namespace'], cap_mib=cap_mib)
        cm['data']['enrollment.json'] = json.dumps(enrollment)
        intent = self.models.CapIntent(**enrollment['intent'])
        relative = '/kubepods.slice/kubepods-burstable-pod' + POD.replace('-', '_') + '.slice'
        identity = self.models.CapIdentity(POD, intent.spec_sha256, NODE, GPU, 'c' * 64,
            211, 345, config['pool']['boot_id'], relative, '/sys/fs/cgroup' + relative,
            29, 71, config['pool']['driver_generation'])
        limit = self.models.CapLimit(cap_mib * 1048576, cap_mib * 1048576)
        sealed = self.models.CapRecord(intent, identity, 'sealed',
            'e148263b-805d-4ccd-857c-84a03d4f4229', limit)
        inventory = {'version': 1, 'backend': 'misc-fallback', 'gpu_uuid': GPU, 'gpu_id': 1,
            'entries': [{'cgroup_id': 71, 'kernfs_id': 71, 'inode': 71,
                'offline': True, 'pinned': True, 'default_hierarchy': True,
                'soft': limit.soft, 'hard': limit.hard, 'used': 0}]}
        if fault == 'used': inventory['entries'][0]['used'] = 1
        elif fault == 'foreign-inode':
            inventory['entries'][0].update(cgroup_id=72, kernfs_id=72, inode=72)
        elif fault == 'foreign-gpu': inventory['gpu_uuid'] = 'GPU-22222222-2222-4222-8222-222222222222'
        elif fault == 'changed-cap': inventory['entries'][0].update(soft=64, hard=64)
        elif fault == 'unlimited': inventory['entries'][0].update(soft=0, hard=self.models.MAX_LIMIT)
        outer = self

        class Host:
            def __init__(self):
                self.exists, self.limit, self.gate = exists, limit, sealed.receipt()
                self.writes = []
            def check_cleanup(self, actual):
                outer.assertEqual(actual, identity)
                return outer.models.CleanupObservation(identity.epoch, None, False,
                    identity.cgroup_path, 29 if self.exists else None,
                    71 if self.exists else None, self.exists, False,
                    not self.exists, True)  # an unrelated peer may remain active
            def read_limit(self, actual):
                outer.assertEqual(actual, identity)
                outer.assertTrue(self.exists, 'Absent cgroup must use physical inventory')
                return self.limit
            def set_limit(self, actual, value):
                outer.assertEqual(actual, identity)
                self.writes.append(value)
                self.limit = value
                if disappear_on_reset:
                    self.exists = False
                    inventory['entries'][0].update(soft=value.soft, hard=value.hard)
            def retired_inert_cap(self, actual, value):
                outer.assertFalse(self.exists)
                outer.assertEqual((actual, value), (identity, limit))
                return outer.models.validate_retired_inventory(inventory, actual, value)
            def read_gate(self, actual):
                outer.assertEqual(actual, identity)
                return copy.deepcopy(self.gate)
            def revoke_gate(self, actual, expected):
                outer.assertEqual((actual, expected), (identity, self.gate))
                self.gate = None
            def seal_gate(self, *args): outer.fail('Stopped lifetime must never reseal')
            def _raw(self, actual):
                outer.assertEqual(actual, identity)
                return {'soft': self.limit.soft, 'hard': self.limit.hard, 'used': 0}

        host, created, output = Host(), [], StringIO()
        maps = {cm['metadata']['name']: cm}
        def create(namespace, body):
            self.assertEqual(namespace, config['authority_namespace'])
            value = copy.deepcopy(body)
            value['metadata'].update(uid='66666666-6666-4666-8666-666666666666', resourceVersion='2')
            maps[value['metadata']['name']] = value
            created.append(value)
            return value
        kube = SimpleNamespace(node=lambda name: {'metadata': {'name': name, 'uid': NODE}},
            enrollments=lambda ns: [cm], configmap=lambda ns, name: maps.get(name),
            pod=lambda value: None, create_configmap=create,
            delete=lambda *args: self.fail('Cleanup must not delete another Pod'))
        qualification = SimpleNamespace(cri_reader=lambda *args: None,
            gpu_clients=lambda *args: (), health=lambda *args, **kwargs: None,
            awaiting_first_gate=lambda *args: False)
        bundle = (SimpleNamespace(QualificationNodeBackend=lambda *args, **kwargs: host),
            qualification, {'models': self.models, 'manual': object(), 'health': object(), 'cdi': object()})
        store_class = self.agent.EnrollmentStore
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            journal = self.models.PrivateJournal(root / 'journal')
            journal.write(sealed)
            with patch.object(self.agent, 'EnrollmentStore', side_effect=lambda path, models:
                    store_class(path, models, trusted_uid=os.getuid())), \
                    patch.object(self.agent, 'abort_current_epoch', return_value=identity.epoch), \
                    redirect_stdout(output):
                if fault:
                    with self.assertRaisesRegex(ValueError, 'blocked errors'):
                        self.agent.run(config, bundle, root, kube, object(), iterations=1,
                            interval=0, crictl='unused', cri_socket='unused')
                else:
                    self.agent.run(config, bundle, root, kube, object(), iterations=1,
                        interval=0, crictl='unused', cri_socket='unused')
            result = journal.read(POD)
            published = list((root / 'published-cleanup').glob('*.json'))
        return sealed, result, host, created, published, [json.loads(line) for line in output.getvalue().splitlines()]

    def test_zero_tasks_and_clients_with_surviving_cgroup_retains_exact_finite_cap(self):
        for cap in (5120, 10240):
            with self.subTest(cap=cap):
                sealed, result, host, created, published, events = self.exercise(cap, exists=True)
                self.assertEqual(result, sealed)
                self.assertEqual(host.limit, sealed.limit)
                self.assertEqual(host.gate, sealed.receipt())
                self.assertEqual((host.writes, created, published), ([], [], []))
                self.assertEqual(events[0]['state'], 'retained-awaiting-stop')

    def test_surviving_cgroup_never_enters_clear_then_disappear_race(self):
        for cap in (5120, 10240):
            with self.subTest(cap=cap):
                sealed, result, host, created, _, events = self.exercise(cap, exists=True, disappear_on_reset=True)
                self.assertEqual(result, sealed)
                self.assertTrue(host.exists)
                self.assertEqual(host.limit, sealed.limit)
                self.assertEqual((host.writes, created), ([], []))
                self.assertEqual(events[0]['state'], 'retained-awaiting-stop')

    def test_absent_cgroup_uses_original_finite_retirement_without_cap_write(self):
        for cap in (5120, 10240):
            with self.subTest(cap=cap):
                sealed, result, host, created, published, events = self.exercise(cap, exists=False)
                self.assertEqual(result.state, 'retired-inert-cap')
                self.assertEqual((result.intent, result.identity, result.seal_id, result.readback),
                    (sealed.intent, sealed.identity, sealed.seal_id, sealed.readback))
                self.assertEqual((result.retirement.entry.soft, result.retirement.entry.hard),
                    (cap * 1048576, cap * 1048576))
                self.assertEqual(host.writes, [])
                self.assertIsNone(host.gate)
                self.assertEqual((len(created), len(published)), (1, 1))
                receipt = json.loads(created[0]['data']['receipt.json'])
                self.assertEqual(receipt['retirement']['journal_sha256'],
                    self.agent.canonical_sha256(result.to_dict()))
                self.assertEqual(events[0]['state'], 'cleanup-confirmed')

    def test_absent_cgroup_with_unsafe_inventory_never_publishes_cleanup(self):
        for fault in ('used', 'foreign-inode', 'foreign-gpu', 'changed-cap', 'unlimited'):
            with self.subTest(fault=fault):
                sealed, result, host, created, published, events = self.exercise(5120, exists=False, fault=fault)
                self.assertEqual(result, sealed)
                self.assertEqual((host.writes, created, published), ([], [], []))
                self.assertEqual(host.gate, sealed.receipt())
                self.assertEqual(events[0]['state'], 'blocked-error')


if __name__ == '__main__':
    unittest.main()

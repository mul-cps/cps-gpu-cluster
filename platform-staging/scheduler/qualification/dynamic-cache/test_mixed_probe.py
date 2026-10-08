"""Offline protocol/quota simulations; no test initializes real CUDA."""
import copy
import ctypes
import datetime as dt
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixed_contract as contract
import mixed_probe as probe

NOW = dt.datetime(2026, 10, 7, 16, 0, tzinfo=dt.timezone.utc)
NOW_NS = int(NOW.timestamp() * 1e9)
GPU = '16128952b438556a00bb93039ee24e56'
COMPILER = {'sourceCommit': contract.SOURCE, 'moduleSha256': contract.MODULE_SHA, 'version': '0.1.0'}


class FakeClock:
    def __init__(self):
        self.ns = NOW_NS + 1_000_000_000

    def now_ns(self):
        return self.ns

    def sleep(self, seconds):
        if seconds < 0:
            raise ValueError('Negative wait')
        self.ns += round(seconds * 1e9)


class Simulation:
    """Per-workspace accounting across two independently owned processes."""
    def __init__(self, role, faults=None):
        self.role = role
        self.clock = FakeClock()
        self.faults = faults or {}
        self.children = []
        self.events = []

    def prepare(self, role):
        if role != self.role:
            raise RuntimeError('Role mismatch')
        approval = {'podUid': 'pod-' + role, 'gpuUuid': 'GPU-' + GPU,
            'mps': {'windowEndsAtNs': NOW_NS + 180 * 10**9, 'observedAt': NOW.isoformat()}}
        return {'runId': 'fake0716', 'hami': {'sha256': 'a' * 64}}, approval, COMPILER

    def factory(self, name):
        worker = FakeChild(name, self)
        if 'ready' in self.faults:
            self.faults['ready'](worker.ready, len(self.children))
        self.children.append(worker)
        self.events.append({'event': 'mixed-child-evidence', 'child': name, 'value': copy.deepcopy(worker.ready)})
        return worker

    def run(self):
        return probe.run_role(self.role, child_factory=self.factory, clock=self.clock,
                              prepare=self.prepare, output=self.events.append)

    @property
    def report(self):
        return [event for event in self.events if event.get('event') == 'mixed-result'][-1]


class FakeChild:
    def __init__(self, name, simulation):
        self.name = name
        self.simulation = simulation
        self.closed = False
        self.allocations = {}
        gib = contract.ROLES[simulation.role]
        self.ready = {'event': 'ready', 'pid': 100 if name == 'a' else 101,
            'gpu': GPU, 'podUid': 'pod-' + simulation.role, 'runId': 'fake0716',
            'role': simulation.role, 'profileGiB': gib, 'compiler': copy.deepcopy(COMPILER),
            'cache': {'device': 7, 'inode': 444, 'uid': contract.UID, 'gid': contract.GID,
                'path': probe.core.CACHE_PATH, 'mappingVerified': True, 'noTmpFallback': True},
            'hami': {'sha256': 'a' * 64, 'loaded': True, 'preloadVerified': True,
                'perDeviceLimitVerified': True, 'singleVisibleDeviceVerified': True,
                'sourceRevisionVerified': False, 'effectiveLimitBytes': gib * 1024**3,
                'canonicalLimitBytes': gib * 1024**3}}

    def request(self, ident, action, label='ordinary', **extra):
        sim = self.simulation
        fault = sim.faults.get(ident)
        if isinstance(fault, BaseException):
            raise fault
        started = sim.clock.now_ns()
        sim.clock.sleep(0.001)
        value = {**copy.deepcopy(self.ready), 'event': 'response', 'id': ident,
            'action': action, 'label': label, 'operationStartedNs': started,
            'operationFinishedNs': sim.clock.now_ns(), 'cudaResult': 0,
            'observedNs': sim.clock.now_ns()}
        if action == 'allocate':
            mib = extra['mib']
            allocated = sum(sum(child.allocations.values()) for child in sim.children)
            value.update(allocationMiB=mib, startMonotonicNs=started - NOW_NS,
                         endMonotonicNs=sim.clock.now_ns() - NOW_NS,
                         freeBytesAfter=(contract.ROLES[sim.role] * 1024 - allocated) * 1024**2,
                         totalBytes=contract.ROLES[sim.role] * 1024**3)
            value['cudaResult'] = 0 if allocated + mib <= contract.ROLES[sim.role] * 1024 else 2
            if value['cudaResult'] == 0:
                self.allocations[label] = mib
                value.update(writeBytes=mib * 1024**2, writeStartedNs=started,
                             writeFinishedNs=sim.clock.now_ns())
        elif action == 'tick':
            if label not in self.allocations:
                raise RuntimeError('Simulated write without a held allocation')
            value.update(writeBytes=1024**2, writeStartedNs=started,
                         writeFinishedNs=sim.clock.now_ns())
        elif action == 'free':
            del self.allocations[label]
        else:
            raise RuntimeError('Unknown simulated action')
        if callable(fault):
            fault(value)
        sim.events.append({'event': 'mixed-child-evidence', 'child': self.name, 'value': copy.deepcopy(value)})
        if not probe.valid_response(value, self.ready, ident, action, label,
                                    allocation_mib=extra.get('mib')):
            raise RuntimeError('Simulated malformed child response')
        return value

    def close(self):
        self.closed = True
        self.allocations.clear()
        if self.simulation.faults.get('close'):
            raise RuntimeError('Simulated cleanup failure')


class MixedProbeTests(unittest.TestCase):
    def test_each_profile_runs_real_protocol_shapes_without_cuda(self):
        for role, gib in contract.ROLES.items():
            with self.subTest(role=role):
                sim = Simulation(role)
                self.assertEqual(sim.run(), 0)
                report = sim.report
                self.assertEqual(report['status'], 'bounded-mixed-role-passed')
                self.assertEqual(report['hold']['payloadMiB'], sum(contract.HOLD_ALLOCATIONS[gib]))
                self.assertEqual(len(report['hold']['ticks']), 40)
                self.assertEqual(report['hold']['finishedNs'] - report['hold']['startedNs'], 20 * 10**9)
                self.assertTrue(probe.ordinary_verdict(report['ordinary'], report['children'], contract.ALLOCATIONS[gib]))
                self.assertEqual(report['ordinary']['bDenied']['cudaResult'], 2)
                self.assertTrue(all(worker.closed and not worker.allocations for worker in sim.children))
                self.assertLess(report['finishedNs'] - report['startedNs'], 115 * 10**9)
                for field in ('productionQualified', 'hostileIsolationQualified', 'mpsThreeClientQualified'):
                    self.assertIs(report[field], False)
                self.assertEqual(len(report['peerProgress']), 90 if role == 'peer5' else 0)

    def test_common_hold_overlaps_and_peer_writes_cover_workspace_oom(self):
        simulations = {role: Simulation(role) for role in contract.ROLES}
        for sim in simulations.values():
            self.assertEqual(sim.run(), 0)
        reports = {role: sim.report for role, sim in simulations.items()}
        common_start = max(report['hold']['startedNs'] for report in reports.values())
        common_end = min(report['hold']['finishedNs'] for report in reports.values())
        self.assertEqual(common_end - common_start, 20 * 10**9)
        self.assertEqual(sum(report['hold']['payloadMiB'] for report in reports.values()), 32896)
        self.assertEqual([len(next(event for event in sim.events if event.get('event') ==
            'mixed-hold-start')['childPids']) for sim in simulations.values()], [1, 2, 2])
        values = reports['peer5']['peerProgress']
        for role in ('workspace10', 'workspace20'):
            self.assertLess(values[0]['observedNs'], reports[role]['ordinaryStartedNs'])
            self.assertGreater(values[-1]['observedNs'], reports[role]['ordinaryFinishedNs'])
            self.assertTrue(any(reports[role]['ordinaryStartedNs'] <= value['observedNs'] <=
                                reports[role]['ordinaryFinishedNs'] for value in values) or
                            reports[role]['ordinaryFinishedNs'] - reports[role]['ordinaryStartedNs'] < 500_000_000)

    def test_failure_cleanup_cannot_pass_oom_or_write_faults(self):
        faults = {
            'wrong-cuda-error': {'b-denied': lambda value: value.update(cudaResult=999)},
            'wrong-success': {'b-denied': lambda value: value.update(cudaResult=0)},
            'first-alloc-failed': {'a-hold': lambda value: value.update(cudaResult=2)},
            'quota-recovery-failed': {'b-after-free': lambda value: value.update(cudaResult=2)},
            'peer-write-failed': {'a-continued': RuntimeError('CUDA writer failed')},
            'worker-timeout': {'b-denied': TimeoutError('Child wait')},
            'child-crash': {'b-denied': RuntimeError('Child exited -9')},
            'hold-write-failed': {'hold-20-0': RuntimeError('Hold CUDA error')},
            'peer-heartbeat-failed': {'peer-alive-4': RuntimeError('Peer stopped')},
            'missing-write': {'a-hold': lambda value: value.pop('writeBytes')},
            'identity-drift': {'b-denied': lambda value: value.update(pid=999)},
            'cache-drift': {'a-continued': lambda value: value['cache'].update(inode=999)},
            'cleanup-failed': {'close': True},
        }
        for name, fault in faults.items():
            with self.subTest(fault=name):
                sim = Simulation('peer5', fault)
                self.assertEqual(sim.run(), 1)
                self.assertEqual(sim.report['status'], 'mixed-role-incomplete')
                self.assertTrue(all(worker.closed for worker in sim.children))
                self.assertIs(sim.report['productionQualified'], False)

    def test_ready_identity_cache_and_quota_tampering_refused(self):
        changes = [lambda value: value.update(pid=True), lambda value: value.update(gpu='a' * 32),
            lambda value: value['cache'].update(uid=10001),
            lambda value: value['cache'].update(mappingVerified=False),
            lambda value: value['cache'].update(noTmpFallback=False),
            lambda value: value['hami'].update(effectiveLimitBytes=40 * 1024**3),
            lambda value: value['hami'].update(loaded=False),
            lambda value: value['compiler'].update(moduleSha256='0' * 64)]
        for change in changes:
            with self.subTest(change=change):
                sim = Simulation('workspace10', {'ready': lambda value, index: change(value) if index == 1 else None})
                self.assertEqual(sim.run(), 1)
                self.assertIsNone(sim.report['hold'])
                self.assertTrue(all(worker.closed for worker in sim.children))

    def test_private_cache_cannot_be_per_child(self):
        sim = Simulation('workspace20', {'ready': lambda value, index: value['cache'].update(inode=444 + index)})
        self.assertEqual(sim.run(), 1)
        self.assertIsNone(sim.report['hold'])

    def test_missing_fresh_approval_never_creates_children(self):
        sim = Simulation('peer5')
        def refused(role):
            raise ValueError('Missing or stale CPU gate approval')
        self.assertEqual(probe.run_role('peer5', child_factory=sim.factory, clock=sim.clock,
                                       prepare=refused, output=sim.events.append), 1)
        self.assertEqual(sim.children, [])

    def test_late_hold_and_short_window_refused(self):
        sim = Simulation('workspace10')
        original = sim.prepare
        def short(role):
            proof, approval, compiler = original(role)
            approval['mps']['windowEndsAtNs'] = NOW_NS + 80 * 10**9
            return proof, approval, compiler
        sim.prepare = short
        self.assertEqual(sim.run(), 1)
        self.assertEqual(sim.children, [])
        sim = Simulation('workspace10')
        sim.clock.ns = NOW_NS + 31 * 10**9
        self.assertEqual(sim.run(), 1)
        self.assertIsNone(sim.report['hold'])

    def test_expired_window_during_hold_cleans_up(self):
        sim = Simulation('workspace20')
        def expire(value):
            sim.clock.ns = NOW_NS + 181 * 10**9
        sim.faults['hold-1-0'] = expire
        self.assertEqual(sim.run(), 1)
        self.assertTrue(all(worker.closed for worker in sim.children))

    def test_ordinary_verdict_rejects_deleted_reordered_forged_receipts(self):
        sim = Simulation('workspace10')
        self.assertEqual(sim.run(), 0)
        record, ready = sim.report['ordinary'], sim.report['children']
        changes = [lambda value: value.pop('bFree'),
            lambda value: value['bDenied'].update(cudaResult=0),
            lambda value: value['bAfterFree'].update(cudaResult=2),
            lambda value: value['aContinued'].update(writeBytes=0),
            lambda value: value['bDenied'].update(operationStartedNs=1),
            lambda value: value['bAfterFree'].update(pid=ready[0]['pid']),
            lambda value: value['aHold'].update(allocationMiB=3072),
            lambda value: value['aHold'].update(writeFinishedNs=10**30),
            lambda value: value['bDenied'].update(writeBytes=1024**2),
            lambda value: value.update(extra={'cudaResult': 0})]
        for change in changes:
            with self.subTest(change=change):
                changed = copy.deepcopy(record)
                change(changed)
                self.assertFalse(probe.ordinary_verdict(changed, ready, 6144))

    def test_import_and_closed_roles_do_not_load_cuda(self):
        saved = {key: getattr(probe.core, key) for key in ('REQUESTED_MIB', 'CANONICAL_LIMIT_MIB',
            'SCHEDULER_INJECTED_MIB', 'ALLOCATION_MIB', 'COMPILER_SOURCE', 'COMPILER_MODULE_SHA256',
            'REVIEWED_IDENTITIES', 'hami_provenance')}
        self.addCleanup(lambda: [setattr(probe.core, key, value) for key, value in saved.items()])
        with patch('ctypes.CDLL', side_effect=AssertionError('Unexpected CUDA load')):
            spec = importlib.util.spec_from_file_location('_inert_mixed_probe', HERE / 'mixed_probe.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with patch.dict(os.environ, {'FIXTURE_ROLE': 'peer5', 'FIXTURE_PROFILE_GIB': '5'}):
                module.configure('peer5')
                with self.assertRaises(RuntimeError):
                    module.configure('workspace10')
            with self.assertRaises(RuntimeError):
                module.configure('mig')

    def test_driver_core_writes_entire_payload_then_small_heartbeat(self):
        driver = FakeDriver()
        def initialize(value):
            value.lib = driver
            value.allocations = {}
            value.context = None
            value.core = driver
        with patch.object(probe.core.Cuda, '__init__', initialize), \
             patch.object(probe.core, 'CANONICAL_LIMIT_MIB', 20480), \
             patch('ctypes.CDLL', side_effect=AssertionError('Unexpected CUDA load')):
            cuda = probe.Cuda()
            value = cuda.allocate('held', 19456)
            self.assertEqual(value['cudaResult'], 0)
            self.assertEqual(value['writeBytes'], 19456 * 1024**2)
            self.assertEqual(driver.writes, [19456 * 1024**2])
            value = cuda.tick('held')
            self.assertEqual(value['writeBytes'], 1024**2)
            self.assertEqual(driver.writes, [19456 * 1024**2, 1024**2])
            cuda.close()
            self.assertEqual(driver.freed, [1234])
            self.assertEqual(cuda.allocations, {})
            self.assertEqual(cuda.sizes, {})

    def test_driver_oom_is_actual_code_and_failed_write_retains_cleanup(self):
        driver = FakeDriver()
        def initialize(value):
            value.lib = driver
            value.allocations = {}
            value.context = None
            value.core = driver
        with patch.object(probe.core.Cuda, '__init__', initialize), \
             patch.object(probe.core, 'CANONICAL_LIMIT_MIB', 20480), \
             patch('ctypes.CDLL', side_effect=AssertionError('Unexpected CUDA load')):
            cuda = probe.Cuda()
            driver.allocation_result = 2
            result = cuda.allocate('oom', 12288)
            self.assertEqual(result['cudaResult'], 2)
            self.assertNotIn('writeBytes', result)
            self.assertEqual(driver.writes, [])
            self.assertEqual(cuda.sizes, {})
            driver.allocation_result = 0
            driver.write_result = 700
            with self.assertRaisesRegex(RuntimeError, 'cuMemsetD8 CUDA error 700'):
                cuda.allocate('bad-write', 12288)
            self.assertIn('bad-write', cuda.allocations)
            cuda.close()
            self.assertEqual(driver.freed, [1234])
            self.assertEqual(cuda.allocations, {})


class FakeDriver:
    def __init__(self):
        self.writes = []
        self.freed = []
        self.allocation_result = 0
        self.write_result = 0

    def get_current_device_memory_limit(self, index):
        return 20480 * 1024**2

    def cuMemAlloc_v2(self, pointer, count):
        if self.allocation_result == 0:
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint64)).contents.value = 1234
        return self.allocation_result

    def cuMemGetInfo_v2(self, free, total):
        ctypes.cast(free, ctypes.POINTER(ctypes.c_size_t)).contents.value = 1024**3
        ctypes.cast(total, ctypes.POINTER(ctypes.c_size_t)).contents.value = 20480 * 1024**2
        return 0

    def cuMemsetD8_v2(self, pointer, byte, count):
        self.writes.append(count)
        return self.write_result

    def cuCtxSynchronize(self):
        return 0

    def cuMemFree_v2(self, pointer):
        self.freed.append(pointer.value)
        return 0


if __name__ == '__main__':
    unittest.main()

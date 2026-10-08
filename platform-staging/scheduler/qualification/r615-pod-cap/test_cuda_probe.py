import importlib
import ctypes
import subprocess
import sys
import unittest
from unittest.mock import patch


class Worker:
    def __init__(self, budget, *, private=False):
        self.budget = budget if not private else dict(budget)
        self.held = 0
    def request(self, operation, **value):
        if operation == 'allocate':
            amount = value['mib']
            if not value.get('managed') and self.budget['used'] + amount > self.budget['cap']:
                return {'cuda_result': 2, 'touch_result': None, 'prefetch_result': None}
            self.held = amount; self.budget['used'] += amount
            return {'cuda_result': 0, 'touch_result': 0, 'prefetch_result': 0 if value.get('managed') else None}
        if operation == 'free':
            self.budget['used'] -= self.held; self.held = 0
        return {'cuda_result': 0}


class CudaProbeTests(unittest.TestCase):
    def setUp(self):
        try: self.probe = importlib.import_module('cuda_probe')
        except ModuleNotFoundError: self.fail('The bounded CUDA probe is not implemented')

    def test_shared_two_context_budget_denies_second_and_recovers_after_free(self):
        budget = {'cap': 64, 'used': 0}
        result = self.probe.ordinary(Worker(budget), Worker(budget), 64)
        self.assertTrue(result['standard_allocations_bounded'])
        self.assertEqual(result['allocation_mib_each'], 38)
        self.assertEqual(result['b_denied']['cuda_result'], 2)
        self.assertEqual(budget['used'], 0)
        self.assertFalse(result['hostile_isolation_qualified'])

    def test_separate_per_context_caps_do_not_pass_aggregate_verdict(self):
        budget = {'cap': 64, 'used': 0}
        result = self.probe.ordinary(Worker(budget, private=True), Worker(budget, private=True), 64)
        self.assertFalse(result['standard_allocations_bounded'])
        self.assertEqual(result['b_denied']['cuda_result'], 0)

    def test_managed_success_above_cap_is_reported_without_qualification(self):
        budget = {'cap': 128, 'used': 0}
        result = self.probe.managed(Worker(budget), 128)
        self.assertEqual(result['managed_mib'], 144)
        self.assertTrue(result['managed_prefetch_above_cap_succeeded'])
        self.assertFalse(result['managed_memory_qualified'])
        self.assertEqual(budget['used'], 0)

    def test_probe_allocation_plan_stays_small_and_rejects_arbitrary_caps(self):
        for cap in (0, True, 5120, 129):
            with self.assertRaises(ValueError): self.probe.plan(cap)
        self.assertEqual(self.probe.plan(64), {'cap_mib': 64, 'allocation_mib_each': 38, 'managed_mib': 80})

    def test_failed_driver_free_retains_exact_pointer_for_cleanup_retry(self):
        driver = self.probe.Cuda.__new__(self.probe.Cuda)
        driver.pointer = ctypes.c_ulonglong(1234)
        class Lib:
            result = 1
            def cuMemFree_v2(self, pointer): return self.result
        driver.lib = Lib(); driver.info = lambda: {}
        self.assertEqual(driver.free()['cuda_result'], 1)
        self.assertEqual(driver.pointer.value, 1234)
        driver.lib.result = 0
        self.assertEqual(driver.free()['cuda_result'], 0)
        self.assertIsNone(driver.pointer)

    def test_failed_context_start_does_not_leave_an_untracked_worker(self):
        process = subprocess.Popen([sys.executable, '-c', 'print(\'{"error_type":"fixture"}\',flush=True);input()'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        with patch('cuda_probe.subprocess.Popen', return_value=process):
            with self.assertRaises(ValueError): self.probe.Child('GPU-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        self.assertIsNotNone(process.poll())

    def test_managed_phase_captures_parent_and_device_state_while_allocation_is_held(self):
        budget = {'cap': 64, 'used': 0}
        def observe(): return {'parent_memory_current': 1000 + budget['used'], 'nvml_limits': {'hard': 67108864}}
        result = self.probe.managed(Worker(budget), 64, observe=observe)
        self.assertEqual(result['before']['parent_memory_current'], 1000)
        self.assertEqual(result['after_gpu_touch']['parent_memory_current'], 1080)
        self.assertEqual(result['after_gpu_touch']['nvml_limits']['hard'], 67108864)
        self.assertEqual(budget['used'], 0)

    def test_fixed512_managed_uses_positive_baseline_and_holds_before_free(self):
        budget = {'cap':512,'used':0}; worker=Worker(budget); held=[]
        def observe(): return {'parent_memory_current':1000,'nvml_limits':{'soft':512*1048576,'hard':512*1048576,'used':8*1048576}}
        result=self.probe.managed(worker,512,observe=observe,hold=lambda:held.append(worker.held))
        self.assertEqual(result['managed_mib'],512)
        self.assertEqual(held,[512]);self.assertEqual(budget['used'],0)
        self.assertTrue(result['baseline_plus_managed_exceeds_cap'])
        self.assertFalse(result['managed_memory_qualified'])

    def test_fixed512_requires_baseline_proof_and_cannot_run_ordinary_aggregate(self):
        worker=Worker({'cap':512,'used':0})
        for before in (None,{'nvml_limits':{'used':0,'hard':512*1048576}}, {'nvml_limits':{'used':1,'hard':1024*1048576}}):
            with self.assertRaises(ValueError):self.probe.managed(worker,512,observe=lambda:before)
        with self.assertRaises(ValueError):self.probe.ordinary(worker,worker,512)
        self.assertEqual(self.probe.plan(512)['managed_mib'],512)


if __name__ == '__main__': unittest.main()

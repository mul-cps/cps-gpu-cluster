import unittest
import subprocess
import tempfile
import time
import sys
from pathlib import Path
import runtime_probe as probe


class Driver:
    def __init__(self,managed=801,ordinary=2):self.managed=managed;self.ordinary=ordinary;self.calls=[]
    def allocate(self,mib,managed=False):
        self.calls.append(('allocate',mib,managed))
        code=self.managed if managed else self.ordinary if mib==256 else 0
        return {'cuda_result':code,'touch_result':0 if code==0 else None}
    def free(self):self.calls.append(('free',));return {'cuda_result':0}
    def tick(self):return {'cuda_result':0}


class RuntimeProbeTests(unittest.TestCase):
    def test_bounded_raw_sequence_and_managed_denial(self):
        driver=Driver();result=probe.run_sequence(driver,lambda:{'limits':{'used':436289216,'hard':512*1048576}})
        self.assertTrue(result['raw_sequence_passed'])
        self.assertTrue(result['managed_allocation_denied'])
        self.assertFalse(result['production_qualified'])
        self.assertEqual([call[1] for call in driver.calls if call[0]=='allocate'],[64,256,64,64])
        self.assertEqual(driver.calls[-1],('free',))

    def test_ordinary_cap_bypass_or_managed_success_does_not_pass(self):
        for driver in (Driver(managed=0),Driver(ordinary=0)):
            result=probe.run_sequence(driver,lambda:{'limits':{'used':436289216,'hard':512*1048576}})
            self.assertFalse(result['raw_sequence_passed'])
            self.assertEqual(driver.calls[-1],('free',))

    def test_unproven_cap_margin_denies_before_allocations(self):
        for used in (0,128*1048576,500*1048576):
            driver=Driver()
            with self.assertRaises(ValueError):
                probe.run_sequence(driver,lambda:{'limits':{'used':used,'hard':512*1048576}})
            self.assertEqual(driver.calls,[])

    def test_timeout_stops_the_owned_fork_child_group(self):
        with tempfile.TemporaryDirectory() as directory:
            heartbeat=Path(directory)/'heartbeat'
            code="import os,time,pathlib; child=os.fork(); p=pathlib.Path(__import__('sys').argv[1]);\nif child==0:\n while True: p.write_text(str(time.time_ns())); time.sleep(.01)\nelse: time.sleep(30)"
            with self.assertRaises(subprocess.TimeoutExpired):
                probe.run_bounded([sys.executable,'-c',code,str(heartbeat)],timeout=.3)
            self.assertTrue(heartbeat.exists())
            before=heartbeat.read_text();time.sleep(.05)
            self.assertEqual(heartbeat.read_text(),before)

    def test_failed_attribute_or_module_guard_preconditions_deny(self):
        good={'uvm_deny_managed_mmap':'Y','uvm_disable_hmm':'1','uvm_ats_mode':'0','uvm_enable_builtin_tests':'0'}
        probe.validate_module_parameters(good)
        probe.validate_module_parameters(dict(good,uvm_disable_hmm='Y'))
        for name in good:
            changed=dict(good);changed[name]='1' if good[name]=='0' else '0'
            with self.assertRaises(ValueError):probe.validate_module_parameters(changed)
        probe.validate_attributes({88:0,100:0})
        for values in ({88:1,100:0},{88:0,100:1},{88:0},{}):
            with self.assertRaises(ValueError):probe.validate_attributes(values)


if __name__=='__main__':unittest.main()

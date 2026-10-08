import ctypes
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import guard


class GuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(os.environ.get('CPS_UVM_GUARD_TEST_SOURCE','/tmp/cps-r615-uvm-guard-primary'))
        cls.original=(root/'uvm_va_range.c').read_bytes();caller=(root/'uvm.c').read_bytes();status=(root/'nvstatuscodes.h').read_bytes()
        guard.verify(cls.original,guard.SOURCE_SHA256);guard.verify(caller,guard.CALLER_SHA256);guard.verify(status,guard.STATUS_SHA256)
        cls.modified=guard.patched(cls.original)
        cls.status={name:int(code,16) for name,code in re.findall(r'NV_STATUS_CODE\((\w+),\s*(0x[0-9A-Fa-f]+)',status.decode())}
        names=('NV_OK','NV_ERR_UVM_ADDRESS_IN_USE','NV_ERR_NOT_SUPPORTED','NV_ERR_NO_MEMORY','NV_ERR_INVALID_ADDRESS')
        definitions='\n'.join('#define '+name+' '+str(cls.status[name])+'u' for name in names)
        function=guard.definition(cls.modified.decode(),'NV_STATUS uvm_va_range_create_mmap(')
        block=guard.definition(caller.decode(),'if (status == NV_ERR_UVM_ADDRESS_IN_USE)')
        harness=(Path(__file__).parent/'cpu_harness.c').read_text().replace('// STATUS_DEFINITIONS',definitions)
        harness=harness.replace('// PARAMETER_DEFINITION',guard.PARAMETER).replace('// ORIGINAL_PATCHED_FUNCTION',function).replace('// ORIGINAL_CALLER_COLLISION_BLOCK',block)
        cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup)
        source=Path(cls.tmp.name)/'harness.c';source.write_text(harness);binary=Path(cls.tmp.name)/'harness.so'
        subprocess.run(['cc','-std=c11','-shared','-fPIC','-Wall','-Wextra','-Werror','-O0',str(source),'-o',str(binary)],check=True,capture_output=True)
        cls.lib=ctypes.CDLL(str(binary));cls.lib.run_case.argtypes=[ctypes.c_int]*5;cls.lib.run_case.restype=ctypes.c_uint
        cls.lib.checked_bound.restype=ctypes.c_ulonglong

    def case(self,enabled,collision=0,reclaim=0,alloc=0,add=0):
        return self.lib.run_case(enabled,collision,reclaim,alloc,add)

    def test_pinned_source_change_and_second_application_deny(self):
        for raw in (self.original+b'\n',self.original.replace(b'vm_end - 1',b'vm_end - 2',1),self.modified):
            with self.assertRaises(ValueError):guard.patched(raw)

    def test_load_time_flag_is_default_off_readonly_and_guard_precedes_reclaim(self):
        text=self.modified.decode();self.assertIn('static bool uvm_deny_managed_mmap = false;',text)
        self.assertIn('module_param(uvm_deny_managed_mmap, bool, 0444);',text)
        body=guard.definition(text,'NV_STATUS uvm_va_range_create_mmap(')
        self.assertLess(body.index('if (uvm_deny_managed_mmap)'),body.index('uvm_hmm_va_block_reclaim'))
        self.assertEqual(text.replace(guard.PARAMETER,'',1).replace(guard.GUARD,'',1).encode(),self.original)

    def test_disabled_guard_preserves_success_and_original_failure_paths(self):
        self.assertEqual(self.case(0),self.status['NV_OK'])
        self.assertEqual([self.lib.counter(i) for i in range(3)],[1,1,1])
        self.assertEqual(self.case(0,reclaim=self.status['NV_ERR_INVALID_ADDRESS']),self.status['NV_ERR_INVALID_ADDRESS'])
        self.assertEqual(self.lib.counter(1),0)
        self.assertEqual(self.case(0,alloc=1),self.status['NV_ERR_NO_MEMORY'])
        self.assertEqual(self.case(0,add=self.status['NV_ERR_NO_MEMORY']),self.status['NV_ERR_NO_MEMORY'])
        self.assertEqual(self.lib.counter(3),1)

    def test_enabled_new_range_denies_before_reclaim_or_allocation(self):
        self.assertEqual(self.case(1),self.status['NV_ERR_NOT_SUPPORTED'])
        self.assertEqual([self.lib.counter(i) for i in range(5)],[0,0,0,0,0])
        self.assertEqual(self.lib.checked_bound(0),4096);self.assertEqual(self.lib.checked_bound(1),8191)
        self.assertEqual(self.case(1,collision=5),self.status['NV_ERR_NOT_SUPPORTED'])

    def test_actual_caller_preserves_exact_semaphore_and_p2p_fallback_only(self):
        for collision in (1,2):
            for enabled in (0,1):
                with self.subTest(collision=collision,enabled=enabled):
                    self.assertEqual(self.case(enabled,collision),self.status['NV_OK'])
                    self.assertEqual(self.lib.counter(4),collision)
                    if enabled:self.assertEqual([self.lib.counter(i) for i in range(4)],[0,0,0,0])
        for collision in (3,4,6):
            with self.subTest(collision=collision):
                self.assertEqual(self.case(1,collision),self.status['NV_ERR_UVM_ADDRESS_IN_USE'])
                self.assertEqual(self.lib.counter(4),0)


if __name__=='__main__':unittest.main()

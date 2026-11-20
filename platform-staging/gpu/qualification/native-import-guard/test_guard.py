"""CPU-only source contract and helper control-flow tests; not driver qualification."""
import hashlib, importlib.util, os, pathlib, subprocess, tempfile, unittest
HERE=pathlib.Path(__file__).parent
class GuardTest(unittest.TestCase):
 def test_helper_control_flow(self):
  self.assertTrue((HERE/'guard.c').exists(), 'Implementation absent')
  with tempfile.TemporaryDirectory() as tmp:
   binary=pathlib.Path(tmp)/'guard-test'
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(HERE),str(HERE/'helper_test.c'),'-o',str(binary)],check=True,timeout=30)
   subprocess.run([str(binary)],check=True,timeout=10)
 def test_parameter_control_flow(self):
  with tempfile.TemporaryDirectory() as tmp:
   binary=pathlib.Path(tmp)/'parameter-test'
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(HERE),str(HERE/'parameter_test.c'),'-o',str(binary)],check=True,timeout=30)
   subprocess.run([str(binary)],check=True,timeout=10)
 def test_limit_lifetime_control_flow(self):
  self.assertTrue((HERE/'limits_lifetime.c').exists(), 'Lifetime pin implementation absent')
  with tempfile.TemporaryDirectory() as tmp:
   binary=pathlib.Path(tmp)/'lifetime-test'
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(HERE),str(HERE/'lifetime_test.c'),'-o',str(binary)],check=True,timeout=30)
   subprocess.run([str(binary)],check=True,timeout=10)
 def test_allocator_control_flow(self):
  with tempfile.TemporaryDirectory() as tmp:
   binary=pathlib.Path(tmp)/'allocation-test'
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(HERE),str(HERE/'allocation_test.c'),'-o',str(binary)],check=True,timeout=30)
   subprocess.run([str(binary)],check=True,timeout=10)
 def test_session_marker_control_flow(self):
  with tempfile.TemporaryDirectory() as tmp:
   binary=pathlib.Path(tmp)/'session-test'
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(HERE),str(HERE/'session_test.c'),'-o',str(binary)],check=True,timeout=30)
   subprocess.run([str(binary)],check=True,timeout=10)
 def test_export_marker_control_flow(self):
  with tempfile.TemporaryDirectory() as tmp:
   binary=pathlib.Path(tmp)/'export-marker-test'
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(HERE),str(HERE/'export_client_test.c'),'-o',str(binary)],check=True,timeout=30)
   subprocess.run([str(binary)],check=True,timeout=10)
 def test_denial_logger_control_flow(self):
  with tempfile.TemporaryDirectory() as tmp:
   binary=pathlib.Path(tmp)/'diagnostic-test'
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(HERE),str(HERE/'diagnostic_test.c'),'-o',str(binary)],check=True,timeout=30)
   subprocess.run([str(binary)],check=True,timeout=10)
 def test_inert_generator(self):
  result=subprocess.run(['python3',str(HERE/'render_patch.py')],capture_output=True,text=True,check=True,timeout=10)
  self.assertIn('"state": "inert"',result.stdout)
 def test_pinned_patch(self):
  source=os.environ.get('CPS_R615_SOURCE')
  if not source:self.skipTest('Set CPS_R615_SOURCE to verified pristine NVIDIA615.71.09 source')
  spec=importlib.util.spec_from_file_location('guard_render',HERE/'render_patch.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  original,changed=module.render(pathlib.Path(source))
  self.assertEqual(len(changed),12)
  self.assertIn('bCpsObjExportClient = NV_FALSE',changed['src/nvidia/src/kernel/rmapi/client.c'])
  self.assertEqual(changed['src/nvidia/arch/nvalloc/unix/src/rmobjexportimport.c'].count('bCpsObjExportClient = NV_TRUE'),1)
  self.assertIn('bCpsGpuOpsSession = NV_FALSE',changed['src/nvidia/src/kernel/rmapi/client.c'])
  self.assertEqual(changed['src/nvidia/src/kernel/rmapi/nv_gpu_ops.c'].count('bCpsGpuOpsSession = NV_TRUE'),1)
  self.assertIn('get_task_struct(task)',changed['kernel-open/nvidia/os-interface.c'])
  self.assertIn('os_cps_cgroup_get_from_pid_info(pidInfo, OS_CGROUP_IMPL_MISC)',changed['src/nvidia/arch/nvalloc/unix/src/os.c'])
  self.assertIn('return memacctTryChargeProtected',changed['src/nvidia/src/kernel/mem_mgr/memacct.c'])
  self.assertIn('NV_CONFTEST_TYPE_COMPILE_TESTS += memory_device_coherent_present',changed['kernel-open/nvidia/nvidia.Kbuild'])
  self.assertIn('memacctValidateMemoryImport',changed['src/nvidia/inc/kernel/mem_mgr/memacct.h'])
  acct=changed['src/nvidia/src/kernel/mem_mgr/memacct.c']
  self.assertLess(acct.index('memacctUnpinLimitGroups(pRegion);'),acct.index('mapClear(&pRegion->clientGroupMap);'))
  insert=acct[acct.index('pLimits = mapInsertNew'):acct.index('pLimits->SoftLimit = softlimit')]
  self.assertLess(insert.index('if (pLimits == NULL)'),insert.index('memacctPinLimitGroup(pLimits, cligrp);'))
  self.assertEqual(acct.count('memacctPinLimitGroup(pLimits, cligrp);'),1)
  copy=changed['src/nvidia/src/kernel/mem_mgr/video_mem.c'];part=copy[copy.index('vidmemCopyConstruct'):copy.index('/*!\n * vidmemConstruct')]
  self.assertLess(part.index('memacctValidateMemoryImport'),part.index('kbusIncreaseStaticBar1Refcount'))
  external=changed['src/nvidia/src/kernel/rmapi/nv_gpu_ops.c'];part=external[external.index('static NV_STATUS dupMemory'):external.index('NV_STATUS nvGpuOpsDupMemory')]
  self.assertLess(part.index('memacctValidateMemoryImport'),part.index('fabricvaspaceGetGpaMemdesc'))
  self.assertIn('ADDR_FBMEM',part)
  parameter=changed['kernel-open/nvidia/os-interface.c']
  self.assertIn('nv_cps_native_import_guard __ro_after_init = 0',parameter)
  self.assertIn('&nv_cps_native_import_guard, 0400',parameter)
  self.assertIn('value > 1',parameter)
  self.assertIn('module_param_cb(NVreg_CpsNativeImportGuard',parameter)
  helper=(HERE/'guard.c').read_text();self.assertLess(helper.index('os_cps_native_import_guard_enabled'),helper.index('g_memacct.impl'))
  for name in ['kernel-open/common/inc/os-interface.h','src/nvidia/arch/nvalloc/unix/include/os-interface.h']:self.assertIn('os_cps_native_import_guard_enabled(void)',changed[name])
  with tempfile.TemporaryDirectory() as tmp:
   target=pathlib.Path(tmp)
   for name,data in original.items():(target/name).parent.mkdir(parents=True,exist_ok=True);(target/name).write_text(data)
   patch=module.patch(original,changed)
   subprocess.run(['git','apply','--check','-'],input=patch,text=True,cwd=target,check=True,timeout=10)
   subprocess.run(['git','apply','-'],input=patch,text=True,cwd=target,check=True,timeout=10)
   for name,data in changed.items():self.assertEqual((target/name).read_text(),data)
   bad=target/'src/nvidia/src/kernel/mem_mgr/memacct.c';bad.write_text(bad.read_text()+'\n')
   with self.assertRaises(ValueError):module.render(target)
if __name__=='__main__':unittest.main()

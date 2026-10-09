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
 def test_inert_generator(self):
  result=subprocess.run(['python3',str(HERE/'render_patch.py')],capture_output=True,text=True,check=True,timeout=10)
  self.assertIn('"state": "inert"',result.stdout)
 def test_pinned_patch(self):
  source=os.environ.get('CPS_R615_SOURCE')
  if not source:self.skipTest('Set CPS_R615_SOURCE to verified pristine NVIDIA615.71.09 source')
  spec=importlib.util.spec_from_file_location('guard_render',HERE/'render_patch.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  original,changed=module.render(pathlib.Path(source))
  self.assertEqual(len(changed),4)
  self.assertIn('memacctValidateMemoryImport',changed['src/nvidia/inc/kernel/mem_mgr/memacct.h'])
  copy=changed['src/nvidia/src/kernel/mem_mgr/video_mem.c'];part=copy[copy.index('vidmemCopyConstruct'):copy.index('/*!\n * vidmemConstruct')]
  self.assertLess(part.index('memacctValidateMemoryImport'),part.index('kbusIncreaseStaticBar1Refcount'))
  external=changed['src/nvidia/src/kernel/rmapi/nv_gpu_ops.c'];part=external[external.index('static NV_STATUS dupMemory'):external.index('NV_STATUS nvGpuOpsDupMemory')]
  self.assertLess(part.index('memacctValidateMemoryImport'),part.index('fabricvaspaceGetGpaMemdesc'))
  self.assertIn('ADDR_FBMEM',part)
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

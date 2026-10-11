"""CPU-only ABI, inert execution and real local IPC transport regression checks."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
HEADER=Path(os.environ.get('CPS_CUDA_HEADER_DIR','/usr/local/cuda/include'))
class ProbeTests(unittest.TestCase):
 def test_source_exists_before_compilation(self):
  self.assertTrue((HERE/'native_imports.c').is_file(),'Native qualification implementation is missing')
 @unittest.skipUnless((HEADER/'cuda.h').exists(),'Set CPS_CUDA_HEADER_DIR to the pinned official CUDA13.4.92 headers')
 def test_compile_inert_and_reject_bad_arguments_before_driver(self):
  self.assertTrue((HERE/'compile_probe.py').exists(),'Pinned CPU compiler helper is missing')
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'probe'
   p=subprocess.run([sys.executable,str(HERE/'compile_probe.py'),'--headers',str(HEADER),'--output',str(out),'--compile'],capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stdout+p.stderr)
   r=subprocess.run([str(out)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   self.assertEqual(json.loads(r.stdout)['state'],'inert');self.assertFalse(json.loads(r.stdout)['gpu_calls'])
   for args in (['--cap-mib','8192'],['--mode','ipc-export','--execute'],['--mode','vmm-direct','--execute','--gpu-uuid','bad']):
    r=subprocess.run([str(out),*args],capture_output=True,text=True);self.assertNotEqual(r.returncode,0);self.assertNotIn('"kind":"cuda"',r.stdout)
 @unittest.skipUnless((HEADER/'cuda.h').exists(),'Set CPS_CUDA_HEADER_DIR to the pinned official CUDA13.4.92 headers')
 def test_real_transport_rejects_missing_fd_and_preserves_scm_rights(self):
  self.assertTrue((HERE/'transport_test.c').exists(),'Local transport regression fixture is missing')
  with tempfile.TemporaryDirectory() as d:
   binary=Path(d)/'transport'
   p=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(HEADER),str(HERE/'transport_test.c'),'-ldl','-o',str(binary)],capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr)
   p=subprocess.run([str(binary)],capture_output=True,text=True,timeout=5)
   self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 @unittest.skipUnless((HEADER/'cuda.h').exists(),'Set CPS_CUDA_HEADER_DIR to the pinned official CUDA13.4.92 headers')
 def test_cleanup_and_over_cap_control_flow_with_cpu_driver_fixture(self):
  self.assertTrue((HERE/'api_test.c').exists(),'CPU cleanup/over-cap driver fixture is missing')
  with tempfile.TemporaryDirectory() as d:
   binary=Path(d)/'api'
   p=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(HEADER),str(HERE/'api_test.c'),'-ldl','-o',str(binary)],capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr)
   p=subprocess.run([str(binary)],capture_output=True,text=True,timeout=5)
   self.assertEqual(p.returncode,0,p.stdout+p.stderr)
if __name__=='__main__':unittest.main()

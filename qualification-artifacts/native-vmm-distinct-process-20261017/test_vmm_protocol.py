import array,copy,ctypes as C,importlib.util,os,socket,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import vmm_endpoint as e
class ProtocolTests(unittest.TestCase):
 def test_layout_and_strict_typed_denial(self):
  self.assertEqual(C.sizeof(e.AllocationProp),32);self.assertEqual(C.sizeof(e.AccessDesc),12)
  result={'api':'cuMemImportFromShareableHandle','expect':'deny','cuda_result':800,'cuda_name':'CUDA_ERROR_NOT_PERMITTED'}
  e.require_import_result(result)
  for key,val in [('cuda_result',0),('cuda_result',2),('cuda_result',801),('cuda_result',True),('cuda_name','CUDA_ERROR_OUT_OF_MEMORY'),('api','cuIpcOpenMemHandle_v2')]:
   bad={**result,key:val}
   with self.subTest(key=key,val=val),self.assertRaises(ValueError):e.require_import_result(bad)
 def test_one_real_fd_and_close_on_excess(self):
  a,b=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
  with a,b,tempfile.TemporaryFile() as f:
   e.send_frame(a,{'phase':'fd'},f.fileno());value,fd=e.receive_frame(b,want_fd=True)
   try:self.assertEqual(value,{'phase':'fd'});self.assertEqual(os.fstat(fd).st_ino,os.fstat(f.fileno()).st_ino)
   finally:os.close(fd)
   a.sendmsg([b'{}'],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[f.fileno(),f.fileno()]))])
   with self.assertRaises(ValueError):e.receive_frame(b,want_fd=True)
 def test_unexpected_rights_close_even_unknown_control(self):
  fake=Mock();fake.recvmsg.return_value=(b'{}',[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[33]).tobytes()),(999,888,b'x')],0,None)
  with patch.object(e.os,'close') as close:
   with self.assertRaises(ValueError):e.receive_frame(fake,want_fd=True)
   close.assert_called_once_with(33)
 def test_duplicate_truncated_and_nonfinite_frames_fail(self):
  for raw in [b'{"x":1,"x":2}',b'{"x":NaN}',b'[]']:
   with self.subTest(raw=raw),self.assertRaises(ValueError):e.parse(raw)
  fake=Mock();fake.recvmsg.return_value=(b'{}',[],socket.MSG_TRUNC,None)
  with self.assertRaises(ValueError):e.receive_frame(fake)
 def test_sequence_preserves_actual_call_then_cleanup(self):
  cuda=Mock();cuda.import_window=(1,2);cuda.try_import.return_value=(800,'CUDA_ERROR_NOT_PERMITTED');cuda.tick.return_value={'vector_verified':True,'vector_elements':256,'cuda_result':0}
  values=[];commands=[]
  e.import_attempt(cuda,12,'deny',mark=lambda phase,**kw:values.append((phase,kw)),wait=lambda op:commands.append(op))
  self.assertEqual(commands,['open','finish']);self.assertEqual([p for p,_ in values],['importer-before-kernel','import-result','importer-after-kernel'])
  self.assertEqual(values[1][1]['cuda_result'],800);cuda.map.assert_not_called()
 def test_unexpected_success_never_maps_and_is_not_denial(self):
  cuda=Mock();cuda.import_window=(1,2);cuda.tick.return_value={'vector_verified':True,'vector_elements':256,'cuda_result':0};cuda.try_import.return_value=(0,'CUDA_SUCCESS');events=[]
  with self.assertRaises(ValueError):e.import_attempt(cuda,12,'deny',mark=lambda p,**k:events.append((p,k)),wait=lambda op:None)
  self.assertEqual(events[1][1]['cuda_result'],0);cuda.map.assert_not_called()
 def test_positive_control_maps_reads_and_restores_backing(self):
  cuda=Mock();cuda.import_window=(1,2);cuda.tick.return_value={'vector_verified':True,'vector_elements':256,'cuda_result':0};cuda.try_import.return_value=(0,'CUDA_SUCCESS')
  e.import_attempt(cuda,12,'allow',mark=lambda p,**k:None,wait=lambda op:None)
  cuda.map.assert_called_once();cuda.readback19.assert_called_once();cuda.restore19.assert_called_once()
 def test_peer_is_exact_real_root_credential(self):
  fake=Mock();fake.getsockopt.return_value=array.array('i',[0,0,0]).tobytes();e.require_root_peer(fake)
  for values in [[5,1000,100],[0,0,100],[0,1000,0],[-1,0,0]]:
   fake.getsockopt.return_value=array.array('i',values).tobytes()
   with self.subTest(values=values),self.assertRaises(ValueError):e.require_root_peer(fake)
 def test_default_is_inert_and_never_cuda(self):
  with patch.object(e,'VmmCuda',side_effect=AssertionError('CUDA called')),patch('builtins.print') as out:e.main([])
  self.assertIn('inert',out.call_args.args[0])
if __name__=='__main__':unittest.main()

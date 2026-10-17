import ast, contextlib, hashlib, io, json, subprocess, sys, unittest, time
from pathlib import Path
from unittest.mock import patch
import kernel_transport as transport

class Socket:
 def __init__(self, events): self.events=events; self.sent=[]
 def send(self,value): self.sent.append(json.loads(value))
 def recv(self,timeout):
  if not self.events: raise TimeoutError()
  value=self.events.pop(0)
  value.setdefault('parent_header',{'msg_id':self.sent[0]['header']['msg_id']})
  return json.dumps(value)
def message(kind,**content): return {'msg_type':kind,'content':content,'channel':'shell' if kind=='execute_reply' else 'iopub'}
class Tests(unittest.TestCase):
 def code(self,source):return transport.probe_code(source,hashlib.sha256(source.encode()).hexdigest(),'peer',5)
 def test_invalid_before_launch(self):
  with patch('subprocess.Popen',side_effect=AssertionError('no subprocess')):
   for args in [('x','0'*64,'peer',5),('x',hashlib.sha256(b'x').hexdigest(),'bad',5),('x',hashlib.sha256(b'x').hexdigest(),'peer',True)]:
    with self.assertRaises(ValueError):transport.probe_code(*args)
 def test_local_child(self):
  result=subprocess.run([sys.executable,'-I','-u','-c',self.code('print(\'{"phase":"ok"}\',flush=True)')],capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout),{'phase':'ok'})
 def test_stderr_sanitized(self):
  result=subprocess.run([sys.executable,'-I','-u','-c',self.code('raise RuntimeError("SECRET")')],capture_output=True,text=True,timeout=10)
  self.assertNotEqual(result.returncode,0);self.assertNotIn('SECRET',result.stderr)
 def test_exchange_correlation_split(self):
  events=[{'parent_header':{'msg_id':'foreign'},'msg_type':'stream','content':{'text':'bad'}},message('stream',text='{"phase":'),message('stream',text='"ok"}\n'),message('status',execution_state='idle'),message('execute_reply',status='ok')]
  socket=Socket(events);out=[];transport.exchange(socket,'code','session',out.append,timeout=1)
  self.assertEqual(out,[{'phase':'ok'}]);self.assertEqual(len(socket.sent),1)
 def test_wrong_channel_not_completion(self):
  wrong=message('execute_reply',status='ok');wrong['channel']='iopub'
  socket=Socket([wrong,message('status',execution_state='idle')])
  with self.assertRaises(TimeoutError):transport.exchange(socket,'code','s',lambda x:None,timeout=.01)
 def test_stream_requires_iopub(self):
  events=[]
  for channel in ('shell',None):
   wrong=message('stream',text='{"wrong":true}\n')
   if channel is None:wrong.pop('channel')
   else:wrong['channel']=channel
   events.append(wrong)
  events.extend([message('stream',text='{"right":true}\n'),message('execute_reply',status='ok'),message('status',execution_state='idle')])
  seen=[];transport.exchange(Socket(events),'c','s',seen.append,timeout=1)
  self.assertEqual(seen,[{'right':True}])
 def test_cases_match_unchanged_probe(self):
  tree=ast.parse(Path(__file__).with_name('peer_probe.py').read_text())
  choices=next(ast.literal_eval(k.value) for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='add_argument' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='--case' for k in n.keywords if k.arg=='choices')
  for case in choices:
   transport.probe_code('',hashlib.sha256(b'').hexdigest(),case,5)
  self.assertEqual(choices,('peer','oom','aggregate-peer','aggregate-oom'))
 def test_runtime_hash_checked_before_child(self):
  code=self.code("print('SECRET')").replace("_source = ","_source = '#changed' + ",1)
  result=subprocess.run([sys.executable,'-I','-u','-c',code],capture_output=True,text=True,timeout=5)
  self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,'')
 def test_child_exit_does_not_exit_kernel(self):
  code=self.code('import os; os._exit(124)')
  result=subprocess.run([sys.executable,'-I','-u','-c',code],capture_output=True,text=True,timeout=5)
  self.assertEqual(result.returncode,1);self.assertIn('Probe child failed',result.stderr)
 def test_reply_error(self):
  socket=Socket([message('execute_reply',status='error',traceback=['SECRET']),message('status',execution_state='idle')])
  with self.assertRaisesRegex(RuntimeError,'Kernel execution failed'):transport.exchange(socket,'code','s',lambda x:None,timeout=.01)
  self.assertEqual(len(socket.sent),1)
 def test_missing_idle_timeout(self):
  socket=Socket([message('execute_reply',status='ok')])
  with self.assertRaises(TimeoutError):transport.exchange(socket,'code','s',lambda x:None,timeout=.01)
  self.assertEqual(len(socket.sent),1)
 def test_output_bound(self):
  socket=Socket([message('stream',text='x'*65537)])
  with self.assertRaises(ValueError):transport.exchange(socket,'code','s',lambda x:None,timeout=1)
 def test_stdout_realtime(self):
  code=self.code("import time; print('{\"phase\":\"first\"}',flush=True); time.sleep(1); print('{\"phase\":\"last\"}',flush=True)")
  child=subprocess.Popen([sys.executable,'-I','-u','-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   self.assertEqual(json.loads(child.stdout.readline()),{'phase':'first'})
   self.assertIsNone(child.poll())
   out,err=child.communicate(timeout=5);self.assertEqual(child.returncode,0,err)
   self.assertEqual(json.loads(out),{'phase':'last'})
  finally:
   if child.poll() is None:child.kill();child.wait()
   child.stdout.close();child.stderr.close()
 def test_failure_and_timeout_reap_only_child_kernel_stays_usable(self):
  real_popen=subprocess.Popen
  unrelated=real_popen([sys.executable,'-I','-c','import time; time.sleep(60)'])
  try:
   for source,error in [('import time; time.sleep(60)',TimeoutError),("import time; print('x'*65537,flush=True); time.sleep(60)",ValueError)]:
    children=[];kills=[]
    def launch(*args,**kwargs):
     child=real_popen(*args,**kwargs);children.append(child)
     original_kill=child.kill
     def kill():kills.append(child.pid);return original_kill()
     child.kill=kill
     return child
    namespace={}
    with patch('subprocess.Popen',side_effect=launch),contextlib.redirect_stdout(io.StringIO()):
     with self.assertRaises(error):exec(self.code(source),namespace)
    exec('still_usable = 6 * 7',namespace)
    self.assertEqual(namespace['still_usable'],42)
    self.assertEqual(len(children),1);child=children[0]
    self.assertEqual(kills,[child.pid]);self.assertIsNotNone(child.returncode)
    with self.assertRaises(ChildProcessError):__import__('os').waitpid(child.pid,__import__('os').WNOHANG)
    self.assertTrue(child.stdout.closed);self.assertTrue(child.stderr.closed)
    self.assertIsNone(unrelated.poll())
  finally:
   unrelated.kill();unrelated.wait(timeout=5)
 def test_stderr_bound(self):
  result=subprocess.run([sys.executable,'-I','-u','-c',self.code("import sys; sys.stderr.write('SECRET'*12000)")],capture_output=True,text=True,timeout=10)
  self.assertNotEqual(result.returncode,0);self.assertNotIn('SECRET',result.stderr)
 def test_total_output_bound(self):
  # Protocol payload itself is bounded, including unrelated messages.
  events=[{'parent_header':{'msg_id':'foreign'},'msg_type':'display_data','content':{'data':'x'*1000000}} for _ in range(9)]
  with self.assertRaisesRegex(ValueError,'output exceeds'):transport.exchange(Socket(events),'c','s',lambda x:None,timeout=1)
 def test_invalid_timeout_no_send(self):
  for value in [0,-1,True,float('nan'),float('inf'),241]:
   socket=Socket([])
   with self.assertRaises(ValueError):transport.exchange(socket,'c','s',lambda x:None,timeout=value)
   self.assertEqual(socket.sent,[])
if __name__=='__main__':unittest.main()

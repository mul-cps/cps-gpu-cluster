"""Compile and execute the exact Source-pod stdin program without network access."""
import json,pathlib,subprocess,sys,unittest
from unittest import mock
import observer as o

class RemoteProgramTests(unittest.TestCase):
 def program(self):
  e={'id':'cps-reservation','required':True,'expectedStatus':200,'expectedJSONSubset':{'active':False,'attempt':None},'authScheme':'Bearer','caFile':'/trust/ca.crt','url':'https://compute-gateway.cps-compute.svc.cluster.local:8000/internal/v1/reservations/owned','transport':'source-pod','podBinding':{'name':'cps-admin-fixed','uid':'uid','containerID':'cid','imageID':'image'}}
  actual={'metadata':{'uid':'uid'},'status':{'containerStatuses':[{'name':'console','containerID':'cid','imageID':'image','ready':True}]}}
  with mock.patch.object(o.subprocess,'check_output',return_value=json.dumps(actual).encode()),mock.patch.object(o.subprocess,'run',return_value=mock.Mock(returncode=0,stdout=json.dumps([{'id':e['id'],'required':True,'ok':True}]).encode()))as run:o.source_probe(e)
  return run.call_args.kwargs['input']
 def test_actual_generated_program_compiles(self):
  code=self.program();compile(code,'actual-remote-stdin','exec')
  self.assertIn(b"source_environment=True",code)
  self.assertNotIn(b"print(json.dumps(run(",code)
 def test_actual_generated_program_executes_with_mock_http_no_network(self):
  code=self.program()
  bootstrap=r'''
import os,sys,json,ssl,socket,urllib.request
os.environ['COMPUTE_POLICY_TOKEN']='owned-dummy-token'
original_context=ssl.create_default_context
ssl.create_default_context=lambda **kw: original_context()
def no_socket(*a,**k):raise AssertionError('Network forbidden in offline test')
socket.socket=no_socket
class Response:
 status=200
 def __enter__(self):return self
 def __exit__(self,*a):return False
 def read(self,bound):return b'{"active":false,"attempt":null}'
class Opener:
 def open(self,request,timeout):
  assert request.get_method()=='GET'
  assert request.get_header('Authorization')=='Bearer owned-dummy-token'
  assert request.full_url=='https://compute-gateway.cps-compute.svc.cluster.local:8000/internal/v1/reservations/owned'
  return Response()
def opener(*handlers):
 assert handlers[0].proxies=={}
 assert handlers[2]._context.check_hostname
 assert handlers[2]._context.verify_mode==ssl.CERT_REQUIRED
 return Opener()
urllib.request.build_opener=opener
exec(compile(sys.stdin.buffer.read(),'actual-remote-stdin','exec'),{'__name__':'remote_probe'})
'''
  r=subprocess.run([sys.executable,'-I','-c',bootstrap],input=code,capture_output=True,timeout=5)
  self.assertEqual(r.returncode,0,r.stderr.decode());body=json.loads(r.stdout)[0]
  self.assertTrue(body['ok']);self.assertEqual(body['category'],'verified-api');self.assertNotIn(b'owned-dummy-token',r.stdout)
if __name__=='__main__':unittest.main()

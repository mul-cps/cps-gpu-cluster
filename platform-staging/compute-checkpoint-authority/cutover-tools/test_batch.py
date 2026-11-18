import copy,json,subprocess,sys,unittest
from unittest import mock
import observer as o
class BatchTests(unittest.TestCase):
 def endpoints(self,source='cps'):
  binding={'source':source,'namespace':'cps-compute','name':source+'-admin-fixed','uid':source+'-uid','containerID':'cid','imageID':'image','container':'console'}
  out=[]
  for key in ['reservation','workspace','profiles','isolation']:
   out.append({'id':source+'-'+key,'required':True,'transport':'source-pod','podBinding':binding,'url':'https://compute-gateway.cps-compute.svc.cluster.local:8000/internal/v1/'+key,'expectedStatus':404 if key=='isolation'else 200,'expectedJSONSubset':{'detail':'Workspace not found'}if key=='isolation'else{'kind':key},'authScheme':'Bearer','caFile':'/trust/ca.crt'})
  return out
 def program(self):
  es=self.endpoints();actual={'metadata':{'uid':'cps-uid'},'status':{'containerStatuses':[{'name':'console','containerID':'cid','imageID':'image','ready':True}]}}
  with mock.patch.object(o.subprocess,'check_output',return_value=json.dumps(actual).encode())as get,mock.patch.object(o.subprocess,'run',return_value=mock.Mock(returncode=0,stdout=json.dumps([{'id':e['id'],'required':True,'ok':True}for e in es]).encode()))as run:
   o.source_probe_batch(es)
  self.assertEqual(get.call_count,1);self.assertEqual(run.call_count,1);self.assertEqual(run.call_args.args[0][-2:],['python','-']);return run.call_args.kwargs['input']
 def test_two_sources_are_two_batches_not_eight(self):
  groups=o.groups(self.endpoints()+self.endpoints('cit'));self.assertEqual(len(groups),2);self.assertEqual([len(g)for g in groups],[4,4])
 def test_inconsistent_same_pod_identity_refused(self):
  es=self.endpoints();es[1]=copy.deepcopy(es[1]);es[1]['podBinding']['containerID']='replacement'
  with self.assertRaises(AssertionError):o.groups(es)
 def test_mixed_source_batch_refused_before_transport(self):
  with mock.patch.object(o.subprocess,'check_output')as get:
   with self.assertRaises(AssertionError):o.source_probe_batch([self.endpoints()[0],self.endpoints('cit')[0]])
  get.assert_not_called()
 def test_generated_four_request_code_one_exec_compiles(self):compile(self.program(),'batch-stdin','exec')
 def test_generated_four_request_code_retains_each_status(self):
  code=self.program();bootstrap=r'''
import os,sys,json,ssl,socket,urllib.request,urllib.error,io
os.environ['COMPUTE_POLICY_TOKEN']='owned-dummy-token'
original_context=ssl.create_default_context
ssl.create_default_context=lambda **kw:original_context()
def no_network(*a,**k):raise AssertionError('No network in offline test')
socket.socket=no_network
calls=[]
class Response:
 status=200
 def __init__(self,body):self.body=body
 def __enter__(self):return self
 def __exit__(self,*a):return False
 def read(self,n):return self.body
class Opener:
 def open(self,request,timeout):
  assert request.get_method()=='GET'
  assert request.get_header('Authorization')=='Bearer owned-dummy-token'
  key=request.full_url.rsplit('/',1)[-1];calls.append(key)
  if key=='isolation':raise urllib.error.HTTPError(request.full_url,404,'not found',{},io.BytesIO(b'{"detail":"Workspace not found"}'))
  # A genuine individual body mismatch must remain visible beside good peers.
  return Response(json.dumps({'kind':'wrong'if key=='profiles'else key}).encode())
def opener(*handlers):
 assert handlers[0].proxies=={}
 assert handlers[2]._context.check_hostname and handlers[2]._context.verify_mode==ssl.CERT_REQUIRED
 return Opener()
urllib.request.build_opener=opener
exec(compile(sys.stdin.buffer.read(),'actual-batch-stdin','exec'),{'__name__':'remote_probe'})
assert calls==['reservation','workspace','profiles','isolation']
'''
  r=subprocess.run([sys.executable,'-I','-c',bootstrap],input=code,capture_output=True,timeout=5);self.assertEqual(r.returncode,0,r.stderr.decode());rows=json.loads(r.stdout)
  self.assertEqual([x['status']for x in rows],[200,200,200,404]);self.assertEqual([x['ok']for x in rows],[True,True,False,True]);self.assertNotIn(b'owned-dummy-token',r.stdout)
if __name__=='__main__':unittest.main()

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
import os,sys,json,ssl,socket,http.client
os.environ['COMPUTE_POLICY_TOKEN']='owned-dummy-token'
original_context=ssl.create_default_context
ssl.create_default_context=lambda **kw:original_context()
def no_network(*a,**k):raise AssertionError('No network in offline test')
socket.socket=no_network
calls=[]
connections=[]
class Response:
 def __init__(self,status,body):self.status=status;self.body=body
 def read(self,n):return self.body
class Connection:
 def __init__(self,host,port,timeout,context):
  assert host=='compute-gateway.cps-compute.svc.cluster.local' and port==8000 and timeout==.6
  assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED
  connections.append(self)
 def request(self,method,path,headers):
  assert method=='GET' and headers['Authorization']=='Bearer owned-dummy-token'
  self.key=path.rsplit('/',1)[-1];calls.append(self.key)
 def getresponse(self):
  if self.key=='isolation':return Response(404,b'{"detail":"Workspace not found"}')
  return Response(200,json.dumps({'kind':'wrong'if self.key=='profiles'else self.key}).encode())
 def close(self):pass
http.client.HTTPSConnection=Connection
exec(compile(sys.stdin.buffer.read(),'actual-batch-stdin','exec'),{'__name__':'remote_probe'})
assert calls==['reservation','workspace','profiles','isolation'] and len(connections)==1
'''
  r=subprocess.run([sys.executable,'-I','-c',bootstrap],input=code,capture_output=True,timeout=5);self.assertEqual(r.returncode,0,r.stderr.decode());rows=json.loads(r.stdout)
  self.assertEqual([x['status']for x in rows],[200,200,200,404]);self.assertEqual([x['ok']for x in rows],[True,True,False,True]);self.assertNotIn(b'owned-dummy-token',r.stdout)
if __name__=='__main__':unittest.main()

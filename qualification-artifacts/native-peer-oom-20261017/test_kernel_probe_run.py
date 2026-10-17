import hashlib,json,os,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import kernel_probe_run as k

UID='11111111-1111-4111-8111-111111111111'
KID='22222222-2222-4222-8222-222222222222'
class Response:
 def __init__(self,value):self.value=value
 def json(self):return self.value
class Socket:
 def __enter__(self):return self
 def __exit__(self,*a):self.closed=True
class Hub:
 def __init__(self,plan,token):self.prefix=k.route(plan);self.calls=[];self.closed=False;self.socket_object=Socket();self.remaining=[];self.actor={'name':'student','kind':'user','admin':False};self.model={'id':KID,'name':'python3'};self.ambiguous=False
 def request(self,method,path,**kwargs):
  self.calls.append((method,path))
  if path=='/hub/api/user':return Response(self.actor)
  if method=='POST':
   if self.ambiguous:raise TimeoutError('uncertain')
   return Response(self.model)
  if method=='DELETE':self.remaining=[];return Response(None)
  return Response(self.remaining)
 def socket(self,*a):return self.socket_object
 def close(self):self.closed=True
class Tests(unittest.TestCase):
 def plan(self,path):return dict(hub_origin=k.ORIGIN,operator='student',owner='shared',server='qa',pod_uid=UID,token_file=str(path))
 def setup_run(self,directory,**kwargs):
  path=Path(directory)/'token';path.write_text('abc123');path.chmod(0o600)
  plan=self.plan(path);hub=Hub(plan,'abc123');source='print("{}")'
  return plan,hub,dict(target={'uid':UID},case='peer',duration=5,source=source.encode(),output=Path(directory),plan=plan,expected_sha=hashlib.sha256(source.encode()).hexdigest(),hub_factory=lambda *a:hub,pod_check=lambda *a:None,**kwargs)
 def test_one_owned_kernel_execution_and_cleanup(self):
  with tempfile.TemporaryDirectory()as d:
   plan,hub,args=self.setup_run(d)
   def exchange(sock,code,session,consume,**kw):consume({'phase':'peer_tick'})
   with patch.object(k,'exchange',side_effect=exchange)as ex:
    run=k.KernelProbeRun(**args);self.assertEqual(run.complete(),[{'phase':'peer_tick'}])
   self.assertEqual(ex.call_count,1);self.assertEqual(sum(m=='POST'for m,p in hub.calls),1)
   self.assertEqual([p for m,p in hub.calls if m=='DELETE'],[hub.prefix+'/api/kernels/'+KID]);self.assertTrue(hub.closed)
   self.assertTrue(json.loads((Path(d)/'peer.kernel.json').read_text())['deleted_own_kernel'])
 def test_unrelated_existing_kernel_preserved(self):
  with tempfile.TemporaryDirectory()as d:
   plan,hub,args=self.setup_run(d);other='33333333-3333-4333-8333-333333333333';hub.remaining=[{'id':other}]
   original=hub.request
   def request(method,path,**kw):
    if method=='DELETE':hub.calls.append((method,path));return Response(None)
    return original(method,path,**kw)
   hub.request=request
   with patch.object(k,'exchange'):k.KernelProbeRun(**args).complete()
   self.assertEqual(hub.remaining,[{'id':other}]);self.assertEqual([p for m,p in hub.calls if m=='DELETE'],[hub.prefix+'/api/kernels/'+KID])
 def test_bad_plans(self):
  with tempfile.TemporaryDirectory()as d:
   plan,hub,args=self.setup_run(d)
   for key,value in [('hub_origin','https://evil.example'),('owner','../other'),('server','x/y'),('pod_uid',str(uuid.uuid4())),('token_file','relative')]:
    altered={**plan,key:value}
    with self.subTest(key=key),self.assertRaises(ValueError):k.validate_plan(altered,{'uid':UID})
 def test_private_token(self):
  with tempfile.TemporaryDirectory()as d:
   path=Path(d)/'token';path.write_text('abc');path.chmod(0o644)
   with self.assertRaises(ValueError):k.read_token(str(path))
   path.chmod(0o600);link=Path(d)/'link';link.symlink_to(path)
   with self.assertRaises(OSError):k.read_token(str(link))
 def test_bad_identity_no_create(self):
  for actor in [{'name':'student','kind':'user','admin':True},{'name':'other','kind':'user','admin':False}]:
   with tempfile.TemporaryDirectory()as d:
    plan,hub,args=self.setup_run(d);hub.actor=actor
    with self.assertRaises(ValueError):k.KernelProbeRun(**args)
    self.assertFalse(any(m=='POST'for m,p in hub.calls));self.assertTrue(hub.closed)
 def test_ambiguous_create_never_replayed_or_deleted(self):
  with tempfile.TemporaryDirectory()as d:
   plan,hub,args=self.setup_run(d);hub.ambiguous=True
   with self.assertRaises(TimeoutError):k.KernelProbeRun(**args)
   self.assertEqual(sum(m=='POST'for m,p in hub.calls),1);self.assertFalse(any(m=='DELETE'for m,p in hub.calls))
   self.assertTrue(json.loads((Path(d)/'peer.kernel.json').read_text())['manual_cleanup_required']);self.assertTrue(hub.closed)
 def test_existing_or_invalid_uuid_not_deleted(self):
  for model,remaining in [({'id':KID,'name':'python3'},[{'id':KID}]),({'id':'invalid','name':'python3'},[])]:
   with tempfile.TemporaryDirectory()as d:
    plan,hub,args=self.setup_run(d);hub.model=model;hub.remaining=remaining
    with self.assertRaises(ValueError):k.KernelProbeRun(**args)
    self.assertFalse(any(m=='DELETE'for m,p in hub.calls));self.assertTrue(hub.closed)
 def test_manifest_hash_and_closed_rows(self):
  with tempfile.TemporaryDirectory()as d:
   plan,hub,args=self.setup_run(d)
   path=Path(d)/'manifest';raw=json.dumps({'a':plan,'b':plan}).encode();path.write_bytes(raw);path.chmod(0o600)
   targets={'pods':{'a':{'uid':UID},'b':{'uid':UID}}}
   self.assertEqual(k.read_plans(path,hashlib.sha256(raw).hexdigest(),targets)['a'],plan)
   with self.assertRaises(ValueError):k.read_plans(path,'0'*64,targets)
   with self.assertRaises(ValueError):k.validate_plan({**plan,'token':'embedded'},{'uid':UID})
 def test_hardlinked_token_rejected(self):
  with tempfile.TemporaryDirectory()as d:
   path=Path(d)/'token';path.write_text('abc');path.chmod(0o600);os.link(path,Path(d)/'other')
   with self.assertRaises(ValueError):k.read_token(str(path))
 def test_created_uuid_persisted_before_execute(self):
  with tempfile.TemporaryDirectory()as d:
   plan,hub,args=self.setup_run(d)
   def execute(*a,**kw):
    receipt=json.loads((Path(d)/'peer.kernel.json').read_text())
    self.assertEqual(receipt['created_kernel'],KID);self.assertEqual(receipt['pod_uid'],UID)
    self.assertEqual(receipt['route'],'/user/shared/qa');self.assertTrue(receipt['manual_cleanup_required'])
   with patch.object(k,'exchange',side_effect=execute):k.KernelProbeRun(**args).complete()
 def test_readback_remaining_means_hold(self):
  with tempfile.TemporaryDirectory()as d:
   plan,hub,args=self.setup_run(d);original=hub.request
   def request(method,path,**kw):
    if method=='DELETE':hub.calls.append((method,path));hub.remaining=[{'id':KID}];return Response(None)
    return original(method,path,**kw)
   hub.request=request
   with patch.object(k,'exchange'):
    run=k.KernelProbeRun(**args)
    with self.assertRaises(ValueError):run.complete()
   self.assertTrue(hub.closed);receipt=json.loads((Path(d)/'peer.kernel.json').read_text())
   self.assertTrue(receipt['manual_cleanup_required']);self.assertFalse(receipt['deleted_own_kernel'])
   self.assertEqual(sum(m=='DELETE'for m,p in hub.calls),1)
 def test_bad_route_environment_fails_before_create(self):
  with tempfile.TemporaryDirectory()as d:
   plan,hub,args=self.setup_run(d);args.pop('pod_check')
   pod={'metadata':{'uid':UID},'spec':{'containers':[{'name':'notebook','env':[]}]},'status':{'phase':'Running','containerStatuses':[{'name':'notebook','ready':True,'state':{'running':{}}}]}}
   with patch('current_preflight.pod',return_value=pod):
    with self.assertRaises(ValueError):k.KernelProbeRun(**args)
   self.assertFalse(any(m=='POST'for m,p in hub.calls))
 def test_watchdog_horizon_after_ambiguous_exchange_not_creation(self):
  with tempfile.TemporaryDirectory()as d:
   plan,hub,args=self.setup_run(d);clock=[0.0]
   original=hub.request
   def request(method,path,**kw):
    if method=='POST':clock[0]=100.0
    return original(method,path,**kw)
   hub.request=request
   class SlowSocket(Socket):
    def __enter__(self):clock[0]=200.0;return self
   hub.socket_object=SlowSocket()
   def exchange(*a,**kw):clock[0]=300.0;raise TimeoutError('ambiguous send')
   with patch.object(k.time,'monotonic',side_effect=lambda:clock[0]),patch.object(k,'exchange',side_effect=exchange),patch.object(k,'wait_watchdog')as wait:
    run=k.KernelProbeRun(**args)
    with self.assertRaises(ValueError):run.complete()
   self.assertEqual(run.started,200.0);wait.assert_called_once_with(315.0)
   self.assertTrue(hub.closed)
 def test_thread_error_waits_watchdog_then_owned_cleanup(self):
  with tempfile.TemporaryDirectory()as d:
   plan,hub,args=self.setup_run(d)
   with patch.object(k,'exchange',side_effect=RuntimeError('private')),patch.object(k,'wait_watchdog')as wait:
    run=k.KernelProbeRun(**args)
    with self.assertRaises(ValueError):run.complete()
   wait.assert_called_once();self.assertTrue(hub.closed);self.assertTrue(hub.socket_object.closed)
if __name__=='__main__':unittest.main()

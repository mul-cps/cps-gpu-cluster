import copy,hashlib,io,json,os,pathlib,tempfile,time,unittest,urllib.error
from unittest import mock
import observer as o
import phase_once as p
class ObserverTests(unittest.TestCase):
 def endpoint(self):return {'id':'cps-reservation','required':True,'category':'authenticated-api','transport':'direct-tls','url':'https://example.test/internal/v1/reservations/owned','expectedStatus':200,'expectedJSONSubset':{'active':False,'attempt':None},'authScheme':'Bearer','tokenFile':'/private/token','caFile':None}
 def config(self):return {'rootRelease':'root-test','operation':'planned-checkpoint-20261118','expiresAt':time.time()+60,'intervalSeconds':.5,'maximumSeconds':10,'endpoints':[self.endpoint()]}
 def test_unarmed_refuses(self):
  c=self.config();c['rootRelease']=None
  with self.assertRaises(AssertionError):o.validate(c)
 def test_health_only_cannot_qualify(self):
  c=self.config();c['endpoints'][0]['url']='https://example.test/health'
  with self.assertRaises(AssertionError):o.validate(c)
 def test_unsafe_urls_refused(self):
  for u in ['http://example.test/internal/v1/profiles','https://user:pass@example.test/internal/v1/profiles','https://example.test/internal/v1/profiles?a=b','https://example.test/internal/v1/profiles#x','https://example.test/internal/v1/reservations/release/extra']:
   c=self.config();c['endpoints'][0]['url']=u
   with self.assertRaises(AssertionError):o.validate(c)
 def test_tls_proxy_redirect_get_and_body(self):
  e=self.endpoint();response=mock.MagicMock();response.status=200;response.read.return_value=b'{"active":false,"attempt":null}';response.__enter__.return_value=response
  opener=mock.Mock();opener.open.return_value=response
  with mock.patch.object(o,'private_file',return_value=b'dummy-private-token'),mock.patch.object(o.urllib.request,'build_opener',return_value=opener)as build:
   r=o.probe(e)
  self.assertTrue(r['ok']);request=opener.open.call_args.args[0];self.assertEqual(request.get_method(),'GET');self.assertEqual(request.get_header('Authorization'),'Bearer dummy-private-token')
  handlers=build.call_args.args;self.assertEqual(handlers[0].proxies,{});self.assertIsInstance(handlers[1],o.NoRedirect);self.assertIsNone(handlers[1].redirect_request(None,None,302,None,None,None));ctx=handlers[2]._context;self.assertTrue(ctx.check_hostname);self.assertEqual(ctx.verify_mode,o.ssl.CERT_REQUIRED)
  self.assertNotIn('dummy-private-token',json.dumps(r));self.assertNotIn('body',r)
 def test_tls_expiry_reported_not_bypassed(self):
  opener=mock.Mock();opener.open.side_effect=urllib.error.URLError(o.ssl.SSLCertVerificationError(10,'expired'))
  with mock.patch.object(o,'private_file',return_value=b'dummy'),mock.patch.object(o.urllib.request,'build_opener',return_value=opener):r=o.probe(self.endpoint())
  self.assertFalse(r['ok']);self.assertEqual(r['category'],'tls-verification-failed')
 def test_expected_404_body_is_positive_isolation_only(self):
  e=self.endpoint();e['expectedStatus']=404;e['expectedJSONSubset']={'detail':'Workspace not found'}
  opener=mock.Mock();opener.open.side_effect=urllib.error.HTTPError(e['url'],404,'not found',{},io.BytesIO(b'{"detail":"Workspace not found"}'))
  with mock.patch.object(o,'private_file',return_value=b'dummy'),mock.patch.object(o.urllib.request,'build_opener',return_value=opener):r=o.probe(e)
  self.assertTrue(r['ok']);self.assertEqual(r['category'],'verified-source-isolation')
 def test_earlier_restriction_counts_and_cross_boot_refused(self):
  s={'hostBootID':'boot','operation':'planned-checkpoint-20261118','monotonicNs':20_000_000_000,'earlierRestrictionMonotonicNs':10_000_000_000}
  self.assertEqual(o.duration(s,80_000_000_000,'boot'),70)
  with self.assertRaises(AssertionError):o.duration(s,80_000_000_000,'other')
 def test_false_is_not_zero_and_root_hash_preserved(self):self.assertFalse(o.subset({'active':False},{'active':0}));self.assertTrue(o.subset({'policy_hash':'sha256:abc'},{'policy_hash':'sha256:abc'}))
 def test_source_probe_replacement_stops_before_exec(self):
  e=self.endpoint();e['podBinding']={'name':'cps-admin-x','uid':'expected','containerID':'cid','imageID':'img'}
  with mock.patch.object(o.subprocess,'check_output',return_value=json.dumps({'metadata':{'uid':'other'}}).encode()),mock.patch.object(o.subprocess,'run')as run:
   with self.assertRaises(AssertionError):o.source_probe(e)
  run.assert_not_called()
 def test_source_transport_never_exports_credential(self):
  e=self.endpoint();e['transport']='source-pod';e['podBinding']={'name':'cps-admin-x','uid':'expected','containerID':'cid','imageID':'img'}
  actual={'metadata':{'uid':'expected'},'status':{'containerStatuses':[{'name':'console','containerID':'cid','imageID':'img','ready':True}]}}
  with mock.patch.object(o.subprocess,'check_output',return_value=json.dumps(actual).encode()),mock.patch.object(o.subprocess,'run',return_value=mock.Mock(returncode=0,stdout=json.dumps([{'id':e['id'],'required':True,'ok':True}]).encode()))as run:r=o.source_probe(e)
  self.assertTrue(r['ok']);args=run.call_args.args[0];self.assertEqual(args[-2:],['python','-']);self.assertNotIn('dummy',str(args));self.assertIn(b"os.environ['COMPUTE_POLICY_TOKEN']",run.call_args.kwargs['input']);self.assertNotIn(b'/private/token',run.call_args.kwargs['input'])
 def test_timing_receipt_other_release_refused(self):
  c=self.config();start={'rootRelease':'other','operation':c['operation'],'hostBootID':'boot','monotonicNs':1};finish={'rootRelease':c['rootRelease'],'operation':c['operation'],'hostBootID':'boot','monotonicNs':2,'bothServicesRestored':True,'targetStatePreservationVerified':True,'requiredControlOperationVerified':True}
  with self.assertRaises(AssertionError):o.validate_timing(c,start,finish,'boot',3)
 def test_killpg_session_race_still_kills_and_reaps(self):
  proc=mock.Mock();proc.pid=123456;alive=[True];proc.is_alive.side_effect=lambda:alive[0];proc.kill.side_effect=lambda:alive.__setitem__(0,False)
  parent=mock.Mock();parent.poll.return_value=False;remote=mock.Mock();ctx=mock.Mock();ctx.Pipe.return_value=(parent,remote);ctx.Process.return_value=proc
  with mock.patch.object(o.mp,'get_context',return_value=ctx),mock.patch.object(o.os,'killpg',side_effect=ProcessLookupError):rows=o.sample([self.endpoint()])
  proc.kill.assert_called_once();proc.join.assert_called();self.assertFalse(alive[0]);self.assertFalse(rows[0]['ok'])
class PhaseTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.d=pathlib.Path(self.tmp.name);self.plan={'operation':'planned-checkpoint-20261118','rootRelease':'root-test','expiresAt':time.time()+60,'targetPVCUID':p.__dict__.get('TARGET_PVC_UID','bfe673db-6d32-4ddd-a8a7-94cf9b86890e'),'targetPVUID':'63513db8-9ec4-48f9-947d-8faf5ba0ccea','phases':{},'evidence':{}}
  self.row={'kind':'cronjob','name':'compute-state-backup','uid':p.OBJECTS['cron'][2],'expectedSpec':self.pin('before.json',{'suspend':False}),'desiredSpec':self.pin('after.json',{'suspend':True})};self.plan['phases']['cron-fence']=self.row
  self.current={'metadata':{'uid':self.row['uid'],'resourceVersion':'123'},'spec':{'suspend':False}}
  self.case=self.d/'case';p.begin_directory(self.case,self.plan);o.save(self.case/'native-service-fence-reply.safe.json',{'phase':'native-service-fence','verifiedSpec':True})
 def tearDown(self):self.tmp.cleanup()
 def pin(self,name,body):
  f=self.d/name;f.write_text(json.dumps(body));return {'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
 def test_uid_or_fullspec_drift_refused(self):
  for change in ['uid','spec']:
   c=copy.deepcopy(self.current)
   if change=='uid':c['metadata']['uid']='wrong'
   else:c['spec']['extra']=True
   with self.assertRaises(AssertionError):p.cas(self.row,c)
 def test_unknown_patch_has_durable_intent_and_never_replays(self):
  with mock.patch.object(p,'get',return_value=self.current),mock.patch.object(p.subprocess,'run',side_effect=TimeoutError('lost reply'))as run:
   with self.assertRaises(TimeoutError):p.run(self.plan,'cron-fence',self.case)
   self.assertTrue((self.case/'cron-fence-intent.safe.json').exists())
   with self.assertRaises(AssertionError):p.run(self.plan,'cron-fence',self.case)
   self.assertEqual(run.call_count,1)
 def test_reconcile_is_get_only_no_continuation(self):
  o.save(self.case/'cron-fence-intent.safe.json',{'status':'UNKNOWN'})
  with mock.patch.object(p,'get',return_value=self.current),mock.patch.object(p.subprocess,'run')as run:r=p.reconcile(self.plan,'cron-fence',self.case)
  self.assertFalse(r['automaticContinuationPermitted']);run.assert_not_called();self.assertFalse((self.case/'cron-fence-reply.safe.json').exists())
 def test_stopped_fact_not_manufactured_from_phase_reply(self):
  self.plan['evidence']={}
  with self.assertRaises(KeyError):p.check_external(self.plan,'admission-deny')
 def test_no_start_without_final_install_or_admission_gate(self):
  with self.assertRaises(KeyError):p.check_external(self.plan,'main-start')
 def test_expired_release_refused(self):
  self.plan['expiresAt']=time.time()-1
  with self.assertRaises(AssertionError):p.validate(self.plan,'cron-fence')
if __name__=='__main__':unittest.main()

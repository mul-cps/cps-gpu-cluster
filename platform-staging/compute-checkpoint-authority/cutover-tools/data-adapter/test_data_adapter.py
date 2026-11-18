"""Offline control-contract tests; never execute a production data RPC/gate."""
import importlib.util,pathlib,tempfile,unittest,json,copy,time,ast,hashlib,types
from unittest.mock import patch
D=pathlib.Path(__file__).parent;s=importlib.util.spec_from_file_location('a',D/'data_adapter.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class FakeTransport:
 def __init__(self):self.calls=[];self.fail=None
 def guard(self,x):self.calls.append('guard')
 def rpc(self,d,phase,pod,code):
  self.calls.append(phase)
  if self.fail==phase:raise TimeoutError('offline lost reply; no RPC executed')
  return {'receiptSHA256':'a'*64,'offlineUnitOnly':True}
 def relay(self,*args):
  self.calls.append('transfer')
  if self.fail=='transfer':raise TimeoutError('offline lost reply')
  return {'offlineUnitOnly':True}
class Offline(a.DataAdapter):
 def __init__(self,d):
  self.d=d;self.x={'workerScriptPath':'/work/fixture-worker.py'};self.stream=types.SimpleNamespace(SOURCE='source',TARGET='target',cmd=lambda *args:args,load_worker_code=lambda *args:'not-executed');self.transport=FakeTransport();self.done={};self.target_may_be_written=False;self.source='/work/unit-snapshot';self.received='/work/unit-received'
 def _gate(self,*args):return {'offlineUnitOnly':True},{'offlineUnitOnly':True}
 def _code(self,*args):return 'NONEXECUTING_UNIT_RPC'
 def _checked_result(self,*args):pass
class Data(unittest.TestCase):
 def tmp(self):t=tempfile.TemporaryDirectory(dir=D);self.addCleanup(t.cleanup);return pathlib.Path(t.name)
 def clock(self):return {'operation':'planned-checkpoint-20261118','rootRelease':'offline clock unit only','hostBootID':'boot','monotonicNs':10000000000,'earlierRestrictionMonotonicNs':None,'noEarlierRestrictionAttested':True}
 def test_unarmed_before_filesystem_or_api(self):
  with patch.object(a.pathlib.Path,'mkdir',side_effect=AssertionError('No writes')),patch.object(a,'stream_module',side_effect=AssertionError('No dependencies/transport')):
   with self.assertRaisesRegex(ValueError,'UNARMED'):a.DataAdapter({'rootRelease':None})
 def test_original_clock_never_reset_and_earlier_restriction_counts(self):
  c=self.clock();self.assertEqual(a.clock_check(c,20000000000,'boot'),10);c['earlierRestrictionMonotonicNs']=5000000000;self.assertEqual(a.clock_check(c,20000000000,'boot'),15)
  with self.assertRaisesRegex(ValueError,'exceeded60'):a.clock_check(c,65000000000,'boot')
 def test_clock_boot_future_and_ambiguous_start_hold(self):
  c=self.clock()
  with self.assertRaises(ValueError):a.clock_check(c,20000000000,'different')
  with self.assertRaises(ValueError):a.clock_check(c,5000000000,'boot')
  c['noEarlierRestrictionAttested']=False
  with self.assertRaises(ValueError):a.clock_check(c,20000000000,'boot')
 def test_snapshot_transfer_no_target_write_install_conservative_boundary(self):
  d=self.tmp();x=Offline(d);x.snapshot(None,None);self.assertFalse(x.target_may_be_written);x.transfer(None,None);self.assertFalse(x.target_may_be_written);x.install(None,None);self.assertTrue(x.target_may_be_written)
  self.assertFalse(json.loads((d/'snapshot-intent.private.json').read_text())['targetMayHaveBeenWritten']);self.assertFalse(json.loads((d/'transfer-intent.private.json').read_text())['targetMayHaveBeenWritten']);self.assertTrue(json.loads((d/'install-intent.private.json').read_text())['targetMayHaveBeenWritten'])
 def test_lost_snapshot_or_transfer_reply_hold_without_target_write_and_no_retry(self):
  for phase in ['snapshot','transfer']:
   d=self.tmp();x=Offline(d)
   if phase=='transfer':x.snapshot(None,None)
   x.transport.fail=phase
   with self.assertRaises(TimeoutError):getattr(x,phase)(None,None)
   self.assertFalse(x.target_may_be_written);before=list(x.transport.calls)
   with self.assertRaises(ValueError):getattr(x,phase)(None,None)
   self.assertEqual(x.transport.calls,before)
 def test_lost_install_reply_target_unknown_no_retry(self):
  d=self.tmp();x=Offline(d);x.snapshot(None,None);x.transfer(None,None);x.transport.fail='install'
  with self.assertRaises(TimeoutError):x.install(None,None)
  self.assertTrue(x.target_may_be_written);self.assertTrue(json.loads((d/'install-HOLD.safe.json').read_text())['targetMayHaveBeenWritten']);before=list(x.transport.calls)
  with self.assertRaises(ValueError):x.install(None,None)
  self.assertEqual(x.transport.calls,before)
 def test_precondition_failure_before_install_dispatch_keeps_target_unwritten(self):
  d=self.tmp();x=Offline(d);x.snapshot(None,None);x.transfer(None,None)
  def refused(*unused):raise ValueError('External real proof expired')
  x._gate=refused
  with self.assertRaises(ValueError):x.install(None,None)
  self.assertFalse(x.target_may_be_written);self.assertFalse((d/'install-intent.private.json').exists());self.assertNotIn('install',x.transport.calls)
 def test_bound_receipt_tamper_refused(self):
  p=self.tmp()/'receipt';p.write_text('{"external":true}')
  with self.assertRaises(ValueError):a.read_bound(p,'0'*64)
 def test_native_rpc_uses_original_protocol_and_gate_not_fixture_functions(self):
  x=Offline(self.tmp());x.x.update({'protectedInputsPath':str(x.d/'protected.json'),'protectedInputsSHA256':None});data=[{'path':'/dummy/'+str(i),'sha256':'a'*64}for i in range(13)];p=x.d/'protected.json';p.write_text(json.dumps(data));x.x['protectedInputsSHA256']=hashlib.sha256(p.read_bytes()).hexdigest();x.source='/work/production-checkpoint-0123456789ab-snapshot';x.received='/work/production-checkpoint-0123456789ab-received';x.done['snapshot']={'receiptSHA256':'a'*64}
  for action in ['snapshot','install']:
   code=a.DataAdapter._code(x,action,{'externalProofOnly':'NOT EXECUTED IN UNIT TEST'});ast.parse(code);self.assertIn("ns['gate'](g)",code);self.assertLess(code.index("ns['gate'](g)"),code.rindex("ns['"+action+"']"));self.assertIn('signal.alarm(30)',code);self.assertNotIn('fixture_create',code)
 def test_swapped_released_authorization_is_rejected_before_native_gate(self):
  x=Offline(self.tmp());x.x={'protocolGatePath':'gate','protocolGateSHA256':'g','clockReceiptPath':'clock','clockReceiptSHA256':'c','rootRelease':'released'}
  gate={'operation':'planned-checkpoint-20261118','rootRelease':'OTHER'};clock=copy.deepcopy(gate);proof={**gate,'gate':'old-writers-stopped','passed':True,'clockReceiptSHA256':'c'}
  with patch.object(a,'read_bound',side_effect=[gate,clock,proof]):
   with self.assertRaisesRegex(ValueError,'release differs'):a.DataAdapter._gate(x,'proof','p')
 def test_native_install_return_must_match_full_protocol_contract(self):
  x=Offline(self.tmp());x.x={'targetPVCUID':'target'};x.done['snapshot']={'receiptSHA256':'a'*64}
  result={'installed':True,'receiptSHA256':'a'*64,'targetPVCUID':'target','all4LogicalExact':True,'allDataFilesExact':True,'noAuthorityProcessStarted':True};a.DataAdapter._checked_result(x,'install',{},result)
  for key in ['installed','all4LogicalExact','allDataFilesExact','noAuthorityProcessStarted']:
   bad=copy.deepcopy(result);bad[key]=False
   with self.assertRaises(ValueError):a.DataAdapter._checked_result(x,'install',{},bad)
  bad=copy.deepcopy(result);bad['receiptSHA256']='b'*64
  with self.assertRaises(ValueError):a.DataAdapter._checked_result(x,'install',{},bad)
 def test_4db_13dummy_fixture_end_to_end_calls_only_readonly_helpers(self):
  # Explicitly separate from production adapter: no fake stopped-writer receipt,
  # production gate, snapshot or install is invoked by this fixture transport.
  ns={'__name__':'explicit_offline_fixture'};exec((a.STREAM/'stream_worker.py').read_text(),ns);exec((a.STREAM/'fixture_worker.py').read_text(),ns);shape=json.loads((a.STREAM/'fixture-shape.safe.json').read_text());source=a.protocol_source()
  source+='\ndef gate(*a,**k):raise AssertionError("No production gate in fixture")\ndef snapshot(*a,**k):raise AssertionError("No production snapshot in fixture")\ndef install(*a,**k):raise AssertionError("No production install in fixture")\n'
  root=self.tmp();src=root/'fixture';ns['fixture_create'](src,shape);before=ns['fixture_proof'](src,source)
  import io
  wire=io.BytesIO();ns['produce'](src,wire);wire.seek(0);out=root/'received';ns['extract'](wire,out);self.assertEqual(before,ns['fixture_proof'](out,source));self.assertEqual(len(before['databases']),4)
if __name__=='__main__':unittest.main()

import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import run_vmm_cross_parent as w
from test_vmm_wrapper import OrchestrationTests

class DiagnosticTests(unittest.TestCase):
 def test_actual_failed_command_preserves_private_streams(self):
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp)
   argv=[sys.executable,'-c','import sys;print("before failure");print("Exact mapped source bytes required",file=sys.stderr);sys.exit(3)']
   with self.assertRaisesRegex(ValueError,'exit 3'):w.diagnostic_run(argv,b'{}\n',root,'positive-root-command',timeout=2)
   r=json.loads((root/'positive-root-command.json').read_text())
   self.assertEqual(r['returncode'],3);self.assertEqual(r['argv'],argv)
   self.assertIn(b'Exact mapped source', (root/'positive-root-command.stderr').read_bytes())
   self.assertEqual((root/'positive-root-command.stdout').read_bytes(),b'before failure\n')
   for p in root.iterdir():self.assertEqual(p.stat().st_mode&0o777,0o600)
 def test_actual_timeout_and_stream_bounds_fail_closed(self):
  for script,timeout,limit in [('import time;time.sleep(2)',.05,1024),('print("x"*4096)',2,100)]:
   with self.subTest(script=script),tempfile.TemporaryDirectory()as tmp:
    root=Path(tmp)
    with self.assertRaises(ValueError):w.diagnostic_run([sys.executable,'-c',script],b'',root,'cmd',timeout=timeout,stream_limit=limit)
    r=json.loads((root/'cmd.json').read_text());self.assertIn(r['state'],['timeout','stream-bound-exceeded'])
    self.assertLessEqual((root/'cmd.stdout').stat().st_size,limit);self.assertIsNotNone(r['returncode'])
 def test_bridge_failure_cleanup_then_postflight_and_unresolved(self):
  trace=[]
  with tempfile.TemporaryDirectory()as raw:
   tmp=Path(raw);tmp.chmod(0o700);args,trial,h,S,T,B,sessions=OrchestrationTests().fixture(tmp)
   before=h.preflight.return_value
   h.preflight.side_effect=lambda c:(trace.append('preflight')or before)
   original=S.abandon
   S.abandon=lambda self:(trace.append('close-'+self.label),original(self))
   with patch.object(w,'load_preflight',return_value=h),patch.object(w,'load_witness',return_value=T),patch.object(w,'Session',S),patch.object(w,'bridge',side_effect=ValueError('Exact mapped source bytes required')),patch.object(w.signal,'signal'):
    with self.assertRaises(SystemExit):w.main(args)
   r=json.loads((tmp/'run/receipt.json').read_text())
   self.assertEqual(trace,['preflight','close-same-parent-positive','close-exporter','preflight'])
   self.assertEqual(r['state'],'inconclusive');self.assertTrue(r['final_postflight_observed'])
   self.assertEqual(r['remote_endpoint_cleanup'],'unresolved');self.assertIn('Exact mapped source',r['error_message'])
   self.assertTrue((tmp/'run/final-postflight.json').exists())
 def test_cleanup_and_final_postflight_errors_both_recorded(self):
  with tempfile.TemporaryDirectory()as raw:
   tmp=Path(raw);tmp.chmod(0o700);args,trial,h,S,T,B,sessions=OrchestrationTests().fixture(tmp)
   h.preflight.side_effect=[h.preflight.return_value,ValueError('final API failed')]
   S.abandon=lambda self:(_ for _ in ()).throw(ValueError('local transport failed'))
   with patch.object(w,'load_preflight',return_value=h),patch.object(w,'load_witness',return_value=T),patch.object(w,'Session',S),patch.object(w,'bridge',side_effect=ValueError('bridge failed')),patch.object(w.signal,'signal'):
    with self.assertRaises(SystemExit):w.main(args)
   r=json.loads((tmp/'run/receipt.json').read_text())
   self.assertEqual(len(r['transport_cleanup_errors']),2);self.assertFalse(r['final_postflight_observed'])
   self.assertIn('final API failed',r['final_postflight_error']['message']);self.assertEqual(r['remote_endpoint_cleanup'],'unresolved')

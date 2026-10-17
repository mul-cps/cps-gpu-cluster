import errno,importlib.util,io,json
from pathlib import Path
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

PATH=Path(__file__).with_name('kernel_witness_collector.py')
c=None
if PATH.exists():
 spec=importlib.util.spec_from_file_location('witness_collector',PATH);c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class CollectorTests(unittest.TestCase):
 def test_default_is_inert_without_kernel_device_or_session(self):
  self.assertIsNotNone(c,'Root collector is required')
  with patch.object(c.os,'open',side_effect=AssertionError('device open')),redirect_stdout(io.StringIO())as out:c.main([])
  self.assertEqual(json.loads(out.getvalue())['state'],'inert')
 def test_stream_rejects_epipe_gap_truncation_and_read_deadline(self):
  self.assertIsNotNone(c,'Root collector is required')
  for fault in ('epipe','gap','size','timeout'):
   rows=[b'4,10,10,-;noise\n',b'4,11,11,-;target\n']
   if fault=='epipe':rows=[OSError(errno.EPIPE,'overrun')]
   elif fault=='gap':rows[-1]=b'4,12,11,-;target\n'
   elif fault=='size':rows=[b'x'*65537]
   with self.subTest(fault=fault),patch.object(c.os,'read',side_effect=rows),patch.object(c.select,'select',return_value=([],[],[])if fault=='timeout'else([99],[],[])):
    stream=c.KernelStream(99,lambda _:None)
    with self.assertRaises((ValueError,OSError,TimeoutError)):stream.until('target',c.time.monotonic()+0.01)
 def test_whole_records_preserve_sequence_and_raw_clock_without_conversion(self):
  self.assertIsNotNone(c,'Root collector is required')
  rows=[b'4,10,9000000000,-;noise\n',b'14,11,9000000001,-;target\n'];saved=[]
  with patch.object(c.os,'read',side_effect=rows),patch.object(c.select,'select',return_value=([99],[],[])):
   stream=c.KernelStream(99,saved.append);result=stream.until('target',c.time.monotonic()+1)
  self.assertEqual(result['sequence'],11);self.assertEqual(saved,rows)
 def test_missing_execution_pins_fail_before_device_access(self):
  self.assertIsNotNone(c,'Root collector is required')
  with patch.object(c.os,'open',side_effect=AssertionError('device open')):
   with self.assertRaises(ValueError):c.main(['--execute','--qualification'])

if __name__=='__main__':unittest.main()

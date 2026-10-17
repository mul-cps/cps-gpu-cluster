import hashlib,importlib.util,json,tempfile
from pathlib import Path
import unittest

PATH=Path(__file__).with_name('kernel_witness_transport.py')
t=None
if PATH.exists():
 spec=importlib.util.spec_from_file_location('witness_transport',PATH);t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)

class TransportTests(unittest.TestCase):
 def test_missing_source_pin_never_starts_external_transport(self):
  self.assertIsNotNone(t,'Bounded Root witness transport required')
  with tempfile.TemporaryDirectory()as tmp:
   with self.assertRaises(ValueError):t.KernelWitness([],Path(tmp),collector_sha256='a'*64,validator_sha256='b'*64)
 def test_real_jsonl_ready_begin_end_handshake_and_explicit_nonce(self):
  self.assertIsNotNone(t,'Bounded Root witness transport required')
  import sys
  validator=hashlib.sha256(Path(__file__).with_name('kernel_witness_validator.py').read_bytes()).hexdigest()
  collector=hashlib.sha256(Path(__file__).with_name('kernel_witness_collector.py').read_bytes()).hexdigest()
  from test_kernel_witness import fixture
  c,a,e=fixture();c['collector_sha256']=collector;c['validator_sha256']=validator
  stub="""import json,sys
capture=json.loads(sys.argv[1]);nonce=capture['nonce']
print(json.dumps({'phase':'witness-ready','nonce':nonce,'boot_id':capture['boot_id'],'driver_generation':capture['driver_generation'],'collector_sha256':capture['collector_sha256'],'validator_sha256':capture['validator_sha256']}),flush=True)
begin=json.loads(sys.stdin.readline());assert begin['op']=='begin' and begin['nonce']==nonce
print(json.dumps({'phase':'witness-begin','trial_id':begin['trial_id'],'nonce':nonce}),flush=True)
end=json.loads(sys.stdin.readline());assert end['op']=='end' and end['nonce']==nonce
import hashlib
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
import importlib.util
spec=importlib.util.spec_from_file_location('validator',sys.argv[2]);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
correlation=v.validate_capture(capture,begin['attribution'],end['api_result'],collector_sha256=capture['collector_sha256'],validator_sha256=capture['validator_sha256'])
print(json.dumps({'phase':'witness-completed','trial_id':begin['trial_id'],'nonce':nonce,'capture':capture,'correlation':correlation,'root_capture_path':'/run/cps-native-gpu/operator/vmm-kmsg-witness/sessions/'+begin['trial_id']+'/capture.json','root_capture_raw_sha256':'sha256:'+hashlib.sha256(canon(capture)+b'\\n').hexdigest()}),flush=True)
"""
  with tempfile.TemporaryDirectory()as tmp:
   # The launcher callback replaces only kubectl with a local stdlib JSONL stub.
   argv=[sys.executable,'-u','-c',stub,json.dumps(c),str(Path(__file__).with_name('kernel_witness_validator.py'))]
   witness=t.KernelWitness(argv,Path(tmp),collector_sha256=collector,validator_sha256=validator)
   witness.begin(a);capture,result=witness.end(e)
   self.assertTrue(result['kernel_witness_correlated']);self.assertFalse(result['production_qualified'])
   self.assertEqual(capture,c);self.assertEqual(witness.process.returncode,0)
   self.assertTrue(witness.closed)

if __name__=='__main__':unittest.main()

import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('deploy',ROOT/'scripts/compute-platform/truenas-artifacts-deploy.py')
class DeploymentTests(unittest.TestCase):
 def test_only_authenticated_tls_endpoint_published(self):
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  c=m.compose()
  s=c['services']['seaweed']
  self.assertEqual(s['ports'],['8333:8333'])
  self.assertIn('@sha256:',s['image'])
  self.assertNotIn('environment',s)
  self.assertIn('-s3.config=/run/cps/s3.json',s['command'])
  self.assertIn('-s3.cert.file=/run/cps/tls.crt',s['command'])
  self.assertFalse(s.get('privileged',False))
  self.assertIn('--cacert',s['healthcheck']['test'])
  self.assertNotIn('--no-check-certificate',s['healthcheck']['test'])
 def test_reject_existing_dataset_overwrite(self):
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with self.assertRaises(ValueError):m.ensure_new([{'id':m.DATASET}],[])
  with self.assertRaises(ValueError):m.ensure_new([],[{'id':m.APP}])

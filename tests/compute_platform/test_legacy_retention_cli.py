import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/compute-platform/truenas-artifacts-retention.py'

class LegacyRetentionTests(unittest.TestCase):
 def module(self):
  spec=importlib.util.spec_from_file_location('legacy_retention',SCRIPT)
  module=importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module

 def test_legacy_apply_is_rejected_before_storage_access(self):
  m=self.module()
  class EmptyStorage:
   touched=False
   def get_paginator(self,name):
    self.touched=True
    return self
   def paginate(self,**kwargs):return []
  storage=EmptyStorage()
  with self.assertRaisesRegex(ValueError,'read-only'):
   m.sweep(storage,'bucket',object(),apply=True)
  self.assertFalse(storage.touched)
 def test_legacy_cli_apply_refuses_before_config_or_client_initialization(self):
  result=subprocess.run([sys.executable,str(ROOT/'scripts/compute-platform/truenas-artifacts-retention.py'),'--apply','--config','/nonexistent/cps-retention.json'],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0)
  self.assertIn('read-only',result.stderr)
  self.assertNotIn('FileNotFoundError',result.stderr)
  self.assertNotIn('ModuleNotFoundError',result.stderr)

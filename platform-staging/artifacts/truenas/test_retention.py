import importlib.util
from pathlib import Path
from datetime import datetime,timezone,timedelta
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('retention',ROOT/'scripts/compute-platform/truenas-artifacts-retention.py')
class RetentionTests(unittest.TestCase):
 def module(self):
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
 def test_active_retained_unknown_are_preserved(self):
  m=self.module();now=datetime.now(timezone.utc);old=now-timedelta(days=100)
  base={'retention':'temporary-expirable','active':'false','retained':'false'}
  self.assertFalse(m.eligible('notebook-inputs/id/snapshot.tar',old,{**base,'active':'true'},now))
  self.assertFalse(m.eligible('notebook-inputs/id/snapshot.tar',old,{**base,'retained':'true'},now))
  self.assertFalse(m.eligible('notebook-inputs/id/snapshot.tar',old,{},now))
  self.assertFalse(m.eligible('unrelated/id',old,base,now))
 def test_exact_retention_age_and_terminal_proof(self):
  m=self.module();now=datetime.now(timezone.utc);tags={'retention':'run-expirable','active':'false','retained':'false'}
  self.assertFalse(m.eligible('run-artifacts/id/executed.ipynb',now-timedelta(days=89),tags,now))
  self.assertTrue(m.eligible('run-artifacts/id/executed.ipynb',now-timedelta(days=90),tags,now))
  workflow={'metadata':{'name':'cps-id','uid':'uid','namespace':'cps-compute','annotations':{'cps.compute/notebook-id':'id'}},'status':{'phase':'Succeeded','finishedAt':(now-timedelta(days=91)).isoformat()}}
  self.assertTrue(m.terminal_proof(workflow,'cps-compute','id','uid',now))
  workflow['status']['phase']='Running';self.assertFalse(m.terminal_proof(workflow,'cps-compute','id','uid',now))

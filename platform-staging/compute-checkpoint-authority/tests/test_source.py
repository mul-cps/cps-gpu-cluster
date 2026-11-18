import copy,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from assert_delivery import assert_current,validate_local,digest,podspec
class SourceTests(unittest.TestCase):
 def setUp(self):
  self.p=validate_local();self.objects={r['name']:json.loads((ROOT/'baseline'/(r['name']+'.json')).read_text()) for r in self.p['resources']}
  for r in self.p['resources']:self.objects[r['name']]['metadata']['uid']=r['uid']
  c=self.p['currentClaim'];self.pvc={'metadata':{'name':c['name'],'namespace':c['namespace'],'uid':c['uid']},'spec':{'volumeName':c['pvName']}}
 def test_baseline_current(self):self.assertTrue(assert_current(self.p,self.pvc,self.objects));self.assertIsNone(self.p['candidateRelease']);self.assertIsNone(self.p['cutoverReceipt'])
 def test_replaced_pvc_refused(self):
  self.pvc['metadata']['uid']='different'
  with self.assertRaises(AssertionError):assert_current(self.p,self.pvc,self.objects)
 def test_controller_replaced_refused(self):
  self.objects['compute-gateway']['metadata']['uid']='different'
  with self.assertRaises(AssertionError):assert_current(self.p,self.pvc,self.objects)
 def test_unreviewed_spec_refused(self):
  self.objects['compute-gateway']['spec']['replicas']=0
  with self.assertRaises(AssertionError):assert_current(self.p,self.pvc,self.objects)
 def test_only_candidate_claim_and_controller_placement_changed(self):
  for row in self.p['resources']:
   old=self.objects[row['name']]['spec'];new=json.loads((ROOT/'candidate'/(row['name']+'.json')).read_text());ps=podspec(new)
   v=next(v for v in ps['volumes'] if v['name']==row['sourceVolume']);self.assertEqual(v['persistentVolumeClaim']['claimName'],self.p['candidateClaim']['name']);v['persistentVolumeClaim']['claimName']=self.p['currentClaim']['name']
   if new['kind']=='Deployment':self.assertEqual(ps['nodeSelector'],{'kubernetes.io/hostname':'k3s-wk-gpu3'});ps['nodeSelector']={'kubernetes.io/hostname':'k3s-wk-gpu2'}
   else:self.assertEqual(next(v for v in ps['volumes']if v['name']=='backup')['persistentVolumeClaim']['claimName'],'compute-state-backup')
   self.assertEqual(new['spec'],old)
 def test_policy_is_unarmed_exact_create_scope(self):
  p=json.loads((ROOT/'admission/policy.json').read_text());b=json.loads((ROOT/'admission/binding-warn-audit.json').read_text());g=json.loads((ROOT/'admission/release.UNARMED.json').read_text())
  self.assertEqual(b['spec']['validationActions'],['Warn','Audit']);self.assertIsNone(g['rootRelease']);self.assertIsNone(g['oldWritersStoppedReceiptSHA256'])
  self.assertEqual(p['spec']['matchConstraints']['resourceRules'],[{'apiGroups':[''],'apiVersions':['v1'],'operations':['CREATE'],'resources':['pods'],'scope':'Namespaced'}])
  self.assertEqual(p['spec']['matchConditions'],[{'name':'exact-namespace','expression':"request.namespace == 'cps-compute'"}])
 def test_no_raw_last_applied_or_secret_payload(self):
  for sub in ['baseline','candidate']:
   for path in (ROOT/sub).glob('*.json'):
    text=path.read_text();o=json.loads(text);self.assertNotIn('last-applied',text);self.assertNotIn('managedFields',text);self.assertNotIn('status',o);self.assertNotEqual(o['kind'],'Secret');self.assertEqual(set(o['metadata']),{'name','namespace'})
if __name__=='__main__':unittest.main()

"""Literal CEL admission compatibility for terminal-only SDK v2 artifacts.

These offline cases are not API-server typing, RBAC or propagation proof.
The admission envelope/discriminators do not replace SDK/Node body validators.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scheduler/qualification/dynamic-admission'))
import cel_evaluate as engine
import render
from test_node_agent import fixtures,BINDING

LABEL='cps.compute/native-binding'
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'))

class AuthorityAdmissionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.config,cls.enrollment,_=fixtures();cls.config['authority_namespace']='cps-native-system'
  cls.items=render.render(cls.config)['items']
  cls.generated=json.loads(Path(__file__).with_name('testdata').joinpath('sdk-v2-terminal-admission.json').read_text())
 def policy(self,who):
  name='cps-native-gateway-authority-create-only'if who=='gateway'else'cps-native-node-agent-cleanup-only'
  return next(p for p in self.items if p['kind']=='ValidatingAdmissionPolicy'and p['metadata']['name']==name)
 def cm(self,prefix,key,body):
  return {'apiVersion':'v1','kind':'ConfigMap','immutable':True,'metadata':{'name':prefix+BINDING[:40],'namespace':'cps-native-system','labels':{LABEL:BINDING}},'data':{key:canonical(body)}}
 def barrier(self):
  claim={**copy.deepcopy(self.enrollment),'state':'releasing','group_id':'group-one','ceiling':{'gpuMemoryGiB':5}}
  return self.cm('cps-native-enrollment-','abort-barrier.json',{'version':2,'kind':'enrollment-abort-barrier','claim':claim,'claim_sha256':'sha256:'+hashlib.sha256(canonical(claim).encode()).hexdigest()})
 def proof(self,kind='abort-barrier'):
  key='abort-barrier.json'if kind=='abort-barrier'else'enrollment.json'
  ref={'namespace':'cps-native-system','name':'cps-native-enrollment-'+BINDING[:40],'uid':'44444444-4444-4444-8444-444444444444','resourceVersion':'123','key':key,'data_sha256':'sha256:'+'d'*64}
  value={'version':2,'outcome':'enrollment-never-published'if kind=='abort-barrier'else'enrollment-never-programmed','binding_id':BINDING,'attempt':self.enrollment['attempt'],'claim_sha256':'sha256:'+'a'*64,'barrier'if kind=='abort-barrier'else'enrollment':ref,'slot_kind':kind,'node_epoch':{'node_uid':self.enrollment['node_uid'],'boot_id':'22222222-2222-4222-8222-222222222222','driver_generation':'33333333-3333-4333-8333-333333333333','gpu_uuid':self.enrollment['gpu_uuid']},'audit_sha256':'sha256:'+'b'*64,'cleanup_confirmed':True}
  return self.cm('cps-native-abort-','abort.json',value)
 def accepted(self,who,obj,namespace='cps-native-system'):
  self.assertEqual(obj['metadata']['namespace'],namespace)
  policy=self.policy(who)
  if namespace!='cps-native-system':
   # Keep real SDK fixture bodies and references byte-exact in their synthetic
   # authority namespace; exercise the same parameterized renderer there.
   config=copy.deepcopy(self.config);config['authority_namespace']=namespace
   policy=next(p for p in render.render(config)['items']if p['kind']=='ValidatingAdmissionPolicy'and p['metadata']['name']==policy['metadata']['name'])
  account='system:serviceaccount:'+('cps-compute:cps-compute-controller'if who=='gateway'else namespace+':cps-native-node-agent')
  result=engine.evaluate_policy(policy,{'object':obj,'oldObject':None,'params':None,'request':{'namespace':namespace,'userInfo':{'username':account}}})
  self.assertTrue(result['compiled'],result);self.assertTrue(result['evaluated'],result)
  return result['allExpressionsTrue']
 def test_exact_v2_barrier_and_both_terminal_proof_outcomes(self):
  provenance=self.generated['provenance'];self.assertEqual(provenance['source_commit'],'56e4c93db31f247e7a44a6face4a0ad18603167b')
  self.assertEqual(provenance['native_driver_writes'],0);self.assertEqual(provenance['live_api_calls'],0)
  objects=self.generated['objects']
  for who,key in (('gateway','barrier_slot'),('gateway','enrollment_slot'),('node','barrier_proof'),('node','enrollment_proof')):
   self.assertTrue(self.accepted(who,objects[key],objects[key]['metadata']['namespace']))
 def test_existing_immutable_enrollment_cleanup_and_empty_ledger_remain_allowed(self):
  self.assertTrue(self.accepted('gateway',self.cm('cps-native-enrollment-','enrollment.json',self.enrollment)))
  self.assertTrue(self.accepted('node',self.cm('cps-native-cleanup-','receipt.json',{'version':1})))
  self.assertTrue(self.accepted('gateway',{'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':'cps-native-system','name':'cps-native-gpu-allocations'},'data':{'state.json':'{"allocations":{},"version":1}'}}))
 def test_gateway_cannot_publish_node_proof_or_mix_slot_keys(self):
  self.assertFalse(self.accepted('gateway',self.proof()))
  obj=self.barrier();obj['data']['enrollment.json']='{}';self.assertFalse(self.accepted('gateway',obj))
  obj=self.barrier();obj['data']={'abort.json':obj['data']['abort-barrier.json']};self.assertFalse(self.accepted('gateway',obj))
 def test_node_cannot_publish_enrollment_barrier_ledger_or_crosskey_completion(self):
  for obj in (self.barrier(),self.cm('cps-native-enrollment-','enrollment.json',self.enrollment),self.cm('cps-native-gpu-allocations','state.json',{})):
   self.assertFalse(self.accepted('node',obj))
  obj=self.proof();obj['metadata']['name']='cps-native-cleanup-'+BINDING[:40];self.assertFalse(self.accepted('node',obj))
  obj=self.proof();obj['data']={'receipt.json':obj['data']['abort.json']};self.assertFalse(self.accepted('node',obj))
 def test_immutable_named_single_label_ownerless_text_envelopes_stay_closed(self):
  for who,source in (('gateway',self.barrier()),('node',self.proof())):
   mutations=(lambda x:x.update(immutable=False),lambda x:x.pop('immutable'),lambda x:x['metadata'].update(name='foreign-'+BINDING[:40]),lambda x:x['metadata']['labels'].update(extra='foreign'),lambda x:x['metadata'].update(ownerReferences=[{'uid':'foreign'}]),lambda x:x.update(binaryData={}),lambda x:x['data'].update(extra='{}'),lambda x:x['metadata']['labels'].update({LABEL:'b'*60}),lambda x:x['metadata']['labels'].update({LABEL:'a'*39+'b'+'a'*20}))
   for index,mutate in enumerate(mutations):
    with self.subTest(who=who,index=index):
     obj=copy.deepcopy(source);mutate(obj);self.assertFalse(self.accepted(who,obj))
 def test_same_name_prefix_cannot_mask_foreign_full_binding_in_v2_body(self):
  for who,obj in (('gateway',self.barrier()),('node',self.proof())):
   obj['metadata']['labels'][LABEL]='a'*40+'b'*20
   self.assertFalse(self.accepted(who,obj))
 def test_v2_discriminator_and_finite_text_bound(self):
  for who,source,key in (('gateway',self.barrier(),'abort-barrier.json'),('node',self.proof(),'abort.json')):
   for field,value in (('version',1),('version',True),('kind'if who=='gateway'else'outcome','foreign')):
    with self.subTest(who=who,field=field,value=value):
     obj=copy.deepcopy(source);body=json.loads(obj['data'][key]);body[field]=value;obj['data'][key]=canonical(body);self.assertFalse(self.accepted(who,obj))
   obj=copy.deepcopy(source);body=json.loads(obj['data'][key]);body['padding']='x'*65536;obj['data'][key]=canonical(body);self.assertFalse(self.accepted(who,obj))
  obj=self.proof();body=json.loads(obj['data']['abort.json']);body['cleanup_confirmed']=False;obj['data']['abort.json']=canonical(body);self.assertFalse(self.accepted('node',obj))
 def test_prefix_guard_retains_exact_40_and_60_hex_bounds_and_ignores_label_tail(self):
  # The old substring guard ignores the final20 label characters. Preserve
  # that accepted set for existing artifacts; full payload authority is SDK-owned.
  for who,obj in (('gateway',self.cm('cps-native-enrollment-','enrollment.json',self.enrollment)),('node',self.cm('cps-native-cleanup-','receipt.json',{'version':1}))):
   obj['metadata']['labels'][LABEL]='a'*40+'b'*20
   self.assertTrue(self.accepted(who,obj))
   for length in (39,41):
    bad=copy.deepcopy(obj);prefix='cps-native-enrollment-'if who=='gateway'else'cps-native-cleanup-';bad['metadata']['name']=prefix+'a'*length;self.assertFalse(self.accepted(who,bad))
   for label in ('a'*59,'a'*61,'A'*60):
    bad=copy.deepcopy(obj);bad['metadata']['labels'][LABEL]=label;self.assertFalse(self.accepted(who,bad))
 def test_namespace_service_accounts_and_create_only_binding_unchanged(self):
  for who in ('gateway','node'):
   p=self.policy(who);self.assertEqual(p['spec']['failurePolicy'],'Fail')
   self.assertEqual(p['spec']['matchConstraints']['resourceRules'],[{'apiGroups':[''],'apiVersions':['v1'],'operations':['CREATE'],'resources':['configmaps'],'scope':'Namespaced'}])
   binding=next(v for v in self.items if v['kind']=='ValidatingAdmissionPolicyBinding'and v['metadata']['name']==p['metadata']['name']);self.assertEqual(binding['spec']['validationActions'],['Deny'])
   account='system:serviceaccount:'+('cps-compute:cps-compute-controller'if who=='gateway'else'cps-native-system:cps-native-node-agent')
   self.assertIn(json.dumps(account),p['spec']['matchConditions'][0]['expression'])
   for namespace,username in (('cps-native-system','system:serviceaccount:foreign:foreign'),('foreign',account)):
    result=engine.evaluate_policy(p,{'object':self.barrier()if who=='gateway'else self.proof(),'oldObject':None,'params':None,'request':{'namespace':namespace,'userInfo':{'username':username}}})
    self.assertTrue(result['compiled'],result);self.assertTrue(result['evaluated'],result)
    self.assertFalse(result['allExpressionsTrue'])
   # A foreign SA is outside this scoped policy, not independently denied by
   # a false match condition; RBAC remains the separate credential boundary.
if __name__=='__main__':unittest.main()

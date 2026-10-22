import copy,importlib.util
from pathlib import Path
import pytest
P=Path(__file__).with_name('plain_lifecycle_rbac.py')
def mod():
 s=importlib.util.spec_from_file_location('rbac',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def fixture():
 return {'config':{'version':1,'enabled':True,'authority_namespace':'cps-native-lifecycle147','policy_hash':'sha256:'+'1'*64,'pool':{'node':'k3s-wk-gpu2','node_uid':'3336cdd5-d245-436e-b57c-2f66c6dcaa41','gpu_uuid':'GPU-16128952-b438-556a-00bb-93039ee24e56','max_workspaces':2},'workspaces':{'cps:test-a':{'profile':'interactive-native-pilot-5'},'cit:test-b':{'profile':'interactive-native-pilot-5'}}},'target_pods':{'cps:test-a':{'namespace':'jupyterhub','name':'jupyter-test-a--rtc'},'cit:test-b':{'namespace':'cit-jhub','name':'jupyter-test-b--rtc'}},'prior_descriptor':{'version':2,'states':[{'state_root':'/var/lib/cps-native-gpu/qualification/example/state','records':[{'intent':{'namespace':'cps-native-qa147-20261022','name':'prior-'+str(i),'pod_uid':f'00000000-0000-4000-8000-{i:012d}'}} for i in range(1,13)]}]}}

def test_exact_subjects_least_privilege_and_original_wire():
 a=fixture();old=copy.deepcopy(a);r=mod().build(**a);assert a==old and r['apply_allowed'] is False
 objs=r['objects'];assert len({(x['kind'],x['metadata'].get('namespace'),x['metadata']['name']) for x in objs})==len(objs)
 assert all(x['metadata']['name'].startswith('native-lifecycle147-') for x in objs)
 for x in objs:
  for rule in x.get('rules',[]):
   assert not {'secrets','roles','rolebindings','clusterroles','clusterrolebindings'}.intersection(rule['resources'])
   assert '*'not in rule['verbs'] and '*'not in rule['resources']
   if 'pods'in rule['resources']:assert rule.get('resourceNames') and set(rule['verbs'])<={'get','delete'}
   if 'patch'in rule['verbs']:assert rule['resources']==['configmaps'] and rule['resourceNames']==['cps-native-gpu-allocations']
 policies=[x for x in objs if x['kind']=='ValidatingAdmissionPolicy'];assert len(policies)==2
 for p in policies:
  spec=p['spec'];text=str(spec);assert 'cps-native-node-agent'not in text and 'cps-compute-controller'not in text
  assert spec['failurePolicy']=='Fail' and spec['matchConstraints']['resourceRules'][0]['operations']==['CREATE']
  assert 'request.namespace'not in spec['matchConditions'][0]['expression']
  assert any('request.namespace == "cps-native-lifecycle147"'==v['expression'] for v in spec['validations'])
 nodeqa=next(x for x in objs if x['kind']=='Role' and x['metadata'].get('namespace')=='cps-native-qa147-20261022');assert nodeqa['rules'][0]['verbs']==['get'] and len(nodeqa['rules'][0]['resourceNames'])==12

@pytest.mark.parametrize('fault',['namespace','scope','target','prior-count','duplicate-uid','prior-namespace','pool','extra'])
def test_wrong_scope_and_unbounded_inputs_denied(fault):
 a=fixture()
 if fault=='namespace':a['config']['authority_namespace']='cps-native-runtime'
 if fault=='scope':a['config']['workspaces'].pop('cit:test-b')
 if fault=='target':a['target_pods']['cps:test-a']['namespace']='default'
 if fault=='prior-count':a['prior_descriptor']['states'][0]['records'].pop()
 if fault=='duplicate-uid':a['prior_descriptor']['states'][0]['records'][1]=copy.deepcopy(a['prior_descriptor']['states'][0]['records'][0])
 if fault=='prior-namespace':a['prior_descriptor']['states'][0]['records'][0]['intent']['namespace']='jupyterhub'
 if fault=='pool':a['config']['pool']['node']='k3s-wk-gpu1'
 if fault=='extra':a['config']['extra']=True
 with pytest.raises(ValueError):mod().build(**a)

def test_node_only_namespace_identity_reads_exact_current_and_original():
 objs=mod().build(**fixture())['objects']
 node=next(x for x in objs if x['kind']=='ClusterRole' and x['metadata']['name']=='native-lifecycle147-node-node')
 ns=[r for r in node['rules'] if r['resources']==['namespaces']]
 assert ns==[{'apiGroups':[''],'resources':['namespaces'],'verbs':['get'],'resourceNames':['cps-native-lifecycle147','cps-native-qa147-20261022']}]
 gateway=next(x for x in objs if x['kind']=='ClusterRole' and x['metadata']['name']=='native-lifecycle147-gateway-node')
 assert not any('namespaces'in r['resources'] for r in gateway['rules'])

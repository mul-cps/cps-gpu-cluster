import copy,json,unittest
import aborted_reuse_guard as g

def obj(kind,name,**fields):return dict(apiVersion='v1',kind=kind,metadata={'namespace':'test','name':name,'uid':'uid-'+name},**fields)
def fixture():
 epoch={'boot_id':'boot','driver_generation':'driver','gpu_uuid':'gpu','node_uid':'node'}
 capsule=obj('ConfigMap','capsule',immutable=True,data={'plan.json':json.dumps({'operation':'abort-unacknowledged-policy-handover','sql_before_revision':'target-revision','old_epoch':epoch}),'guard.py':'sealed guard'})
 deps={k:obj('Deployment',k.replace(':','-'),spec={'replicas':0 if k in ('gateway','hub:cps','hub:cit','writer') else 1,'template':{'pinned':1,'spec':{'serviceAccountName':k.replace(':','-')}}})for k in ('gateway','hub:cps','hub:cit','writer','observer','node')}
 plan={'version':1,'operation':'reuse-exact-retained-aborted-source','capsule':capsule,'capsule_sha256':g.sha(capsule['data']),'deployments':deps,'services':{'service':obj('Service','service',spec={'selector':{'fence':'reviewed'}})},'roles':{'role':obj('Role','role',rules=[{'verbs':['get'],'resourceNames':['exact']}])},'heads':{k:obj('ConfigMap','head-'+k.replace(':','-'),data={'head.json':'old-head'})for k in ('gateway','hub:cps','hub:cit','node')},'acks':{k:obj('ConfigMap','ack-'+k.replace(':','-'),data={'ack.json':json.dumps({'revision':'old-revision','process':'old-process','observed_at':'before'})})for k in ('gateway','hub:cps','hub:cit','node')},'ledger':obj('ConfigMap','ledger',data={'state.json':json.dumps({'allocations':{'old':{'state':'released'}}})}),'epoch':epoch,'node_configuration':{'pinned':'config'},'policy':{'pinned':'old-policy'},'target_revision':'target-revision','target_policy_hash':'target-policy'}
 view={k:copy.deepcopy(plan[k])for k in ('capsule','deployments','services','roles','heads','acks','ledger','epoch')};view.update(publishers_absent=True,fenced_endpoints_empty=True)
 return plan,view

class PhysicalGuard(unittest.TestCase):
 def test_valid_fixture_is_only_a_unit_fixture(self):
  p,v=fixture();self.assertIs(g.validate(p,v),True)
 def test_node_only_observation_time_may_advance(self):
  p,v=fixture();v['acks']['node']['data']['ack.json']=json.dumps({'revision':'old-revision','process':'old-process','observed_at':'later'});self.assertIs(g.validate(p,v),True)
 def test_closed_schema_identity_spec_and_runtime_faults_deny(self):
  faults=['extra-plan','bool-version','extra-view','missing-view','capsule-uid','capsule-owner','capsule-deleting','capsule-mutable','capsule-data','capsule-digest','capsule-operation','capsule-target','capsule-epoch','deployment-set','deployment-uid','deployment-spec','typed-spec-alias','service-spec','role-rules','head-data','ack-data','node-ack-semantics','target-ack','target-policy-ack','node-time-only-is-not-enough','publisher-present','publisher-truthy','endpoint-present','endpoint-truthy','epoch','ledger-uid','ledger-data','active-allocation','reviewed-publisher-not-paused']
  for fault in faults:
   with self.subTest(fault=fault):
    p,v=fixture()
    if fault=='extra-plan':p['extra']=1
    elif fault=='bool-version':p['version']=True
    elif fault=='extra-view':v['extra']=1
    elif fault=='missing-view':v.pop('roles')
    elif fault=='capsule-uid':v['capsule']['metadata']['uid']='foreign'
    elif fault=='capsule-owner':v['capsule']['metadata']['ownerReferences']=[{'uid':'foreign'}]
    elif fault=='capsule-deleting':v['capsule']['metadata']['deletionTimestamp']='now'
    elif fault=='capsule-mutable':v['capsule']['immutable']=False
    elif fault=='capsule-data':v['capsule']['data']['guard.py']='foreign'
    elif fault=='capsule-digest':p['capsule_sha256']='foreign'
    elif fault in ('capsule-operation','capsule-target','capsule-epoch'):
     body=json.loads(p['capsule']['data']['plan.json']);key={'capsule-operation':'operation','capsule-target':'sql_before_revision','capsule-epoch':'old_epoch'}[fault];body[key]='foreign';p['capsule']['data']['plan.json']=json.dumps(body);p['capsule_sha256']=g.sha(p['capsule']['data']);v['capsule']=copy.deepcopy(p['capsule'])
    elif fault=='deployment-set':v['deployments'].pop('node')
    elif fault=='deployment-uid':v['deployments']['gateway']['metadata']['uid']='foreign'
    elif fault=='deployment-spec':v['deployments']['gateway']['spec']['replicas']=1
    elif fault=='typed-spec-alias':v['deployments']['node']['spec']['template']['pinned']=True
    elif fault=='service-spec':v['services']['service']['spec']['selector']['fence']='foreign'
    elif fault=='role-rules':v['roles']['role']['rules'][0]['resourceNames'].append('foreign')
    elif fault=='head-data':v['heads']['node']['data']['head.json']='foreign'
    elif fault in ('ack-data','node-ack-semantics','target-ack','target-policy-ack','node-time-only-is-not-enough'):
     key='node'if fault in ('node-ack-semantics','node-time-only-is-not-enough')else'gateway';body=json.loads(v['acks'][key]['data']['ack.json']);body['revision']='target-revision'if fault=='target-ack'else'foreign';body['observed_at']='later'
     if fault=='target-policy-ack':body['policy_hash']='target-policy'
     v['acks'][key]['data']['ack.json']=json.dumps(body)
    elif fault=='publisher-present':v['publishers_absent']=False
    elif fault=='publisher-truthy':v['publishers_absent']=1
    elif fault=='endpoint-present':v['fenced_endpoints_empty']=False
    elif fault=='endpoint-truthy':v['fenced_endpoints_empty']=1
    elif fault=='epoch':v['epoch']['boot_id']='foreign'
    elif fault=='ledger-uid':v['ledger']['metadata']['uid']='foreign'
    elif fault=='ledger-data':v['ledger']['data']['state.json']='foreign'
    elif fault=='active-allocation':p['ledger']['data']['state.json']=json.dumps({'allocations':{'old':{'state':'running'}}});v['ledger']=copy.deepcopy(p['ledger'])
    elif fault=='reviewed-publisher-not-paused':p['deployments']['gateway']['spec']['replicas']=1;v['deployments']=copy.deepcopy(p['deployments'])
    with self.assertRaises((ValueError,KeyError)):g.validate(p,v)

class PublisherAbsence(unittest.TestCase):
 def test_active_pod_and_job_closure(self):
  plan,_=fixture();ns=next(iter(g.publisher_namespaces(plan)));names=g.publisher_namespaces(plan);base={k:[]for k in names}
  self.assertIs(g.publishers_absent(plan,base,base),True)
  for phase in ('Pending','Running','Unknown',None):
   with self.subTest(pod=phase):
    pods=copy.deepcopy(base);pods[ns]=[{'spec':{'serviceAccountName':'writer'},'status':{'phase':phase}}];self.assertIs(g.publishers_absent(plan,pods,base),False)
  for phase in ('Succeeded','Failed'):
   pods=copy.deepcopy(base);pods[ns]=[{'spec':{'serviceAccountName':'writer'},'status':{'phase':phase}}];self.assertIs(g.publishers_absent(plan,pods,base),True)
  pods=copy.deepcopy(base);pods[ns]=[{'spec':{'serviceAccountName':'student'},'status':{'phase':'Running'}}];self.assertIs(g.publishers_absent(plan,pods,base),True)
  for status in ({},{'failed':1},{'active':0},{'conditions':[{'type':'Failed','status':'False'}]},{'conditions':[{'type':'SuccessCriteriaMet','status':'True'}]}):
   with self.subTest(job=status):
    jobs=copy.deepcopy(base);jobs[ns]=[{'spec':{'template':{'spec':{'serviceAccountName':'writer'}}},'status':status}];self.assertIs(g.publishers_absent(plan,base,jobs),False)
  for condition in ('Complete','Failed'):
   jobs=copy.deepcopy(base);jobs[ns]=[{'spec':{'template':{'spec':{'serviceAccountName':'writer'}}},'status':{'conditions':[{'type':condition,'status':'True'}]}}];self.assertIs(g.publishers_absent(plan,base,jobs),True)
  jobs=copy.deepcopy(base);jobs[ns]=[{'spec':{'template':{'spec':{'serviceAccountName':'separate-readonly-sql-operator'}}}}];self.assertIs(g.publishers_absent(plan,base,jobs),True)
  self.assertIs(g.publishers_absent(plan,{},base),False)
  self.assertIs(g.publishers_absent(plan,base,{}),False)

class CompleteCapture(unittest.TestCase):
 def call(self,*,partial=None):
  import sys,types
  from unittest.mock import MagicMock,patch
  p,_=fixture();maps={}
  for value in [p['capsule'],p['ledger'],*p['heads'].values(),*p['acks'].values()]:maps[(value['metadata']['namespace'],value['metadata']['name'])]=value
  core=MagicMock();apps=MagicMock();rbac=MagicMock();batch=MagicMock()
  core.read_namespaced_config_map.side_effect=lambda name,ns,**kw:copy.deepcopy(maps[(ns,name)])
  apps.read_namespaced_deployment.side_effect=lambda name,ns,**kw:copy.deepcopy(next(x for x in p['deployments'].values() if x['metadata']['name']==name))
  core.read_namespaced_service.side_effect=lambda name,ns,**kw:copy.deepcopy(p['services']['service'])
  rbac.read_namespaced_role.side_effect=lambda name,ns,**kw:copy.deepcopy(p['roles']['role'])
  def listing(kind):
   value={'apiVersion':'v1'if kind=='PodList'else'batch/v1','kind':kind,'metadata':{'resourceVersion':'42'},'items':[]}
   if partial==kind:value['metadata']['continue']='next-page-with-publisher'
   return value
  core.list_namespaced_pod.side_effect=lambda ns,**kw:listing('PodList');batch.list_namespaced_job.side_effect=lambda ns,**kw:listing('JobList');core.read_namespaced_endpoints.return_value={'subsets':[]}
  parent=types.ModuleType('cps_compute');parent.__path__=[];nodeparent=types.ModuleType('cps_compute.native_node');nodeparent.__path__=[]
  modules={'cps_compute':parent,'cps_compute.native_node':nodeparent}
  for name in ('native_group_revision','native_group_capture_server','native_node.config','immutable_configmap','policy'):modules['cps_compute.'+name]=types.ModuleType('cps_compute.'+name)
  modules['cps_compute.native_group_revision']._api_document=lambda api,value:copy.deepcopy(value)
  epoch=MagicMock(return_value=types.SimpleNamespace(observe=lambda:copy.deepcopy(p['epoch'])));modules['cps_compute.native_group_capture_server'].HeadNodeEpochObserver=epoch
  configuration=types.SimpleNamespace(deployment=object(),document={'component_declarations':{'node':{'name':'node','service_account_uid':'uid'}},'acknowledgment_targets':{'node':{}}},approval_head={})
  modules['cps_compute.native_node.config'].NodeConfiguration=types.SimpleNamespace(load=lambda *args:configuration)
  modules['cps_compute.immutable_configmap'].ImmutableConfigMapRef=types.SimpleNamespace(from_dict=lambda value:value)
  modules['cps_compute.policy'].Policy=lambda value:value
  with patch.dict(sys.modules,modules):return g.observe(p,core,apps,rbac,batch)
 def test_complete_synthetic_capture_can_reach_validation(self):self.assertIs(self.call(),True)
 def test_partial_pod_list_cannot_authorize_absence(self):
  with self.assertRaises(ValueError):self.call(partial='PodList')
 def test_partial_job_list_cannot_authorize_absence(self):
  with self.assertRaises(ValueError):self.call(partial='JobList')

if __name__=='__main__':unittest.main()

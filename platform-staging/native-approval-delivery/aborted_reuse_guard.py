"""Root-injected observer for one reviewed paused reuse boundary; no import I/O."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json

def sha(value):
 return 'sha256:'+hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def identity(value):
 m=value['metadata']
 if m.get('deletionTimestamp') or m.get('ownerReferences'):raise ValueError('Protected object ownership drift')
 return (value['apiVersion'],value['kind'],m.get('namespace',''),m['name'],m['uid'])

def validate(plan,view):
 if set(plan)!={'version','operation','capsule','capsule_sha256','deployments','services','roles','heads','acks','ledger','epoch','node_configuration','policy','target_revision','target_policy_hash'} or type(plan['version']) is not int or plan['version']!=1 or plan['operation']!='reuse-exact-retained-aborted-source':raise ValueError('Closed reviewed physical reuse plan required')
 if set(view)!={'capsule','deployments','services','roles','heads','acks','ledger','epoch','publishers_absent','fenced_endpoints_empty'}:raise ValueError('Closed actual physical observation required')
 original=plan['capsule'];capsule=view['capsule']
 if identity(capsule)!=identity(original) or capsule.get('immutable') is not True or capsule.get('data')!=original['data'] or sha(capsule['data'])!=plan['capsule_sha256']:raise ValueError('Immutable original abort capsule drift')
 body=json.loads(capsule['data']['plan.json'])
 if body['operation']!='abort-unacknowledged-policy-handover' or body['sql_before_revision']!=plan['target_revision'] or body['old_epoch']!=plan['epoch']:raise ValueError('Abort capsule source/epoch binding differs')
 for group in ('deployments','services','roles','heads','acks'):
  if set(view[group])!=set(plan[group]):raise ValueError('Actual protected object set differs')
  for key,pinned in plan[group].items():
   actual=view[group][key]
   if identity(actual)!=identity(pinned):raise ValueError('Protected identity drift')
   if group in ('deployments','services'):
    if sha(actual['spec'])!=sha(pinned['spec']):raise ValueError('Protected full spec drift')
   elif group=='roles':
    if sha(actual.get('rules'))!=sha(pinned['rules']):raise ValueError('Exact protected Role rules drift')
   elif group=='heads':
    if actual.get('data')!=pinned['data']:raise ValueError('Protected approval selection drift')
   else:
    before=json.loads(pinned['data']['ack.json']);now=json.loads(actual['data']['ack.json'])
    if key=='node':before.pop('observed_at',None);now.pop('observed_at',None)
    if sha(before)!=sha(now):raise ValueError('Paused publisher ACK preimage drift')
    if plan['target_revision'] in json.dumps(actual['data']) or plan['target_policy_hash'] in json.dumps(actual['data']):raise ValueError('Target acknowledgment forbids reuse')
 if view['publishers_absent'] is not True or view['fenced_endpoints_empty'] is not True:raise ValueError('Actual publishers/endpoints must remain absent')
 for key in ('gateway','hub:cps','hub:cit','writer'):
  if plan['deployments'][key]['spec']['replicas']!=0:raise ValueError('Reviewed publishers must be paused')
 if sha(view['epoch'])!=sha(plan['epoch']):raise ValueError('Actual authenticated physical epoch changed')
 if identity(view['ledger'])!=identity(plan['ledger']) or view['ledger'].get('data')!=plan['ledger']['data']:raise ValueError('Exact allocation custody changed')
 if not all(a['state']=='released' for a in json.loads(view['ledger']['data']['state.json'])['allocations'].values()):raise ValueError('Active allocation forbids reuse')
 return True

def publisher_namespaces(plan):
 accounts={}
 for key in ('gateway','hub:cps','hub:cit','writer'):
  d=plan['deployments'][key];accounts.setdefault(d['metadata']['namespace'],set()).add(d['spec']['template']['spec']['serviceAccountName'])
 return accounts

def publishers_absent(plan,pods,jobs):
 accounts=publisher_namespaces(plan)
 if set(pods)!=set(accounts) or set(jobs)!=set(accounts):return False
 for ns,names in accounts.items():
  if any(p['spec'].get('serviceAccountName','default') in names and p.get('status',{}).get('phase') not in ('Succeeded','Failed') for p in pods[ns]):return False
  for job in jobs[ns]:
   if job['spec']['template']['spec'].get('serviceAccountName','default') not in names:continue
   if not any(c.get('type') in ('Complete','Failed') and c.get('status')=='True' for c in job.get('status',{}).get('conditions',[])):return False
 return True

def complete_items(api,value,kind):
 from cps_compute.native_group_revision import _api_document
 document=_api_document(api,value);metadata=document.get('metadata',{})
 version='v1' if kind=='PodList' else 'batch/v1'
 if document.get('apiVersion')!=version or document.get('kind')!=kind or type(document.get('items')) is not list or type(metadata) is not dict:raise ValueError('Exact complete publisher LIST required')
 if metadata.get('continue') not in (None,'') or type(metadata.get('resourceVersion')) is not str or not metadata['resourceVersion']:raise ValueError('Partial publisher LIST cannot prove absence')
 remaining=metadata.get('remainingItemCount')
 if remaining is not None and (type(remaining) is not int or remaining!=0):raise ValueError('Publisher LIST still has unobserved items')
 return document['items']

def capture(plan,core,apps,rbac,batch):
 from cps_compute.native_group_revision import _api_document
 from cps_compute.native_group_capture_server import HeadNodeEpochObserver
 from cps_compute.native_node.config import NodeConfiguration
 from cps_compute.immutable_configmap import ImmutableConfigMapRef
 from cps_compute.policy import Policy
 def doc(api,value):return _api_document(api,value)
 def cm(value):m=value['metadata'];return doc(core,core.read_namespaced_config_map(m['name'],m['namespace'],_request_timeout=15))
 view={'capsule':cm(plan['capsule']),'ledger':cm(plan['ledger'])}
 for group,api,method in (('deployments',apps,apps.read_namespaced_deployment),('services',core,core.read_namespaced_service),('roles',rbac,rbac.read_namespaced_role),('heads',core,core.read_namespaced_config_map),('acks',core,core.read_namespaced_config_map)):
  view[group]={}
  for key,pinned in plan[group].items():
   m=pinned['metadata'];view[group][key]=doc(api,method(m['name'],m['namespace'],_request_timeout=15))
 accounts=publisher_namespaces(plan)
 pods={ns:complete_items(core,core.list_namespaced_pod(ns,_request_timeout=15),'PodList')for ns in accounts}
 jobs={ns:complete_items(batch,batch.list_namespaced_job(ns,_request_timeout=15),'JobList')for ns in accounts}
 view['publishers_absent']=publishers_absent(plan,pods,jobs);empty=True
 for pinned in plan['services'].values():
  m=pinned['metadata'];endpoints=doc(core,core.read_namespaced_endpoints(m['name'],m['namespace'],_request_timeout=15))
  if any(s.get('addresses') or s.get('notReadyAddresses') for s in endpoints.get('subsets',[])):empty=False
 view['fenced_endpoints_empty']=empty
 policy=Policy(deepcopy(plan['policy']));node=NodeConfiguration.load(core,ImmutableConfigMapRef.from_dict(plan['node_configuration']),policy);decl=node.document['component_declarations']['node']
 view['epoch']=HeadNodeEpochObserver(policy,node.deployment,node.document['acknowledgment_targets']['node'],{k:v for k,v in decl.items() if k!='service_account_uid'},core,apps,head_binding=node.approval_head,ttl_seconds=30,now=lambda:datetime.now(timezone.utc)).observe()
 view['acks']['node']=cm(plan['acks']['node'])
 return view

def observe(plan,core,apps,rbac,batch):
 return validate(plan,capture(plan,core,apps,rbac,batch))

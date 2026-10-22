"""Pure bounded pilot RBAC/admission proposal; never apply or auth evidence."""
import ast,copy,hashlib,json,re,uuid
from pathlib import Path
RENDER_SHA='353a818fe4622fd0380619b927cde459ef4a75e1cbc8da49b8bc1545dea958e3'
NS='cps-native-lifecycle147';PREFIX='native-lifecycle147-'
GATEWAY={'kind':'ServiceAccount','namespace':'cps-compute','name':PREFIX+'gateway'}
NODE={'kind':'ServiceAccount','namespace':NS,'name':PREFIX+'node'}
def require(ok,msg):
 if not ok:raise ValueError(msg)
def named(s):return type(s)is str and bool(re.fullmatch(r'[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?',s))
def item(kind,name,namespace=None,**fields):
 api='admissionregistration.k8s.io/v1' if kind.startswith('Validating') else 'rbac.authorization.k8s.io/v1'
 r={'apiVersion':api,'kind':kind,'metadata':{'name':name},**fields}
 if namespace:r['metadata']['namespace']=namespace
 return r

def admission():
 """Execute only the exact hash-pinned pure wire-expression AST span."""
 path=Path(__file__).resolve().parents[2]/'native-group-pilot/render.py';raw=path.read_bytes()
 require(hashlib.sha256(raw).hexdigest()==RENDER_SHA,'Reviewed renderer bytes changed')
 tree=ast.parse(raw);f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render')
 start=next(i for i,n in enumerate(f.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='policy_name' for t in n.targets))
 end=max(i for i,n in enumerate(f.body) if i>start and isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and ast.unparse(n.test)=='pending is not None')
 nodes=f.body[start:end]
 class Actor(ast.NodeTransformer):
  def visit_Constant(self,n):
   replacements={'cps-compute-controller':GATEWAY['name'],'system:serviceaccount:cps-compute:cps-compute-controller':'system:serviceaccount:cps-compute:'+GATEWAY['name']}
   return ast.copy_location(ast.Constant(replacements[n.value]),n) if type(n.value)is str and n.value in replacements else n
 nodes=Actor().visit(ast.Module(body=copy.deepcopy(nodes),type_ignores=[]));ast.fix_missing_locations(nodes)
 env={'namespace':NS,'node':'k3s-wk-gpu2','ACCOUNT':NODE['name'],'objects':[],'item':item,'json':json,'allow_pending_current_groups':False}
 exec(compile(nodes,'<pinned-original-admission-wire>','exec'),env)
 policies=[copy.deepcopy(x) for x in env['objects'] if x['kind']=='ValidatingAdmissionPolicy']
 require(len(policies)==2,'Exact original two admission forms required')
 out=[]
 for p,subject,label in zip(policies,(NODE,GATEWAY),('node','gateway')):
  name=PREFIX+label+'-create-only';p['metadata']['name']=name
  p['spec']['matchConditions']=[{'name':'dedicated-pilot-subject','expression':'request.userInfo.username == '+json.dumps('system:serviceaccount:'+subject['namespace']+':'+subject['name'])}]
  namespace_guard={'expression':'request.namespace == '+json.dumps(NS),'message':'Pilot records stay in the explicit pilot namespace.'}
  if not any(x['expression']==namespace_guard['expression'] for x in p['spec']['validations']):p['spec']['validations'].insert(0,namespace_guard)
  out += [p,item('ValidatingAdmissionPolicyBinding',name,spec={'policyName':name,'validationActions':['Deny']})]
 return out

def build(*,config,target_pods,prior_descriptor):
 require(type(config)is dict and set(config)=={'version','enabled','authority_namespace','policy_hash','pool','workspaces'}
  and type(config['version'])is int and config['version']==1 and config['enabled']is True
  and config['authority_namespace']==NS,'Exact separate v1 pilot namespace/config required')
 pool=config['pool'];require(type(pool)is dict and pool=={'node':'k3s-wk-gpu2','node_uid':'3336cdd5-d245-436e-b57c-2f66c6dcaa41','gpu_uuid':'GPU-16128952-b438-556a-00bb-93039ee24e56','max_workspaces':2}
  and type(pool['max_workspaces'])is int,'Exact selected GPU2 pool required')
 require(type(config['policy_hash'])is str and re.fullmatch(r'sha256:[a-f0-9]{64}',config['policy_hash']),'Pinned derived pilot policy required')
 scopes=config['workspaces'];require(type(scopes)is dict and len(scopes)==2 and all(type(k)is str and re.fullmatch(r'(cps|cit):[A-Za-z0-9_.-]{1,128}',k) and v=={'profile':'interactive-native-pilot-5'} for k,v in scopes.items()),'Exact two5 workspace scopes required')
 require(type(target_pods)is dict and set(target_pods)==set(scopes),'Explicit reviewed target Pod names required')
 targets={}
 for scope,pod in target_pods.items():
  require(type(pod)is dict and set(pod)=={'namespace','name'} and pod['namespace']=={'cps':'jupyterhub','cit':'cit-jhub'}[scope.split(':')[0]] and named(pod['name']),'Exact owning-Hub target names required')
  targets.setdefault(pod['namespace'],set()).add(pod['name'])
 require(sum(map(len,targets.values()))==2,'Distinct current target names required')
 require(type(prior_descriptor)is dict and set(prior_descriptor)=={'version','states'} and type(prior_descriptor['version'])is int and prior_descriptor['version']==2 and type(prior_descriptor['states'])is list and 1<=len(prior_descriptor['states'])<=8,'Explicit original prior descriptor required')
 prior=[]
 for state in prior_descriptor['states']:
  require(type(state)is dict and set(state)=={'state_root','records'} and type(state['state_root'])is str and state['state_root'].startswith('/var/lib/cps-native-gpu/qualification/') and '..'not in Path(state['state_root']).parts and type(state['records'])is list,'Closed original prior state required')
  prior+=state['records']
 require(len(prior)==12,'All12 explicit original prior records required')
 uids=set();oldnames=set()
 for record in prior:
  require(type(record)is dict and type(record.get('intent'))is dict,'Actual original record intent required')
  i=record['intent'];uid=i.get('pod_uid')
  try:valid=type(uid)is str and str(uuid.UUID(uid))==uid and uuid.UUID(uid).int!=0
  except (ValueError,AttributeError):valid=False
  require(valid and uid not in uids and i.get('namespace')=='cps-native-qa147-20261022' and named(i.get('name')),'Distinct original QA UID/name required')
  uids.add(uid);oldnames.add(i['name'])
 objects=[]
 def bind(kind,name,ns,rules,subject):
  objects.append(item(kind,name,ns,rules=rules));objects.append(item('ClusterRoleBinding' if kind=='ClusterRole' else 'RoleBinding',name,ns,subjects=[copy.deepcopy(subject)],roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':kind,'name':name}))
 def rule(resource,verbs,names=None):
  r={'apiGroups':[''],'resources':[resource],'verbs':verbs}
  if names is not None:r['resourceNames']=sorted(names)
  return r
 for label,subject in [('gateway',GATEWAY),('node',NODE)]:
  bind('ClusterRole',PREFIX+label+'-node',None,[rule('nodes',['get'],[pool['node']])]+([rule('namespaces',['get'],[NS,'cps-native-qa147-20261022'])] if label=='node' else []),subject)
  bind('Role',PREFIX+label+'-records',NS,[rule('configmaps',['get','create'] if label=='gateway' else ['get','list','create'])]+([rule('configmaps',['patch'],['cps-native-gpu-allocations'])] if label=='gateway' else []),subject)
  for ns,names in targets.items():bind('Role',PREFIX+label+'-targets',ns,[rule('pods',['get','delete'] if label=='node' else ['get'],names)],subject)
 bind('Role',PREFIX+'node-prior-qa','cps-native-qa147-20261022',[rule('pods',['get'],oldnames)],NODE)
 objects+=admission()
 return {'version':1,'proposal_only':True,'apply_allowed':False,'objects':objects,'renderer_source_sha256':RENDER_SHA,
  'subjects':{'gateway':copy.deepcopy(GATEWAY),'node':copy.deepcopy(NODE)},'prior_record_count':12,
  'pending':['Root explicit SubjectAccessReview with actual user/groups (never Rancher --as)','Server CEL typechecking and positive/negative CREATE qualification before binding promotion','Actual SA UID verification and independently authenticated full prior descriptor','GET rights are not proof of original custody or global hardware retirement']}

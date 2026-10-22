"""Pure exact-two fresh provisioning permissions; no executor or NAS authority.

VAP server typechecking/negative qualification and an independent archive-route
deny boundary remain required. Kubernetes RBAC cannot block NAS archive RPC.
"""
import copy,hashlib,json,re
SERVER='193.170.30.58';ACTOR='system:serviceaccount:cps-compute:native-lifecycle147-gateway'
PREFIX='native-lifecycle147-storage-';ROOTS={1:'/mnt/persistent1/cps_persistent1_shared/compute',2:'/mnt/persistent1/cps_compute_workspaces'}
def require(ok,msg):
 if not ok:raise ValueError(msg)
def item(kind,name,namespace=None,**kw):
 d={'apiVersion':'admissionregistration.k8s.io/v1' if kind.startswith('Validating') else 'rbac.authorization.k8s.io/v1','kind':kind,'metadata':{'name':name},**kw}
 if namespace:d['metadata']['namespace']=namespace
 return d

def validate(provider,targets):
 require(type(provider)is dict and set(provider)<={'enabled','ssh','storageVersion','readonlyMounts','verificationImage','allowedOperations','allowedTargets'} and provider.get('enabled')is True and provider.get('allowedOperations')==['provision'],'Actual enabled provider references required')
 version=provider.get('storageVersion',1);require(type(version)is int and version in ROOTS,'Actual supported storageVersion required')
 ssh=provider.get('ssh');require(type(ssh)is dict and set(ssh)<={'host','user','port','identity_file','known_hosts_file'} and ssh.get('host')in(SERVER,'truenas.local','artifacts.cps-artifacts-relay.svc.cluster.local') and ssh.get('port',8022)==8022 and type(ssh.get('user'))is str and re.fullmatch(r'[a-z_][a-z0-9_-]*',ssh['user']),'Existing fixed NAS SSH provider required')
 for k in ('identity_file','known_hosts_file'):
  require(type(ssh.get(k))is str and ssh[k].startswith('/storage-bridge/') and '..'not in ssh[k].split('/'),'Actual read-only storage bridge file references required')
 require(type(provider.get('allowedTargets'))is list and provider['allowedTargets']==targets,'Exact two NAS provisioning targets must be guarded before metadata/NAS')
 require(type(targets)is list and len(targets)==2,'Exactly two explicit fresh targets required')
 out=[]
 for t in targets:
  require(type(t)is dict and set(t)=={'source','workspace','group_id'} and t['source']in('cps','cit') and all(type(t[k])is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',t[k]) for k in ('workspace','group_id')),'Closed source/workspace/group target required')
  h=hashlib.sha256((t['source']+'\0'+t['group_id']).encode()).hexdigest()
  out.append({**copy.deepcopy(t),'namespace':{'cps':'jupyterhub','cit':'cit-jhub'}[t['source']],'group_hash':h,'name':'cps-workspace-'+h[:40],'path':ROOTS[version]+'/'+t['source']+'/'+h,'storage_version':version})
 require(len({(t['source'],t['workspace']) for t in out})==len({t['name'] for t in out})==2,'Distinct fresh workspaces and group storage names required')
 return out

def build(*,provider,targets):
 rows=validate(provider,targets);objects=[];subject=[{'kind':'ServiceAccount','namespace':'cps-compute','name':'native-lifecycle147-gateway'}]
 def bind(kind,name,ns,rules):
  objects.extend([item(kind,name,ns,rules=rules),item('ClusterRoleBinding' if kind=='ClusterRole' else 'RoleBinding',name,ns,subjects=subject,roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':kind,'name':name})])
 bind('ClusterRole',PREFIX+'inventory',None,[{'apiGroups':[''],'resources':['persistentvolumes','persistentvolumeclaims','pods'],'verbs':['list']},{'apiGroups':[''],'resources':['persistentvolumes'],'verbs':['create']},{'apiGroups':[''],'resources':['persistentvolumes'],'verbs':['get'],'resourceNames':sorted(t['name'] for t in rows)}])
 for ns in sorted({t['namespace'] for t in rows}):
  bind('Role',PREFIX+'claims',ns,[{'apiGroups':[''],'resources':['persistentvolumeclaims'],'verbs':['create']},{'apiGroups':[''],'resources':['persistentvolumeclaims'],'verbs':['get'],'resourceNames':sorted(t['name'] for t in rows if t['namespace']==ns)}])
 def q(x):return json.dumps(x)
 for resource,label in [('persistentvolumes','pv'),('persistentvolumeclaims','pvc')]:
  alternatives=[]
  for t in rows:
   clauses=['object.metadata.name == '+q(t['name']),"has(object.metadata.labels) && size(object.metadata.labels) == 2", "object.metadata.labels['cps.compute/workspace-storage'] == "+q(t['group_hash'][:63]),"object.metadata.labels['cps.compute/source'] == "+q(t['source']),"object.spec.accessModes == ['ReadWriteMany']","object.spec.storageClassName == ''","(!has(object.spec.volumeMode) || object.spec.volumeMode == 'Filesystem')"]
   if label=='pv':clauses += ["dyn(object.spec).capacity['storage'] == '1Ti'","object.spec.persistentVolumeReclaimPolicy == 'Retain'","object.spec.mountOptions == ['hard','nfsvers=4.1']",'has(object.spec.nfs) && object.spec.nfs.server == '+q(SERVER)+' && object.spec.nfs.path == '+q(t['path'])+' && object.spec.nfs.readOnly == false','has(object.spec.claimRef) && object.spec.claimRef.namespace == '+q(t['namespace'])+' && object.spec.claimRef.name == '+q(t['name'])+" && (!has(object.spec.claimRef.uid) || object.spec.claimRef.uid == '')"]
   else:clauses += ['request.namespace == '+q(t['namespace']),'object.spec.volumeName == '+q(t['name']),"dyn(object.spec.resources).requests['storage'] == '1Ti'","(!has(dyn(object.spec.resources).limits) || size(dyn(object.spec.resources).limits) == 0)","!has(object.spec.selector) && !has(object.spec.dataSource) && !has(object.spec.dataSourceRef)"]
   alternatives.append('('+' && '.join(clauses)+')')
  spec={'failurePolicy':'Fail','matchConstraints':{'resourceRules':[{'apiGroups':[''],'apiVersions':['v1'],'operations':['CREATE'],'resources':[resource],'scope':'Cluster' if label=='pv' else 'Namespaced'}]},'matchConditions':[{'name':'dedicated-pilot-storage-subject','expression':'request.userInfo.username == '+q(ACTOR)}],'validations':[{'expression':' || '.join(alternatives),'message':'Only the exact two reviewed fresh retained workspace objects are permitted.'},{'expression':'!has(object.metadata.ownerReferences) || size(object.metadata.ownerReferences) == 0','message':'Retained workspace storage cannot inherit owner garbage collection.'}]}
  name=PREFIX+label;objects += [item('ValidatingAdmissionPolicy',name,spec=spec),item('ValidatingAdmissionPolicyBinding',name,spec={'policyName':name,'validationActions':['Deny']})]
 return {'version':1,'proposal_only':True,'apply_allowed':False,'targets':rows,'objects':objects,'archive_authorized':False,'pending':['Server CEL schema/typechecking and exact positive/negative qualification before admission binding promotion','SDK enforcement of allowedOperations and exact allowedTargets before metadata/NAS; config alone is not enforcement','Root authenticate actual provider refs, fresh target absence, Secret mounts and direct SubjectAccessReview']}

PARENT_NAME='cps-compute-private-workspace-pv'
PARENT_PREDICATE="request.userInfo.username == 'system:serviceaccount:cps-compute:cps-compute-controller'"
def _parent_ref(parent):
 require(type(parent)is dict and parent.get('apiVersion')=='admissionregistration.k8s.io/v1' and parent.get('kind')=='ValidatingAdmissionPolicy','Actual parent admission policy required')
 meta=parent.get('metadata',{})
 require(type(meta)is dict and meta.get('name')==PARENT_NAME and all(type(meta.get(k))is str and meta[k] for k in ('uid','resourceVersion')) and type(parent.get('spec'))is dict,'Exact parent identity and spec required')
 return {k:meta[k] for k in ('name','uid','resourceVersion')}
def _parent_patch(ref,before,after):
 return [{'op':'test','path':'/metadata/uid','value':ref['uid']},{'op':'test','path':'/metadata/resourceVersion','value':ref['resourceVersion']},{'op':'test','path':'/spec','value':copy.deepcopy(before)},{'op':'replace','path':'/spec','value':copy.deepcopy(after)}]
def parent_exception(parent,*,expected_ref,provider,targets):
 """Proposal only. Retire immediately after the two PV creates; no apply path.

 Root must authenticate the captured parent and qualify both admission layers.
 All original server/path/Retain and UPDATE checks remain byte-for-byte intact.
 """
 ref=_parent_ref(parent);require(ref==expected_ref,'Parent UID/resourceVersion preimage mismatch')
 rows=validate(provider,targets);before=copy.deepcopy(parent['spec']);after=copy.deepcopy(before)
 validations=after.get('validations')
 require(type(validations)is list and all(type(v)is dict and type(v.get('expression'))is str for v in validations),'Actual parent validation expressions required')
 require(sum(v['expression'].count(PARENT_PREDICATE) for v in validations)==1,'Exactly one parent actor predicate required')
 replacement='('+PARENT_PREDICATE+" || (request.operation == 'CREATE' && request.userInfo.username == "+json.dumps(ACTOR)+' && object.metadata.name in '+json.dumps(sorted(t['name'] for t in rows))+'))'
 for v in validations:v['expression']=v['expression'].replace(PARENT_PREDICATE,replacement)
 return {'version':1,'apply_allowed':False,'expected_ref':ref,'before_spec':before,'after_spec':after,'replacement':replacement,'patch':_parent_patch(ref,before,after),'rollback_requires':'Fresh actual parent readback; call parent_exception_rollback after both PV creates; UID and exact modified spec must still match.'}
def parent_exception_rollback(actual,plan):
 """CAS rollback with fresh actual RV, never a guessed post-patch RV."""
 ref=_parent_ref(actual)
 require(ref['uid']==plan['expected_ref']['uid'] and actual['spec']==plan['after_spec'],'Parent changed after exception; rollback denied')
 return _parent_patch(ref,actual['spec'],plan['before_spec'])

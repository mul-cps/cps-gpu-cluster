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
 ssh=provider.get('ssh');require(type(ssh)is dict and set(ssh)<={'host','user','port','identity_file','known_hosts_file'} and ssh.get('host')in(SERVER,'truenas.local') and ssh.get('port',8022)==8022 and type(ssh.get('user'))is str and re.fullmatch(r'[a-z_][a-z0-9_-]*',ssh['user']),'Existing fixed NAS SSH provider required')
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
   if label=='pv':clauses += ["object.spec.capacity['storage'] == '1Ti'","object.spec.persistentVolumeReclaimPolicy == 'Retain'","object.spec.mountOptions == ['hard','nfsvers=4.1']",'has(object.spec.nfs) && object.spec.nfs.server == '+q(SERVER)+' && object.spec.nfs.path == '+q(t['path'])+' && object.spec.nfs.readOnly == false','has(object.spec.claimRef) && object.spec.claimRef.namespace == '+q(t['namespace'])+' && object.spec.claimRef.name == '+q(t['name'])+" && (!has(object.spec.claimRef.uid) || object.spec.claimRef.uid == '')"]
   else:clauses += ['request.namespace == '+q(t['namespace']),'object.spec.volumeName == '+q(t['name']),"object.spec.resources.requests['storage'] == '1Ti'","(!has(object.spec.resources.limits) || size(object.spec.resources.limits) == 0)","!has(object.spec.selector) && !has(object.spec.dataSource) && !has(object.spec.dataSourceRef)"]
   alternatives.append('('+' && '.join(clauses)+')')
  spec={'failurePolicy':'Fail','matchConstraints':{'resourceRules':[{'apiGroups':[''],'apiVersions':['v1'],'operations':['CREATE'],'resources':[resource],'scope':'Cluster' if label=='pv' else 'Namespaced'}]},'matchConditions':[{'name':'dedicated-pilot-storage-subject','expression':'request.userInfo.username == '+q(ACTOR)}],'validations':[{'expression':' || '.join(alternatives),'message':'Only the exact two reviewed fresh retained workspace objects are permitted.'},{'expression':'!has(object.metadata.ownerReferences) || size(object.metadata.ownerReferences) == 0','message':'Retained workspace storage cannot inherit owner garbage collection.'}]}
  name=PREFIX+label;objects += [item('ValidatingAdmissionPolicy',name,spec=spec),item('ValidatingAdmissionPolicyBinding',name,spec={'policyName':name,'validationActions':['Deny']})]
 return {'version':1,'proposal_only':True,'apply_allowed':False,'targets':rows,'objects':objects,'archive_authorized':False,'pending':['Server CEL schema/typechecking and exact positive/negative qualification before admission binding promotion','SDK enforcement of allowedOperations and exact allowedTargets before metadata/NAS; config alone is not enforcement','Root authenticate actual provider refs, fresh target absence, Secret mounts and direct SubjectAccessReview']}

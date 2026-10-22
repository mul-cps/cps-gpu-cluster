"""Pure reviewed storage-reuse intent. Never opens SQLite, NAS or Kubernetes.

Hash pins establish consistency, NOT reviewer authentication or fresh physical
storage evidence. Root must authenticate captured inputs and recheck them inside
its actual canonical-database transaction before attaching unchanged bytes.
"""
import copy,hashlib,json,re
PROFILE='interactive-native-pilot-5'
ROOTS={1:'/mnt/persistent1/cps_persistent1_shared/compute',2:'/mnt/persistent1/cps_compute_workspaces'}
def require(ok,msg):
 if not ok:raise ValueError(msg)
def sha(value):
 try:return 'sha256:'+hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
 except (TypeError,ValueError):raise ValueError('Canonical finite reviewed JSON required') from None

def plan(*,source,new_registration,expected_registration_sha256,policy,canonical_people,
         old_record,expected_old_record_sha256,lifecycle,reservations,bindings,existing_new_row,actor):
 require(source in ('cps','cit') and type(actor)is str and 0<len(actor)<=128 and actor==actor.strip(),'Explicit reviewed source/operator required')
 require(type(new_registration)is dict and type(old_record)is dict and sha(new_registration)==expected_registration_sha256
  and sha(old_record)==expected_old_record_sha256,'Exact independently reviewed old/new record pins required')
 require(type(reservations)is list and not reservations and type(bindings)is list and not bindings
  and existing_new_row is None,'Absent new row and no reservations/bindings required')
 require(lifecycle in (None,'active'),'Existing group storage lifecycle must be unfenced')
 fields={'workspace','owner','server','members','principal','profiles','ceiling','namespace','pod','policy_hash','group_id','course_id','term_id'}
 require(set(new_registration)==fields,'Closed explicit new workspace registration required')
 n=new_registration;o=old_record;namespace={'cps':'jupyterhub','cit':'cit-jhub'}[source]
 require(all(type(n[k])is str and bool(n[k]) and not any(c.isspace() for c in n[k]) for k in fields-{'members','profiles','ceiling'})
  and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',n['workspace']) and n['principal']=='workspace:'+source+':'+n['workspace']
  and n['namespace']==namespace,'Exact source-owned new registration identity required')
 require(type(o.get('workspace'))is str and o.get('principal')=='workspace:'+source+':'+o['workspace']
  and o.get('namespace')==namespace and o.get('workspace')!=n['workspace'] and o.get('owner')!=n['owner']
  and all(type(o.get(k))is str and o[k]==n[k] for k in ('group_id','course_id','term_id')),
  'Distinct new identity and unchanged source/group/course/term required')
 require(type(canonical_people)is dict and source in canonical_people and all(type(v)is dict for v in canonical_people.values()),'Actual canonical directory map required')
 require(all(type(k)is str and type(v)is str for directory in canonical_people.values() for k,v in directory.items()),'Flat canonical directory required')
 people={p for v in canonical_people.values() for p in v.values()}
 require(type(n['members'])is list and 1<=len(n['members'])<=128 and all(type(x)is str and x in people for x in n['members'])
  and len(set(n['members']))==len(n['members']) and n['owner']not in canonical_people[source]
  and n['owner']not in n['members'],'Verified canonical members and distinct neutral owner required')
 require(type(o.get('members'))is list and o['members']==n['members'],'Storage reuse cannot change original canonical member roster')
 require(type(policy)is dict and type(policy.get('profiles'))is dict,'Actual derived pilot policy document required')
 unhashed={k:v for k,v in policy.items() if k!='policyHash'};ph=sha(unhashed)
 require(policy.get('policyHash')==ph and n['policy_hash']==ph and o.get('policy_hash')!=ph,
  'Honest derived policy hash distinct from retained production record required')
 profile=policy.get('profiles',{}).get(PROFILE,{})
 require(type(profile)is dict and type(profile.get('gpu'))is dict,'Closed pilot profile required')
 require(n['profiles']==[PROFILE] and n['ceiling']=={'cpu':'4','memory':'16Gi','gpuMemoryGiB':5}
  and profile.get('enabled') is False and profile.get('kind')=='interactive' and profile.get('queue')=='interactive'
  and profile.get('cpu')=='4' and profile.get('memory')=='16Gi' and type(profile.get('images'))is list and bool(profile['images'])
  and all(type(i)is str and re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}',i) for i in profile['images'])
  and profile.get('gpu',{}).get('mode')=='shared' and type(profile['gpu'].get('nominalMemoryGiB'))is int
  and profile['gpu']['nominalMemoryGiB']==5 and profile['gpu'].get('qualification')=={
   'mechanism':'r615-native-cgroup-managed-deny','status':'pilot-unqualified'},'Exact disabled unqualified5 pilot and ceiling required')
 storage=o.get('storage');require(type(storage)is dict and storage.get('state')=='active' and storage.get('namespace')==namespace,'Actual original active source storage required')
 version=storage.get('storage_version',1);group_hash=hashlib.sha256((source+'\0'+n['group_id']).encode()).hexdigest()
 require(type(version)is int and version in ROOTS and storage.get('group_hash')==group_hash
  and storage.get('path')==ROOTS[version]+'/'+source+'/'+group_hash
  and all(type(storage.get(k))is str and bool(storage[k]) for k in ('pv','pvc')),
  'Existing deterministic source/group retained storage binding required')
 evidence=storage.get('evidence');expected={'permissions_verified':True,'acltype':'POSIX1E','aclmode':'DISCARD','uid':1000,'gid':1000,'mode':'0770','default_acl':False}
 require(type(evidence)is dict and all(type(evidence.get(k))is type(v) and evidence[k]==v for k,v in expected.items()),
  'Original verified private permission evidence must be retained, never invented')
 require(type(storage.get('readonly_mounts'))is list,'Original readonly storage mounts required')
 for mount in storage['readonly_mounts']:
  require(type(mount)is dict and set(mount)=={'server','path','mount_path','read_only'} and mount['read_only']is True,'Exact original readonly mount required')
 return {'version':1,'operation':'plain_lifecycle_storage_reuse_proposal','execute_allowed':False,
  'registration':{'method':'PUT','path':'/internal/v1/workspaces','source':source,'body':copy.deepcopy(n)},
  'trusted_storage_binding':{'api':'ControlStore.set_storage','source':source,'workspace':n['workspace'],'storage':copy.deepcopy(storage)},
  'preimages':{'old_record_sha256':expected_old_record_sha256,'new_registration_sha256':expected_registration_sha256,
   'original_storage_sha256':sha(storage),'new_row':None,'group_lifecycle':lifecycle,'reservations':[],'bindings':[]},
  'audit':{'actor':actor,'target':source+':'+n['workspace'],'outcome':'storage_reuse_proposed','previous':None,
   'new':{'registration_sha256':expected_registration_sha256,'storage_sha256':sha(storage)},'retained_original_record_sha256':expected_old_record_sha256},
  'required_before_local_transaction':['Authenticate independent review pins; hashes alone confer no authority',
   'Fresh exact original record/storage/lifecycle and actual retained PV/PVC/permissions identity check',
   'Register new neutral identity through existing authenticated API and live Hub provenance check',
   'Inside canonical local transaction recheck exact newly registered row, no reservations/bindings, untouched old row',
   'Attach exact original storage bytes, audit actual outcome and verify readback; do not call NAS provision/archive',
   'Real grants must include pilot alias; plan does not create grants or authorize Start']}

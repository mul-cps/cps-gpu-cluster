import copy,hashlib,json,importlib.util
from pathlib import Path
import pytest
P=Path(__file__).with_name('plain_lifecycle_storage_reuse.py')
def h(v):return 'sha256:'+hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def module():
 s=importlib.util.spec_from_file_location('reuse',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def fixture():
 group='reviewed-test-group';gh=hashlib.sha256(('cps\0'+group).encode()).hexdigest()
 policy={'version':'0.1.2','profiles':{'interactive-native-pilot-5':{'enabled':False,'kind':'interactive','queue':'interactive','cpu':'4','memory':'16Gi','images':['image@sha256:'+'a'*64],'gpu':{'mode':'shared','nominalMemoryGiB':5,'qualification':{'mechanism':'r615-native-cgroup-managed-deny','status':'pilot-unqualified'}}}}};policy['policyHash']=h(policy)
 old={'workspace':'retained-test','principal':'workspace:cps:retained-test','owner':'retained-neutral','members':['person:test-member'],'group_id':group,'course_id':'test-course','term_id':'test-term','namespace':'jupyterhub','policy_hash':'sha256:'+'b'*64,'storage':{'namespace':'jupyterhub','storage_version':2,'state':'active','pv':'actual-retained-pv','pvc':'actual-retained-pvc','path':'/mnt/persistent1/cps_compute_workspaces/cps/'+gh,'group_hash':gh,'readonly_mounts':[],'evidence':{'permissions_verified':True,'acltype':'POSIX1E','aclmode':'DISCARD','uid':1000,'gid':1000,'mode':'0770','default_acl':False}}}
 new={'workspace':'new-lifecycle-test','owner':'new-neutral','server':'rtc','members':['person:test-member'],'principal':'workspace:cps:new-lifecycle-test','profiles':['interactive-native-pilot-5'],'ceiling':{'cpu':'4','memory':'16Gi','gpuMemoryGiB':5},'namespace':'jupyterhub','pod':'jupyter-new-neutral--rtc','policy_hash':policy['policyHash'],'group_id':group,'course_id':'test-course','term_id':'test-term'}
 return dict(source='cps',new_registration=new,expected_registration_sha256=h(new),policy=policy,canonical_people={'cps':{'actual-user':'person:test-member'}},old_record=old,expected_old_record_sha256=h(old),lifecycle='active',reservations=[],bindings=[],existing_new_row=None,actor='reviewed-root-operator')

def test_plan_exact_original_storage_no_mutation_or_production_overwrite():
 a=fixture();saved=copy.deepcopy(a);r=module().plan(**a);assert a==saved
 assert r['registration']['method']=='PUT' and r['registration']['path']=='/internal/v1/workspaces'
 assert 'storage'not in r['registration']['body']
 assert r['trusted_storage_binding']['storage']==a['old_record']['storage']
 assert r['trusted_storage_binding']['workspace']==a['new_registration']['workspace']
 assert r['execute_allowed'] is False and r['audit']['outcome']=='storage_reuse_proposed'
 assert r['preimages']['old_record_sha256']==h(a['old_record'])

@pytest.mark.parametrize('fault',['oldhash','newhash','group','source','inactive','lifecycle','reservation','binding','overwrite','sameid','sameowner','policy','profile','member','evidence','path','extra','old-members'])
def test_unreviewed_or_live_or_inconsistent_reuse_denied(fault):
 a=fixture()
 if fault=='oldhash':a['expected_old_record_sha256']='sha256:'+'0'*64
 if fault=='newhash':a['expected_registration_sha256']='sha256:'+'0'*64
 if fault=='group':a['new_registration']['group_id']='other'
 if fault=='source':a['source']='cit'
 if fault=='inactive':a['old_record']['storage']['state']='archived'
 if fault=='lifecycle':a['lifecycle']='provisioning'
 if fault=='reservation':a['reservations']=[{'actual':'reservation'}]
 if fault=='binding':a['bindings']=[{'actual':'binding'}]
 if fault=='overwrite':a['existing_new_row']=copy.deepcopy(a['new_registration'])
 if fault=='sameid':a['new_registration']['workspace']=a['old_record']['workspace']
 if fault=='sameowner':a['new_registration']['owner']=a['old_record']['owner']
 if fault=='policy':a['new_registration']['policy_hash']=a['old_record']['policy_hash']
 if fault=='profile':a['new_registration']['profiles']=['interactive-shared-5']
 if fault=='old-members':a['old_record']['members']=['person:different']
 if fault=='member':a['new_registration']['members']=['person:unknown']
 if fault=='evidence':a['old_record']['storage']['evidence'].pop('permissions_verified')
 if fault=='path':a['old_record']['storage']['path']='/mnt/arbitrary'
 if fault=='extra':a['new_registration']['storage']=a['old_record']['storage']
 # Re-pin deliberate semantic mutations so tests exercise actual guards as well.
 if fault not in ('oldhash','newhash'):
  a['expected_old_record_sha256']=h(a['old_record']);a['expected_registration_sha256']=h(a['new_registration'])
 with pytest.raises(ValueError):module().plan(**a)

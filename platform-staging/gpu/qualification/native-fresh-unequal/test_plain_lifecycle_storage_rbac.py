import copy,importlib.util
from pathlib import Path
import pytest
P=Path(__file__).with_name('plain_lifecycle_storage_rbac.py')
def mod():
 s=importlib.util.spec_from_file_location('sr',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def targets():return [{'source':'cps','workspace':'fresh-a','group_id':'lifecycle147-fresh-a'},{'source':'cit','workspace':'fresh-b','group_id':'lifecycle147-fresh-b'}]
def provider():return {'enabled':True,'allowedOperations':['provision'],'allowedTargets':targets(),'storageVersion':2,'ssh':{'host':'193.170.30.58','user':'cps-workspace-control','port':8022,'identity_file':'/storage-bridge/id_ed25519','known_hosts_file':'/storage-bridge/known_hosts'},'readonlyMounts':[]}
def test_two_fresh_exact_storage_objects_and_shape_bound_admission():
 t=targets();old=copy.deepcopy(t);r=mod().build(provider=provider(),targets=t);assert t==old
 assert len(r['targets'])==2 and r['apply_allowed']is False
 policies=[x for x in r['objects'] if x['kind']=='ValidatingAdmissionPolicy'];assert len(policies)==2
 for p in policies:
  text=str(p);assert 'system:serviceaccount:cps-compute:native-lifecycle147-gateway'in text
  assert '193.170.30.58'in text or p['metadata']['name'].endswith('pvc')
  assert p['spec']['matchConstraints']['resourceRules'][0]['operations']==['CREATE']
 for o in r['objects']:
  for rule in o.get('rules',[]):
   assert not {'delete','patch','update'}.intersection(rule['verbs'])
   assert not {'secrets','roles','rolebindings','jobs'}.intersection(rule['resources'])
   assert not ('pods'in rule['resources'] and 'create'in rule['verbs'])
   if 'get'in rule['verbs']:assert rule.get('resourceNames')
 for row in r['targets']:
  assert row['path'].startswith('/mnt/persistent1/cps_compute_workspaces/'+row['source']+'/')
  assert row['name']=='cps-workspace-'+row['group_hash'][:40]
  assert any(row['name']in str(p) and row['path']in str(p) for p in policies)

@pytest.mark.parametrize('fault',['extra','same','source','group','version','host','port','enabled'])
def test_unbounded_inputs_denied(fault):
 t=targets();p=provider()
 if fault=='extra':t[0]['path']='/mnt/arbitrary'
 if fault=='same':t[1]=t[0]
 if fault=='source':t[0]['source']='other'
 if fault=='group':t[0]['group_id']='../escape'
 if fault=='version':p['storageVersion']=3
 if fault=='host':p['ssh']['host']='other'
 if fault=='port':p['ssh']['port']=22
 if fault=='enabled':p['enabled']=False
 with pytest.raises(ValueError):mod().build(provider=p,targets=t)


def test_kubernetes_permissions_cannot_be_claimed_without_nas_target_guard():
 p=provider();p.pop('allowedTargets')
 with pytest.raises(ValueError):mod().build(provider=p,targets=targets())
 p=provider();p['allowedTargets']=[]
 with pytest.raises(ValueError):mod().build(provider=p,targets=targets())

def test_actual_existing_relay_provider_accepts_without_changing_nfs_server():
 p=provider();p['ssh'].update(host='artifacts.cps-artifacts-relay.svc.cluster.local',user='truenas_admin',identity_file='/storage-bridge/identity')
 r=mod().build(provider=p,targets=targets())
 pv=next(x for x in r['objects'] if x['kind']=='ValidatingAdmissionPolicy' and x['metadata']['name'].endswith('-pv'))
 assert '193.170.30.58' in str(pv) and 'artifacts.cps-artifacts-relay.svc.cluster.local'not in str(pv)
 p['ssh']['host']='foreign.example'
 with pytest.raises(ValueError):mod().build(provider=p,targets=targets())

def test_quantity_subtrees_use_dynamic_type_only_without_dropping_guards():
 rows=mod().build(provider=provider(),targets=targets())['objects']
 pv=next(x for x in rows if x['kind']=='ValidatingAdmissionPolicy' and x['metadata']['name'].endswith('-pv'))
 pvc=next(x for x in rows if x['kind']=='ValidatingAdmissionPolicy' and x['metadata']['name'].endswith('-pvc'))
 pve=pv['spec']['validations'][0]['expression'];pvce=pvc['spec']['validations'][0]['expression']
 assert pve.count("dyn(object.spec).capacity['storage'] == '1Ti'")==2
 assert pvce.count("dyn(object.spec.resources).requests['storage'] == '1Ti'")==2
 assert pvce.count('(!has(dyn(object.spec.resources).limits) || size(dyn(object.spec.resources).limits) == 0)')==2
 assert 'object.spec.nfs.server' in pve and 'object.spec.volumeName' in pvce
 assert pv['spec']['failurePolicy']==pvc['spec']['failurePolicy']=='Fail'

def parent():
 return {'apiVersion':'admissionregistration.k8s.io/v1','kind':'ValidatingAdmissionPolicy','metadata':{'name':'cps-compute-private-workspace-pv','uid':'2f1fa127-7c14-450e-9a69-b420a6fc207c','resourceVersion':'360103757'},'spec':{'failurePolicy':'Fail','matchConstraints':{'resourceRules':[{'operations':['CREATE','UPDATE'],'resources':['persistentvolumes']}]},'validations':[{'expression':"path_guard && server_guard && Retain_guard && (request.userInfo.username == 'system:serviceaccount:cps-compute:cps-compute-controller' || (request.operation == 'UPDATE' && old_guard))",'message':'unchanged'}]}}
def test_parent_exception_exact_substitution_and_fresh_readback_rollback():
 m=mod();p=parent();old=copy.deepcopy(p);ref=copy.deepcopy(p['metadata'])
 plan=m.parent_exception(p,expected_ref=ref,provider=provider(),targets=targets())
 assert p==old and plan['apply_allowed']is False
 after=plan['patch'][-1]['value'];before=p['spec'];expr=after['validations'][0]['expression']
 assert expr.replace(plan['replacement'],m.PARENT_PREDICATE)==before['validations'][0]['expression']
 assert "request.operation == 'CREATE'"in plan['replacement'] and m.ACTOR in plan['replacement']
 assert all(t['name']in plan['replacement'] for t in m.validate(provider(),targets()))
 assert plan['patch'][:3]==[{'op':'test','path':'/metadata/uid','value':ref['uid']},{'op':'test','path':'/metadata/resourceVersion','value':ref['resourceVersion']},{'op':'test','path':'/spec','value':before}]
 actual=copy.deepcopy(p);actual['spec']=after;actual['metadata']['resourceVersion']='360103999'
 rollback=m.parent_exception_rollback(actual,plan)
 assert rollback[1]['value']=='360103999' and rollback[-1]['value']==before
 actual['spec']['failurePolicy']='Ignore'
 with pytest.raises(ValueError):m.parent_exception_rollback(actual,plan)

@pytest.mark.parametrize('fault',['uid','rv','name','duplicate','missing'])
def test_parent_exception_rejects_wrong_preimage(fault):
 m=mod();p=parent();ref=copy.deepcopy(p['metadata'])
 if fault=='uid':p['metadata']['uid']='foreign'
 if fault=='rv':p['metadata']['resourceVersion']='changed'
 if fault=='name':p['metadata']['name']='other'
 if fault=='duplicate':p['spec']['validations'][0]['expression']+=' || '+m.PARENT_PREDICATE
 if fault=='missing':p['spec']['validations'][0]['expression']='true'
 with pytest.raises(ValueError):m.parent_exception(p,expected_ref=ref,provider=provider(),targets=targets())

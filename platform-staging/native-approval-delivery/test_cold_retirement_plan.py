import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import uuid

import pytest

spec=importlib.util.spec_from_file_location('cold_retirement_plan',Path(__file__).with_name('cold_retirement_plan.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def uid(i):return str(uuid.uuid5(uuid.NAMESPACE_DNS,'retirement-'+str(i)))
def sha(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def obj(kind,name,ns='',**fields):
 return {'apiVersion':'v1','kind':kind,'metadata':{'name':name,'uid':uid(name+ns),'resourceVersion':'12',**({'namespace':ns} if ns else {})},**fields}
def fixture():
 namespaces={n:{'apiVersion':'v1','kind':'List','metadata':{'resourceVersion':'123'},'items':[],'capture_preimages':[]} for n in m.NAMESPACES}
 for ns,name,sa in m.CONTROLLERS:
  account=obj('ServiceAccount',sa,ns);namespaces[ns]['items'].append(account)
  deployment=obj('Deployment',name,ns,spec={'replicas':1,'template':{'spec':{'serviceAccountName':sa,'nodeSelector':{'kubernetes.io/hostname':'k3s-wk-gpu2'} if name=='cps-native-node-agent' else {},'containers':[{'name':'agent','image':'example@sha256:'+'a'*64}]}}})
  namespaces[ns]['items'].append(deployment);namespaces[ns]['capture_preimages'].append({'kind':'Deployment','namespace':ns,'name':name,'uid':deployment['metadata']['uid'],'raw_object_sha256':sha(deployment),'raw_spec_sha256':sha(deployment['spec'])})
 gateway=obj('Deployment','compute-gateway','cps-compute',spec={'replicas':1,'template':{'spec':{'serviceAccountName':'cps-compute-controller','containers':[{'name':'gateway'}]}}});namespaces['cps-compute']['items'].append(gateway)
 for ns in ('cps-native-system','cps-compute','jupyterhub','cit-jhub'):
  role=obj('Role','cps-native-head-delivery',ns,rules=[{'apiGroups':[''],'resources':['configmaps'],'verbs':['get','create']}]);binding=obj('RoleBinding',role['metadata']['name'],ns,roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':role['metadata']['name']},subjects=[{'kind':'ServiceAccount','namespace':'cps-compute','name':'cps-native-head-delivery'}]);namespaces[ns]['items'] += [role,binding]
 old=obj('Namespace','cps-native-system',spec={},status={});old['metadata']['labels']={'retained':'yes'}
 new=obj('Namespace','cps-native-runtime',spec={},status={});new['metadata']['labels']={'pod-security.kubernetes.io/enforce':'restricted'}
 return {'version':1,'scope':{'node':'k3s-wk-gpu2','node_uid':uid('node'),'gpu_uuid':'GPU-'+uid('gpu')},'old_namespace':old,'new_namespace':new,'node':obj('Node','k3s-wk-gpu2'), 'namespaced':namespaces,'cluster':{'items':[]},'secret_metadata':{n:{'items':[]} for n in m.NAMESPACES},'fleet_metadata':{'items':[]}}
def render(value):
 value=copy.deepcopy(value);value['node']['metadata']['uid']=value['scope']['node_uid'];return m.render(value,reviewed_sha256=sha(value))

def test_closed_plan_preserves_shared_specs_and_is_not_executor():
 value=fixture();before=copy.deepcopy(value);p=render(value)
 assert value==before and p['status']=='draft-incomplete' and p['executable'] is False
 assert len(p['controller_intents'])==4 and all(x['desired_replicas']==0 for x in p['controller_intents'])
 assert all(x['operation']=='empty-subjects' for x in p['rbac_intents'])
 assert all(x['object']['name']!='compute-gateway' for x in p['controller_intents'])
 assert len(p['admission_candidates'])==2 and p['admission_candidates'][0]['spec']['failurePolicy']=='Fail'
 assert p['namespace_patch']['operations'][-2]['value']['pod-security.kubernetes.io/enforce']=='restricted'
 assert p['unmet_gates'] and p['coverage']['no_hardware_fence_claim'] is True

@pytest.mark.parametrize('fault',['wrong-uid','extra-sa','broad-rbac','gpu1','wrong-node','missing-sa','missing-preimage','secret-values','unknown-root','duplicate-object','unreviewed'])
def test_scope_and_capture_denials(fault):
 v=fixture();v['node']['metadata']['uid']=v['scope']['node_uid']
 if fault=='wrong-uid':v['namespaced']['cps-native-system']['capture_preimages'][0]['uid']=uid('foreign')
 elif fault=='extra-sa':
  x=next(x for x in v['namespaced']['jupyterhub']['items'] if x['kind']=='RoleBinding');x['subjects'].append({'kind':'ServiceAccount','namespace':'jupyterhub','name':'foreign'})
 elif fault=='broad-rbac':next(x for x in v['namespaced']['jupyterhub']['items'] if x['kind']=='Role')['rules'][0]['resources']=['*']
 elif fault=='gpu1':v['scope']['node']='k3s-wk-gpu1';v['node']['metadata']['name']='k3s-wk-gpu1'
 elif fault=='wrong-node':next(x for x in v['namespaced']['cps-native-system']['items'] if x['kind']=='Deployment')['spec']['template']['spec']['nodeSelector']={'kubernetes.io/hostname':'k3s-wk-gpu1'}
 elif fault=='missing-sa':v['namespaced']['cps-native-system']['items']=[x for x in v['namespaced']['cps-native-system']['items'] if x['kind']!='ServiceAccount']
 elif fault=='missing-preimage':v['namespaced']['cps-native-system']['capture_preimages']=[]
 elif fault=='secret-values':v['secret_metadata']['cps-compute']['items']=[{'data':{'password':'forbidden'}}]
 elif fault=='unknown-root':v['apply']=True
 elif fault=='duplicate-object':v['namespaced']['jupyterhub']['items']*=2
 with pytest.raises(ValueError):m.render(v,reviewed_sha256='0'*64 if fault=='unreviewed' else sha(v))


def test_controller_intent_never_treats_redacted_spec_as_api_preimage():
 v=fixture();dep=next(x for x in v['namespaced']['cps-native-system']['items'] if x['kind']=='Deployment');dep['spec']['template']['spec']['containers'][0]['env']=[{'name':'TOKEN','value':'<REDACTED>'}]
 p=render(v);i=p['controller_intents'][0]
 assert i['materialization']=='fresh-full-spec-matching-original-sha256'
 assert 'spec' not in i and 'operations' not in i
 assert i['preconditions']['raw_spec_sha256'] != sha(dep['spec'])


def test_actual_node_uses_fixed_node_name_not_invented_selector():
 v=fixture();dep=next(x for x in v['namespaced']['cps-native-system']['items'] if x['kind']=='Deployment' and x['metadata']['name']=='cps-native-node-agent');pod=dep['spec']['template']['spec'];pod.pop('nodeSelector');pod['nodeName']='k3s-wk-gpu2'
 assert render(v)['scope']['node']=='k3s-wk-gpu2'
 pod['nodeName']='k3s-wk-gpu1'
 with pytest.raises(ValueError):render(v)


def test_scale_subresource_cannot_use_scale_kind_to_evade_controller_fence():
 policy=render(fixture())['admission_candidates'][0]
 expressions=[x['expression'] for x in policy['spec']['validations']]
 assert any("request.subResource == 'scale'" in x and "cps-native-system/cps-native-node-agent" in x for x in expressions)


def test_token_subresources_use_admission_request_name_not_body_metadata():
 p=render(fixture())['admission_candidates'][0]
 assert next(v['expression'] for v in p['spec']['variables'] if v['name']=='name')=='request.name'


def test_direct_grants_resolve_rolebinding_namespace_without_global_group_freeze():
 p=render(fixture());policy=p['admission_candidates'][0]
 expr=next(x['expression'] for x in policy['spec']['validations'] if x['message'].startswith('Retired native grants'))
 assert "s.kind == 'User'" in expr
 assert "has(s.namespace) && s.namespace != '' ? s.namespace : request.namespace" in expr
 assert "s.kind == 'Group'" not in expr
 assert 'broad-group-and-aggregated-capability-closure-with-complete-retired-credential-denial' in p['unmet_gates']


def test_retired_writer_policy_matches_exact_five_users_all_mutations_only():
 p=render(fixture());policies=p['retired_writer_admission_candidates']
 assert len(policies)==2
 policy,binding=policies
 assert policy['kind']=='ValidatingAdmissionPolicy'
 assert policy['spec']['failurePolicy']=='Fail'
 rule=policy['spec']['matchConstraints']['resourceRules'][0]
 assert rule=={'apiGroups':['*'],'apiVersions':['*'],'operations':['CREATE','UPDATE','DELETE','CONNECT'],'resources':['*/*'],'scope':'*'}
 expression=policy['spec']['validations'][0]['expression']
 assert expression=="!(request.userInfo.username in "+json.dumps(sorted('system:serviceaccount:'+s.replace('/',':') for s in m.DEDICATED),separators=(',',':'))+")"
 assert len(m.DEDICATED)==5
 for shared in ('cps-compute-controller','jupyterhub:hub','cit-jhub:hub','kai-scheduler:binder','system:authenticated'):
  assert shared not in expression
 assert binding['spec']=={'policyName':policy['metadata']['name'],'validationActions':['Deny']}
 assert 'read-secret-exfiltration-cached-RPC-host-process-and-existing-credential-proof' in p['unmet_gates']


def test_admission_policy_apis_are_explicit_external_coverage_exception():
 p=render(fixture())
 policy=p['admission_candidates'][0]
 rule=policy['spec']['matchConstraints']['resourceRules'][0]
 assert 'validatingadmissionpolicies' not in rule['resources']
 assert 'validatingadmissionpolicybindings' not in rule['resources']
 assert not any('Retirement admission fence cannot' in x['message'] for x in policy['spec']['validations'])
 assert 'admission-policy-and-binding-RBAC-admin-privilege-denial-explicit-SAR' in p['unmet_gates']
 assert p['coverage']['admission_policy_apis_excluded'] is True

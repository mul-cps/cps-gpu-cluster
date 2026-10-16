"""Maintenance cannot open either SQLite provider while a foreign writer exists."""
import copy,hashlib,importlib.util,json
from pathlib import Path
import sys,uuid
from datetime import datetime,timezone
import pytest
HERE=Path(__file__).parent
sys.path[:0]=[str(HERE),str(HERE.parent)]
IMAGE='ghcr.io/mul-cps/e2x-course-hub@sha256:dbaad51899ccb634f5a07c44bd9f7022dbca71724d7cfd66e5d67abf9d569ace'
uid=lambda n:str(uuid.UUID(int=n))

def helper():
 p=HERE/'source_maintenance.py';assert p.exists(),'Exclusive Source maintenance executor required'
 s=importlib.util.spec_from_file_location('source_maintenance',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def admins():
 return {s:dict(apiVersion='apps/v1',kind='Deployment',metadata=dict(namespace='cps-compute',name=s+'-admin',uid=uid(n),resourceVersion='2'),
  spec=dict(replicas=1,selector={'matchLabels':{'app':s+'-admin'}},template=dict(metadata={'labels':{'app':s+'-admin'}},spec=dict(
   containers=[dict(name='console',image=IMAGE,env=[{'name':'SOURCE','value':s}],args=['original'],ports=[{'containerPort':8080}],readinessProbe={'httpGet':{'path':'/','port':8080}},
      volumeMounts=[dict(name='data',mountPath='/data'),dict(name='config',mountPath='/config',readOnly=True)])],
   volumes=[dict(name='data',persistentVolumeClaim={'claimName':s+'-admin-data'}),dict(name='config',configMap={'name':s+'-admin-config'})])))) for s,n in [('cps',1),('cit',2)]}

def test_operator_uses_exact_source_runtime_and_is_not_selected_by_console_service():
 a=admins();before=copy.deepcopy(a)
 pod=helper().maintenance_pod(a['cps'],node_name='worker-original',freeze_id=uid(4),helper_configmap='qa531-helpers')
 spec=pod['spec'];c=spec['containers'][0]
 assert c['image']==IMAGE and c['env']==a['cps']['spec']['template']['spec']['containers'][0]['env']
 assert c['command']==['python','-B','-c'] and 'sleep(3600)' in c['args'][0]
 assert not any(k in c for k in ('ports','readinessProbe','livenessProbe','startupProbe'))
 assert spec['nodeName']=='worker-original' and spec['serviceAccountName']=='cps-qa531-source-operator'
 assert pod['metadata']['labels'].get('app')!='cps-admin'
 assert spec['volumes'][:2]==a['cps']['spec']['template']['spec']['volumes'] and a==before
 assert c['securityContext']['allowPrivilegeEscalation'] is False


def observations():
 m=helper();a=admins();pod=m.maintenance_pod(a['cps'],node_name='worker-original',freeze_id=uid(4),helper_configmap='qa531-helpers')
 pod['metadata']['uid']=uid(5);pod['status']={'phase':'Running'}
 live=copy.deepcopy(a)
 for d in live.values():d['spec']['replicas']=0
 review=dict(operator_spec_sha256=m.digest(pod['spec']),gateway={'pod_uid':uid(6),'policy_hash':'sha256:'+'b'*64,'contract_sha256':'a'*64},version=1,freeze_id=uid(4),operator_uid=uid(5),source_deployment_uids={s:d['metadata']['uid'] for s,d in a.items()},
   no_alternate_group_start_path=True,source_service_token_custody='root-exclusive-during-external-freeze',passed=True,observed_at=datetime.now(timezone.utc).isoformat())
 return a,live,pod,review


def test_fresh_freeze_verifies_both_deployments_and_every_database_writer():
 a,live,pod,review=observations();m=helper()
 result=m.verify_freeze(originals=a,current=live,pods={'apiVersion':'v1','kind':'PodList','metadata':{},'items':[pod]},operator=pod,review=review,gateway={'pod_uid':uid(6),'policy_hash':'sha256:'+'b'*64,'contract_sha256':'a'*64})
 assert result['active'] is result['external_starts_excluded'] is True and result['writer_pods']==[]


@pytest.mark.parametrize('fault',['replicas','uid','template','old-console-pod','foreign-pvc-writer','terminating-writer','pagination','operator-image','operator-host','operator-env','review','gateway-binding','stale'])
def test_unresolved_writer_or_unreviewed_start_exclusion_denies_freeze(fault):
 a,live,pod,review=observations();items=[pod];metadata={}
 if fault=='replicas':live['cit']['spec']['replicas']=1
 elif fault=='uid':live['cps']['metadata']['uid']=uid(100)
 elif fault=='template':live['cps']['spec']['template']['spec']['containers'][0]['image']='foreign'
 elif fault in ('old-console-pod','foreign-pvc-writer','terminating-writer'):
  other=copy.deepcopy(pod);other['metadata']['uid']=uid(100);other['metadata']['name']='foreign';other['metadata']['labels']={'app':'cps-admin'} if fault=='old-console-pod' else {}
  if fault=='terminating-writer':other['metadata']['deletionTimestamp']=datetime.now(timezone.utc).isoformat()
  items.append(other)
 elif fault=='pagination':metadata['continue']='next'
 elif fault=='operator-image':pod['spec']['containers'][0]['image']='foreign'
 elif fault=='operator-env':pod['spec']['containers'][0]['env'][0]['value']='foreign'
 elif fault=='operator-host':pod['spec']['hostNetwork']=True
 elif fault=='gateway-binding':review['gateway']['pod_uid']=uid(99)
 elif fault=='review':review['no_alternate_group_start_path']=False
 else:review['observed_at']='2000-01-01T00:00:00+00:00'
 with pytest.raises(ValueError):helper().verify_freeze(originals=a,current=live,pods={'apiVersion':'v1','kind':'PodList','metadata':metadata,'items':items},operator=pod,review=review,gateway={'pod_uid':uid(6),'policy_hash':'sha256:'+'b'*64,'contract_sha256':'a'*64})

@pytest.mark.parametrize('shape',['omitted','null','foreign-version','foreign-kind'])
def test_core_v1_pod_list_items_inherit_type_from_list_without_accepting_foreign_types(shape):
 a,live,pod,review=observations()
 pod.pop('apiVersion');pod.pop('kind')
 if shape=='null':pod.update(apiVersion=None,kind=None)
 elif shape=='foreign-version':pod['apiVersion']='foreign/v1'
 elif shape=='foreign-kind':pod['kind']='Deployment'
 kwargs=dict(originals=a,current=live,pods={'apiVersion':'v1','kind':'PodList','metadata':{},'items':[pod]},operator=pod,review=review,gateway={'pod_uid':uid(6),'policy_hash':'sha256:'+'b'*64,'contract_sha256':'a'*64})
 if shape.startswith('foreign'):
  with pytest.raises(ValueError):helper().verify_freeze(**kwargs)
 else:assert helper().verify_freeze(**kwargs)['active'] is True

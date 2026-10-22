import copy,importlib.util
from pathlib import Path
import pytest
P=Path(__file__).with_name('prepare_plain_gateway.py')
def mod():
 s=importlib.util.spec_from_file_location('plain_gateway',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def fixture():
 image='ghcr.io/mul-cps/cps-compute@sha256:0e215c9c5767b4162ae0e57ff3f1614ad16be144c57b19a187f7c6cbe6bdb8cd'
 c={'name':'gateway','image':image,'command':['uvicorn'],'args':['cps_compute.runtime:create_runtime','--factory','--host','0.0.0.0','--port','8443','--ssl-certfile','/tls/tls.crt','--ssl-keyfile','/tls/tls.key'],'env':[{'name':'CPS_COMPUTE_CONFIG','value':'/config/runtime.json'},{'name':'CPS_NATIVE_APPROVAL_PUBLISHER_PATH','value':'/publisher/config.json'}]+[{'name':x,'valueFrom':{'secretKeyRef':{'name':'existing-auth','key':x}}} for x in ('SOURCE','HUB','ARGO')],'volumeMounts':[{'name':'state','mountPath':'/data'},{'name':'config','mountPath':'/config'},{'name':'tls','mountPath':'/tls'},{'name':'argo-ca','mountPath':'/argo-ca','readOnly':True},{'name':'reader','mountPath':'/reader','readOnly':True},{'name':'publisher','mountPath':'/publisher'}],'ports':[{'name':'https','containerPort':8443}],'securityContext':{'runAsUser':10001,'readOnlyRootFilesystem':True}}
 pod={'containers':[c,{'name':'approval-capture','image':image}],'initContainers':[{'name':'bootstrap','image':image}],'serviceAccountName':'old','volumes':[{'name':'state','persistentVolumeClaim':{'claimName':'compute-state'}},{'name':'config','secret':{'secretName':'old-runtime'}},{'name':'tls','secret':{'secretName':'old-tls'}},{'name':'argo-ca','configMap':{'name':'actual-argo-ca'}},{'name':'reader','secret':{'secretName':'actual-reader'}},{'name':'publisher','configMap':{'name':'old-publisher'}}]}
 dep={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'namespace':'cps-compute','name':'compute-gateway','uid':'11111111-1111-4111-8111-111111111111','resourceVersion':'123'},'spec':{'replicas':1,'selector':{'matchLabels':{'app':'old'}},'template':{'metadata':{'labels':{'app':'old'}},'spec':pod}}}
 runtime={'state_directory':'/data','policy_file':'/config/policy.json','policy_hash':'sha256:'+'1'*64,'service_token_envs':{'cps':'SOURCE'},'hubs':{'cps':{'service_token_env':'HUB','url':'https://hub','canonical_people':{}}},'argo_token_env':'ARGO','argo_ca_file':'/argo-ca/ca.crt','argoUI':{'enabled':True,'readerTokenFile':'/reader/token'},'nativeGpuGroups':{'enabled':True},'storage':{'enabled':True}}
 pilot={'proposal_only':True,'lifecycle_runnable':False,'production_qualified':False,'policy':{'policyHash':'sha256:'+'2'*64},'runtime':{'state_directory':'/data','nativeGpuPilot':{'enabled':True,'authorityNamespace':'cps-native-lifecycle-147','native_pilot_workspaces':{'cps:a':{'profile':'interactive-native-pilot-5'}},'node_pool':{'node':'k3s-wk-gpu2'}}}}
 return dict(deployment=dep,runtime=runtime,pilot=pilot,tls_secret_ref={'namespace':'cps-compute','name':'pilot-tls'},ca_configmap_ref={'namespace':'cps-compute','name':'pilot-ca'},policy_configmap_ref={'namespace':'cps-compute','name':'pilot-policy'},runtime_secret_ref={'namespace':'cps-compute','name':'pilot-runtime'},new_name='native-lifecycle-gateway',selected_state_node='k3s-wk-gpu1')

def test_full_preimage_preserved_narrow_temp_projection():
 a=fixture();old=copy.deepcopy(a);r=mod().prepare(**a);assert a==old
 d=r['deployment'];p=d['spec']['template']['spec'];assert p['nodeName']=='k3s-wk-gpu1' and p['serviceAccountName']=='native-lifecycle-gateway'
 assert len(p['containers'])==1 and not p.get('initContainers');assert r['runtime']['state_directory']=='/data'
 assert r['runtime']['nativeGpuGroups']=={'enabled':False} and r['runtime']['storage']=={'enabled':False}
 assert r['runtime']['policy_hash']==a['pilot']['policy']['policyHash'];assert r['runtime']['shutdownObserver']=={'kubernetes':True}
 assert not any(x['name'].startswith('CPS_NATIVE_') for x in p['containers'][0]['env'])
 assert 'argo-ca' in {v['name'] for v in p['volumes']} and 'reader'not in {v['name'] for v in p['volumes']}
 assert r['deploy_ready'] is False and r['rbac']['pending'] is True
 assert r['service']['spec']['selector']==d['spec']['selector']['matchLabels']

@pytest.mark.parametrize('fault',['namespace','node','pvc','image','tlsns','oldname','credential','metadata','tlsargs'])
def test_actual_contract_mismatch_denied(fault):
 a=fixture();c=a['deployment']['spec']['template']['spec']['containers'][0]
 if fault=='namespace':a['deployment']['metadata']['namespace']='jupyterhub'
 if fault=='node':a['selected_state_node']='k3s-wk-gpu2'
 if fault=='pvc':a['deployment']['spec']['template']['spec']['volumes'][0]['persistentVolumeClaim']['claimName']='fake'
 if fault=='image':c['image']='image:latest'
 if fault=='tlsns':a['tls_secret_ref']['namespace']='other'
 if fault=='oldname':a['new_name']='compute-gateway'
 if fault=='credential':c['env']=[x for x in c['env'] if x['name']!='ARGO']
 if fault=='metadata':a['deployment']['metadata'].pop('resourceVersion')
 if fault=='tlsargs':c['args'].remove('--ssl-keyfile')
 with pytest.raises(ValueError):mod().prepare(**a)


def test_actual_old_image_combined_command_lowercase_ui_and_fresh_sa():
 a=fixture();pod=a['deployment']['spec']['template']['spec'];c=pod['containers'][0]
 c['image']='ghcr.io/mul-cps/cps-compute@sha256:5f1dd4f55710f1cdf97d24a1165b265681c61c67578680b8f5ef8bd67a34fc3c'
 c['command']=c['command']+c['args'];c['args']=None
 pod['automountServiceAccountToken']=False
 pod['volumes'].append({'name':'old-api','projected':{'sources':[{'serviceAccountToken':{'path':'token','expirationSeconds':600}}]}})
 c['volumeMounts'].append({'name':'old-api','mountPath':'/var/run/secrets/kubernetes.io/serviceaccount','readOnly':True})
 a['runtime']['argoUi']=a['runtime'].pop('argoUI')
 old=copy.deepcopy(a);r=mod().prepare(**a);assert a==old
 out=r['deployment']['spec']['template']['spec'];main=out['containers'][0]
 assert main['image']==mod().IMAGE
 assert '--factory' in main['command'] and main['command'][main['command'].index('--ssl-keyfile')+1]=='/pilot-tls/tls.key'
 assert r['runtime']['argoUi']=={'enabled':False} and not r['runtime'].get('argoUI',{}).get('enabled')
 assert out['automountServiceAccountToken'] is True
 assert 'old-api' not in {x['name'] for x in out['volumes']}
 assert not any(x.get('projected',{}).get('sources') for x in out['volumes'])
 assert not any(x['mountPath']=='/var/run/secrets/kubernetes.io/serviceaccount' for x in main['volumeMounts'])
 assert 'reader'not in {x['name'] for x in out['volumes']}

def inherited_fixture():
 a=fixture();p=a['deployment']['spec']['template']['spec'];c=p['containers'][0]
 c['image']='ghcr.io/mul-cps/cps-compute@sha256:5f1dd4f55710f1cdf97d24a1165b265681c61c67578680b8f5ef8bd67a34fc3c'
 c['command']=['uvicorn','cps_compute.runtime:create_runtime','--factory','--workers','1','--host','0.0.0.0','--port','8000','--ssl-keyfile','/tls/tls.key','--ssl-certfile','/tls/tls.crt'];c['args']=None
 c['ports']=[{'name':'http','containerPort':8000,'protocol':'TCP'}];c['readinessProbe']={'tcpSocket':{'port':'http'}}
 c['env']=[x for x in c['env'] if x['name'].startswith('CPS_')];c['envFrom']=[{'secretRef':{'name':'existing-auth'}}]
 a['credential_secret_metadata']=[{'namespace':'cps-compute','name':'existing-auth','uid':'22222222-2222-4222-8222-222222222222','resourceVersion':'44','keys':['SOURCE','HUB','ARGO','UNRELATED']}]
 a['runtime']['argoUi']=a['runtime'].pop('argoUI');p['automountServiceAccountToken']=False
 return a

def test_actual_inherited_credentials_resolve_narrowly_and_keep_http_probe():
 r=mod().prepare(**inherited_fixture());c=r['deployment']['spec']['template']['spec']['containers'][0]
 assert 'envFrom'not in c and c['readinessProbe']=={'tcpSocket':{'port':'http'}}
 assert r['service']['spec']['ports'][0]['targetPort']=='http'
 keys={x['name'] for x in c['env']};assert {'SOURCE','HUB','ARGO'}<=keys and 'UNRELATED'not in keys
 for row in c['env']:
  if row['name']in {'SOURCE','HUB','ARGO'}:assert row['valueFrom']['secretKeyRef']=={'name':'existing-auth','key':row['name']}
 assert r['runtime']['argoUi']=={'enabled':False}

@pytest.mark.parametrize('fault',['missing','key','foreign','ambiguous'])
def test_inherited_metadata_missing_or_ambiguous_denied(fault):
 a=inherited_fixture()
 if fault=='missing':a.pop('credential_secret_metadata')
 if fault=='key':a['credential_secret_metadata'][0]['keys'].remove('HUB')
 if fault=='foreign':a['credential_secret_metadata'][0]['name']='foreign'
 if fault=='ambiguous':
  row=copy.deepcopy(a['credential_secret_metadata'][0]);row['name']='second';a['credential_secret_metadata'].append(row)
  a['deployment']['spec']['template']['spec']['containers'][0]['envFrom'].append({'secretRef':{'name':'second'}})
 with pytest.raises(ValueError):mod().prepare(**a)

def test_actual_standard_argo_token_uses_new_sa_mount_not_old_projection():
 a=inherited_fixture();p=a['deployment']['spec']['template']['spec'];c=p['containers'][0]
 a['runtime'].pop('argo_token_env');a['runtime']['argo_token_file']='/var/run/secrets/kubernetes.io/serviceaccount/token'
 p['volumes'].append({'name':'old-api','projected':{'sources':[{'serviceAccountToken':{'path':'token','expirationSeconds':600}},{'configMap':{'name':'kube-root-ca.crt'}}]}})
 c['volumeMounts'].append({'name':'old-api','mountPath':'/var/run/secrets/kubernetes.io/serviceaccount','readOnly':True})
 r=mod().prepare(**a);out=r['deployment']['spec']['template']['spec'];main=out['containers'][0]
 assert out['automountServiceAccountToken'] is True
 assert not {'old-api','reader'}.intersection(x['name'] for x in out['volumes'])
 assert 'argo-ca' in {x['name'] for x in out['volumes']}
 assert r['runtime']['argo_token_file']=='/var/run/secrets/kubernetes.io/serviceaccount/token'
 assert 'ARGO'not in {x['name'] for x in main['env']}

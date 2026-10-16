"""Node8c actually runs image-backed source; retain that original on unwind."""
import copy,importlib.util,json
from pathlib import Path
import sys
import pytest
HERE=Path(__file__).parent;sys.path[:0]=[str(HERE),str(HERE.parent)]
import test_configuration_inverse as prior

IMAGE='ghcr.io/mul-cps/cps-compute@sha256:8c2c456b90330622645d509f94882a11a465ac208a6fa7fc824900d6320e5c0b'
FLAGS={'--approval-reference':'/var/run/cps-native-approvals/reference.json','--approval-template':'/var/run/cps-native-approvals/template.json','--approval-process':'/var/run/cps-native-approvals/process.json','--approval-acknowledgment':'/var/run/cps-native-approvals/acknowledgment.json'}

def helper():
 p=HERE/'image_node_transition.py';assert p.exists(),'Actual image-backed Node transition required'
 spec=importlib.util.spec_from_file_location('image_node_transition',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def fixture(phase='complete'):
 terminal={'complete':prior.fixture,'partial':prior.partial_fixture,'unstarted':prior.unstarted_fixture}[phase]()
 deployment=dict(apiVersion='apps/v1',kind='Deployment',metadata=dict(namespace='cps-native-system',name='cps-native-node-agent',uid=prior.uid(999),resourceVersion='4'),
  spec=dict(replicas=1,template=dict(metadata={'labels':{'app':'cps-native-node-agent'}},spec=dict(
   containers=[dict(name='node-agent',image=IMAGE,command=['python3','/opt/native/node_agent.py'],
    args=['--execute','--config','/config/config.json','--bundle','/opt/native','--iterations','10000','--interval','2']+[v for pair in FLAGS.items() for v in pair],
    volumeMounts=[dict(name='config',mountPath='/config/config.json',subPath='config.json',readOnly=True),dict(name='state',mountPath='/run/cps-native-gpu')])],
   volumes=[dict(name='config',configMap={'name':terminal['original']['metadata']['name']}),dict(name='state',hostPath={'path':'/run/cps-native-gpu','type':'Directory'})]))))
 return dict(original_deployment=deployment,original_configuration=terminal['original'],proposed_node=json.loads(terminal['current']['data']['config.json']),
  original_node_source=terminal['original_node_source'],original_epoch_source=terminal['original_epoch_source'],contract_raw=terminal['contract_raw'],contract_sha256=terminal['contract_sha256']),terminal

def actual_objects(forward,args,terminal):
 current=copy.deepcopy(args['original_deployment']);current['metadata']['resourceVersion']='5';current['spec']=forward['deployment.patch.json'][-1]['value']
 config=copy.deepcopy(terminal['current']);config['metadata']['name']=forward['configuration.json']['metadata']['name'];config['data']=forward['configuration.json']['data']
 code=copy.deepcopy(config);code['metadata']['uid']=prior.uid(998);code['metadata']['name']=forward['code.json']['metadata']['name'];code['data']=forward['code.json']['data']
 return current,config,code

def test_forward_preserves_image_and_host_mounts_and_overlays_exact_two_files():
 args,_=fixture();before=copy.deepcopy(args);out=helper().forward_intent(**args);spec=out['deployment.patch.json'][-1]['value'];old=args['original_deployment']['spec']
 container=spec['template']['spec']['containers'][0]
 assert container['image']==IMAGE and container['command']==['python3','/opt/native/node_agent.py']
 assert not any(flag in container['args'] for flag in FLAGS)
 mounts=container['volumeMounts'];assert mounts[:2]==old['template']['spec']['containers'][0]['volumeMounts']
 assert {m['subPath'] for m in mounts[2:]}=={'node_agent.py','native_operator_epoch.py'}
 assert all(m['readOnly'] is True and m['mountPath']=='/opt/native/'+m['subPath'] for m in mounts[2:])
 assert spec['template']['spec']['volumes'][-1]['configMap'].get('defaultMode')==0o644
 assert set(out['code.json']['data'])=={'node_agent.py','native_operator_epoch.py'}
 assert args==before and out['live_applied'] is False

@pytest.mark.parametrize('phase',['unstarted','partial','complete'])
def test_inverse_validates_full_terminal_custody_and_restores_dynamic_flags(phase):
 args,terminal=fixture(phase);tool=helper();out=tool.forward_intent(**args);current,config,code=actual_objects(out,args,terminal)
 terminal['current']=config
 result=tool.inverse_intent(forward_inputs=args,current_deployment=current,current_configuration=config,current_code=code,terminal_inputs=terminal,phase=phase)
 restored=result['node-deployment.patch.json'][-1]['value'];container=restored['template']['spec']['containers'][0]
 assert container['args']==args['original_deployment']['spec']['template']['spec']['containers'][0]['args']
 if phase=='unstarted':assert restored==args['original_deployment']['spec']
 else:assert len(container['volumeMounts'])==4 and len(result['full-terminal-authority-archive.json'])==(2 if phase=='partial' else 3)
 assert result['node-deployment.patch.json'][1]['value']=='5'

@pytest.mark.parametrize('fault',['image','source','epoch','command','config-mount','code-overlap','flag','extra-code-volume'])
def test_forward_rejects_unreviewed_image_code_or_bootstrap_shape(fault):
 args,_=fixture();spec=args['original_deployment']['spec']['template']['spec'];c=spec['containers'][0]
 if fault=='image':c['image']='registry.example/foreign@sha256:'+'a'*64
 elif fault=='source':args['original_node_source']+=b'\n'
 elif fault=='epoch':args['original_epoch_source']+=b'\n'
 elif fault=='command':c['command']=['sh','-c','python']
 elif fault=='config-mount':spec['volumes'][0]['configMap']['name']='foreign'
 elif fault=='code-overlap':c['volumeMounts'].append(dict(name='foreign',mountPath='/opt/native'))
 elif fault=='flag':c['args']+=['--approval-process','/foreign']
 else:spec['volumes'].append(dict(name='cps-native-qualification-code',emptyDir={}))
 with pytest.raises(ValueError):helper().forward_intent(**args)

@pytest.mark.parametrize('fault',['deployment','code','config','uid','live-pod'])
def test_inverse_refuses_changed_actual_readbacks_or_unreleased_work(fault):
 args,terminal=fixture();tool=helper();out=tool.forward_intent(**args);current,config,code=actual_objects(out,args,terminal);terminal['current']=config
 if fault=='deployment':current['spec']['replicas']=2
 elif fault=='code':code['data']['node_agent.py']+='\n'
 elif fault=='config':config['data']['config.json']+=' '
 elif fault=='uid':current['metadata']['uid']=prior.uid(997)
 else:
  row=next(r for r in json.loads(terminal['final']['ledger']['data']['state.json'])['allocations'].values() if r['workspace'].startswith('operator-qualification-531-'))
  terminal['final']['pods']['items']=[dict(metadata=dict(uid=row['intent']['pod_uid'],name=row['name'],namespace=row['namespace']))]
 with pytest.raises(ValueError):tool.inverse_intent(forward_inputs=args,current_deployment=current,current_configuration=config,current_code=code,terminal_inputs=terminal,phase='complete')

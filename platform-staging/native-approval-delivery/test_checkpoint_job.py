"""Protected checkpoint reference stays outside settings and migration inputs."""
import copy,json,uuid
import pytest
from test_rotation_job import inputs,load


def reference():
 return {'namespace':'cps-compute','name':'reviewed-checkpoint','uid':str(uuid.uuid4()),
  'resourceVersion':'12','data_sha256':'sha256:'+'f'*64,'key':'checkpoint.json'}


def daemon_args(values):
 return {k:values[k]for k in ('configuration','image','config_secret','journal_pvc')}


def test_daemon_and_rotation_forward_only_independent_reference():
 values=inputs();pin=reference();original=copy.deepcopy(values['config'])
 base=load('render').render(values['config'],**daemon_args(values))
 actual=load('render').render(values['config'],**daemon_args(values),checkpoint_reference=pin)
 main=next(v for v in actual if v['kind']=='Deployment')['spec']['template']['spec']['containers'][0]
 assert main['args'][-2:]==['--checkpoint-reference-json',json.dumps(pin,sort_keys=True,separators=(',',':'))]
 normalized=copy.deepcopy(actual)
 next(v for v in normalized if v['kind']=='Deployment')['spec']['template']['spec']['containers'][0]['args']=next(v for v in base if v['kind']=='Deployment')['spec']['template']['spec']['containers'][0]['args']
 assert normalized==base
 assert load('render').render(values['config'],**daemon_args(values),checkpoint_reference=None)==base
 baseline=load('rotation_job').render(**values)
 job=load('rotation_job').render(**values,checkpoint_reference=pin)
 args=job['spec']['template']['spec']['containers'][0]['args']
 assert args.count('--checkpoint-reference-json')==1 and json.loads(args[args.index('--checkpoint-reference-json')+1])==pin
 assert args.count('--rotate-config')==1 and '--checkpoint'not in args and '--adopt-legacy'not in args
 normalized=copy.deepcopy(job);i=normalized['spec']['template']['spec']['containers'][0]['args'].index('--checkpoint-reference-json')
 del normalized['spec']['template']['spec']['containers'][0]['args'][i:i+2]
 assert normalized==baseline and values['config']==original
 assert 'checkpoint_reference'not in json.dumps(values['config'])


def test_checkpoint_job_reuses_exact_daemon_without_rotation_or_legacy_arguments():
 values=inputs();pin=reference()
 job=load('checkpoint_job').render(values['config'],**daemon_args(values),checkpoint_reference=pin,job_name='reviewed-checkpoint')
 assert job['kind']=='Job'and job['spec']['backoffLimit']==0 and job['spec']['activeDeadlineSeconds']==300
 assert job['spec']['parallelism']==job['spec']['completions']==1
 daemon=load('render').render(values['config'],**daemon_args(values),checkpoint_reference=pin)
 expected=copy.deepcopy(next(v for v in daemon if v['kind']=='Deployment')['spec']['template'])
 expected['spec']['restartPolicy']='Never';expected['spec']['containers'][0]['args']+=['--checkpoint']
 assert job['spec']['template']==expected
 assert not any(arg.startswith('--previous')or arg.startswith('--legacy')or arg=='--rotate-config'
  for arg in expected['spec']['containers'][0]['args'])


@pytest.mark.parametrize('fault',['extra','key','uid','namespace','hash','zero-hash','missing','null'])
def test_invalid_refs_rejected_by_all_entrypoints(fault):
 values=inputs();pin=reference()
 if fault=='extra':pin['unknown']=True
 elif fault=='key':pin['key']='other.json'
 elif fault=='uid':pin['uid']='not-a-uid'
 elif fault=='namespace':pin['namespace']='../foreign'
 elif fault=='hash':pin['data_sha256']='f'*64
 elif fault=='zero-hash':pin['data_sha256']='sha256:'+'0'*64
 elif fault=='missing':del pin['resourceVersion']
 else:pin=None
 if fault!='null':
  with pytest.raises(ValueError):load('render').render(values['config'],**daemon_args(values),checkpoint_reference=pin)
  with pytest.raises(ValueError):load('rotation_job').render(**values,checkpoint_reference=pin)
 with pytest.raises(ValueError):load('checkpoint_job').render(values['config'],**daemon_args(values),checkpoint_reference=pin,job_name='reviewed-checkpoint')


@pytest.mark.parametrize('mixed',[{'previous_state_sha256':'sha256:'+'a'*64},{'legacy_seed_sha256':'sha256:'+'a'*64}])
def test_checkpoint_job_rejects_mixed_migration_inputs(mixed):
 values=inputs()
 with pytest.raises(TypeError):load('checkpoint_job').render(values['config'],**daemon_args(values),checkpoint_reference=reference(),job_name='reviewed-checkpoint',**mixed)


@pytest.mark.parametrize('field,value',[('job_name','Bad_Name'),('active_deadline_seconds',False),('active_deadline_seconds',0),('active_deadline_seconds',901)])
def test_checkpoint_job_has_same_bounded_identity_and_deadline_contract(field,value):
 values=inputs();args=dict(checkpoint_reference=reference(),job_name='reviewed-checkpoint');args[field]=value
 with pytest.raises(ValueError):load('checkpoint_job').render(values['config'],**daemon_args(values),**args)


@pytest.mark.parametrize('field',['checkpoint_reference','checkpoint','rotate_config'])
def test_checkpoint_authority_cannot_be_injected_into_delivery_settings(field):
 values=inputs();values['config'][field]=reference()
 with pytest.raises(ValueError):load('render').render(values['config'],**daemon_args(values))


def test_legacy_adoption_cannot_accept_checkpoint_reference():
 values=inputs()
 with pytest.raises(TypeError):load('adoption_job').render(values['config'],**daemon_args(values),job_name='legacy',
  legacy_state_sha256='sha256:'+'b'*64,legacy_seed_sha256='sha256:'+'c'*64,checkpoint_reference=reference())


def test_explicit_checkpoint_reads_are_only_four_namespace_pod_lists_and_seven_named_role_gets():
 from cps_compute.native_observer_permissions import role_targets
 values=inputs();configuration=values['configuration'];before=copy.deepcopy(configuration.document)
 job_before=load('checkpoint_job').render(values['config'],**daemon_args(values),checkpoint_reference=reference(),job_name='reviewed-checkpoint')
 docs=load('checkpoint_job').read_permissions(configuration)
 targets=role_targets(configuration.document);namespaces={ns for ns,_ in targets}
 assert len(docs)==8 and len(namespaces)==4
 for ns in namespaces:
  metadata={'namespace':ns,'name':'cps-native-head-checkpoint-reader'}
  assert next(d for d in docs if d['kind']=='Role'and d['metadata']['namespace']==ns)=={
   'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':metadata,'rules':[
    {'apiGroups':['rbac.authorization.k8s.io'],'resources':['roles'],'verbs':['get'],
     'resourceNames':sorted(name for namespace,name in targets if namespace==ns)},
    {'apiGroups':[''],'resources':['pods'],'verbs':['list']}]}
  assert next(d for d in docs if d['kind']=='RoleBinding'and d['metadata']['namespace']==ns)=={
   'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':metadata,
   'subjects':[{'kind':'ServiceAccount','namespace':'cps-compute','name':'cps-native-head-delivery'}],
   'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':metadata['name']}}
 assert configuration.document==before
 # Rendering remains independent; no read permissions are embedded or applied.
 job_after=load('checkpoint_job').render(values['config'],**daemon_args(values),checkpoint_reference=json.loads(job_before['spec']['template']['spec']['containers'][0]['args'][-2]),job_name='reviewed-checkpoint')
 assert job_after==job_before
 renamed=load('checkpoint_job').read_permissions(configuration,namespace='operator-system',name='reviewed-read-window')
 assert len(renamed)==8
 assert all(d['metadata']['name']=='reviewed-read-window'for d in renamed)
 assert all(d['subjects']==[{'kind':'ServiceAccount','namespace':'operator-system','name':'cps-native-head-delivery'}]
  and d['roleRef']['name']=='reviewed-read-window'for d in renamed if d['kind']=='RoleBinding')


@pytest.mark.parametrize('field,value',[(field,value)for field in ('namespace','name')for value in ('Bad_Name','*','',False,'a'*64)])
def test_checkpoint_read_permissions_reject_noncanonical_actor_and_object_names(field,value):
 values=inputs()
 with pytest.raises(ValueError):load('checkpoint_job').read_permissions(values['configuration'],**{field:value})


@pytest.mark.parametrize('configuration',[None,{},object()])
def test_checkpoint_read_permissions_require_actual_immutable_configuration(configuration):
 with pytest.raises(ValueError):load('checkpoint_job').read_permissions(configuration)

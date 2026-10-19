"""Public, actual-shaped v4 Gateway rotation fixtures; no API or private inputs."""
import copy
import importlib.util
import json
from pathlib import Path
import uuid

import pytest
from cps_compute.native_groups import canonical_sha256
from cps_compute.native_node.config import NodeConfiguration
from cps_compute.native_scheduler_group_contract import GroupPendingContext
from test_native_node_config import ref
from test_observer_adoption import fixture as image_fixture, image

HERE=Path(__file__).parent


def load(name):
    path=HERE/(name+'.py')
    spec=importlib.util.spec_from_file_location('head_rotation_test_'+name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def actual(candidate):
    value=copy.deepcopy(candidate)
    value['metadata'].update(uid=str(uuid.uuid4()),resourceVersion='51')
    return value


def fixture():
    start=image_fixture();snapshot=copy.deepcopy(start['image_snapshot'])
    policy,old=image._context(snapshot);boot=load('head_bootstrap');runtime=load('head_runtime_adoption')
    def add(obj):
        m=obj['metadata'];snapshot['objects'][image._key(obj['kind'],m['namespace'],m['name'])]=obj
        return obj
    seed=image.secret_volume(snapshot,'gateway','capture-seed')
    cfg=image._decode(seed['data']['config.json'])
    cfg.update(database='/data/control.sqlite',policy_json='/inputs/policy.json',token_file='/inputs/token',
        ttl_seconds=30,host='0.0.0.0',port=8001,tls_cert_file='/inputs/cert',tls_key_file='/inputs/key')
    seed['data']['config.json']=image._encoded(cfg)
    approvals={c:image.volume(snapshot,c,'cps-native-approval-document')for c in image.COMPONENTS}
    pointers={c:add(actual(v))for c,v in boot.pointer_candidates(old,approvals,policy).items()}
    anchors={c:add(actual(v))for c,v in boot.anchor_candidates(old,approvals,policy,pointers).items()}
    heads=boot.bind(old,approvals,policy,pointers,anchors)
    node=add(actual(heads['node_configuration']))
    bindings={c:add(actual(v))for c,v in boot.runtime_candidates(old,approvals,policy,pointers,anchors).items()}
    plan=runtime.prepare(snapshot,pointers,anchors,bindings,node,expected_snapshot_sha256=canonical_sha256(snapshot))
    created={label:actual(v)for label,v in plan['creates'].items()}
    for obj in created.values():add(obj)
    capture={'version':1,'configmaps':[v for v in snapshot['objects'].values()if v['kind']=='ConfigMap'],
        'deployments':list(snapshot['deployments'].values()),
        'roles':[image._get(snapshot,'Role',r['namespace'],r['name'])for r in start['previous_release']['roles']]}
    class Core:
        def read_namespaced_config_map(self,name,namespace):return copy.deepcopy(image._get(snapshot,'ConfigMap',namespace,name))
    new=NodeConfiguration.load(Core(),ref(node),policy)
    observed=load('head_observer_adoption').compose(start['previous_release'],start['reviewed_sha256'],policy.catalog,
        old,new,created['node.bootstrap'],heads['heads'],capture,plan['runtime_specs'],
        reviewed_runtime_specs_sha256=canonical_sha256(plan['runtime_specs']),actual_gateway_capture_seed=created['gateway.capture-seed'],
        head_get_rows=[{'namespace':r['namespace'],'name':r['name'],'index':next(i for i,row in enumerate(r['rules'])
            if row.get('apiGroups')==[''] and row.get('resources')==['configmaps'] and row.get('verbs')==['get'])}
            for r in start['previous_release']['roles']])
    for component,spec in plan['runtime_specs'].items():
        snapshot['deployments'][component]['spec']=copy.deepcopy(spec);add(snapshot['deployments'][component])
    runtime_secret=image.secret_volume(snapshot,'gateway','config')
    runtime_secret['data']=copy.deepcopy(plan['gateway_runtime_patch']['patch'][-1]['value'])
    for record in observed['static_role_patches'].values():
        target=record['target'];image._get(snapshot,'Role',target['namespace'],target['name'])['rules']=copy.deepcopy(record['patch'][-1]['value'])
    # Live v4 baseline is released. The next rotation must create a new held CM.
    created['node.bootstrap']['data']['release']='true'
    add(created['node.bootstrap'])
    operators=[]
    for declaration in new.document['component_declarations'].values():
        ns=declaration['namespace'];names=sorted(v['metadata']['name']for v in snapshot['objects'].values()
            if v['kind']=='ConfigMap' and v['metadata']['namespace']==ns)
        role=add({'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':{'namespace':ns,
            'name':'cps-native-observer-operator','uid':str(uuid.uuid4()),'resourceVersion':'61'},
            'rules':[{'apiGroups':[''],'resources':['configmaps'],'verbs':['get'],'resourceNames':names},
                {'apiGroups':['rbac.authorization.k8s.io'],'resources':['roles'],'verbs':['get','patch','escalate'],
                 'resourceNames':sorted(r['name']for r in observed['release']['roles']if r['namespace']==ns)}]})
        operators.append({**{k:role['metadata'][k]for k in ('namespace','name','uid')},'index':0,'rules':copy.deepcopy(role['rules'])})
    # Build actual endpoint output against this same authenticated v4 context.
    path=HERE.parent/'current-group-integration'/'endpoint.py'
    spec=importlib.util.spec_from_file_location('rotation_endpoint',path);endpoint=importlib.util.module_from_spec(spec);spec.loader.exec_module(endpoint)
    context=GroupPendingContext.load(Core(),ref(node),policy);dep=context.deployment
    declaration=new.document['component_declarations']
    def account(component):
        d=declaration[component];return image._get(snapshot,'ServiceAccount',d['namespace'],d['service_account'])
    binder={'apiVersion':'v1','kind':'ServiceAccount','metadata':{'namespace':'kai-scheduler','name':'binder',
        'uid':str(uuid.uuid4()),'resourceVersion':'1'}}
    reservation={'namespace':'kai-resource-reservation','serviceAccount':'kai-resource-reservation',
        'image':'ghcr.io/example/reservation@sha256:'+'a'*64,'appLabel':'kai-resource-reservation','runtimeClassName':'',
        'containerResources':{'requests':{'nvidia.com/gpu':'1'},'limits':{'nvidia.com/gpu':'1'}},'podSecurityContext':{},'containerSecurityContext':{}}
    gateway=snapshot['deployments']['gateway']['spec']['template']['spec'];gateway['securityContext']={'fsGroup':10001}
    gateway.setdefault('volumes',[]).append({'name':'data','persistentVolumeClaim':{'claimName':'existing-control'}})
    main=next(c for c in gateway['containers']if c['name']==declaration['gateway']['container'])
    main.setdefault('volumeMounts',[]).append({'name':'data','mountPath':'/data'})
    main.setdefault('env',[]).append({'name':'UNRELATED','value':'retained'})
    add(snapshot['deployments']['gateway'])
    runtime_settings=image._decode(runtime_secret['data']['runtime.json'])['nativeGroupApprovals']
    proposal=endpoint.render(context,gateway_account=account('gateway'),binder_account=binder,
        hub_accounts={s:account('hub:'+s)for s in ('cps','cit')},
        hub_settings={s:{'enabled':True,'source':s,'gatewayUrl':endpoint.ORIGIN,
            'gatewayCAFile':'/etc/cps-native-hub/ca.crt','groupDeployment':json.loads(dep.document)}for s in ('cps','cit')},
        readiness=runtime_settings,reservation_template=reservation,api_audience='reviewed-api-audience',
        binder_pod_labels={'app':'binder'},gateway_pod_security_context={'fsGroup':10001},gateway_data_volume_name='data')
    endpoint_seed=add(actual(proposal['seed']))
    return {'snapshot':snapshot,'previous_release':observed['release'],'operator_baselines':operators,
        'gateway_image':'ghcr.io/mul-cps/cps-compute@sha256:'+'9'*64,'endpoint_proposal':proposal,'actual_endpoint_seed':endpoint_seed,
        'expected_snapshot_sha256':canonical_sha256(snapshot),'expected_release_sha256':canonical_sha256(observed['release']),
        'expected_operator_baselines_sha256':canonical_sha256(operators),'expected_revision':context.approval_ref['revision']}


def prepare(values):
    return load('head_gateway_rotation').prepare(**values)


def mounted_fixture(*, api_defaults=False):
    values=fixture();snapshot=values['snapshot'];deployment=snapshot['deployments']['gateway']
    path=HERE.parent/'current-group-integration'/'gateway_rollout.py'
    spec=importlib.util.spec_from_file_location('mounted_gateway_rollout',path)
    rollout=importlib.util.module_from_spec(spec);spec.loader.exec_module(rollout)
    desired=rollout.compose_gateway(deployment,values['endpoint_proposal'],values['actual_endpoint_seed'],
        expected={k:deployment['metadata'][k]for k in ('namespace','name','uid','resourceVersion')})['spec']
    # Model an independently reviewed permission repair without accepting an
    # arbitrary command copied from the captured live Deployment.
    marker='\n# Independently reviewed 0660-to-0600 permission repair fixture\n'
    values['endpoint_proposal']['gateway']['initContainer']['command'][-1]+=marker
    values['expected_endpoint_proposal_sha256']=canonical_sha256(values['endpoint_proposal'])
    initializer=next(c for c in desired['template']['spec']['initContainers']if c['name']=='native-kai-private-inputs')
    initializer['command'][-1]+=marker
    if api_defaults:
        defaults={'imagePullPolicy':'IfNotPresent','resources':{},
            'terminationMessagePath':'/dev/termination-log','terminationMessagePolicy':'File'}
        assert not set(defaults)&set(values['endpoint_proposal']['gateway']['initContainer'])
        initializer.update(defaults)
    deployment['spec']=desired
    meta=deployment['metadata']
    snapshot['objects'][image._key('Deployment',meta['namespace'],meta['name'])]=copy.deepcopy(deployment)
    values['expected_snapshot_sha256']=canonical_sha256(snapshot)
    return values


@pytest.mark.parametrize('api_defaults',[False,True])
def test_mounted_coordinator_rotation_preserves_reviewed_repair_and_full_spec(api_defaults):
    values=mounted_fixture(api_defaults=api_defaults);before=copy.deepcopy(values)
    module,prepared,node,bound,created=phases(values)
    result=ready_bind(values,module,bound,created)
    assert values==before
    expected=copy.deepcopy(values['snapshot']['deployments']['gateway']['spec'])
    pod=expected['template']['spec']
    for section,names in [('containers',{'gateway','approval-capture'}),
                          ('initContainers',{'capture-private-inputs','native-kai-private-inputs'})]:
        for container in pod[section]:
            if container['name']in names:container['image']=values['gateway_image']
    next(v for v in pod['volumes']if v['name']=='cps-native-approval-publisher')['configMap']['name']=created['gateway.publisher']['metadata']['name']
    next(v for v in pod['volumes']if v['name']=='kai-seed')['configMap']['name']=created['coordinator.seed']['metadata']['name']
    assert bound['runtime_specs']['gateway']==expected
    assert result['runtime_specs']['gateway']==expected
    reviewed=values['endpoint_proposal']['gateway']['initContainer']['command']
    assert next(c for c in pod['initContainers']if c['name']=='native-kai-private-inputs')['command']==reviewed
    assert result['endpoint_proposal']['gateway']['initContainer']['command']==reviewed
    assert result['observer_release']['heads']==values['previous_release']['heads']
    assert len(result['operator_baselines'])==4
    assert result['operator_baselines']==values['operator_baselines']
    namespace=image._context(values['snapshot'])[1].document['component_declarations']['node']['namespace']
    assert set(result['patches'])=={'gateway.runtime-secret','gateway.deployment','node.deployment',
        'component-role:'+namespace+'/cps-native-approval-node',
        'component-role:'+namespace+'/cps-native-approval-gateway'}


@pytest.mark.parametrize('field,value',[
    ('imagePullPolicy','Always'),('resources',{'requests':{'cpu':'100m'}}),
    ('terminationMessagePath','/foreign/log'),('terminationMessagePolicy','FallbackToLogsOnError'),
    ('stdin',True)])
def test_mounted_initializer_rejects_nondefault_or_unknown_api_fields(field,value):
    values=mounted_fixture(api_defaults=True);snapshot=values['snapshot']
    deployment=snapshot['deployments']['gateway'];meta=deployment['metadata']
    initializer=next(c for c in deployment['spec']['template']['spec']['initContainers']if c['name']=='native-kai-private-inputs')
    initializer[field]=value
    snapshot['objects'][image._key('Deployment',meta['namespace'],meta['name'])]=copy.deepcopy(deployment)
    values['expected_snapshot_sha256']=canonical_sha256(snapshot)
    with pytest.raises(ValueError):prepare(values)


@pytest.mark.parametrize('fault',['env','mount','seed','current-node-ref','init-image','init-command'])
def test_mounted_coordinator_drift_is_rejected_after_snapshot_repin(fault):
    values=mounted_fixture();snapshot=values['snapshot']
    pod=snapshot['deployments']['gateway']['spec']['template']['spec']
    main=next(c for c in pod['containers']if c['name']=='gateway')
    initializer=next(c for c in pod['initContainers']if c['name']=='native-kai-private-inputs')
    if fault=='env':next(e for e in main['env']if e['name']=='CPS_NATIVE_KAI_COORDINATOR_CONFIG')['value']='/foreign/coordinator.json'
    elif fault=='mount':main['volumeMounts'][-1]['mountPath']+='/foreign'
    elif fault=='seed':next(v for v in pod['volumes']if v['name']=='kai-seed')['configMap']['name']='foreign-seed'
    elif fault=='current-node-ref':
        seed=values['actual_endpoint_seed'];body=json.loads(seed['data']['coordinator.json'])
        body['nodeConfigurationRef']['uid']=str(uuid.uuid4());seed['data']['coordinator.json']=json.dumps(body)
    elif fault=='init-image':initializer['image']='ghcr.io/mul-cps/cps-compute@sha256:'+'7'*64
    else:initializer['command'][-1]+='\n# Unreviewed live-only command change\n'
    deployment=snapshot['deployments']['gateway'];meta=deployment['metadata']
    snapshot['objects'][image._key('Deployment',meta['namespace'],meta['name'])]=copy.deepcopy(deployment)
    values['expected_snapshot_sha256']=canonical_sha256(snapshot)
    with pytest.raises(ValueError):prepare(values)


@pytest.mark.parametrize('pin',[None,'sha256:'+'0'*64])
def test_mounted_coordinator_requires_independent_reviewed_endpoint_pin(pin):
    values=mounted_fixture()
    if pin is None:values.pop('expected_endpoint_proposal_sha256')
    else:values['expected_endpoint_proposal_sha256']=pin
    with pytest.raises(ValueError):prepare(values)


def test_staged_endpoint_seed_is_not_an_existing_mounted_coordinator():
    values=fixture();snapshot=values['snapshot'];gateway=snapshot['deployments']['gateway']['spec']['template']['spec']
    assert len({d['metadata']['namespace']for d in snapshot['deployments'].values()})==4
    assert len(values['previous_release']['roles'])==7 and len(values['operator_baselines'])==4
    assert not any(e['name']=='CPS_NATIVE_KAI_COORDINATOR_CONFIG'for c in gateway['containers']for e in c.get('env',[]))
    assert not any(v.get('configMap',{}).get('name')==values['actual_endpoint_seed']['metadata']['name']for v in gateway['volumes'])
    result=prepare(values)
    assert set(result['creates'])=={'node-config'}


def phases(values):
    module=load('head_gateway_rotation');prepared=module.prepare(**values)
    node=actual(prepared['creates']['node-config'])
    bound=module.bind_node(values['snapshot'],prepared,node)
    created={label:actual(cm)for label,cm in bound['creates'].items()}
    return module,prepared,node,bound,created


def ready_bind(values,module,bound,created):
    pending=module.bind(values['snapshot'],bound,created)
    permissions={label:actual(obj)for label,obj in pending['creates'].items()}
    result=module.bind(values['snapshot'],bound,created,actual_permissions=permissions)
    assert result['permissions_pending'] is False
    assert result['operator_baselines']==values['operator_baselines']
    assert not any(label.startswith('operator-role:')for label in result['patches'])
    return result


def test_complete_rotation_preserves_head_history_peer_images_and_all_role_identities():
    values=fixture();before=copy.deepcopy(values)
    module,prepared,node,bound,created=phases(values)
    assert set(bound['creates'])=={'node.bootstrap','gateway.publisher','coordinator.seed'}
    assert created['node.bootstrap']['data']['release']=='false'
    result=ready_bind(values,module,bound,created)
    assert values==before
    old_cfg=image._parse(image.volume(values['snapshot'],'node','packaged-bootstrap-input')['data']['config-ref.json'])
    old_node=image._get(values['snapshot'],'ConfigMap',old_cfg['namespace'],old_cfg['name'])
    old_body=image._parse(old_node['data']['config.json']);new_body=image._parse(node['data']['config.json'])
    expected=copy.deepcopy(old_body);expected['component_declarations']['gateway']['image']=values['gateway_image']
    assert new_body==expected and new_body['approval_head']==old_body['approval_head']
    assert result['observer_release']['version']==2
    assert result['observer_release']['heads']==values['previous_release']['heads']
    for field in ('namespace','name','uid'):
        assert [r[field]for r in result['observer_release']['roles']]==[r[field]for r in values['previous_release']['roles']]
        assert [r[field]for r in result['operator_baselines']]==[r[field]for r in values['operator_baselines']]
    allowed={node['metadata']['name'],*(v['metadata']['name']for v in created.values())}
    for olds,news in ((values['previous_release']['roles'],result['observer_release']['roles']),
                      (values['operator_baselines'],result['operator_baselines'])):
        for old,new in zip(olds,news):
            assert len(old['rules'])==len(new['rules'])
            for a,b in zip(old['rules'],new['rules']):
                if a==b:continue
                assert a['apiGroups']==b['apiGroups']==[''] and a['resources']==b['resources']==['configmaps']
                assert a['verbs']==b['verbs']==['get']
                assert {k:v for k,v in a.items()if k!='resourceNames'}=={k:v for k,v in b.items()if k!='resourceNames'}
                assert set(a['resourceNames'])<=set(b['resourceNames'])
                assert set(b['resourceNames'])-set(a['resourceNames'])<=allowed
    originals={d['metadata']['uid']:d for d in values['snapshot']['deployments'].values()}
    for dep in result['prospective_capture']['deployments']:
        old=originals[dep['metadata']['uid']]
        if dep['metadata']['namespace']!=old_body['component_declarations']['gateway']['namespace']:
            assert dep['spec']['template']['spec']['containers']==old['spec']['template']['spec']['containers']
    assert result['patches']


@pytest.mark.parametrize('field',['expected_snapshot_sha256','expected_release_sha256','expected_operator_baselines_sha256','expected_revision'])
def test_prepare_refuses_unreviewed_pins(field):
    values=fixture();values[field]='sha256:'+'0'*64
    with pytest.raises(ValueError):prepare(values)


@pytest.mark.parametrize('fault',['uid','data','mutable','owner','missing'])
def test_actual_endpoint_seed_is_mandatory_and_exact(fault):
    values=fixture();seed=values['actual_endpoint_seed']
    if fault=='uid':seed['metadata']['uid']=str(uuid.UUID(int=0))
    elif fault=='data':seed['data']['coordinator.json']='{}'
    elif fault=='mutable':seed['immutable']=False
    elif fault=='owner':seed['metadata']['ownerReferences']=[{'kind':'Deployment','uid':str(uuid.uuid4())}]
    else:values['actual_endpoint_seed']=None
    with pytest.raises(ValueError):prepare(values)


@pytest.mark.parametrize('target',['observer','operator'])
def test_live_role_privilege_drift_never_becomes_trusted_baseline(target):
    values=fixture();row=(values['previous_release']['roles']if target=='observer' else values['operator_baselines'])[0]
    obj=image._get(values['snapshot'],'Role',row['namespace'],row['name'])
    obj['rules'].append({'apiGroups':[''],'resources':['secrets'],'verbs':['get']})
    # Repinning the capture cannot promote new API privileges into reviewed rules.
    values['expected_snapshot_sha256']=canonical_sha256(values['snapshot'])
    with pytest.raises(ValueError):prepare(values)


@pytest.mark.parametrize('fault',['node-uid','node-data','node-owner','node-mutable','plan'])
def test_node_bind_refuses_changed_actual_node_config_or_prepared_plan(fault):
    values=fixture();module=load('head_gateway_rotation');prepared=prepare(values);node=actual(prepared['creates']['node-config'])
    if fault=='node-uid':node['metadata']['uid']=str(uuid.UUID(int=0))
    elif fault=='node-data':node['data']['config.json']='{}'
    elif fault=='node-owner':node['metadata']['ownerReferences']=[{'uid':str(uuid.uuid4())}]
    elif fault=='node-mutable':node['immutable']=False
    else:prepared['creates']['node-config']['data']['config.json']='{}'
    with pytest.raises(ValueError):module.bind_node(values['snapshot'],prepared,node)


def test_existing_staged_prepared_plan_without_optional_proposal_pin_still_binds():
    values=fixture();module=load('head_gateway_rotation');prepared=prepare(values)
    # Retained staged plans predate the mounted-only independent proposal pin.
    prepared['inputs'].pop('expected_endpoint_proposal_sha256',None)
    node=actual(prepared['creates']['node-config'])
    bound=module.bind_node(values['snapshot'],prepared,node)
    assert bound['actual_node_config']==node
    assert bound['prepared']==prepared
    assert set(bound['creates'])=={'node.bootstrap','gateway.publisher','coordinator.seed'}


@pytest.mark.parametrize('fault',['missing','extra','uid','data','owner','mutable','plan'])
def test_final_bind_requires_exact_three_actual_created_objects(fault):
    values=fixture();module,prepared,node,bound,created=phases(values)
    if fault=='missing':created.pop('gateway.publisher')
    elif fault=='extra':created['unexpected']=copy.deepcopy(created['gateway.publisher'])
    elif fault=='uid':created['gateway.publisher']['metadata']['uid']=str(uuid.UUID(int=0))
    elif fault=='data':created['gateway.publisher']['data']['publisher.json']='{}'
    elif fault=='owner':created['gateway.publisher']['metadata']['ownerReferences']=[{'uid':str(uuid.uuid4())}]
    elif fault=='mutable':created['gateway.publisher']['immutable']=False
    else:bound['creates']['node.bootstrap']['data']['release']='true'
    with pytest.raises(ValueError):module.bind(values['snapshot'],bound,created)


def test_already_mounted_coordinator_is_not_reapplied_as_staged_seed():
    values=fixture();pod=values['snapshot']['deployments']['gateway']['spec']['template']['spec']
    declaration=image._context(values['snapshot'])[1].document['component_declarations']['gateway']
    main=next(c for c in pod['containers']if c['name']==declaration['container'])
    main['env']+=copy.deepcopy(values['endpoint_proposal']['gateway']['env'])
    values['expected_snapshot_sha256']=canonical_sha256(values['snapshot'])
    with pytest.raises(ValueError):prepare(values)


@pytest.mark.parametrize('component',['gateway','hub:cps','hub:cit','node'])
def test_mounted_head_drift_is_rejected_even_after_snapshot_repin(component):
    values=fixture();pod=values['snapshot']['deployments'][component]['spec']['template']['spec']
    volume=next(v for v in pod['volumes']if v['name']=='cps-native-head-anchor')
    volume['configMap']['name']='foreign-head-projection'
    values['expected_snapshot_sha256']=canonical_sha256(values['snapshot'])
    with pytest.raises(ValueError):prepare(values)


def test_actual_observer_renderer_accepts_prospective_capture_with_exact_operator_deltas():
    from cps_compute.native_group_process import _template
    values=fixture();module,prepared,node,bound,created=phases(values)
    result=ready_bind(values,module,bound,created)
    release=result['observer_release'];capture=result['prospective_capture']
    policy=image._context(values['snapshot'])[0]
    path=HERE.parents[2]/'native-observer-operator'/'render.py'
    spec=importlib.util.spec_from_file_location('rotation_observer_renderer',path)
    renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
    rendered=renderer.render(release,canonical_sha256(release),policy.catalog,capture,
        'ghcr.io/mul-cps/cps-native-observer@sha256:'+'8'*64)
    deployment=next(v for v in rendered if v['kind']=='Deployment')
    assert deployment['spec']['replicas']==0  # Prospective validation is not live readiness.
    assert result['operator_baselines']==values['operator_baselines']
    assert result['previous_node_template_sha256']==canonical_sha256(result['previous_node_template'])
    assert result['previous_node_template_sha256']==values['previous_release']['held_node_template_sha256']
    future_node=next(d for d in capture['deployments']if d['metadata']['uid']==values['snapshot']['deployments']['node']['metadata']['uid'])
    assert release['held_node_template_sha256']==canonical_sha256(_template(future_node))
    assert release['held_node_template_sha256']!=values['previous_release']['held_node_template_sha256']


def test_separate_read_grants_must_be_published_before_any_active_patches():
    values=fixture();module,prepared,node,bound,created=phases(values)
    pending=module.bind(values['snapshot'],bound,created)
    assert pending['permissions_pending'] is True and pending['patches']=={}
    assert pending['operator_baselines']==values['operator_baselines']
    assert set(pending['creates'])=={'observer.read-role','observer.read-binding'}
    role=pending['creates']['observer.read-role'];binding=pending['creates']['observer.read-binding']
    namespace=node['metadata']['namespace']
    assert role['kind']=='Role' and role['metadata']['namespace']==namespace
    assert role['rules']==[{'apiGroups':[''],'resources':['configmaps'],'verbs':['get'],
        'resourceNames':sorted([node['metadata']['name'],created['node.bootstrap']['metadata']['name']])}]
    assert binding['kind']=='RoleBinding' and binding['metadata']['namespace']==namespace
    assert binding['subjects']==[{'kind':'ServiceAccount','name':'cps-native-observer-operator','namespace':namespace}]
    assert binding['roleRef']=={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':role['metadata']['name']}
    assert module.bind(values['snapshot'],bound,created)['creates']==pending['creates']
    assert 'uid' not in role['metadata'] and 'resourceVersion' not in role['metadata']
    ready=ready_bind(values,module,bound,created)
    assert len(ready['patches'])==5


@pytest.mark.parametrize('fault',['missing','extra','role-uid','role-rv','binding-uid','binding-rv',
    'role-owner','binding-owner','rules','subject','role-ref','role-name','binding-name','namespace'])
def test_active_patches_require_exact_actual_separate_permission_readbacks(fault):
    values=fixture();module,prepared,node,bound,created=phases(values)
    pending=module.bind(values['snapshot'],bound,created)
    permissions={label:actual(obj)for label,obj in pending['creates'].items()}
    role=permissions['observer.read-role'];binding=permissions['observer.read-binding']
    if fault=='missing':permissions.pop('observer.read-role')
    elif fault=='extra':permissions['extra']=copy.deepcopy(role)
    elif fault.endswith('-uid'):(role if fault.startswith('role-')else binding)['metadata']['uid']=str(uuid.UUID(int=0))
    elif fault.endswith('-rv'):(role if fault.startswith('role-')else binding)['metadata']['resourceVersion']='0'
    elif fault.endswith('-owner'):(role if fault.startswith('role-')else binding)['metadata']['ownerReferences']=[{'uid':str(uuid.uuid4())}]
    elif fault=='rules':role['rules'][0]['verbs'].append('list')
    elif fault=='subject':binding['subjects'][0]['name']='foreign-operator'
    elif fault=='role-ref':binding['roleRef']['name']='foreign-role'
    elif fault=='role-name':role['metadata']['name']='foreign-role'
    elif fault=='binding-name':binding['metadata']['name']='foreign-binding'
    else:binding['metadata']['namespace']='foreign-system'
    with pytest.raises(ValueError):
        module.bind(values['snapshot'],bound,created,actual_permissions=permissions)


@pytest.mark.parametrize('fault',[None,'zero-uid','owner'])
def test_captured_observer_service_account_uid_is_preserved_or_rejected(fault):
    values=fixture();namespace=image._context(values['snapshot'])[1].reference.to_dict()['namespace']
    account={'apiVersion':'v1','kind':'ServiceAccount','metadata':{'namespace':namespace,
        'name':'cps-native-observer-operator','uid':str(uuid.uuid4()),'resourceVersion':'73'}}
    if fault=='zero-uid':account['metadata']['uid']=str(uuid.UUID(int=0))
    elif fault=='owner':account['metadata']['ownerReferences']=[{'uid':str(uuid.uuid4())}]
    values['snapshot']['objects'][image._key('ServiceAccount',namespace,account['metadata']['name'])]=account
    values['expected_snapshot_sha256']=canonical_sha256(values['snapshot'])
    module,prepared,node,bound,created=phases(values)
    if fault is not None:
        with pytest.raises(ValueError):module.bind(values['snapshot'],bound,created)
    else:
        pending=module.bind(values['snapshot'],bound,created)
        assert pending['observer_service_account']=={k:account['metadata'][k]for k in ('namespace','name','uid')}


def test_node_only_successor_updates_all_node_image_pins_and_preserves_hubs():
    values=mounted_fixture(api_defaults=True);snapshot=values['snapshot']
    _,old=image._context(snapshot)
    values['gateway_image']=old.document['component_declarations']['gateway']['image']
    values['node_image']='ghcr.io/mul-cps/cps-native-node@sha256:'+'8'*64
    prepared=prepare(values);node=actual(prepared['creates']['node-config'])
    bound=load('head_gateway_rotation').bind_node(snapshot,prepared,node)
    new=json.loads(node['data']['config.json'])
    assert new['component_declarations']['node']['image']==values['node_image']
    expected_document=copy.deepcopy(old.document)
    expected_document['component_declarations']['node']['image']=values['node_image']
    assert new==expected_document
    assert new['component_declarations']['gateway']==old.document['component_declarations']['gateway']
    pod=bound['runtime_specs']['node']['template']['spec']
    assert next(c for c in pod['containers'] if c['name']==old.document['component_declarations']['node']['container'])['image']==values['node_image']
    assert next(c for c in pod['initContainers'] if c['name']=='packaged-bootstrap')['image']==values['node_image']
    bootstrap=next(c for c in pod['initContainers'] if c['name']=='packaged-bootstrap')
    assert next(e for e in bootstrap['env'] if e['name']=='NODE_IMAGE')=={'name':'NODE_IMAGE','value':values['node_image']}
    runtime=image._decode(bound['gateway_runtime_patch']['patch'][-1]['value']['runtime.json'])
    assert runtime['nativeGroupApprovals']['processes']['node']['image']==values['node_image']
    expected_runtime=image._decode(image.secret_volume(snapshot,'gateway','config')['data']['runtime.json'])
    expected_runtime['nativeGroupApprovals']['processes']['node']['image']=values['node_image']
    assert runtime==expected_runtime
    capture=bound['creates']['gateway.capture-seed']
    assert capture['kind']=='Secret' and capture['type']=='Opaque' and capture['immutable'] is True
    assert image._decode(capture['data']['config.json'])['node_process']['image']==values['node_image']
    expected_capture=copy.deepcopy(image.secret_volume(snapshot,'gateway','capture-seed')['data'])
    capture_settings=image._decode(expected_capture['config.json'])
    capture_settings['node_process']['image']=values['node_image']
    expected_capture['config.json']=image._encoded(capture_settings)
    assert capture['data']==expected_capture
    assert bound['endpoint_proposal']['coordinator']['epoch']['nodeProcess']['image']==values['node_image']
    assert next(v for v in bound['runtime_specs']['gateway']['template']['spec']['volumes'] if v['name']=='capture-seed')['secret']['secretName']==capture['metadata']['name']
    for source in ('cps','cit'):assert bound['runtime_specs']['hub:'+source]==snapshot['deployments']['hub:'+source]['spec']
    actuals={label:actual(candidate) for label,candidate in bound['creates'].items()}
    pending=load('head_gateway_rotation').bind(snapshot,bound,actuals)
    complete=load('head_gateway_rotation').bind(snapshot,bound,actuals,
        actual_permissions={label:actual(candidate) for label,candidate in pending['creates'].items()})
    assert set(complete['patches'])=={'gateway.runtime-secret','gateway.deployment','node.deployment',
        'component-role:'+old.document['component_declarations']['node']['namespace']+'/cps-native-approval-gateway',
        'component-role:'+old.document['component_declarations']['node']['namespace']+'/cps-native-approval-node'}
    assert all(o['kind']=='ConfigMap' for o in complete['prospective_capture']['configmaps'])


@pytest.mark.parametrize('value',['ghcr.io/mul-cps/cps-native-node:latest',
    'ghcr.io/mul-cps/cps-native-node@sha256:'+'0'*64,
    'ghcr.io/foreign/node@sha256:'+'8'*64,False])
def test_node_successor_requires_exact_reviewed_repository_digest(value):
    values=mounted_fixture();values['node_image']=value
    with pytest.raises(ValueError):prepare(values)


STOCK_CDI_FILE='k8s.device-plugin.nvidia.com-gpu.json'
CDI_FILES={'stock_cdi_update':STOCK_CDI_FILE,'management_cdi_update':'management.nvidia.com-gpu.yaml'}


def stock_cdi_fixture(monkeypatch,provider='stock_cdi_update'):
    from test_observer_adoption import image_tests
    original=image_tests.node_fixture
    def node_fixture():
        policy,node,core,maps=original()
        document=json.loads(node['data']['config.json'])
        document['cdi_pins']['other_cdi_files'].update({name:'a'*64 for name in CDI_FILES.values()})
        node['data']['config.json']=image.canonical(document)
        return policy,node,core,maps
    monkeypatch.setattr(image_tests,'node_fixture',node_fixture)
    values=mounted_fixture(api_defaults=True)
    _,old=image._context(values['snapshot'])
    values['gateway_image']=old.document['component_declarations']['gateway']['image']
    values[provider]={'previous_sha256':'a'*64,'sha256':'b'*64}
    return values,old


@pytest.mark.parametrize('provider',CDI_FILES)
def test_cdi_only_rotation_preserves_every_other_pin_and_process(monkeypatch,provider):
    values,old=stock_cdi_fixture(monkeypatch,provider);before=copy.deepcopy(values)
    module,prepared,node,bound,created=phases(values)
    expected=old.document
    expected['cdi_pins']['other_cdi_files'][CDI_FILES[provider]]='b'*64
    assert json.loads(node['data']['config.json'])==expected
    assert values==before
    for component,spec in bound['runtime_specs'].items():
        previous=values['snapshot']['deployments'][component]['spec']['template']['spec']
        for section in ('containers','initContainers'):
            assert [(c['name'],c['image']) for c in spec['template']['spec'].get(section,[])]==[
                (c['name'],c['image']) for c in previous.get(section,[])]
    assert set(created)=={'node.bootstrap','gateway.publisher','coordinator.seed'}
    result=ready_bind(values,module,bound,created)
    assert result['observer_release']['heads']==values['previous_release']['heads']
    assert result['operator_baselines']==values['operator_baselines']
    for component in ('hub:cps','hub:cit'):
        assert result['runtime_specs'][component]==values['snapshot']['deployments'][component]['spec']
    runtime=image._decode(bound['gateway_runtime_patch']['patch'][-1]['value']['runtime.json'])
    assert runtime==image._decode(image.secret_volume(values['snapshot'],'gateway','config')['data']['runtime.json'])
    changed=copy.deepcopy(node);document=json.loads(changed['data']['config.json'])
    document['cdi_pins']['selected_filename']='foreign.json'
    changed['data']['config.json']=image.canonical(document)
    with pytest.raises(ValueError):module.bind_node(values['snapshot'],prepared,changed)
    changed=copy.deepcopy(bound);changed['runtime_specs']['node']['template']['spec']['initContainers'][0]['image']='foreign'
    with pytest.raises(ValueError):module.bind(values['snapshot'],changed,created)


@pytest.mark.parametrize('update',[
    {'previous_sha256':'c'*64,'sha256':'b'*64},
    {'previous_sha256':'0'*64,'sha256':'b'*64},
    {'previous_sha256':'A'*64,'sha256':'b'*64},
    {'previous_sha256':'a'*64,'sha256':'a'*64},
    {'previous_sha256':'a'*64,'sha256':'0'*64},
    {'previous_sha256':'a'*64,'sha256':'B'*64},
    {'previous_sha256':'a'*64,'sha256':'sha256:'+'b'*64},
    {'previous_sha256':'a'*64,'sha256':False},
    {'previous_sha256':'a'*64},
    *[{'previous_sha256':'a'*64,'sha256':'b'*64,key:'foreign'} for key in (
        'filename','selected_filename','common_edits_sha256','runtime_files','other_cdi_files')],
])
@pytest.mark.parametrize('provider',CDI_FILES)
def test_cdi_update_rejects_stale_malformed_or_expanded_scope(monkeypatch,update,provider):
    values,_=stock_cdi_fixture(monkeypatch,provider);values[provider]=update
    with pytest.raises(ValueError):prepare(values)


def test_absent_stock_cdi_update_preserves_existing_plan_exactly():
    values=mounted_fixture();module=load('head_gateway_rotation')
    assert module.prepare(**values,stock_cdi_update=None,management_cdi_update=None)==module.prepare(**values)



@pytest.mark.parametrize('provider',CDI_FILES)
def test_cdi_update_cannot_add_a_missing_provider_pin(provider):
    values=mounted_fixture();_,old=image._context(values['snapshot'])
    assert CDI_FILES[provider] not in old.document['cdi_pins']['other_cdi_files']
    values['gateway_image']=old.document['component_declarations']['gateway']['image']
    values[provider]={'previous_sha256':'a'*64,'sha256':'b'*64}
    with pytest.raises(ValueError):prepare(values)



@pytest.mark.parametrize('provider',CDI_FILES)
@pytest.mark.parametrize('component',['gateway','node'])
def test_cdi_pin_updates_cannot_be_combined_with_image_changes(monkeypatch,provider,component):
    values,_=stock_cdi_fixture(monkeypatch,provider)
    if component=='gateway':values['gateway_image']='ghcr.io/mul-cps/cps-compute@sha256:'+'8'*64
    else:values['node_image']='ghcr.io/mul-cps/cps-native-node@sha256:'+'8'*64
    with pytest.raises(ValueError):prepare(values)


def test_management_and_stock_pin_updates_are_mutually_exclusive(monkeypatch):
    values,_=stock_cdi_fixture(monkeypatch)
    values['management_cdi_update']={'previous_sha256':'a'*64,'sha256':'c'*64}
    with pytest.raises(ValueError):prepare(values)

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


def test_complete_rotation_preserves_head_history_peer_images_and_all_role_identities():
    values=fixture();before=copy.deepcopy(values)
    module,prepared,node,bound,created=phases(values)
    assert set(bound['creates'])=={'node.bootstrap','gateway.publisher','coordinator.seed'}
    assert created['node.bootstrap']['data']['release']=='false'
    result=module.bind(values['snapshot'],bound,created)
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
    result=module.bind(values['snapshot'],bound,created)
    release=result['observer_release'];capture=result['prospective_capture']
    policy=image._context(values['snapshot'])[0]
    path=HERE.parents[2]/'native-observer-operator'/'render.py'
    spec=importlib.util.spec_from_file_location('rotation_observer_renderer',path)
    renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
    rendered=renderer.render(release,canonical_sha256(release),policy.catalog,capture,
        'ghcr.io/mul-cps/cps-native-observer@sha256:'+'8'*64)
    deployment=next(v for v in rendered if v['kind']=='Deployment')
    assert deployment['spec']['replicas']==0  # Prospective validation is not live readiness.
    namespace=node['metadata']['namespace']
    for old,new in zip(values['operator_baselines'],result['operator_baselines']):
        if old['namespace']!=namespace:
            assert new==old
            continue
        expected=copy.deepcopy(old)
        names=expected['rules'][old['index']]['resourceNames']
        expected['rules'][old['index']]['resourceNames']=sorted(set(names)|{
            node['metadata']['name'],created['node.bootstrap']['metadata']['name']})
        assert new==expected
    assert result['previous_node_template_sha256']==canonical_sha256(result['previous_node_template'])
    assert result['previous_node_template_sha256']==values['previous_release']['held_node_template_sha256']
    future_node=next(d for d in capture['deployments']if d['metadata']['uid']==values['snapshot']['deployments']['node']['metadata']['uid'])
    assert release['held_node_template_sha256']==canonical_sha256(_template(future_node))
    assert release['held_node_template_sha256']!=values['previous_release']['held_node_template_sha256']

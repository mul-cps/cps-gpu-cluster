"""Current mounted-endpoint, paired-Hub-only v4 trust rotation proposals."""
import copy,json
from pathlib import Path
import pytest
from cps_compute.native_groups import canonical_sha256
from test_head_gateway_rotation import fixture as gateway_fixture,load,actual,image

HERE=Path(__file__).parent

def fixture():
    v=gateway_fixture();snapshot=v['snapshot']
    rollout=load('head_gateway_rotation')._module(HERE.parent/'current-group-integration'/'gateway_rollout.py')
    dep=snapshot['deployments']['gateway']
    composed=rollout.compose_gateway(dep,v['endpoint_proposal'],v['actual_endpoint_seed'],
        expected={k:dep['metadata'][k]for k in ('namespace','name','uid','resourceVersion')})
    dep['spec']=composed['spec']
    snapshot['objects'][image._key('Deployment',dep['metadata']['namespace'],dep['metadata']['name'])]=copy.deepcopy(dep)
    for component in ('hub:cps','hub:cit'):
        dep=snapshot['deployments'][component];pod=dep['spec']['template']['spec']
        pod.setdefault('initContainers',[]).append({'name':'cps-native-kai-hub-inputs',
            'image':pod['containers'][0]['image'],'command':['python','-c','materialize_fixed_inputs()']})
        snapshot['objects'][image._key('Deployment',dep['metadata']['namespace'],dep['metadata']['name'])]=copy.deepcopy(dep)
    return {k:value for k,value in v.items()if k not in ('gateway_image','endpoint_proposal','actual_endpoint_seed','expected_snapshot_sha256')}|{
        'hub_image':'ghcr.io/mul-cps/cps-compute@sha256:'+'8'*64,'snapshot':snapshot,
        'expected_snapshot_sha256':canonical_sha256(snapshot)}

def module():
    assert (HERE/'head_hub_rotation.py').exists(),'Dedicated current v4 Hub-pair rotation composer required'
    return load('head_hub_rotation')

def phases(values):
    m=module();p=m.prepare(**values);node=actual(p['creates']['node-config'])
    b=m.bind_node(values['snapshot'],p,node);created={k:actual(v)for k,v in b['creates'].items()}
    return m,p,node,b,created


def personal_cpu_fixture(monkeypatch):
    import test_native_groups
    original=test_native_groups.qualified_catalog
    def catalog():
        value=original()
        value['profiles']['interactive-cpu']={**copy.deepcopy(value['profiles']['cpu']),'enabled':True}
        return value
    # Seed the profile before any policy hashes or immutable authorities exist.
    monkeypatch.setattr(test_native_groups,'qualified_catalog',catalog)
    return fixture()


@pytest.mark.parametrize('existing',[False,True])
def test_personal_cpu_opt_in_changes_only_two_hub_main_envs_and_reuses_exact_literal(monkeypatch,existing):
    v=personal_cpu_fixture(monkeypatch);literal={'name':'CPS_PERSONAL_CPU_PROFILE_ALIASES','value':'{"cpu-default":"interactive-cpu"}'}
    if existing:
        for component in ('hub:cps','hub:cit'):
            dep=v['snapshot']['deployments'][component]
            dep['spec']['template']['spec']['containers'][0].setdefault('env',[]).append(copy.deepcopy(literal))
            meta=dep['metadata'];v['snapshot']['objects'][image._key('Deployment',meta['namespace'],meta['name'])]=copy.deepcopy(dep)
        v['expected_snapshot_sha256']=canonical_sha256(v['snapshot'])
    ordinary=copy.deepcopy(v);v['personal_cpu_profile_aliases']={'cpu-default':'interactive-cpu'}
    before=copy.deepcopy(v);m,p,node,b,created=phases(v)
    old=m.bind_node(v['snapshot'],m.prepare(**ordinary),node)
    for component,spec in old['runtime_specs'].items():
        expected=copy.deepcopy(spec)
        if component in ('hub:cps','hub:cit'):
            env=expected['template']['spec']['containers'][0].setdefault('env',[])
            if not existing:env.append(literal)
            assert [e for e in b['runtime_specs'][component]['template']['spec']['containers'][0]['env']
                if e['name']==literal['name']]==[literal]
        assert b['runtime_specs'][component]==expected
    pending=m.bind(v['snapshot'],b,created)
    permissions={k:actual(o)for k,o in pending['creates'].items()}
    result=m.bind(v['snapshot'],b,created,actual_permissions=permissions)
    namespace=image._context(v['snapshot'])[1].document['component_declarations']['node']['namespace']
    assert set(result['patches'])=={'gateway.runtime-secret','node.deployment','gateway.deployment',
        'hub:cps.deployment','hub:cit.deployment','component-role:'+namespace+'/cps-native-approval-node',
        'component-role:'+namespace+'/cps-native-approval-gateway'}
    assert result['runtime_specs']==b['runtime_specs'] and v==before
    assert result['observer_release']['heads']==v['previous_release']['heads']
    assert result['operator_baselines']==v['operator_baselines']


@pytest.mark.parametrize('aliases',[{},[],True,{'cpu-default':'cpu'},
    {'other':'interactive-cpu'},{'cpu-default':'interactive-cpu','extra':'interactive-cpu'}])
def test_personal_cpu_opt_in_rejects_any_other_mapping(monkeypatch,aliases):
    v=personal_cpu_fixture(monkeypatch);v['personal_cpu_profile_aliases']=aliases
    with pytest.raises(ValueError):module().prepare(**v)


@pytest.mark.parametrize('fault',['duplicate','value-from','conflict'])
def test_personal_cpu_opt_in_rejects_ambiguous_existing_hub_environment(monkeypatch,fault):
    v=personal_cpu_fixture(monkeypatch);v['personal_cpu_profile_aliases']={'cpu-default':'interactive-cpu'}
    dep=v['snapshot']['deployments']['hub:cps'];env=dep['spec']['template']['spec']['containers'][0].setdefault('env',[])
    entry={'name':'CPS_PERSONAL_CPU_PROFILE_ALIASES','value':'{"cpu-default":"interactive-cpu"}'}
    if fault=='duplicate':env.extend([copy.deepcopy(entry),copy.deepcopy(entry)])
    elif fault=='value-from':env.append({'name':entry['name'],'valueFrom':{'configMapKeyRef':{'name':'foreign','key':'aliases'}}})
    else:env.append({'name':entry['name'],'value':'{"cpu-default":"foreign"}'})
    meta=dep['metadata'];v['snapshot']['objects'][image._key('Deployment',meta['namespace'],meta['name'])]=copy.deepcopy(dep)
    v['expected_snapshot_sha256']=canonical_sha256(v['snapshot'])
    with pytest.raises(ValueError):
        m=module();p=m.prepare(**v);m.bind_node(v['snapshot'],p,actual(p['creates']['node-config']))


def test_existing_hub_prepared_plan_without_personal_cpu_option_still_binds():
    v=fixture();m=module();p=m.prepare(**v)
    p['inputs'].pop('personal_cpu_profile_aliases',None)
    node=actual(p['creates']['node-config']);bound=m.bind_node(v['snapshot'],p,node)
    assert bound['prepared']==p and bound['actual_node_config']==node


def test_hub_pair_updates_only_reviewed_images_and_immutable_projections():
    v=fixture();before=copy.deepcopy(v);m,p,node,b,created=phases(v)
    assert set(created)=={'node.bootstrap','hub:cps.publisher','hub:cit.publisher','coordinator.seed'}
    pending=m.bind(v['snapshot'],b,created);assert pending['permissions_pending'] and not pending['patches']
    permissions={k:actual(o)for k,o in pending['creates'].items()}
    result=m.bind(v['snapshot'],b,created,actual_permissions=permissions)
    assert not result['permissions_pending'] and v==before
    oldref=v['previous_release']['node_configuration'];old=image._get(v['snapshot'],'ConfigMap',oldref['namespace'],oldref['name'])
    expected=image._parse(old['data']['config.json'])
    for c in ('hub:cps','hub:cit'):expected['component_declarations'][c]['image']=v['hub_image']
    assert image._parse(node['data']['config.json'])==expected
    assert result['observer_release']['heads']==v['previous_release']['heads']
    assert result['operator_baselines']==v['operator_baselines']
    assert result['previous_node_template_sha256']==v['previous_release']['held_node_template_sha256']
    for c,dep in v['snapshot']['deployments'].items():
        spec=copy.deepcopy(dep['spec']);pod=spec['template']['spec']
        if c=='node':next(x for x in pod['volumes']if x['name']=='packaged-bootstrap-input')['configMap']['name']=created['node.bootstrap']['metadata']['name']
        elif c=='gateway':next(x for x in pod['volumes']if x['name']=='kai-seed')['configMap']['name']=created['coordinator.seed']['metadata']['name']
        else:
            pod['containers'][0]['image']=v['hub_image']
            next(x for x in pod['initContainers']if x['name']=='cps-native-kai-hub-inputs')['image']=v['hub_image']
            next(x for x in pod['volumes']if x['name']=='cps-native-approval-publisher')['configMap']['name']=created[c+'.publisher']['metadata']['name']
        assert result['runtime_specs'][c]==spec
    oldseed=image.volume(v['snapshot'],'gateway','kai-seed');newseed=created['coordinator.seed']
    expectedseed=copy.deepcopy(oldseed['data']);cfg=image._parse(expectedseed['coordinator.json']);cfg['nodeConfigurationRef']=b['node_config_ref'];expectedseed['coordinator.json']=image.canonical(cfg)
    assert newseed['data']==expectedseed
    assert created['node.bootstrap']['data']['release']=='false'

@pytest.mark.parametrize('fault',['hub-helper','hub-main','account-uid','coordinator-ref','coordinator-env',
    'publisher-image','head-pointer','bootstrap-held','active-ledger','coordinator-path',
    'main-private-writable','init-seed-writable','init-private-subpath','initializer-image','initializer-missing'])
def test_actual_authority_or_template_drift_is_rejected_after_snapshot_repin(fault):
    v=fixture();s=v['snapshot'];hub=s['deployments']['hub:cps'];pod=hub['spec']['template']['spec']
    if fault=='hub-helper':pod['initContainers'][0]['image']='foreign@sha256:'+'a'*64
    elif fault=='hub-main':pod['containers'][0]['image']='foreign@sha256:'+'a'*64
    elif fault=='account-uid':
        a=image._get(s,'ServiceAccount',hub['metadata']['namespace'],pod['serviceAccountName']);a['metadata']['uid']='11111111-1111-4111-8111-111111111111'
    elif fault=='coordinator-ref':
        cm=image.volume(s,'gateway','kai-seed');body=image._parse(cm['data']['coordinator.json']);body['nodeConfigurationRef']['uid']='11111111-1111-4111-8111-111111111111';cm['data']['coordinator.json']=image.canonical(body)
    elif fault=='coordinator-env':
        main=s['deployments']['gateway']['spec']['template']['spec']['containers'][0];main['env']=[e for e in main['env']if e['name']!='CPS_NATIVE_KAI_COORDINATOR_CONFIG']
    elif fault in ('coordinator-path','main-private-writable','init-seed-writable','init-private-subpath','initializer-image','initializer-missing'):
        gp=s['deployments']['gateway']['spec']['template']['spec'];main=gp['containers'][0];init=next(c for c in gp['initContainers']if c['name']=='native-kai-private-inputs')
        if fault=='coordinator-path':next(e for e in main['env']if e['name']=='CPS_NATIVE_KAI_COORDINATOR_CONFIG')['value']='/unused/coordinator.json'
        elif fault=='main-private-writable':next(m for m in main['volumeMounts']if m['name']=='kai-private')['readOnly']=False
        elif fault=='init-seed-writable':next(m for m in init['volumeMounts']if m['name']=='kai-seed')['readOnly']=False
        elif fault=='init-private-subpath':next(m for m in init['volumeMounts']if m['name']=='kai-private')['subPath']='foreign'
        elif fault=='initializer-image':init['image']='foreign@sha256:'+'a'*64
        else:gp['initContainers'].remove(init)
    elif fault=='publisher-image':
        cm=image.volume(s,'hub:cps','cps-native-approval-publisher');body=image._parse(cm['data']['publisher.json']);body['process']['image']='foreign@sha256:'+'a'*64;cm['data']['publisher.json']=image.canonical(body)
    elif fault=='head-pointer':
        pin=v['previous_release']['heads']['hub:cps']['anchor']['pointer'];image._get(s,'ConfigMap',pin['namespace'],pin['name'])['metadata']['uid']='11111111-1111-4111-8111-111111111111'
    elif fault=='bootstrap-held':image.volume(s,'node','packaged-bootstrap-input')['data']['release']='false'
    else:
        oldref=v['previous_release']['node_configuration'];cfg=image._parse(image._get(s,'ConfigMap',oldref['namespace'],oldref['name'])['data']['config.json']);ns=image._context(s)[1].deployment.authority_namespace;cm=image._get(s,'ConfigMap',ns,'cps-native-gpu-allocations');body=image._parse(cm['data']['state.json']);body['allocations']={'active':{'state':'reserved'}};cm['data']['state.json']=image.canonical(body)
    for dep in s['deployments'].values():s['objects'][image._key('Deployment',dep['metadata']['namespace'],dep['metadata']['name'])]=copy.deepcopy(dep)
    v['expected_snapshot_sha256']=canonical_sha256(s)
    with pytest.raises(ValueError):module().prepare(**v)

@pytest.mark.parametrize('fault',['absent','uid','namespace','data','mutable'])
def test_actual_immutable_successor_readback_required(fault):
    v=fixture();m=module();p=m.prepare(**v);node=actual(p['creates']['node-config'])
    if fault=='absent':node.pop('metadata')
    elif fault=='uid':node['metadata']['uid']='unknown'
    elif fault=='namespace':node['metadata']['namespace']='foreign'
    elif fault=='data':node['data']['config.json']='{}'
    else:node['immutable']=False
    with pytest.raises(ValueError):m.bind_node(v['snapshot'],p,node)

@pytest.mark.parametrize('label',['node.bootstrap','hub:cps.publisher','hub:cit.publisher','coordinator.seed'])
def test_each_actual_dependent_readback_is_exact(label):
    v=fixture();m,p,n,b,created=phases(v);created[label]['data']['unexpected']='changed'
    with pytest.raises(ValueError):m.bind(v['snapshot'],b,created)

def test_peer_settings_secrets_capture_and_source_fields_are_preserved():
    v=fixture();m,p,n,b,created=phases(v)
    old=image.secret_volume(v['snapshot'],'gateway','config');new=b['gateway_runtime_patch']['patch'][-1]['value']
    expected=copy.deepcopy(old['data']);body=image._decode(expected['runtime.json'])
    for c in ('hub:cps','hub:cit'):body['nativeGroupApprovals']['processes'][c]['image']=v['hub_image']
    expected['runtime.json']=image._encoded(body)
    assert new==expected
    for c in ('hub:cps','hub:cit'):
        old=image.volume(v['snapshot'],c,'cps-native-approval-publisher');body=image._parse(old['data']['publisher.json']);body['process']['image']=v['hub_image']
        assert created[c+'.publisher']['data']=={'publisher.json':image.canonical(body)}
    assert b['gateway_runtime_patch']['patch'][:3]==[
        {'op':'test','path':'/metadata/uid','value':image.secret_volume(v['snapshot'],'gateway','config')['metadata']['uid']},
        {'op':'test','path':'/metadata/resourceVersion','value':image.secret_volume(v['snapshot'],'gateway','config')['metadata']['resourceVersion']},
        {'op':'test','path':'/data','value':image.secret_volume(v['snapshot'],'gateway','config')['data']}]

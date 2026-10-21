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


def test_immutable_runtime_creates_bound_successor_and_preserves_every_other_secret_byte():
    v=fixture();snapshot=v['snapshot'];secret=image.secret_volume(snapshot,'gateway','config')
    secret['immutable']=True
    secret['data']['unrelated-credential']=image._encoded('synthetic-credential-only')
    meta=secret['metadata'];snapshot['objects'][image._key('Secret',meta['namespace'],meta['name'])]=secret
    v['expected_snapshot_sha256']=canonical_sha256(snapshot);before=copy.deepcopy(v)
    m,p,node,b,created=phases(v)
    assert set(created)=={'node.bootstrap','coordinator.seed','hub:cps.publisher','hub:cit.publisher','gateway.runtime-secret'}
    successor=created['gateway.runtime-secret']
    assert successor['kind']=='Secret' and successor['immutable'] is True and successor['type']==secret['type']
    assert successor['metadata']['name']!=secret['metadata']['name']
    expected=copy.deepcopy(secret['data']);runtime=image._decode(expected['runtime.json'])
    for component in ('hub:cps','hub:cit'):runtime['nativeGroupApprovals']['processes'][component]['image']=v['hub_image']
    expected['runtime.json']=image._encoded(runtime)
    assert successor['data']==expected and successor['data']['unrelated-credential']==secret['data']['unrelated-credential']
    assert b['gateway_runtime_patch'] is None
    volume=next(o for o in b['runtime_specs']['gateway']['template']['spec']['volumes'] if o['name']=='config')
    assert volume['secret']['secretName']==successor['metadata']['name']
    pending=m.bind(snapshot,b,created);assert pending['permissions_pending'] and not pending['patches']
    permissions={k:actual(o)for k,o in pending['creates'].items()}
    final=m.bind(snapshot,b,created,actual_permissions=permissions)
    assert 'gateway.runtime-secret' not in final['patches'] and v==before
    assert final['runtime_specs']['gateway']==b['runtime_specs']['gateway']
    assert all(value['kind']=='ConfigMap' for value in final['prospective_capture']['configmaps'])
    assert final['observer_release']['heads']==v['previous_release']['heads']
    assert final['operator_baselines']==v['operator_baselines']


@pytest.mark.parametrize('fault',['missing','data','mutable','uid','namespace','name','type','owner'])
def test_immutable_runtime_successor_requires_exact_actual_readback(fault):
    v=fixture();secret=image.secret_volume(v['snapshot'],'gateway','config');secret['immutable']=True
    v['expected_snapshot_sha256']=canonical_sha256(v['snapshot'])
    m,p,node,b,created=phases(v);successor=created['gateway.runtime-secret']
    if fault=='missing':created.pop('gateway.runtime-secret')
    elif fault=='data':successor['data']['unrelated-credential']='changed'
    elif fault=='mutable':successor['immutable']=False
    elif fault=='uid':successor['metadata']['uid']='unknown'
    elif fault=='namespace':successor['metadata']['namespace']='foreign'
    elif fault=='name':successor['metadata']['name']='foreign'
    elif fault=='type':successor['type']='foreign'
    else:successor['metadata']['ownerReferences']=[{'kind':'Pod','name':'foreign','uid':'00000000-0000-4000-8000-000000000001'}]
    with pytest.raises(ValueError):m.bind(v['snapshot'],b,created)

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


def operator_fixture():
    import uuid
    v=fixture();snapshot=v['snapshot']
    namespace=image._context(snapshot)[1].deployment.authority_namespace
    for label,name,main in [('observer','cps-native-observer-operator','observer'),
                            ('writer','cps-native-head-delivery','delivery')]:
        old='ghcr.io/mul-cps/cps-compute@sha256:'+('4' if label=='observer' else '5')*64
        pod={'serviceAccountName':name,'containers':[{'name':main,'image':old,
            'command':['preserved-command'],'args':['--checkpoint-reference-json','preserved-checkpoint'],
            'env':[{'name':'PRESERVED','value':'exact'}],
            'volumeMounts':[{'name':'journal','mountPath':'/journal'}]}],
            'volumes':[{'name':'journal','persistentVolumeClaim':{'claimName':'preserved-journal'}}]}
        if label=='writer':pod['initContainers']=[{'name':'private-inputs','image':old,'command':['preserved-copy']}]
        dep={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'namespace':namespace,'name':name,
            'uid':str(uuid.uuid4()),'resourceVersion':'71'},'spec':{'replicas':0,'strategy':{'type':'Recreate'},
            'selector':{'matchLabels':{'app':name}},'template':{'metadata':{'labels':{'app':name}},'spec':pod}}}
        snapshot['objects'][image._key('Deployment',namespace,name)]=dep
    v['operator_images']={'observer':'ghcr.io/mul-cps/cps-compute@sha256:'+'a'*64,
                          'writer':'ghcr.io/mul-cps/cps-compute@sha256:'+'b'*64}
    v['expected_snapshot_sha256']=canonical_sha256(snapshot)
    return v


def test_gateway_node_stage_after_hub_pair_refresh_changes_only_selected_fixed_images():
    v=operator_fixture();snapshot=v['snapshot'];_,old=image._context(snapshot)
    v['hub_image']=old.document['component_declarations']['hub:cps']['image']
    v['component_images']={'gateway':'ghcr.io/mul-cps/cps-compute@sha256:'+'9'*64,
                           'node':'ghcr.io/mul-cps/cps-native-node@sha256:'+'6'*64}
    before=copy.deepcopy(v);m,p,node,b,created=phases(v)
    doc=image._parse(node['data']['config.json']);expected=old.document
    for component,value in v['component_images'].items():expected['component_declarations'][component]['image']=value
    assert doc==expected and v==before
    assert 'hub:cps.publisher' not in created and 'hub:cit.publisher' not in created
    assert {'gateway.publisher','gateway.capture-seed'}<=set(created)
    runtime=image._decode(b['gateway_runtime_patch']['patch'][-1]['value']['runtime.json'])
    for component,value in v['component_images'].items():
        assert runtime['nativeGroupApprovals']['processes'][component]['image']==value
    node_pod=b['runtime_specs']['node']['template']['spec']
    bootstrap=next(c for c in node_pod['initContainers']if c['name']=='packaged-bootstrap')
    assert bootstrap['image']==v['component_images']['node']
    assert next(e['value']for e in bootstrap['env']if e['name']=='NODE_IMAGE')==v['component_images']['node']
    gateway=b['runtime_specs']['gateway']['template']['spec']
    assert all(next(c for c in gateway[section]if c['name']==name)['image']==v['component_images']['gateway']
               for section,name in [('containers','approval-capture'),('initContainers','capture-private-inputs'),
                                    ('initContainers','native-kai-private-inputs')])
    settings=image._decode(created['gateway.capture-seed']['data']['config.json'])
    assert settings['node_process']['image']==v['component_images']['node']
    coordinator=image._parse(created['coordinator.seed']['data']['coordinator.json'])
    assert coordinator['epoch']['nodeProcess']['image']==v['component_images']['node']
    pending=m.bind(snapshot,b,created);assert pending['permissions_pending'] and pending['patches']=={}
    permissions={k:actual(o)for k,o in pending['creates'].items()}
    result=m.bind(snapshot,b,created,actual_permissions=permissions)
    assert {'observer.deployment','writer.deployment'}<=set(result['patches'])
    for label,name,main in [('observer','cps-native-observer-operator','observer'),
                            ('writer','cps-native-head-delivery','delivery')]:
        old_dep=image._get(snapshot,'Deployment',old.deployment.authority_namespace,name)
        expected=copy.deepcopy(old_dep['spec']);pod=expected['template']['spec']
        next(c for c in pod['containers']if c['name']==main)['image']=v['operator_images'][label]
        if label=='writer':next(c for c in pod['initContainers']if c['name']=='private-inputs')['image']=v['operator_images'][label]
        assert result['operator_specs'][label]==expected
        patch=result['patches'][label+'.deployment']['patch']
        assert patch[:3]==[{'op':'test','path':'/metadata/uid','value':old_dep['metadata']['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':old_dep['metadata']['resourceVersion']},
            {'op':'test','path':'/spec','value':old_dep['spec']}]
    assert result['observer_release']['heads']==v['previous_release']['heads']
    assert result['operator_baselines']==v['operator_baselines'] and v==before


@pytest.mark.parametrize('fault',['all-components','single-hub','unknown-component','mutable-image','unknown-operator','missing-operator','writer-helper','operator-identity','operator-account'])
def test_selected_component_or_operator_refresh_denies_unsupported_or_unpinned_inputs(fault):
    v=operator_fixture()
    if fault=='all-components':v['component_images']={'gateway':'ghcr.io/mul-cps/cps-compute@sha256:'+'9'*64,
        'node':'ghcr.io/mul-cps/cps-native-node@sha256:'+'6'*64}
    elif fault=='single-hub':v['component_images']={'hub:cps':'ghcr.io/mul-cps/cps-compute@sha256:'+'9'*64}
    elif fault=='unknown-component':v['component_images']={'foreign':v['hub_image']}
    elif fault=='mutable-image':v['operator_images']['observer']='ghcr.io/mul-cps/cps-compute:latest'
    elif fault=='unknown-operator':v['operator_images']['foreign']=v['hub_image']
    else:
        namespace=image._context(v['snapshot'])[1].deployment.authority_namespace
        key=image._key('Deployment',namespace,'cps-native-head-delivery')
        if fault=='missing-operator':v['snapshot']['objects'].pop(key)
        elif fault=='operator-identity':v['snapshot']['objects'][key]['metadata']['name']='foreign'
        elif fault=='operator-account':v['snapshot']['objects'][key]['spec']['template']['spec']['serviceAccountName']='foreign'
        else:v['snapshot']['objects'][key]['spec']['template']['spec']['initContainers'][0]['image']='foreign@sha256:'+'c'*64
        v['expected_snapshot_sha256']=canonical_sha256(v['snapshot'])
    before=copy.deepcopy(v)
    with pytest.raises(ValueError):module().prepare(**v)
    assert v==before


def test_paired_hub_stage_accepts_image_only_operator_refresh():
    v=operator_fixture();m,p,node,b,created=phases(v)
    result=m.bind(v['snapshot'],b,created)
    assert result['patches']=={} and set(result['operator_specs'])=={'observer','writer'}
    assert {'hub:cps.publisher','hub:cit.publisher'}<=set(created)
    assert 'gateway.publisher' not in created and 'gateway.capture-seed' not in created
    assert image._parse(node['data']['config.json'])['component_declarations']['hub:cit']['image']==v['hub_image']

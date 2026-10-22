"""Pure staged migration tests using actual SDK authority validators; no cluster."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import uuid
import pytest
pytest.importorskip('cps_compute.native_approval_head')
legacy_fixture=pytest.importorskip('test_native_observer_permissions').fixture
ref=pytest.importorskip('test_native_node_config').ref
from cps_compute.native_node.config import NodeConfiguration


def fixture():
    source=Path(__file__).with_name('head_bootstrap.py')
    spec=importlib.util.spec_from_file_location('reviewed_head_bootstrap',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    f=legacy_fixture();configuration=NodeConfiguration.load(f.core,ref(f.cm),f.policy)
    approvals={}
    for component,declaration in configuration.document['component_declarations'].items():
        cm=copy.deepcopy(f.maps['approval'])
        if component!='node':
            cm['metadata'].update(namespace=declaration['namespace'],name='initial-'+component.replace(':','-'),uid=str(uuid.uuid4()))
        approvals[component]=cm
    return SimpleNamespace(**locals())


def actual(candidate):
    value=copy.deepcopy(candidate)
    value['metadata'].update(uid=str(uuid.uuid4()),resourceVersion='21')
    return value


def stages(f):
    pointers={key:actual(value) for key,value in f.module.pointer_candidates(f.configuration,f.approvals,f.f.policy).items()}
    anchors={key:actual(value) for key,value in f.module.anchor_candidates(f.configuration,f.approvals,f.f.policy,pointers).items()}
    return pointers,anchors


def test_staged_bootstrap_requires_actual_uids_and_preserves_node_authority():
    f=fixture();before=f.configuration.document
    candidates=f.module.pointer_candidates(f.configuration,f.approvals,f.f.policy)
    assert len(candidates)==4
    assert all(set(c['metadata'])=={'namespace','name'} for c in candidates.values())
    pointers,anchors=stages(f)
    result=f.module.bind(f.configuration,f.approvals,f.f.policy,pointers,anchors)
    assert set(result)=={'heads','node_configuration'} and len(result['heads'])==4
    body=copy.deepcopy(before);body.pop('approval_ref');body.update(version=4,approval_head=result['heads']['node'])
    import json
    assert json.loads(result['node_configuration']['data']['config.json'])==body
    assert f.configuration.document==before
    candidate=actual(result['node_configuration'])
    qualification=before['qualification_ref']
    typed=NodeConfiguration.from_configmap(candidate,ref(candidate),f.f.policy,
        deployment=f.configuration.deployment,qualification_cm=f.f.core.read_namespaced_config_map(
            qualification['name'],qualification['namespace']))
    assert typed.document==body and typed.deployment_document==f.configuration.deployment_document
    for component,binding in result['heads'].items():
        assert binding['anchor']['pointer']['uid']==pointers[component]['metadata']['uid']
        assert binding['projection']['uid']==anchors[component]['metadata']['uid']
        assert binding['projection']['key']=='anchor.json'


def test_pointer_readback_drift_and_fabricated_uid_are_refused():
    f=fixture();pointers,anchors=stages(f)
    for key,value in [('uid','not-a-uid'),('resourceVersion','0')]:
        changed=copy.deepcopy(pointers);changed['node']['metadata'][key]=value
        with pytest.raises(ValueError):f.module.anchor_candidates(f.configuration,f.approvals,f.f.policy,changed)
    changed=copy.deepcopy(pointers);changed['node']['data']['head.json']='{}'
    with pytest.raises(ValueError):f.module.anchor_candidates(f.configuration,f.approvals,f.f.policy,changed)


def test_anchor_readback_and_node_initial_authority_must_match():
    f=fixture();pointers,anchors=stages(f)
    anchors['node']['data']['anchor.json']='{}'
    with pytest.raises(ValueError):f.module.bind(f.configuration,f.approvals,f.f.policy,pointers,anchors)
    changed=copy.deepcopy(f.approvals);changed['node']['metadata']['uid']=str(uuid.uuid4())
    with pytest.raises(ValueError):f.module.pointer_candidates(f.configuration,changed,f.f.policy)


def test_missing_component_and_foreign_namespace_are_refused():
    f=fixture();changed=copy.deepcopy(f.approvals);changed.pop('hub:cit')
    with pytest.raises(ValueError):f.module.pointer_candidates(f.configuration,changed,f.f.policy)
    changed=copy.deepcopy(f.approvals);changed['hub:cit']['metadata']['namespace']='foreign'
    with pytest.raises(ValueError):f.module.pointer_candidates(f.configuration,changed,f.f.policy)


def test_mixed_authenticated_registry_heads_cannot_bootstrap():
    import json
    from cps_compute.native_group_approvals import ApprovalSnapshot
    from cps_compute.native_group_revision import approval_envelope
    from cps_compute.native_groups import canonical_sha256
    f=fixture();changed=copy.deepcopy(f.approvals)
    current=json.loads(changed['hub:cit']['data']['approval.json'])
    registry=current['registry'];registry['generation']+=1
    snapshot=ApprovalSnapshot.from_document(registry,f.f.policy,f.configuration.deployment,
        expected_revision=canonical_sha256(registry))
    changed['hub:cit']['data']['approval.json']=json.dumps(approval_envelope(snapshot,current['history']),
        sort_keys=True,separators=(',',':'))
    with pytest.raises(ValueError,match='registries must agree'):
        f.module.pointer_candidates(f.configuration,changed,f.f.policy)


@pytest.mark.parametrize('change',[
    {'ownerReferences':[{'uid':str(uuid.uuid4())}]},
    {'deletionTimestamp':'2026-10-17T09:00:00Z'},
])
def test_pending_deletion_or_garbage_collected_pointer_is_refused(change):
    f=fixture();pointers,anchors=stages(f)
    pointers['node']['metadata'].update(change)
    with pytest.raises(ValueError):f.module.bind(f.configuration,f.approvals,f.f.policy,pointers,anchors)


def test_initial_v3_history_must_agree_before_any_bootstrap_candidates():
    import json
    from cps_compute.native_group_approvals import ApprovalSnapshot
    from cps_compute.native_group_revision import ApprovalRevision,approval_envelope
    from cps_compute.native_groups import _canonical,canonical_sha256
    f=fixture()
    node=ApprovalRevision.from_configmap(f.approvals['node'],f.f.policy,f.configuration.deployment)
    registry=node.document['registry'];registry['generation']=0;registry['deployment']['workspaces']={}
    old=ApprovalSnapshot.from_document(registry,f.f.policy,f.configuration.deployment,
        expected_revision=canonical_sha256(registry))
    cm=actual({'apiVersion':'v1','kind':'ConfigMap','immutable':True,'metadata':{
        'namespace':node.reference['namespace'],'name':'actual-older-empty'},
        'data':{'approval.json':_canonical(approval_envelope(old)).decode()}})
    prior=ApprovalRevision.from_configmap(cm,f.f.policy,f.configuration.deployment)
    body=json.loads(f.approvals['hub:cps']['data']['approval.json']);body['history']=[prior.reference]
    f.approvals['hub:cps']['data']['approval.json']=_canonical(body).decode()
    ApprovalRevision.from_configmap(f.approvals['hub:cps'],f.f.policy,f.configuration.deployment)
    with pytest.raises(ValueError):f.module.pointer_candidates(f.configuration,f.approvals,f.f.policy)


def test_runtime_mounts_use_actual_bound_anchor_and_three_protected_binding_files():
    f=fixture();pointers,anchors=stages(f)
    candidates=f.module.runtime_candidates(f.configuration,f.approvals,f.f.policy,pointers,anchors)
    assert set(candidates)=={'gateway','hub:cps','hub:cit'}
    bindings={key:actual(value) for key,value in candidates.items()}
    controllers={key:f.f.apps.read_namespaced_deployment(value['name'],value['namespace'])
        for key,value in f.configuration.document['component_declarations'].items()}
    for controller in controllers.values():controller['metadata']['resourceVersion']='21'
    before=copy.deepcopy(controllers)
    patches=f.module.bind_runtime(f.configuration,f.approvals,f.f.policy,pointers,anchors,bindings,controllers)
    assert set(patches)=={'gateway','hub:cps','hub:cit','node'}
    for component,patch in patches.items():
        original=controllers[component]
        assert patch[:3]==[
            {'op':'test','path':'/metadata/uid','value':original['metadata']['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':original['metadata']['resourceVersion']},
            {'op':'test','path':'/spec','value':original['spec']}]
        desired=patch[3]['value'];pod=desired['template']['spec']
        declaration=f.configuration.document['component_declarations'][component]
        container=next(c for c in pod['containers'] if c['name']==declaration['container'])
        assert container['image']==declaration['image']
        anchor_mount=next(m for m in container['volumeMounts'] if m['name']=='cps-native-head-anchor')
        assert anchor_mount==dict(name='cps-native-head-anchor',mountPath='/var/run/cps-native-approvals/head-anchor.json',subPath='anchor.json',readOnly=True)
        volume=next(v for v in pod['volumes'] if v['name']=='cps-native-head-anchor')
        assert volume['configMap']['name']==anchors[component]['metadata']['name']
        if component!='node':
            assert next(e for e in container['env'] if e['name']=='CPS_NATIVE_GROUP_APPROVAL_HEAD')['value']=='/etc/cps-native-head-binding.json'
        else:
            assert not any(e['name']=='CPS_NATIVE_GROUP_APPROVAL_HEAD' for e in container.get('env',[]))
    assert controllers==before


def test_runtime_refuses_binding_drift_and_unreviewed_controller_identity():
    f=fixture();pointers,anchors=stages(f)
    bindings={key:actual(value) for key,value in f.module.runtime_candidates(f.configuration,f.approvals,f.f.policy,pointers,anchors).items()}
    controllers={key:f.f.apps.read_namespaced_deployment(value['name'],value['namespace'])
        for key,value in f.configuration.document['component_declarations'].items()}
    for controller in controllers.values():controller['metadata']['resourceVersion']='21'
    changed=copy.deepcopy(bindings);changed['gateway']['data']['head-binding.json']='{}'
    with pytest.raises(ValueError):f.module.bind_runtime(f.configuration,f.approvals,f.f.policy,pointers,anchors,changed,controllers)
    changed=copy.deepcopy(controllers);changed['gateway']['metadata']['name']='unreviewed'
    with pytest.raises(ValueError):f.module.bind_runtime(f.configuration,f.approvals,f.f.policy,pointers,anchors,bindings,changed)


def test_replaced_deployment_uid_is_not_a_new_migration_baseline():
    f=fixture();pointers,anchors=stages(f)
    bindings={key:actual(value) for key,value in f.module.runtime_candidates(f.configuration,f.approvals,f.f.policy,pointers,anchors).items()}
    controllers={key:f.f.apps.read_namespaced_deployment(value['name'],value['namespace'])
        for key,value in f.configuration.document['component_declarations'].items()}
    for controller in controllers.values():controller['metadata']['resourceVersion']='21'
    controllers['gateway']['metadata']['uid']=str(uuid.uuid4())
    with pytest.raises(ValueError):f.module.bind_runtime(f.configuration,f.approvals,f.f.policy,pointers,anchors,bindings,controllers)


def readiness_fixture(f):
    body=f.configuration.document
    return {'enabled':True,'ttlSeconds':60,
        'acknowledgments':copy.deepcopy(body['acknowledgment_targets']),
        'processes':{c:{k:v for k,v in d.items() if k!='service_account_uid'}
            for c,d in body['component_declarations'].items()},
        'driver_epoch':{k:f.configuration.deployment.node_pool[k]
            for k in ('node_uid','boot_id','driver_generation','gpu_uuid')}}


def test_readiness_migration_preserves_exact_existing_authority_and_adds_four_heads():
    f=fixture();pointers,anchors=stages(f);settings=readiness_fixture(f);before=copy.deepcopy(settings)
    migrated=f.module.readiness_settings(f.configuration,f.approvals,f.f.policy,pointers,anchors,settings)
    expected=copy.deepcopy(before);expected.update(version=2,heads=f.module.bind(
        f.configuration,f.approvals,f.f.policy,pointers,anchors)['heads'])
    assert migrated==expected and settings==before
    from cps_compute.runtime import native_group_approval_configuration
    assert native_group_approval_configuration({'nativeGroupApprovals':migrated})==migrated


@pytest.mark.parametrize('change',['process','ack','epoch','already-dynamic'])
def test_readiness_migration_rejects_different_authority_or_repeat_migration(change):
    f=fixture();pointers,anchors=stages(f);settings=readiness_fixture(f)
    if change=='process':settings['processes']['hub:cps']['image']='example.invalid/hub@sha256:'+'b'*64
    elif change=='ack':settings['acknowledgments']['node']['uid']=str(uuid.uuid4())
    elif change=='epoch':settings['driver_epoch']['driver_generation']='sha256:'+'b'*64
    else:settings.update(version=2,heads=f.module.bind(f.configuration,f.approvals,f.f.policy,pointers,anchors)['heads'])
    with pytest.raises(ValueError):f.module.readiness_settings(f.configuration,f.approvals,f.f.policy,pointers,anchors,settings)


def test_new_configmap_volumes_pin_api_default_mode_for_exact_spec_adoption():
    f=fixture();pointers,anchors=stages(f)
    bindings={c:actual(v) for c,v in f.module.runtime_candidates(f.configuration,f.approvals,f.f.policy,pointers,anchors).items()}
    controllers={c:f.f.apps.read_namespaced_deployment(d['name'],d['namespace']) for c,d in f.configuration.document['component_declarations'].items()}
    for d in controllers.values():d['metadata']['resourceVersion']='21'
    patches=f.module.bind_runtime(f.configuration,f.approvals,f.f.policy,pointers,anchors,bindings,controllers)
    for patch in patches.values():
        volumes=patch[-1]['value']['template']['spec']['volumes']
        selected=[v for v in volumes if v['name'] in {'cps-native-head-anchor','cps-native-head-binding'}]
        assert selected and all(v['configMap'].get('defaultMode')==0o644 for v in selected)


def test_distinct_domain_heads_bind_through_real_sdk_without_reusing_old_pointers():
    f=fixture();domain_uid=str(uuid.uuid4());before=copy.deepcopy(f.configuration.document)
    legacy=f.module.pointer_candidates(f.configuration,f.approvals,f.f.policy)
    candidates=f.module.pointer_candidates(f.configuration,f.approvals,f.f.policy,domain_uid=domain_uid)
    for component,candidate in candidates.items():
        assert candidate['metadata']['name']!=legacy[component]['metadata']['name']
        assert candidate['metadata']['namespace']==legacy[component]['metadata']['namespace']
        assert candidate['data']==legacy[component]['data']
    pointers={c:actual(v) for c,v in candidates.items()}
    anchors={c:actual(v) for c,v in f.module.anchor_candidates(
        f.configuration,f.approvals,f.f.policy,pointers,domain_uid=domain_uid).items()}
    bound=f.module.bind(f.configuration,f.approvals,f.f.policy,pointers,anchors,domain_uid=domain_uid)
    config=actual(bound['node_configuration']);qualification=before['qualification_ref']
    typed=NodeConfiguration.from_configmap(config,ref(config),f.f.policy,
        deployment=f.configuration.deployment,qualification_cm=f.f.core.read_namespaced_config_map(
            qualification['name'],qualification['namespace']))
    assert typed.document['approval_head']==bound['heads']['node']
    for component,head in bound['heads'].items():
        assert head['anchor']['pointer']['uid']==pointers[component]['metadata']['uid']
        assert head['anchor']['pointer']['name']==candidates[component]['metadata']['name']
    bindings={c:actual(v) for c,v in f.module.runtime_candidates(
        f.configuration,f.approvals,f.f.policy,pointers,anchors,domain_uid=domain_uid).items()}
    controllers={c:f.f.apps.read_namespaced_deployment(d['name'],d['namespace'])
        for c,d in f.configuration.document['component_declarations'].items()}
    for controller in controllers.values():controller['metadata']['resourceVersion']='21'
    patches=f.module.bind_runtime(f.configuration,f.approvals,f.f.policy,pointers,anchors,
        bindings,controllers,domain_uid=domain_uid)
    assert set(patches)==set(bound['heads'])
    settings=f.module.readiness_settings(f.configuration,f.approvals,f.f.policy,pointers,anchors,
        readiness_fixture(f),domain_uid=domain_uid)
    assert settings['heads']==bound['heads']
    assert f.configuration.document==before
    for token in (None,str(uuid.uuid4())):
        with pytest.raises(ValueError,match='readback'):
            f.module.bind(f.configuration,f.approvals,f.f.policy,pointers,anchors,domain_uid=token)


@pytest.mark.parametrize('domain_uid',['not-a-uid','../old',True,'00000000-0000-0000-0000-000000000000'])
def test_domain_naming_refuses_invalid_uid_tokens(domain_uid):
    f=fixture()
    with pytest.raises(ValueError,match='domain UID'):
        f.module.pointer_candidates(f.configuration,f.approvals,f.f.policy,domain_uid=domain_uid)

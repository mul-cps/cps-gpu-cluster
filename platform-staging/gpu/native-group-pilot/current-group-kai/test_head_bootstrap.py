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

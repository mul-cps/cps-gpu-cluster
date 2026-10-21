"""Cold SDK loader permissions over synthetic captured Kubernetes objects only."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
from cps_compute.native_groups import canonical_sha256 as sha
from test_native_observer_head_permissions import fixture as head_fixture


def module():
    spec=importlib.util.spec_from_file_location('consumer_proof_reads',Path(__file__).with_name('consumer_proof_reads.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def payload(f):
    base=f.f
    result = {'version':1,'release':f.release.document,'policy':base.policy.catalog,'capture':{
        'configmaps':copy.deepcopy(list(f.objects.values())),
        'deployments':[base.apps.read_namespaced_deployment(d['name'],d['namespace']) for d in base.body['component_declarations'].values()],
        'roles':[base.rbac.read_namespaced_role(r['name'],r['namespace']) for r in f.release.document['roles']],
        'serviceaccounts':copy.deepcopy(list(base.accounts.values()))}}
    # Older SDK fixtures omit apiserver metadata on projected bootstrap/SA objects.
    for cm in result['capture']['configmaps']:
        cm['metadata'].setdefault('uid',str(uuid.uuid4()))
        cm['metadata'].setdefault('resourceVersion','900')
    for group in ('deployments','roles','serviceaccounts'):
        for value in result['capture'][group]:
            value['metadata'].setdefault('resourceVersion','900')
    # Observer-only fixtures carry an intentionally inert terminal-index stub.
    # Replace it with a valid empty SDK index and repin the captured current
    # Node/bootstrap inputs; production validation remains strict.
    import json
    from cps_compute.native_groups import _canonical
    from test_native_node_config import ref
    maps={(cm['metadata']['namespace'],cm['metadata']['name']):cm for cm in result['capture']['configmaps']}
    node_ref=result['release']['node_configuration'];node=maps[(node_ref['namespace'],node_ref['name'])]
    body=json.loads(node['data']['config.json']);index_ref=body['terminal_index_ref'];index=maps[(index_ref['namespace'],index_ref['name'])]
    if json.loads(index['data']['index.json'])=={'version':1}:
        index['data']['index.json']=_canonical({'version':1,'authority_namespace':index_ref['namespace'],
            'ledger':{'namespace':index_ref['namespace'],'name':'cps-native-gpu-allocations','uid':str(uuid.uuid4())},
            'pages':[],'total_records':0,'entries_sha256':sha({})}).decode()
        def repin_node(cm):
            document=json.loads(cm['data']['config.json'])
            if document['terminal_index_ref']['name']==index_ref['name']:
                document['terminal_index_ref']=ref(index).to_dict()
            for field in ('lifetime_transition','policy_transition'):
                if field in document:
                    previous=document[field]['previous_node_configuration_ref']
                    prior=maps[(previous['namespace'],previous['name'])]
                    repin_node(prior)
                    document[field]['previous_node_configuration_ref']=ref(prior).to_dict()
            cm['data']['config.json']=_canonical(document).decode()
        repin_node(node)
        result['release']['node_configuration']=ref(node).to_dict()
        for cm in maps.values():
            if 'config-ref.json' in cm.get('data',{}) and json.loads(cm['data']['config-ref.json'])==node_ref:
                cm['data']['config-ref.json']=_canonical(ref(node).to_dict()).decode()
    return result


def test_default_inert_without_sdk_or_api():
    result=subprocess.run([sys.executable,'-I','-B',str(Path(__file__).with_name('consumer_proof_reads.py'))],capture_output=True,text=True)
    assert result.returncode==0 and '"execute": false' in result.stdout


def test_actual_cold_loaders_get_only_authenticated_immutable_dependencies():
    f=head_fixture();document=payload(f)
    result=module().compile_proof_reads(document,reviewed_sha256=sha(document))
    assert set(result['consumers'])=={'gateway','hub:cps','hub:cit','node'}
    assert result['manifests']
    for value in result['manifests']:
        if value['kind']=='Role':
            assert all(row['apiGroups']==[''] and row['resources']==['configmaps'] and row['verbs']==['get']
                and row['resourceNames'] and '*' not in row['resourceNames'] for row in value['rules'])
    for component,value in result['consumers'].items():
        actual=f.f.body['component_declarations'][component]
        assert value['subject']=={'namespace':actual['namespace'],'name':actual['service_account'],'uid':actual['service_account_uid']}
        assert f.heads[component]['anchor']['pointer']['name'] not in {
            p['name'] for p in value['proofs'] if p['namespace']==actual['namespace']}


def chained_payload(tmp_path,monkeypatch):
    from test_native_delivery_policy_transition import rooted_fixture,image_successor
    from test_native_delivery_lifetime_transition import complete_producers
    from test_native_addon_policy_node import second_receipt
    from types import SimpleNamespace
    f,receipt=rooted_fixture(tmp_path,monkeypatch)
    for step,software in ((1,receipt),(2,second_receipt(receipt))):
        args,_,_=image_successor(f,software,step=step)
        assert not f.x.controller().continue_policy_configuration(**args)['ready']
        complete_producers(f)
        assert f.x.controller().continue_policy_configuration(**args)['ready']
    shell=SimpleNamespace(f=f.x.f.f,objects=f.x.f.objects)
    # DeliveryController does not own the public release factory instance.
    from cps_compute.native_observer_permissions import ObserverRelease
    shell.release=ObserverRelease.from_dict(f.x.settings['observer_release'])
    return f,payload(shell)


class RestrictedCore:
    def __init__(self,maps,allowed,underlying=None):
        self.maps=maps;self.allowed=allowed;self.underlying=underlying;self.reads=[]
    def read_namespaced_config_map(self,name,namespace,**kwargs):
        key=namespace,name
        if key not in self.allowed:raise PermissionError('Named consumer GET missing')
        self.reads.append(key)
        return copy.deepcopy(self.maps[key])
    def __getattr__(self,name):return getattr(self.underlying,name)


def cold_load(core,document,component):
    from cps_compute.policy import Policy
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    from cps_compute.native_node.config import NodeConfiguration
    from cps_compute.native_approval_head import HeadSnapshot
    policy=Policy(document['policy']);release=document['release']
    configuration=NodeConfiguration.load(core,ImmutableConfigMapRef.from_dict(release['node_configuration']),policy)
    for selected in (('node',) if component=='node' else ('gateway','hub:cps','hub:cit','node')):
        head=HeadSnapshot.load(core,release['heads'][selected],policy,configuration.deployment,component=selected)
        from cps_compute.native_group_revision import validate_retained_approval_identity
        for reference in head.approval.document['history']:
            actual=core.read_namespaced_config_map(reference['name'],reference['namespace'])
            validate_retained_approval_identity(actual,reference,policy,configuration.deployment)
    if component=='node':module()._terminal_reads(core,configuration.document['terminal_index_ref'])
    return configuration


def test_real_age_two_images_cold_rbac_denial_then_exact_compiled_closure(tmp_path,monkeypatch):
    f,document=chained_payload(tmp_path,monkeypatch)
    maps={(v['metadata']['namespace'],v['metadata']['name']):v for v in document['capture']['configmaps']}
    pointers={(h['anchor']['pointer']['namespace'],h['anchor']['pointer']['name']) for h in document['release']['heads'].values()}
    component='hub:cps';decl=f.configuration.document['component_declarations'][component]
    local={(ns,name) for ns,name in maps if ns==decl['namespace']}
    with pytest.raises(PermissionError):cold_load(RestrictedCore(maps,local|pointers),document,component)
    result=module().compile_proof_reads(document,reviewed_sha256=sha(document))
    for component,value in result['consumers'].items():
        allowed={(p['namespace'],p['name']) for p in value['proofs']}
        core=RestrictedCore(maps,allowed|pointers)
        configuration=cold_load(core,document,component)
        assert len(configuration.deployment.qualification_authority.policy_transitions)==3
        assert allowed==set(core.reads)-pointers
        for proof in value['proofs']:
            key=proof['namespace'],proof['name']
            assert proof['uid']==maps[key]['metadata']['uid'] and proof['data_sha256']==sha(maps[key]['data'])
        # Every emitted name is needed by the real cold path, not arbitrary capture.
        for removed in allowed:
            with pytest.raises(PermissionError):cold_load(RestrictedCore(maps,(allowed-{removed})|pointers),document,component)


@pytest.mark.parametrize('fault',['input-sha','proof-uid','proof-data','proof-mutable','foreign-history',
    'sa-uid','extra-subject','capture-overflow','bootstrap-policy','role-uid','role-static'])
def test_altered_or_unreviewed_cold_inputs_fail_without_intents(fault):
    import json
    from cps_compute.native_group_revision import ApprovalRevision
    from cps_compute.native_groups import _canonical
    f=head_fixture();document=payload(f);review=sha(document)
    if fault=='input-sha':document['version']=2
    elif fault.startswith('proof-'):
        expected=document['release']['node_configuration']
        cm=next(cm for cm in document['capture']['configmaps'] if cm['metadata']['name']==expected['name'])
        if fault=='proof-uid':cm['metadata']['uid']=str(uuid.uuid4())
        elif fault=='proof-data':cm['data']['config.json']+=' '
        else:cm['immutable']=False
    elif fault=='foreign-history':
        original=next(iter(f.current.values()));foreign=copy.deepcopy(f.objects[(original.reference['namespace'],original.reference['name'])])
        foreign['metadata'].update(namespace='foreign',uid=str(uuid.uuid4()))
        reference=ApprovalRevision.from_configmap(foreign,f.f.policy,f.qualification).reference
        from test_native_observer_head_permissions import advance
        advance(f)
        for component,current in f.current.items():
            body=current.document;body['history'].append(reference)
            cm=f.objects[(current.reference['namespace'],current.reference['name'])]
            cm['data']['approval.json']=_canonical(body).decode();actual=ApprovalRevision.from_configmap(cm,f.f.policy,f.qualification)
            f.pointers[component]['data']['head.json']=_canonical({'version':1,'generation':actual.document['registry']['generation'],'reference':actual.reference}).decode()
        document=payload(f);document['capture']['configmaps'].append(foreign)
    elif fault=='sa-uid':document['capture']['serviceaccounts'][0]['metadata']['uid']=str(uuid.uuid4())
    elif fault=='extra-subject':
        account=copy.deepcopy(document['capture']['serviceaccounts'][0]);account['metadata']['name']='foreign';document['capture']['serviceaccounts'].append(account)
    elif fault=='capture-overflow':document['capture']['configmaps']*=100
    elif fault=='bootstrap-policy':
        cm=next(c for c in document['capture']['configmaps'] if c['metadata']['name']=='bootstrap');cm['data']['policy.json']='{}'
    elif fault=='role-uid':
        role=next(r for r in document['capture']['roles'] if r['metadata']['name']=='cps-native-approval-gateway');role['metadata']['uid']=str(uuid.uuid4())
    else:
        role=next(r for r in document['capture']['roles'] if r['metadata']['name']=='cps-native-approval-gateway');role['rules'][1]['verbs']=['patch']
    if fault!='input-sha':review=sha(document)
    with pytest.raises((ValueError,KeyError)):module().compile_proof_reads(document,reviewed_sha256=review)


def test_unrelated_immutable_capture_is_excluded_and_context_cas_preserves_dynamic_names():
    f=head_fixture();document=payload(f)
    unrelated=copy.deepcopy(document['capture']['configmaps'][0]);unrelated['metadata'].update(name='unrelated-proof',uid=str(uuid.uuid4()))
    document['capture']['configmaps'].append(unrelated)
    ns=document['release']['node_configuration']['namespace']
    bootstrap=next(c for c in document['capture']['configmaps'] if c['metadata']['name']=='bootstrap')
    # Only new, independently justified static baseline additions. Existing
    # arbitrary dynamic head/process names remain exact preimages, not new grants.
    for baseline in document['release']['roles']:
        if (baseline['namespace'],baseline['name']) in ((ns,'cps-native-approval-gateway'),(ns,'cps-native-approval-node')):
            baseline['rules'][0]['resourceNames'].append(bootstrap['metadata']['name'])
    for role in document['capture']['roles']:
        if role['metadata']['namespace']==ns:
            role['rules'][0]['resourceNames'].append('existing-dynamic-head')
    result=module().compile_proof_reads(document,reviewed_sha256=sha(document))
    assert len(result['process_context_intents'])==2
    for consumer in result['consumers'].values():assert 'unrelated-proof' not in {p['name'] for p in consumer['proofs']}
    for intent in result['process_context_intents']:
        assert intent['added_names']==['bootstrap']
        assert [p['path'] for p in intent['patch']]==['/metadata/uid','/metadata/resourceVersion','/rules','/rules']
        old=intent['patch'][2]['value'];new=intent['patch'][3]['value']
        assert set(old[0]['resourceNames'])<=set(new[0]['resourceNames'])
        assert 'existing-dynamic-head' in new[0]['resourceNames'] and old[1:]==new[1:]


@pytest.mark.parametrize('fault',['uid','image','service-account'])
def test_actual_consumer_controller_must_match_typed_identity(fault):
    f=head_fixture();document=payload(f)
    declaration=f.f.body['component_declarations']['gateway']
    dep=next(d for d in document['capture']['deployments'] if d['metadata']['namespace']==declaration['namespace'])
    if fault=='uid':dep['metadata']['uid']=str(uuid.uuid4())
    elif fault=='image':dep['spec']['template']['spec']['containers'][0]['image']='registry.example/foreign@sha256:'+'f'*64
    else:dep['spec']['template']['spec']['serviceAccountName']='foreign'
    with pytest.raises(ValueError):module().compile_proof_reads(document,reviewed_sha256=sha(document))


def test_actual_node_snapshot_has_its_historical_peer_proof_gets(request,monkeypatch):
    from test_native_addon_policy_heads import fixture as actual_fixture
    from cps_compute.native_node.config import NodeConfiguration
    from cps_compute.native_approval_head import HeadSnapshot
    from cps_compute.native_node.custody import NodeCustodyConsumer
    current,policy,maps,configuration,authority,approval=actual_fixture(request,monkeypatch)
    objects={(v['metadata']['namespace'],v['metadata']['name']):v for v in maps.values() if v.get('kind')=='ConfigMap'}
    pointers={(configuration.approval_head['anchor']['pointer']['namespace'],configuration.approval_head['anchor']['pointer']['name'])}
    namespaces={d['namespace'] for d in configuration.document['component_declarations'].values()}
    trace=module().CapturedCore(objects,pointers,namespaces)
    loaded=NodeConfiguration.load(trace,configuration.reference,policy)
    HeadSnapshot.load(trace,configuration.approval_head,policy,loaded.deployment,component='node')
    module()._terminal_reads(trace,loaded.document['terminal_index_ref'])
    # Existing Node-local custody permissions still cover mutable ledger and
    # enrollment/completion objects; this compiler does not broaden them.
    namespace=configuration.deployment.authority_namespace
    existing={key for key in objects if key[0]==namespace}|pointers
    allowed=existing|set(trace.proofs)
    cold=NodeCustodyConsumer(RestrictedCore(objects,allowed,current.core),configuration.reference,
        policy,current.store,current.journal)
    snapshot=cold.snapshot()
    assert not snapshot.intents and snapshot.approval.reference==approval.reference
    assert len(snapshot.configuration.deployment.qualification_authority.policy_transitions)==3


def test_context_patch_rejects_stale_uid_rv_and_fullrules_in_existing_sdk_api_fixture():
    f=head_fixture();document=payload(f);ns=document['release']['node_configuration']['namespace']
    for row in document['release']['roles']:
        if row['namespace']==ns and row['name'] in ('cps-native-approval-gateway','cps-native-approval-node'):
            row['rules'][0]['resourceNames'].append('bootstrap')
    output=module().compile_proof_reads(document,reviewed_sha256=sha(document))
    for intent in output['process_context_intents']:
        key=intent['target']['namespace'],intent['target']['name']
        original=copy.deepcopy(f.f.roles[key]);original['rules']=copy.deepcopy(intent['patch'][2]['value'])
        original['metadata']['resourceVersion']=intent['target']['resourceVersion']
        for fault in ('uid','resourceVersion','rules'):
            actual=copy.deepcopy(original)
            if fault=='rules':actual['rules'][0]['resourceNames'].append('concurrent-addition')
            else:actual['metadata'][fault]=str(uuid.uuid4()) if fault=='uid' else '999999'
            f.f.roles[key]=actual;before=copy.deepcopy(actual)
            with pytest.raises(AssertionError):f.f.rbac.patch_namespaced_role(key[1],key[0],intent['patch'])
            assert f.f.roles[key]==before
        f.f.roles[key]=copy.deepcopy(original)
        f.f.rbac.patch_namespaced_role(key[1],key[0],intent['patch'])
        assert f.f.roles[key]['rules']==intent['patch'][-1]['value']


@pytest.mark.parametrize('fault',['target-envelope','unrelated-baseline'])
def test_target_readback_and_new_context_names_must_be_authenticated(fault):
    f=head_fixture();document=payload(f)
    if fault=='target-envelope':
        actual=f.current['hub:cps'].reference
        cm=next(c for c in document['capture']['configmaps'] if (c['metadata']['namespace'],c['metadata']['name'])==(actual['namespace'],actual['name']))
        cm['data']['approval.json']+=' '
    else:
        ns=document['release']['node_configuration']['namespace']
        row=next(r for r in document['release']['roles'] if (r['namespace'],r['name'])==(ns,'cps-native-approval-gateway'))
        row['rules'][0]['resourceNames'].append('unrelated-proof')
        cm=copy.deepcopy(document['capture']['configmaps'][0]);cm['metadata'].update(name='unrelated-proof',uid=str(uuid.uuid4()))
        document['capture']['configmaps'].append(cm)
    with pytest.raises(ValueError):module().compile_proof_reads(document,reviewed_sha256=sha(document))

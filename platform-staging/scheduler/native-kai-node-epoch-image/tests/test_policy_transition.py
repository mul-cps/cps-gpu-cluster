"""CPU-only actual standalone consumer tests; synthetic operator authority."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import node_agent as agent
import native_approval_revision as node
from cps_compute.native_groups import canonical_sha256
from cps_compute.native_policy_transition import PolicyWorkloadTransition
from test_native_group_packing import measured_fixture
import test_native_policy_transition as core_fixtures


@pytest.fixture
def epoch(tmp_path, request):
    def original():
        if getattr(request,'param',None)=='deployed':
            from cps_compute.policy import Policy
            data=json.loads((Path(__file__).parents[4]/'platform-staging/gpu/native-group-pilot/testdata/reviewed-d48-native-source.json').read_text())
            return Policy(data['catalog']),data['runtime']['nativeGpuGroups']
        return measured_fixture((5,10),budget=15360,slots=2)
    with patch.object(core_fixtures, 'qualified_fixture', original):
        value = core_fixtures.request()
    old = value['old']['registry']
    maps = {}
    for reference in value['retired_references']:
        document = dict(version=1, revision=reference['revision'], policy_hash=reference['policy_hash'],
                        registry=old, history=[])
        cm = dict(apiVersion='v1', kind='ConfigMap', immutable=True,
                  metadata={k: reference[k] for k in ('namespace', 'name', 'uid')},
                  data={'approval.json': node.canonical(document)})
        reference['data_sha256'] = canonical_sha256(cm['data'])
        maps[reference['name']] = cm
    new = value['new']['registry']; template = new['deployment']
    document = dict(version=1, revision=canonical_sha256(new), policy_hash=template['policy_hash'],
                    registry=new, history=value['retired_references'])
    cm = dict(apiVersion='v1', kind='ConfigMap', immutable=True,
              metadata=dict(namespace='cps-compute', name='new-node-epoch',
                            uid='99999999-1234-4234-8234-123456789abc'),
              data={'approval.json': node.canonical(document)})
    reference = dict(cm['metadata'], data_sha256=canonical_sha256(cm['data']),
                     revision=document['revision'], policy_hash=document['policy_hash'])
    maps[reference['name']] = cm
    config = dict(version=2, enabled=True, mode='qualified-group', authority_namespace=template['authorityNamespace'],
                  policy_hash=template['policy_hash'], pool=template['node_pool'], terminal_history={},
                  workspaces={scope: dict(profile=row['profiles'][0],
                    cap_mib=template['evidence']['profile_caps'][row['profiles'][0]])
                    for scope, row in template['workspaces'].items()})
    initial = tmp_path/'initial.json'; initial.write_text(json.dumps(value))
    chain_file = tmp_path/'chain.json'; chain = [copy.deepcopy(value)]
    chain_file.write_text(json.dumps(chain))
    settings = dict(version=1, intent_sha256=PolicyWorkloadTransition.intent_sha256(value),
                    initial_record_file=str(initial), phase_chain_file=str(chain_file))
    config['policyTransition'] = settings
    from cps_compute.native_policy_transition_config import load_policy_transition
    transition = load_policy_transition(settings)
    current = {'value': copy.deepcopy(value)}
    def advance(**changes):
        core_fixtures.advance(current, **changes); chain.append(copy.deepcopy(current['value']))
        chain_file.write_text(json.dumps(chain))
    def consumer():
        return node.ApprovalConsumer(agent, config, template, reference,
            lambda namespace, name: copy.deepcopy(maps[name]), transition=transition)
    return SimpleNamespace(**locals())


def activate(epoch):
    publication={'acknowledgments':{component:dict(policy_hash=epoch.config['policy_hash'],revision=epoch.reference['revision'])
        for component in ('gateway','hub:cps','hub:cit','node')},'journal':dict(
            uid='87654321-1234-4234-8234-123456789abc',raw_sha256='sha256:'+'e'*64,
            previous_journal_sha256=epoch.value['previous_journal_sha256'],
            policy_hash=epoch.config['policy_hash'],revision=epoch.reference['revision'])}
    epoch.advance(publication=publication)
    epoch.advance(registrations={scope:dict(before=body,after=dict(body,policy_hash=epoch.config['policy_hash']),
        response_sha256='sha256:'+'f'*64) for scope,body in epoch.value['retained_workspace_records'].items()})
    epoch.advance(state='active')


def enrollment(epoch, side):
    deployment=epoch.value[side]['registry']['deployment'];scope,approval=next(iter(deployment['workspaces'].items()))
    source,workspace=scope.split(':',1);pool=deployment['node_pool'];profile=approval['profiles'][0]
    intent=dict(namespace=approval['namespace'],name=approval['pod'],pod_uid='11111111-1111-4111-8111-111111111111',
        node=pool['node'],node_uid=pool['node_uid'],gpu_uuid=pool['gpu_uuid'],spec_sha256='c'*64,
        cap_mib=deployment['evidence']['profile_caps'][profile],policy_hash=deployment['policy_hash'])
    reference=epoch.reference if side=='new' else epoch.value['retired_references'][0]
    body=dict(version=1,binding_id='a'*60,source=source,actor='service:'+source+'-hub',workspace=workspace,
        principal=approval['principal'],members=sorted(approval['members']),attempt='22222222-2222-4222-8222-222222222222',
        profile=profile,intent=intent,approval_ref=reference,**{k:intent[k] for k in
        ('policy_hash','namespace','name','node','node_uid','gpu_uuid','cap_mib')})
    cm=dict(apiVersion='v1',kind='ConfigMap',immutable=True,metadata=dict(
        name='cps-native-enrollment-'+'a'*40,namespace=epoch.config['authority_namespace'],
        uid='44444444-4444-4444-8444-444444444444',labels={agent.LABEL:'a'*60}),
        data={'enrollment.json':node.canonical(body)})
    return cm,body


def test_actual_consumer_parses_prepared_epoch_but_holds_live_admission(epoch):
    consumer = epoch.consumer()
    assert consumer.current()['policy_hash'] == epoch.config['policy_hash']
    with pytest.raises(ValueError):
        consumer.validate_enrollment({}, None)
    published = copy.deepcopy(epoch.value)
    published['publication'] = {'acknowledgments': {component: {
        'policy_hash': epoch.config['policy_hash'], 'revision': epoch.reference['revision']}
        for component in ('gateway', 'hub:cps', 'hub:cit', 'node')},
        'journal': dict(uid='87654321-1234-4234-8234-123456789abc', raw_sha256='sha256:'+'e'*64,
            previous_journal_sha256=epoch.value['previous_journal_sha256'],
            policy_hash=epoch.config['policy_hash'], revision=epoch.reference['revision'])}
    epoch.advance(publication=published['publication'])
    assert consumer.current()['policy_hash'] == epoch.config['policy_hash']
    with pytest.raises(ValueError):consumer.validate_enrollment({}, None)
    registrations = {scope: dict(before=body, after=dict(body, policy_hash=epoch.config['policy_hash']),
        response_sha256='sha256:'+'f'*64) for scope, body in epoch.value['retained_workspace_records'].items()}
    epoch.advance(registrations=registrations); epoch.advance(state='active')
    consumer.require_admission()
    epoch.advance(state='revoked')
    with pytest.raises(ValueError):consumer.require_admission()
    with pytest.raises(ValueError):consumer.current()


@pytest.mark.parametrize('fault', ['missing', 'unknown', 'mixed', 'old_current', 'pool'])
def test_actual_consumer_rejects_mixed_or_incomplete_epoch(epoch, fault):
    if fault == 'missing':
        document=json.loads(epoch.cm['data']['approval.json']); document['history'].pop()
        epoch.cm['data']['approval.json']=node.canonical(document)
        epoch.reference['data_sha256']=canonical_sha256(epoch.cm['data'])
    elif fault == 'unknown':epoch.reference['policy_hash']='sha256:'+'a'*64
    elif fault == 'mixed':epoch.template=copy.deepcopy(epoch.template); epoch.template['workloadImage']='registry.invalid/foreign@sha256:'+'1'*64
    elif fault == 'old_current':epoch.reference=epoch.value['retired_references'][0]
    else:epoch.config['pool']=dict(epoch.config['pool'],max_workspaces=1)
    with pytest.raises(ValueError):
        node.ApprovalConsumer(agent, epoch.config, epoch.template, epoch.reference,
            lambda namespace,name:copy.deepcopy(epoch.maps[name]), transition=epoch.transition).current()


def test_retired_document_is_readable_only_in_its_original_epoch(epoch):
    consumer=epoch.consumer(); reference=epoch.value['retired_references'][0]
    retired=consumer.document(reference)
    assert retired['policy_hash']==epoch.value['old']['registry']['deployment']['policy_hash']
    changed=copy.deepcopy(reference); changed['uid']='88888888-1234-4234-8234-123456789abc'
    with pytest.raises(ValueError):consumer.document(changed)


def test_actual_enrollment_uses_new_epoch_and_retired_context_cannot_admit(epoch):
    consumer=epoch.consumer();models=agent.load_models_from_snapshot();current,body=enrollment(epoch,'new')
    with pytest.raises(ValueError):consumer.validate_enrollment(current,models)
    activate(epoch)
    envelope=consumer.validate_enrollment(current,models);consumer.models=models
    assert envelope['enrollment']==body
    retired,old_body=enrollment(epoch,'old');ref=epoch.value['retired_references'][0]
    old_document=consumer.document(ref)
    assert consumer._envelope(retired,models,old_document,ref)['enrollment']==old_body
    with pytest.raises(ValueError):consumer.validate_enrollment(retired,models)
    epoch.advance(state='revoked')
    with pytest.raises(ValueError):consumer.validate_approved_pod({},envelope)


def test_prepared_node_can_acknowledge_loaded_document_without_opening_admission(epoch):
    consumer=epoch.consumer();consumer.current();pool=epoch.config['pool']
    process=dict(namespace=epoch.reference['namespace'],name='node',uid='11111111-1111-4111-8111-111111111111',
        container='node',image='example/node@sha256:'+'a'*64,service_account='node')
    pod=dict(apiVersion='v1',kind='Pod',metadata={k:process[k] for k in ('namespace','name','uid')},
        spec=dict(nodeName=pool['node'],serviceAccountName='node',containers=[dict(name='node',image=process['image'])]),
        status=dict(phase='Running',conditions=[dict(type='Ready',status='True')],
            containerStatuses=[dict(name='node',ready=True,imageID=process['image'])]))
    epoch_proof={k:pool[k] for k in ('node_uid','boot_id','driver_generation','gpu_uuid')}
    ack=consumer.acknowledge(process,pod,epoch_proof,True,lambda value:None)
    assert ack['policy_hash']==epoch.config['policy_hash'] and ack['document']==epoch.reference
    with pytest.raises(ValueError):consumer.require_admission()


def test_unreferenced_seed_cannot_bypass_prepared_admission_hold(epoch,tmp_path):
    consumer=epoch.consumer();models=agent.load_models_from_snapshot();cm,body=enrollment(epoch,'new')
    body.pop('approval_ref');cm['data']['enrollment.json']=node.canonical(body)
    envelope=agent.validate_enrollment(cm,epoch.config,models)
    ledger=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(namespace=epoch.config['authority_namespace'],
        name='cps-native-gpu-allocations',uid='55555555-5555-4555-8555-555555555555',resourceVersion='1'),
        data={'state.json':node.canonical(dict(version=1,allocations={body['binding_id']:dict(body,state='enrolled')}))})
    kube=SimpleNamespace(configmap=lambda namespace,name:ledger)
    store=SimpleNamespace(state=tmp_path,backend=SimpleNamespace(private_read=lambda *args:envelope),uid=0)
    with pytest.raises(ValueError,match='Admission held'):
        consumer.validate_enrollments([cm],models,store,SimpleNamespace(),kube)


def test_actual_runtime_begin_retains_the_typed_authority(epoch,monkeypatch,tmp_path):
    inputs={'/reference':epoch.reference,'/qualification':epoch.template}
    monkeypatch.setattr(node,'read_private',lambda path,**kw:copy.deepcopy(inputs[str(path)]))
    original=agent.load_source
    def load(name,raw,expected,filename):
        module=original(name,raw,expected,filename)
        if name=='_approval_private_backend':
            # There is no pre-existing Root-owned private acknowledgment in
            # this CPU fixture; its filesystem authorization is tested upstream.
            module.private_read=lambda path,uid:None
        return module
    monkeypatch.setattr(agent,'load_source',load)
    runtime=node.NodeApprovalRuntime(agent,'/reference','/qualification','/process',tmp_path,transition=epoch.transition)
    consumer=runtime.begin(epoch.config,SimpleNamespace(configmap=lambda namespace,name:copy.deepcopy(epoch.maps[name])))
    assert consumer.transition is epoch.transition
    with pytest.raises(ValueError):consumer.require_admission()


@pytest.mark.parametrize('fault',['rollback','missing_chain'])
def test_existing_consumer_denies_replayed_or_unavailable_protected_phase(epoch,fault):
    consumer=epoch.consumer();activate(epoch);consumer.require_admission()
    if fault=='rollback':epoch.chain_file.write_text(json.dumps([epoch.value]))
    else:epoch.chain_file.unlink()
    with pytest.raises(ValueError):consumer.current()
    with pytest.raises(ValueError):consumer.require_admission()


@pytest.mark.parametrize('epoch',['deployed'],indirect=True)
def test_original_39ef_history_remains_pinned_under_bound_successor(epoch):
    old=copy.deepcopy(epoch.config);old.pop('policyTransition');old['policy_hash']='sha256:39ef15d3b5a76f96d135beb1afcd538775c64301cb51751086b44d68c54f8012'
    old['mode']='operator-qualification';old['pool']['memory_budget_mib']=25600
    old['workspaces']={'cps:native-group-b':dict(profile='interactive-native-qualification-5',cap_mib=5120),
                       'cit:native-group-a':dict(profile='interactive-native-qualification-20',cap_mib=20480)}
    cm=dict(apiVersion='v1',kind='ConfigMap',immutable=True,metadata=dict(
        namespace=old['authority_namespace'],name='cps-native-node-qualification-original',
        uid='77777777-7777-4777-8777-777777777777'),data={'config.json':node.canonical(old)})
    ref=dict(cm['metadata'],data_sha256=canonical_sha256(cm['data']),policy_hash=old['policy_hash'])
    entry={'policy_hash':old['policy_hash']}
    legacy=copy.deepcopy(epoch.config);legacy.pop('policyTransition');legacy['policy_hash']=epoch.value['old']['registry']['deployment']['policy_hash']
    assert agent.validate_historical_configuration(cm,ref,legacy,entry)==old
    with pytest.raises(ValueError):agent.validate_historical_configuration(cm,ref,epoch.config,entry)
    assert agent.validate_historical_configuration(cm,ref,epoch.config,entry,transition=epoch.transition)==old
    changed=copy.deepcopy(epoch.config);changed['pool']['memory_budget_mib']=20480
    with pytest.raises(ValueError):agent.validate_historical_configuration(cm,ref,changed,entry,transition=epoch.transition)


def test_node_configuration_requires_explicit_group_mode_for_transition(epoch):
    assert agent.validate_config(epoch.config)==epoch.config
    for field,value in (('mode','operator-qualification'),('enabled',False),('version',1)):
        changed=copy.deepcopy(epoch.config); changed[field]=value
        with pytest.raises(ValueError):agent.validate_config(changed)


def test_node_factory_loads_transition_before_driver_or_api(epoch, monkeypatch):
    class BeforeDriver(Exception):pass
    monkeypatch.setattr(agent.os,'geteuid',lambda:0)
    monkeypatch.setattr(agent,'read_config',lambda path:epoch.config)
    monkeypatch.setattr(agent,'load_bundle',lambda path:(_ for _ in ()).throw(BeforeDriver()))
    epoch.chain_file.unlink()
    with pytest.raises(ValueError):
        agent.main(['--execute','--config','/unused','--approval-reference','/r',
                    '--approval-template','/t','--approval-process','/p'])


def test_unmodified_driver_helpers_and_updated_consumer_pin():
    root=Path(__file__).parents[1]; manifest=json.loads((root/'bundle-manifest.json').read_text())
    pins=manifest.get('files',manifest.get('sha256',manifest))
    for name,digest in pins.items():
        if name in ('node_agent.py','native_approval_revision.py') or not name.endswith('.py'):continue
        assert hashlib.sha256((root/'bundle'/name).read_bytes()).hexdigest()==digest
    assert hashlib.sha256(Path(node.__file__).read_bytes()).hexdigest() in Path(agent.__file__).read_text()

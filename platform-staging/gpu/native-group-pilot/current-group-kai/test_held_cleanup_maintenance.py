"""Closed prepared-only maintenance evidence; no private data or API operations."""
import copy
import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest
from cps_compute.native_gpu_controller import CapRecord
from cps_compute.native_groups import canonical_sha256
from test_native_gpu_controller import intent, identity
from test_head_gateway_rotation import fixture as rotation_fixture, prepare

HERE=Path(__file__).parent

def module():
    spec=importlib.util.spec_from_file_location('held_cleanup_test',HERE/'held_cleanup_maintenance.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)

def fixture():
    pod={'apiVersion':'v1','kind':'Pod','metadata':{'namespace':'qualification','name':'jupyter-neutral--rtc','uid':intent().pod_uid},'spec':{'nodeName':'gpu2','containers':[{'name':'notebook','image':'example@sha256:'+'1'*64}]}}
    digest=canonical_sha256(pod['spec'])[7:]
    i=replace(intent(),name='jupyter-neutral--rtc',spec_sha256=digest);who=replace(identity(),spec_sha256=digest)
    record=CapRecord(i,who,'prepared','11111111-1111-4111-8111-111111111111',None).to_dict()
    binding='a'*60;attempt='22222222-2222-4222-8222-222222222222'
    body={'version':1,'binding_id':binding,'source':'cps','actor':'workspace:cps:shared-gpu-lab','workspace':'shared-gpu-lab','principal':'workspace:cps:shared-gpu-lab','members':['p1','p2','p3'],'attempt':attempt,'profile':'interactive-shared-5','policy_hash':i.policy_hash,**{k:getattr(i,k) for k in ['namespace','name','node','node_uid','gpu_uuid','cap_mib']},'intent':i.to_dict()}
    enrollment={'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':'authority','name':'cps-native-enrollment-'+binding[:40],'uid':'33333333-3333-4333-8333-333333333333','labels':{'cps.compute/native-binding':binding}},'immutable':True,'data':{'enrollment.json':canonical(body)}}
    row={**body,'state':'releasing','group_id':'group','ceiling':{'cpu':'4','memory':'16Gi','gpuMemoryGiB':5}}
    def ledger(rows):return {'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':'authority','name':'cps-native-gpu-allocations','uid':'44444444-4444-4444-8444-444444444444','resourceVersion':'4'},'data':{'state.json':canonical({'version':1,'allocations':rows})}}
    prior={'b'*60:{'state':'released','unchanged':'original'},**{format(n,'060x'):{'state':'released','unchanged':str(n)} for n in range(166)}}
    old=ledger(prior);current=ledger({**prior,binding:row})
    entry={'cgroup_id':who.cgroup_inode,'kernfs_id':who.cgroup_inode,'inode':who.cgroup_inode,'offline':True,'pinned':True,'default_hierarchy':True,'soft':0,'hard':2**64-1,'used':0}
    observation={'baseline_ledger':old,'enrollment':enrollment,'journal_raw':canonical(record)+'\n','inventory':{'version':1,'backend':'misc-fallback','gpu_uuid':i.gpu_uuid,'gpu_id':1552,'entries':[entry]},'epoch_before':who.epoch.__dict__,'epoch_after':who.epoch.__dict__,'original_pod':pod,'pod_absent':True,'cgroup_absent':True,'sql':{'reservation':[{'person':p,'workspace':'cps:shared-gpu-lab'} for p in body['members']],'reservation_binding':[{'workspace':'cps:shared-gpu-lab','attempt':attempt,'binding':json.dumps({k:row[k] for k in ['policy_hash','principal','profile','ceiling']})}]},'workspaces':{'cps':[{'id':'shared-gpu-lab','state':'stopping','hub_user':'neutral','hub_server':'rtc','profile':'interactive-shared-5'}],'cit':[{'id':'other','state':'stopped','hub_user':'other','hub_server':'rtc','profile':'interactive-cpu'}]}}
    observation['gate_receipt_before']={'path':'/run/cps-native-gpu/receipts/'+i.pod_uid+'.json','absent':True}
    observation['gate_receipt_after']=copy.deepcopy(observation['gate_receipt_before'])
    observation['workspaces']['cps'] += [{'id':'stopped-'+str(n),'state':'stopped','hub_user':'neutral-'+str(n),'hub_server':'rtc','profile':'interactive-cpu'} for n in range(7)]
    packet={'version':1,'kind':'single-held-prepared-cleanup-maintenance','observation':observation,'review':{'binding_id':binding,'expected_counts':{'released_claims':167,'workspaces':{'cps':8,'cit':1},'reservation':3,'reservation_binding':1},'ledger_sha256':canonical_sha256(current),'observation_sha256':canonical_sha256(observation)}}
    return current,packet

def repin(ledger,p):
    p['review']['ledger_sha256']=canonical_sha256(ledger);p['review']['observation_sha256']=canonical_sha256(p['observation'])

def test_closed_evidence_preserves_every_input():
    ledger,p=fixture();before=copy.deepcopy((ledger,p));result=module().validate(ledger,p)
    assert result['held_binding_id']==p['review']['binding_id'] and result['reservation_counts']=={'reservation':3,'reservation_binding':1}
    assert (ledger,p)==before

@pytest.mark.parametrize('fault',['extra-packet','extra-observation','extra-review','ledger-pin','observation-pin','readback','state','journal-extra','epoch','used','online','unpinned','finite','duplicate-inode','missing-entry','pod-present','cgroup-present','spec','enrollment-uid','enrollment-body','other-claim','prior-changed','sql-extra','sql-attempt','sql-person','sql-binding','workspace-running','workspace-foreign-stopping'])
def test_refuses_closed_input_drift_even_when_operator_repins(fault):
    ledger,p=fixture();o=p['observation']
    if fault=='extra-packet':p['ignore_active']=True
    elif fault=='extra-observation':o['ignore_active']=True
    elif fault=='extra-review':p['review']['ignore_active']=True
    elif fault=='ledger-pin':p['review']['ledger_sha256']='sha256:'+'0'*64
    elif fault=='observation-pin':p['review']['observation_sha256']='sha256:'+'0'*64
    elif fault in ('readback','state','journal-extra'):
        v=json.loads(o['journal_raw'])
        if fault=='readback':v['readback']={'soft':1,'hard':1}
        elif fault=='state':v['state']='cap-applied'
        else:v['unknown']=True
        o['journal_raw']=canonical(v)
    elif fault=='epoch':o['epoch_after']['driver_generation']='55555555-5555-4555-8555-555555555555'
    elif fault in ('used','online','unpinned','finite'):
        k,v={'used':('used',1),'online':('offline',False),'unpinned':('pinned',False),'finite':('hard',5)}[fault];o['inventory']['entries'][0][k]=v
    elif fault=='duplicate-inode':o['inventory']['entries']*=2
    elif fault=='missing-entry':o['inventory']['entries']=[]
    elif fault=='pod-present':o['pod_absent']=False
    elif fault=='cgroup-present':o['cgroup_absent']=False
    elif fault=='spec':o['original_pod']['spec']['containers'][0]['image']='changed'
    elif fault=='enrollment-uid':o['enrollment']['metadata']['uid']='invalid'
    elif fault=='enrollment-body':o['enrollment']['data']['enrollment.json']=canonical({})
    elif fault in ('other-claim','prior-changed'):
        v=json.loads(ledger['data']['state.json']);v['allocations']['b'*60]['state']='releasing' if fault=='other-claim' else 'released';v['allocations']['b'*60]['unchanged']='changed';ledger['data']['state.json']=canonical(v)
    elif fault=='sql-extra':o['sql']['reservation'].append(copy.deepcopy(o['sql']['reservation'][0]))
    elif fault=='sql-attempt':o['sql']['reservation_binding'][0]['attempt']='foreign'
    elif fault=='sql-person':o['sql']['reservation'][0]['person']='foreign'
    elif fault=='sql-binding':o['sql']['reservation_binding'][0]['binding']='{}'
    elif fault=='workspace-running':o['workspaces']['cps'][0]['state']='running'
    elif fault=='workspace-foreign-stopping':o['workspaces']['cit'][0]['state']='stopping'
    if fault not in ('ledger-pin','observation-pin'):repin(ledger,p)
    with pytest.raises((ValueError,TypeError,KeyError)):module().validate(ledger,p)

def compiler_fixture():
    from test_head_gateway_rotation import image
    v=rotation_fixture();policy,config=image._context(v['snapshot']);ledger,p=fixture();o=p['observation']
    pool=config.deployment.node_pool;binding=p['review']['binding_id'];rows=json.loads(ledger['data']['state.json'])['allocations'];claim=rows[binding]
    record=json.loads(o['journal_raw']);i=record['intent'];who=record['identity']
    for key in ('node_uid','gpu_uuid'):i[key]=who[key]=pool[key]
    for key in ('boot_id','driver_generation'):who[key]=pool[key]
    i['namespace']=config.document['component_declarations']['hub:cps']['namespace'];o['original_pod']['metadata']['namespace']=i['namespace']
    i['node']=pool['node'];i['policy_hash']=policy.hash;o['original_pod']['spec']['nodeName']=pool['node']
    i['spec_sha256']=who['spec_sha256']=canonical_sha256(o['original_pod']['spec'])[7:]
    claim['intent']=i
    for key in ('namespace','node_uid','gpu_uuid','node','policy_hash'):claim[key]=i[key]
    for key in ('epoch_before','epoch_after'):o[key]={k:pool[k] for k in ('node_uid','boot_id','driver_generation','gpu_uuid')}
    o['inventory']['gpu_uuid']=pool['gpu_uuid'];o['journal_raw']=canonical(record)+'\n'
    o['enrollment']['data']['enrollment.json']=canonical({k:value for k,value in claim.items() if k not in ('state','group_id','ceiling')})
    for cm in (ledger,o['baseline_ledger'],o['enrollment']):cm['metadata']['namespace']=config.deployment.authority_namespace
    ledger['data']['state.json']=canonical({'version':1,'allocations':rows})
    o['sql']['reservation_binding'][0]['binding']=canonical({k:claim[k] for k in ('policy_hash','principal','profile','ceiling')})
    repin(ledger,p)
    snapshot=v['snapshot'];snapshot['objects'][image._key('ConfigMap',config.deployment.authority_namespace,'cps-native-gpu-allocations')]=ledger
    v['expected_snapshot_sha256']=canonical_sha256(snapshot)
    v['node_image']='ghcr.io/mul-cps/cps-native-node@sha256:'+'8'*64
    return v,p

def test_default_compiler_still_rejects_held_ledger():
    v,p=compiler_fixture()
    with pytest.raises(ValueError,match='Released-only ledger'):prepare(v)

def test_explicit_closed_variant_compiles_real_plan_without_changing_custody():
    v,p=compiler_fixture();v['held_cleanup']=p;v['expected_held_cleanup_sha256']=canonical_sha256(p);before=copy.deepcopy(v)
    plan=prepare(v)
    assert plan['inputs']['held_cleanup']==p and v==before
    assert plan['live_applied'] is False

def test_absent_variant_preserves_default_plan_bytes():
    v=rotation_fixture();old=prepare(v);v['held_cleanup']=None
    assert prepare(v)==old

@pytest.mark.parametrize('fault',['missing-pin','wrong-pin','pin-without-mode','gateway-only','node-only','same-node','epoch','policy','authority'])
def test_real_compiler_rejects_mode_authority_or_scope_drift(fault):
    v,p=compiler_fixture();v['held_cleanup']=p;v['expected_held_cleanup_sha256']=canonical_sha256(p)
    if fault=='missing-pin':v.pop('expected_held_cleanup_sha256')
    elif fault=='wrong-pin':v['expected_held_cleanup_sha256']='sha256:'+'0'*64
    elif fault=='pin-without-mode':v.pop('held_cleanup')
    elif fault=='gateway-only':v.pop('node_image')
    elif fault=='same-node':
        from test_head_gateway_rotation import image
        _,config=image._context(v['snapshot']);v['node_image']=config.document['component_declarations']['node']['image']
    elif fault=='node-only':
        from test_head_gateway_rotation import image
        _,config=image._context(v['snapshot']);v['gateway_image']=config.document['component_declarations']['gateway']['image']
    else:
        o=p['observation']
        if fault=='epoch':o['epoch_after']['boot_id']='66666666-6666-4666-8666-666666666666'
        elif fault=='policy':
            record=json.loads(o['journal_raw']);record['intent']['policy_hash']='sha256:'+'0'*64;o['journal_raw']=canonical(record)
        else:o['enrollment']['metadata']['namespace']='foreign'
        repin(next(x for x in v['snapshot']['objects'].values() if x.get('metadata',{}).get('name')=='cps-native-gpu-allocations'),p)
        v['expected_held_cleanup_sha256']=canonical_sha256(p)
    with pytest.raises(ValueError):prepare(v)

@pytest.mark.parametrize('fault',['receipt-before-present','receipt-after-present','receipt-wrong-path','receipt-missing','count-prior','count-workspaces','count-reservations','count-binding','count-extra'])
def test_reviewed_counts_and_actual_gate_absence_are_mandatory(fault):
    ledger,p=fixture();o=p['observation'];counts=p['review']['expected_counts']
    if fault=='receipt-before-present':o['gate_receipt_before']['absent']=False
    elif fault=='receipt-after-present':o['gate_receipt_after']['absent']=False
    elif fault=='receipt-wrong-path':o['gate_receipt_before']['path']='/tmp/foreign'
    elif fault=='receipt-missing':o.pop('gate_receipt_after')
    elif fault=='count-prior':counts['released_claims']-=1
    elif fault=='count-workspaces':counts['workspaces']['cps']-=1
    elif fault=='count-reservations':counts['reservation']-=1
    elif fault=='count-binding':counts['reservation_binding']=2
    else:counts['ignore']=True
    repin(ledger,p)
    with pytest.raises(ValueError):module().validate(ledger,p)


def test_counts_come_from_independent_review_not_current_run_literals():
    ledger,p=fixture();o=p['observation'];counts=p['review']['expected_counts'];binding=p['review']['binding_id']
    old=json.loads(o['baseline_ledger']['data']['state.json']);current=json.loads(ledger['data']['state.json'])
    key=format(165,'060x');old['allocations'].pop(key);current['allocations'].pop(key);counts['released_claims']=166
    claim=current['allocations'][binding];claim['members'].pop();counts['reservation']=2;o['sql']['reservation'].pop()
    body=json.loads(o['enrollment']['data']['enrollment.json']);body['members']=claim['members'];o['enrollment']['data']['enrollment.json']=canonical(body)
    o['baseline_ledger']['data']['state.json']=canonical(old);ledger['data']['state.json']=canonical(current)
    o['workspaces']['cps'].pop();counts['workspaces']['cps']=7;repin(ledger,p)
    assert module().validate(ledger,p)['reservation_counts']=={'reservation':2,'reservation_binding':1}

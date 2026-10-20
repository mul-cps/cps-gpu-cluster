"""Offline phase transitions use real typed cleanup codecs and actual-shaped envelopes."""
import copy
import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest
from cps_compute.native_gpu_controller import CapRecord, prepared_offline_provenance, validate_prepared_offline_inventory
from cps_compute.native_groups import canonical_sha256
from cps_compute.native_gpu_control import NativeAuthorityError
from test_held_cleanup_maintenance import fixture, canonical

HERE=Path(__file__).parent

def module():
    spec=importlib.util.spec_from_file_location('held_phases_test',HERE/'held_cleanup_phases.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def phases():
    ledger,packet=fixture();o=copy.deepcopy(packet['observation']);original=CapRecord.from_dict(json.loads(o['journal_raw']))
    proof=validate_prepared_offline_inventory(o['inventory'],original.identity)
    terminal=replace(original,state='prepared-offline-unlimited',prepared_offline=proof)
    o['journal_raw']=canonical(terminal.to_dict())+'\n'
    enrollment=o['enrollment'];body=json.loads(enrollment['data']['enrollment.json']);binding=body['binding_id']
    receipt={'version':1,'binding_id':binding,'attempt':body['attempt'],'intent':body['intent'],'cleanup_confirmed':True,
        'prepared_offline':prepared_offline_provenance(terminal,enrollment['metadata']['uid'],canonical_sha256(body))}
    cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':enrollment['metadata']['namespace'],'name':'cps-native-cleanup-'+binding[:40],
        'uid':'55555555-5555-4555-8555-555555555555','resourceVersion':'99','labels':{'cps.compute/native-binding':binding}},'immutable':True,'data':{'receipt.json':canonical(receipt)}}
    cleanup={'observation':o,'cleanup_configmap':cm}
    current={'ledger':copy.deepcopy(ledger),'observation':copy.deepcopy(o),'cleanup_configmap':copy.deepcopy(cm)}
    rows=json.loads(current['ledger']['data']['state.json']);rows['allocations'][binding]['state']='released'
    current['ledger']['data']['state.json']=canonical(rows);current['ledger']['metadata']['resourceVersion']='5'
    current['observation']['sql']={'reservation':[],'reservation_binding':[]}
    current['observation']['workspaces']['cps'][0]['state']='stopped'
    return ledger,packet,cleanup,current

def test_all_three_real_codec_phases_preserve_inputs_and_never_authorize_mutations():
    ledger,p,cleanup,current=phases();before=copy.deepcopy((ledger,p,cleanup,current));m=module()
    assert m.validate_pre_upgrade(ledger,p,p['observation'],expected_sha256=canonical_sha256(p['observation']))['phase']=='pre-upgrade'
    assert m.validate_cleanup_published(ledger,p,cleanup,expected_sha256=canonical_sha256(cleanup))['phase']=='cleanup-published-held'
    out=m.validate_released_successor(ledger,p,cleanup,current,expected_prior_sha256=canonical_sha256(cleanup),expected_sha256=canonical_sha256(current))
    assert out['phase']=='released-successor-observed' and out['release_authorized'] is False
    assert out['ledger_unchanged'] is False
    assert (ledger,p,cleanup,current)==before

@pytest.mark.parametrize('fault',['new-journal','gate-present','epoch','ledger-pin'])
def test_pre_upgrade_requires_original_exact_prepared_snapshot(fault):
    ledger,p,cleanup,_=phases();fresh=copy.deepcopy(p['observation'])
    if fault=='new-journal':fresh['journal_raw']=cleanup['observation']['journal_raw']
    elif fault=='gate-present':fresh['gate_receipt_after']['absent']=False
    elif fault=='epoch':fresh['epoch_after']['boot_id']='66666666-6666-4666-8666-666666666666'
    else:ledger['metadata']['uid']='66666666-6666-4666-8666-666666666666'
    with pytest.raises((ValueError, TypeError, KeyError, NativeAuthorityError)):module().validate_pre_upgrade(ledger,p,fresh,expected_sha256=canonical_sha256(fresh))

@pytest.mark.parametrize('fault',['prepared','finite','receipt-missing','receipt-mutable','receipt-owner','receipt-uid','receipt-namespace','receipt-binding','receipt-proof','receipt-original','inventory','gate-present','sql-changed','workspace-changed','wrong-pin'])
def test_cleanup_successor_requires_genuine_exact_typed_provenance(fault):
    ledger,p,c,_=phases();o=c['observation'];cm=c['cleanup_configmap']
    if fault=='prepared':o['journal_raw']=p['observation']['journal_raw']
    elif fault=='finite':
        r=json.loads(o['journal_raw']);r['prepared_offline']['entry']['hard']=5120;o['journal_raw']=canonical(r)+'\n'
    elif fault=='receipt-missing':c['cleanup_configmap']=None
    elif fault=='receipt-mutable':cm['immutable']=False
    elif fault=='receipt-owner':cm['metadata']['ownerReferences']=[{'uid':'foreign'}]
    elif fault=='receipt-uid':cm['metadata']['uid']='invalid'
    elif fault=='receipt-namespace':cm['metadata']['namespace']='foreign'
    elif fault=='receipt-binding':cm['metadata']['labels']['cps.compute/native-binding']='b'*60
    elif fault in ('receipt-proof','receipt-original'):
        r=json.loads(cm['data']['receipt.json'])
        if fault=='receipt-proof':r['prepared_offline']['enrollment_uid']='66666666-6666-4666-8666-666666666666'
        else:r['prepared_offline']['original']['seal_id']='66666666-6666-4666-8666-666666666666'
        cm['data']['receipt.json']=canonical(r)
    elif fault=='inventory':o['inventory']['gpu_id']+=1
    elif fault=='gate-present':o['gate_receipt_before']['absent']=False
    elif fault=='sql-changed':o['sql']['reservation'].pop()
    elif fault=='workspace-changed':o['workspaces']['cps'][0]['state']='stopped'
    pin='sha256:'+'0'*64 if fault=='wrong-pin' else canonical_sha256(c)
    with pytest.raises((ValueError, TypeError, KeyError, NativeAuthorityError)):module().validate_cleanup_published(ledger,p,c,expected_sha256=pin)

@pytest.mark.parametrize('fault',['still-releasing','other-row','selected-extra','sql-retained','workspace-retained','workspace-other','receipt-uid','journal','wrong-pin','wrong-prior-pin'])
def test_released_phase_allows_only_the_canonical_logical_successor(fault):
    ledger,p,c,current=phases();binding=p['review']['binding_id']
    if fault in ('still-releasing','other-row','selected-extra'):
        rows=json.loads(current['ledger']['data']['state.json'])
        if fault=='still-releasing':rows['allocations'][binding]['state']='releasing'
        elif fault=='other-row':rows['allocations']['b'*60]['unchanged']='changed'
        else:rows['allocations'][binding]['ignored']=True
        current['ledger']['data']['state.json']=canonical(rows)
    elif fault=='sql-retained':current['observation']['sql']=copy.deepcopy(c['observation']['sql'])
    elif fault=='workspace-retained':current['observation']['workspaces']['cps'][0]['state']='stopping'
    elif fault=='workspace-other':current['observation']['workspaces']['cit'][0]['profile']='changed'
    elif fault=='receipt-uid':current['cleanup_configmap']['metadata']['uid']='66666666-6666-4666-8666-666666666666'
    elif fault=='journal':current['observation']['journal_raw']=p['observation']['journal_raw']
    pin='sha256:'+'0'*64 if fault=='wrong-pin' else canonical_sha256(current)
    prior='sha256:'+'0'*64 if fault=='wrong-prior-pin' else canonical_sha256(c)
    with pytest.raises((ValueError, TypeError, KeyError, NativeAuthorityError)):module().validate_released_successor(ledger,p,c,current,expected_prior_sha256=prior,expected_sha256=pin)

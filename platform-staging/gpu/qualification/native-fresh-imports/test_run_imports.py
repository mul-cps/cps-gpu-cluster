from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest

HERE=Path(__file__).parent

def runner():
    s=importlib.util.spec_from_file_location('fresh_import_runner',HERE/'run_imports.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def test_default_inert_does_not_read_artifacts_or_contact_cluster():
    m=runner()
    with patch.object(m.Path,'read_bytes',side_effect=AssertionError('source I/O')), \
         patch.object(m.subprocess,'run',side_effect=AssertionError('API')), \
         patch('sys.stdout',new_callable=io.StringIO) as output:m.main([])
    assert 'inert' in output.getvalue()

def test_changed_original_protected_or_process_authority_denies_postflight():
    m=runner()
    target={'pod_uid':'uid','intent':{},'identity':{},'seal_id':'seal','journal_sha256':'j',
            'gate_sha256':'g','limit':{'soft':5,'hard':5,'used':0}}
    before={'pods':['exact'], 'host':{'processes':['same-pid-start'], 'targets':[target]}}
    m.unchanged(before,deepcopy(before))
    for mutation in ('pod','process','seal','charge'):
        after=deepcopy(before)
        if mutation=='pod':after['pods']=['replaced']
        elif mutation=='process':after['host']['processes']=['new-pid-start']
        elif mutation=='seal':after['host']['targets'][0]['seal_id']='replacement'
        else:after['host']['targets'][0]['limit']['used']=1
        with pytest.raises(ValueError):m.unchanged(before,after)

@pytest.mark.parametrize('failure',[None,'late-process','late-proof','cancel'])
def test_one_actual_command_postflight_failure_and_cancellation_never_accept(tmp_path,failure):
    m=runner()
    target={'pod_uid':'uid','intent':{},'identity':{},'seal_id':'seal','journal_sha256':'j',
            'gate_sha256':'g','limit':{'soft':5,'hard':5,'used':0}}
    before={'pods':['actual-a','actual-b'],'host':{'processes':['fixed-actual-processes'],'targets':[target,deepcopy(target)]}}
    after=deepcopy(before)
    if failure=='late-process':after['host']['processes']=['changed']
    observed=[]
    def preflight(_):
        observed.append('fresh')
        if len(observed)==2 and failure=='late-proof':raise ValueError('fresh authority denied')
        return before if len(observed)==1 else after
    class Peer:
        def __init__(self,*args):self.args=args
        def wait(self,*_):pass
        def complete(self):return ['actual-bounded-peer-events']
    cleaned=[]
    transport=SimpleNamespace(ProbeRun=Peer,abandon=lambda run:cleaned.append(run))
    current=SimpleNamespace(read_targets=lambda *_:{'pods':{key:{'namespace':'qa','name':key} for key in ('a','b')}},
                            preflight=preflight)
    engine=SimpleNamespace(bundle=lambda *_:b'exact reviewed stream',assess=lambda *_:{'same_parent_measurement':True})
    result=SimpleNamespace(returncode=0,stdout=b'{"stage_cleanup_confirmed":true}',stderr=b'')
    args=['--execute','--manifest','reviewed','--manifest-sha256','raw','--binary','approved',
          '--binary-sha256',m.BINARY_SHA,'--runner-sha256','reviewed','--output',str(tmp_path/'out')]
    with patch.object(m,'checked_bytes',return_value=b'approved'),patch.object(m,'load',side_effect=[engine,transport,current]), \
         patch.object(m.subprocess,'run',side_effect=KeyboardInterrupt if failure=='cancel' else None,return_value=result) as call, \
         patch('sys.stdout',new_callable=io.StringIO):
        if failure=='cancel':
            with pytest.raises(KeyboardInterrupt):m.main(args)
        elif failure:
            with pytest.raises(SystemExit):m.main(args)
        else:m.main(args)
    assert call.call_count==1 and len(cleaned)==1
    assert call.call_args.args[0][-4:]==['python','-I','-u','-']
    receipt=json.loads((tmp_path/'out/receipt.json').read_text())
    assert receipt['production_qualified'] is False and receipt['cross_parent_isolation_qualified'] is False
    if failure:
        assert receipt['state']=='inconclusive' and 'unchanged_native_authorities' not in receipt
    else:
        assert observed==['fresh','fresh'] and receipt['unchanged_native_authorities'] is True

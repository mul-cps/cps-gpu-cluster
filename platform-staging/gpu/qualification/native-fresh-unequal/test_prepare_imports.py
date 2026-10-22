from pathlib import Path
import ast
import hashlib
import importlib.util
from unittest.mock import patch

import pytest

HERE=Path(__file__).parent


def adapter():
    s=importlib.util.spec_from_file_location('unequal_import_adapter',HERE/'prepare_imports.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def test_five_gib_import_engines_unchanged_and_peer_is_fixed_ten_gib():
    m=adapter();out=m.build_sources()
    assert hashlib.sha256(out['same_parent_engine.py']).hexdigest()=='dc6103ae49c8b91dab546f62fa67515a1fecd3caa3964cb220bda7d1c5aa9e58'
    assert hashlib.sha256(out['same_pod_imports.py']).hexdigest()=='d8cdbf06d93a0f46e0fc122f5f547ff121d0728b7d99b55f1ca8345c574e4f6c'
    assert hashlib.sha256(out['run_peer_oom.py']).hexdigest()=='4962c47258748f569122a4f9a51f247b94ddbfa206350d6c33ef81d3931e8b77'
    assert hashlib.sha256(out['fresh_preflight.py']).hexdigest()=='8ada30e9aca3c49dd1835816589435986209145b5204b256368b933c50b6ff1c'
    def funcs(raw):return {n.name:ast.dump(n) for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name!='main'}
    assert funcs(out['run_imports.py'])==funcs((HERE.parent/'native-fresh-imports/run_imports.py').read_bytes())


def test_preparation_defaults_inert_and_writes_only_exclusive_private_artifacts(tmp_path):
    m=adapter()
    with patch.object(Path,'read_bytes',side_effect=AssertionError('inert IO')),patch('builtins.print'):
        m.main([])
    out=tmp_path/'prepared';m.main(['--prepare','--output',str(out)])
    assert out.stat().st_mode&0o777==0o700
    for p in out.iterdir():assert p.stat().st_mode&0o777==0o600
    with pytest.raises(FileExistsError):m.main(['--prepare','--output',str(out)])


@pytest.mark.parametrize('failure',[None,'wrong-policy','late-process','late-proof','cancel'])
def test_generated_main_rechecks_actual_source_policy_and_fresh_custody_before_acceptance(tmp_path,failure):
    from copy import deepcopy
    from types import SimpleNamespace
    import io
    import json
    import types
    raw=adapter().build_sources()['run_imports.py']
    m=types.ModuleType('unequal_import_runtime');m.__file__=str(tmp_path/'run_imports.py')
    exec(compile(raw,m.__file__,'exec'),m.__dict__)
    policy=adapter().POLICY
    row={'pod_uid':'actual-a','intent':{'policy_hash':policy},'identity':{},'seal_id':'original',
         'journal_sha256':'original','gate_sha256':'original','limit':{'soft':5,'hard':5,'used':0}}
    before={'pods':['actual-a','actual-b'],'host':{'processes':['actual-a-start','actual-b-start'],
            'targets':[row,{**deepcopy(row),'pod_uid':'actual-b'}]}}
    if failure=='wrong-policy':before['host']['targets'][0]['intent']['policy_hash']='sha256:'+'d'*64
    after=deepcopy(before)
    if failure=='late-process':after['host']['processes'][0]='changed'
    observations=[];cleaned=[];peer_targets=[]
    def preflight(_):
        observations.append(True)
        if len(observations)==2 and failure=='late-proof':raise ValueError('fresh proof denied')
        return before if len(observations)==1 else after
    class Peer:
        def __init__(self,target,*_):peer_targets.append(target)
        def wait(self,*_):pass
        def complete(self):return ['actual reviewed peer events']
    current=SimpleNamespace(read_targets=lambda *_:{'pods':{'a':{'namespace':'qa','name':'a','cap_mib':5120},
        'b':{'namespace':'qa','name':'b','cap_mib':10240}}},preflight=preflight)
    engine=SimpleNamespace(bundle=lambda *_:b'unchanged reviewed binary stream',assess=lambda *_:{'passed':True})
    transport=SimpleNamespace(ProbeRun=Peer,abandon=lambda run:cleaned.append(run))
    result=SimpleNamespace(returncode=0,stdout=b'{"original_helper_events":true}',stderr=b'')
    argv=['--execute','--manifest','reviewed','--manifest-sha256','raw','--binary','approved',
        '--binary-sha256',m.BINARY_SHA,'--runner-sha256','raw','--output',str(tmp_path/'out')]
    with patch.object(m,'checked_bytes',return_value=b'approved'),patch.object(m,'load',side_effect=[engine,transport,current]), \
         patch.object(m.subprocess,'run',side_effect=KeyboardInterrupt if failure=='cancel' else None,return_value=result) as call, \
         patch('sys.stdout',new_callable=io.StringIO):
        if failure=='cancel':
            with pytest.raises(KeyboardInterrupt):m.main(argv)
        elif failure:
            with pytest.raises(SystemExit):m.main(argv)
        else:m.main(argv)
    assert call.call_count==(0 if failure=='wrong-policy' else 1)
    assert len(peer_targets)==(0 if failure=='wrong-policy' else 1)
    if peer_targets:assert peer_targets[0]['cap_mib']==10240
    receipt=json.loads((tmp_path/'out/receipt.json').read_text())
    assert receipt['production_qualified'] is False and receipt['cross_parent_isolation_qualified'] is False
    assert (receipt['state']=='inconclusive') is bool(failure)
    assert len(cleaned)==1


def test_generated_runner_cannot_run_five_gib_helper_on_ten_gib_side(tmp_path):
    import types
    raw=adapter().build_sources()['run_imports.py'];m=types.ModuleType('restricted_imports');m.__file__='unused'
    exec(compile(raw,'restricted','exec'),m.__dict__)
    with patch.object(m,'checked_bytes',side_effect=AssertionError('IO')):
        with pytest.raises(SystemExit):m.main(['--execute','--side','b'])


def test_source_drift_prevents_producer_dependency_execution(tmp_path,monkeypatch):
    m=adapter();original=Path.read_bytes
    def changed(path):
        if path.name=='same_parent_engine.py':return b'raise RuntimeError("unreviewed")'
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',changed)
    with pytest.raises(ValueError,match='before execution'):m.build_sources()

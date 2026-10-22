import ast,hashlib,importlib.util
from pathlib import Path
import pytest
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('prepare_mps',HERE/'prepare_mps.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def test_sources_preserve_probe_engine_mapper_and_exact_cap_transport():
 result=m.build_sources()
 for name in ('engine.py','mapper.py','mps_probe.py'):assert hashlib.sha256(result[name]).hexdigest()==m.PINS[name]
 for name,pin in [('fresh_preflight.py','8ada30e9aca3c49dd1835816589435986209145b5204b256368b933c50b6ff1c'),('run_peer_oom.py','4962c47258748f569122a4f9a51f247b94ddbfa206350d6c33ef81d3931e8b77'),('peer_probe.py','4e526355f18832da728b6fcdb9f525513c6451fc06b3ea56a57eb9795519a0b0')]:assert hashlib.sha256(result[name]).hexdigest()==pin
 old=ast.parse((HERE.parent/'native-fresh-mps/run_mps.py').read_text());new=ast.parse(result['run_mps.py'])
 for node in old.body:
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name!='main':assert ast.dump(node)==ast.dump(next(n for n in new.body if isinstance(n,type(node)) and n.name==node.name))
 runner=result['run_mps.py'].decode();assert "choices=('a',)" in runner and "['a']['cap_mib']==5120" in runner and "['b']['cap_mib']==10240" in runner
 for name,raw in result.items():compile(raw,name,'exec')
def test_missing_or_changed_source_denied(monkeypatch):
 original=m.PINS['engine.py'];monkeypatch.setitem(m.PINS,'engine.py','0'*64)
 with pytest.raises(ValueError,match='Exact original'):m.build_sources()
 assert original!='0'*64
def test_inert_does_not_read_or_write(monkeypatch,capsys):
 monkeypatch.setattr(m,'build_sources',lambda:pytest.fail('inert source I/O'));m.main([]);assert 'inert' in capsys.readouterr().out
def test_materialization_and_existing_output_denial(tmp_path):
 out=tmp_path/'prepared';m.main(['--prepare','--output',str(out)])
 assert {p.name:p.read_bytes() for p in out.iterdir()}==m.build_sources()
 with pytest.raises(FileExistsError):m.main(['--prepare','--output',str(out)])

@pytest.mark.parametrize('policy',['sha256:'+'d'*64,None])
def test_actual_generated_main_rejects_non332_sealed_intent_before_cuda(tmp_path,monkeypatch,policy):
 import json,types
 from unittest.mock import Mock
 sources=m.build_sources();out=tmp_path/'sources';out.mkdir()
 for name,raw in sources.items():(out/name).write_bytes(raw)
 spec=importlib.util.spec_from_file_location('generated_mps',out/'run_mps.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
 targets={'pods':{'a':{'cap_mib':5120},'b':{'cap_mib':10240}}}
 current=types.SimpleNamespace(read_targets=lambda *a:targets,preflight=lambda *a:{'host':{'targets':[{'intent':{'policy_hash':policy}},{'intent':{'policy_hash':policy}}]}})
 engine=types.SimpleNamespace(finish_all=lambda sessions:([],[]),Session=Mock(side_effect=AssertionError('No CUDA dispatch')))
 transport=types.SimpleNamespace(ProbeRun=Mock(side_effect=AssertionError('No peer dispatch')))
 monkeypatch.setattr(runner,'load',lambda path,raw:{'engine':engine,'fresh_preflight':current,'run_peer_oom':transport}[path.stem])
 vector=tmp_path/'mapper.json';vector.write_text(json.dumps(['ssh','host','python3','/root/mapper.py','--execute','--source-sha256',runner.MAPPER_SHA]));vector.chmod(0o600)
 with pytest.raises(SystemExit):runner.main(['--execute','--manifest','unused','--manifest-sha256','unused','--runner-sha256',hashlib.sha256(sources['run_mps.py']).hexdigest(),'--mapper-argv',str(vector),'--mapper-argv-sha256',hashlib.sha256(vector.read_bytes()).hexdigest(),'--output',str(tmp_path/'result')])
 engine.Session.assert_not_called();transport.ProbeRun.assert_not_called()
 assert json.loads((tmp_path/'result/receipt.json').read_text())['state']=='inconclusive'

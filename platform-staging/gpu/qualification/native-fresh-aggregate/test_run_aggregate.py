import importlib.util
from pathlib import Path
from unittest.mock import patch
import pytest

def module():
 s=importlib.util.spec_from_file_location('aggregate',Path(__file__).with_name('run_aggregate.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def fixture():
 def peer(case,pid):
  rows=[dict(phase='peer_tick',tick=i,pid=pid,run_id=case,monotonic_ns=i*10**9,holder_tensor_mib=2048 if case=='aggregate-peer' else 0) for i in range(1,13)]
  if case=='aggregate-peer':rows.append(dict(phase='aggregate-holder-ready',held_tensor_mib=2048,pid=pid,run_id=case))
  rows.append(dict(phase='receipt',case=case,pid=pid,run_id=case,state='measurement-completed',hardware={'gpu_uuid':module().GPU,'torch_version':'2.11.0'},peer_loop_passed=True,production_qualified=False));return rows
 oom=[dict(phase='over-allocation-error',monotonic_ns=2*10**9,typed_oom=True),dict(phase='oom-held-start',monotonic_ns=2100000000,held_tensor_mib=2048),dict(phase='oom-held-end',monotonic_ns=10100000000,held_tensor_mib=2048),dict(phase='after-recovery-free64',monotonic_ns=10500000000),dict(phase='receipt',case='aggregate-oom',state='measurement-completed',hardware={'gpu_uuid':module().GPU,'torch_version':'2.11.0'},bounded_step_sequence_passed=True,over_denied=True,ordinary_byte=19,recovery_byte=37,held_before_oom_mib=2048,over_error={'kind':'torch.OutOfMemoryError','cuda_error_code':None},production_qualified=False)]
 for x in oom:x.update(pid=303,run_id='oom')
 samples=[dict(observed_monotonic_ns=n*10**9,physical_free_bytes=8*1024**3,physical_total_bytes=40*1024**3,gpu_uuid=module().GPU)for n in (3,5,7)]
 return peer('aggregate-peer',202),oom,peer('peer',101),samples

def test_same_parent_and_other_peer_both_required():
 m=module();assert m.assess_aggregate(*fixture())['same_parent_aggregate'] is True
 assert m.roles({'pods':{'a':{'uid':'A'},'b':{'uid':'B'}}},'a-to-b')=={'ordinary':'a','holder':'b','oom':'b'}

@pytest.mark.parametrize('fault',['same-pid','missing-holder','over-budget','no-ordinary-progress','wrong-case'])
def test_denials(fault):
 m=module();holder,oom,ordinary,samples=fixture()
 if fault=='same-pid':
  for x in holder:x['pid']=303
 elif fault=='missing-holder':holder=[x for x in holder if x['phase']!='aggregate-holder-ready']
 elif fault=='over-budget':oom[-1]['held_before_oom_mib']=4096
 elif fault=='no-ordinary-progress':ordinary=[x for x in ordinary if x['phase']!='peer_tick']
 else:holder[-1]['case']='peer'
 with pytest.raises(ValueError):m.assess_aggregate(holder,oom,ordinary,samples)

def test_default_inert(capsys):
 m=module()
 with patch.object(m.subprocess,'run',side_effect=AssertionError('API')):m.main([])
 assert '"inert": true' in capsys.readouterr().out


def test_probe_is_exact_existing_reviewed_program():
 root=Path(__file__).parent
 assert (root/'peer_probe.py').read_bytes()==(root.parent/'native-fresh-domain'/'peer_probe.py').read_bytes()


def test_both_directions_keep_holder_and_oom_in_same_target():
 m=module();targets={'pods':{'a':{'uid':'A'},'b':{'uid':'B'}}}
 assert m.roles(targets,'b-to-a')=={'ordinary':'b','holder':'a','oom':'a'}
 targets['pods']['b']['uid']='A'
 with pytest.raises(ValueError):m.roles(targets,'a-to-b')


def test_actual_main_dispatches_same_parent_and_drains_all_three_on_failure(tmp_path,monkeypatch):
 m=module();runs=[]
 class Run:
  def __init__(self,target,case,*args):self.target=target;self.case=case;self.closed=False;runs.append(self)
  def wait(self,*args):
   if self.case=='aggregate-oom':raise ValueError('injected bounded overlap denial')
  def close(self):self.closed=True
 targets={'pods':{'a':{'uid':'A'},'b':{'uid':'B'}}}
 source=('def read_targets(*args):return '+repr(targets)+'\ndef preflight(config):return {}\n').encode()
 monkeypatch.setattr(m,'verified_source',lambda path,pin:source if path.name=='fresh_preflight.py' else b'reviewed')
 monkeypatch.setattr(m,'ProbeRun',Run)
 with pytest.raises(ValueError,match='overlap denial'):
  m.main(['--execute','--manifest','actual','--manifest-sha256','a'*64,'--output',str(tmp_path/'new'),'--runner-sha256','b'*64,'--probe-sha256','c'*64,'--preflight-sha256','d'*64])
 assert [(r.case,r.target['uid']) for r in runs]==[('peer','A'),('aggregate-peer','B'),('aggregate-oom','B')]
 assert len(runs)==3 and all(r.closed for r in runs)

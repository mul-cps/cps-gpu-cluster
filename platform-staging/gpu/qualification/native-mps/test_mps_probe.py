"""CPU-only tests: no NVIDIA library or GPU process is opened."""
import importlib.util,json,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
P=Path(__file__).with_name('mps_probe.py')

def module():
 spec=importlib.util.spec_from_file_location('qualified_mps_probe',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

@pytest.mark.parametrize('cap',[5120,20480])
def test_default_inert_uses_selected_bounded_cap_without_gpu_calls(cap):
 r=subprocess.run([sys.executable,str(P),'--cap-mib',str(cap)],capture_output=True,text=True,check=True)
 v=json.loads(r.stdout);assert v['state']=='inert' and v['gpu_calls'] is False and v['cap_mib']==cap and v['max_attempted_mib']==cap+256

@pytest.mark.parametrize('exited',[True,False])
def test_unreadable_same_lifetime_requires_pidfd_exit_and_closes_descriptor(exited):
 m=module();process={'pid':71,'start_ticks':99};closed=[]
 m.open_pidfd=lambda pid:8;m.identity=lambda pid:dict(process);m.os=SimpleNamespace(close=closed.append)
 m.select=SimpleNamespace(select=lambda reads,writes,errors,timeout:([8] if exited else [],[],[]))
 if exited:m.confirm_private_process_exit(process)
 else:
  with pytest.raises(PermissionError):m.confirm_private_process_exit(process)
 assert closed==[8]

def test_reused_numeric_pid_is_rejected_even_if_new_process_exited():
 m=module();closed=[];m.open_pidfd=lambda pid:8;m.identity=lambda pid:{'pid':71,'start_ticks':100};m.os=SimpleNamespace(close=closed.append)
 m.select=SimpleNamespace(select=lambda *args:([8],[],[]))
 with pytest.raises(ValueError,match='lifetime changed'):m.confirm_private_process_exit({'pid':71,'start_ticks':99})
 assert closed==[8]

def test_disappeared_process_requires_positive_exit_on_open_descriptor():
 m=module();closed=[];m.open_pidfd=lambda pid:8
 def missing(pid):raise FileNotFoundError()
 m.identity=missing;m.os=SimpleNamespace(close=closed.append);m.select=SimpleNamespace(select=lambda *args:([],[],[]))
 with pytest.raises(ValueError,match='exit proof'):m.confirm_private_process_exit({'pid':71,'start_ticks':99})
 assert closed==[8]

def test_unknown_permission_failure_is_never_treated_as_absence():
 m=module()
 class Proc:
  name='71'
  def joinpath(self,name):return self
  def read_bytes(self):raise PermissionError('cannot establish identity')
 m.Path=lambda path:SimpleNamespace(iterdir=lambda:[Proc()]) if path=='/proc' else Path(path)
 with pytest.raises(PermissionError):m.owned_processes(Path('/tmp/cps-mps-test/pipe'))

@pytest.mark.parametrize('exited',[True,False])
def test_scan_only_skips_unreadable_daemon_after_matching_exit_proof(exited):
 m=module();proof={'pid':71,'start_ticks':99};closed=[]
 class Proc:
  name='71'
  def joinpath(self,name):
   def read():
    if name=='environ':raise PermissionError('exiting daemon')
    return b'/usr/bin/nvidia-cuda-mps-server\0'
   return SimpleNamespace(read_bytes=read)
 m.Path=lambda path:SimpleNamespace(iterdir=lambda:[Proc()]) if path=='/proc' else Path(path)
 m.identity=lambda pid:dict(proof);m.open_pidfd=lambda pid:8;m.os=SimpleNamespace(close=closed.append)
 m.select=SimpleNamespace(select=lambda *args:([8] if exited else [],[],[]))
 if exited:assert m.owned_processes(Path('/tmp/cps-mps-test/pipe'))==[]
 else:
  with pytest.raises(PermissionError):m.owned_processes(Path('/tmp/cps-mps-test/pipe'))
 assert closed==[8]

@pytest.mark.parametrize('cap',[5120,20480])
def test_aggregate_exhaustion_and_both_client_recovery_remain_bounded(cap):
 m=module();m.CAP_MIB=cap;m.MAX_ATTEMPT_MIB=cap+256;m.time=SimpleNamespace(sleep=lambda _:None);held=[0,0];touched=[]
 class Client:
  def __init__(self,index):self.index=index
  def request(self,op,**values):
   if op=='allocate':
    if sum(held)+values['mib']>cap-512:return {'cuda_result':2}
    held[self.index]+=values['mib'];touched.append(sum(held));return {'cuda_result':0}
   if op=='free':held[self.index]=0
   return {'cuda_result':0}
 result=m.aggregate_sequence([Client(0),Client(1)],lambda *args:None)
 assert result['typed_oom']['cuda_result']==2 and result['recovery_clients']==2 and held==[0,0]
 assert max(touched)<=cap and result['typed_oom']['held_mib']>=cap*4//5

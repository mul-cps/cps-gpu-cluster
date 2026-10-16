"""CPU-only descriptor transport and default-inert checks."""
import array,ctypes,importlib.util,json,os,socket,struct,subprocess,sys,uuid
from pathlib import Path
import pytest
import tempfile
HERE=Path(__file__).parent

def module():
 s=importlib.util.spec_from_file_location('vmm_endpoint',HERE/'endpoint.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

@pytest.mark.parametrize('file',['endpoint.py','fd_relay.py'])
def test_inert_opens_no_cuda_or_descriptor(file):
 r=subprocess.run([sys.executable,str(HERE/file)],capture_output=True,text=True,check=True);v=json.loads(r.stdout)
 assert v['gpu_calls'] is False and (v.get('phase')=='inert' or v.get('state')=='inert')

def test_reviewed_cuda_layout():
 m=module();assert ctypes.sizeof(m.AllocationProp)==32 and ctypes.sizeof(m.AccessDesc)==12
 assert m.AllocationProp.location.offset==8 and m.AllocationProp.win32HandleMetaData.offset==16 and m.AllocationProp.allocFlags.offset==24

class Receiver:
 def __init__(self,connection,uid=1000,gid=100):self.connection=connection;self.uid=uid;self.gid=gid;self.delivered=[]
 def getsockopt(self,*args):return struct.pack('3i',71,self.uid,self.gid)
 def recvmsg(self,*args):
  value=self.connection.recvmsg(*args)
  for level,kind,data in value[1]:
   a=array.array('i');a.frombytes(data);self.delivered.extend(a)
  return value

@pytest.mark.parametrize('wrong_trial',[False,True])
def test_actual_scm_rights_descriptor_received_or_closed_on_header_rejection(wrong_trial):
 m=module();trial=str(uuid.uuid4());pod=str(uuid.uuid4());a,b=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
 holder=tempfile.TemporaryFile();fd=os.dup(holder.fileno());received=None
 try:
  os.write(fd,b'cpu-only');os.lseek(fd,0,0)
  header=dict(trial_id=str(uuid.uuid4()) if wrong_trial else trial,exporter_pod_uid=pod,bytes=m.BYTES)
  a.sendmsg([json.dumps(header).encode()],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))]);receiver=Receiver(b)
  if wrong_trial:
   with pytest.raises(ValueError):m.receive_descriptor(receiver,trial,pod)
   assert len(receiver.delivered)==1
   with pytest.raises(OSError):os.fstat(receiver.delivered[0])
  else:
   received=m.receive_descriptor(receiver,trial,pod);assert os.read(received,32)==b'cpu-only' and not os.get_inheritable(received)
 finally:
  if received is not None:os.close(received)
  os.close(fd);holder.close();a.close();b.close()

def test_foreign_sender_rejected_before_descriptor_read():
 m=module();receiver=Receiver(None,uid=0)
 with pytest.raises(ValueError,match='ordinary'):m.receive_descriptor(receiver,str(uuid.uuid4()),str(uuid.uuid4()))

def test_constructor_releases_context_when_required_vmm_symbol_is_absent(monkeypatch):
 from types import SimpleNamespace
 m=module();closed=[]
 monkeypatch.setattr(m.Native,'__init__',lambda self:setattr(self,'lib',SimpleNamespace()))
 monkeypatch.setattr(m.Native,'close',lambda self:closed.append(True))
 with pytest.raises(AttributeError):m.VmmNative()
 assert closed==[True]

"""Unchanged pure same-parent bundle/assessment from reviewed historical engine.

No old preflight, retirement allowlist or hardware result is imported.
Original engine SHA256:1fcb76aae4ab13e34cdc3e6071560abd2bbb90720ef4c7b4ea54cb8a2cb6593c.
"""
import base64
import uuid
BINARY_SHA='0e19d4ec396dd64cabe364607fee151c001821cdcb2da5e5b181d7f902a76f69'
HELPER_SHA='d8cdbf06d93a0f46e0fc122f5f547ff121d0728b7d99b55f1ca8345c574e4f6c'
GPU='GPU-16128952-b438-556a-00bb-93039ee24e56'
def require(ok,message):
    if not ok:raise ValueError(message)


def bundle(binary,helper,mode,trial):
    require(mode in ('vmm-direct','ipc','vmm') and str(uuid.UUID(trial))==trial and uuid.UUID(trial).int!=0,'Bounded import mode/trial required')
    # Only ephemeral files under fresh exact /tmp roots owned by the notebook.
    # No persistent mounts, host IPC, daemon, environment, cap or module changes.
    return (f'''import base64,contextlib,hashlib,io,json,os,signal,sys
from pathlib import Path
if os.getuid()!=1000 or os.getgid()!=100 or os.environ.get('LD_PRELOAD'):raise ValueError('UID1000/GID100 no preload required')
signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('Import watchdog')));signal.alarm(115)
binary=base64.b64decode({base64.b64encode(binary).decode()!r},validate=True)
helper=base64.b64decode({base64.b64encode(helper).decode()!r},validate=True)
if hashlib.sha256(binary).hexdigest()!={BINARY_SHA!r} or hashlib.sha256(helper).hexdigest()!={HELPER_SHA!r}:raise ValueError('Approved import artifact changed')
root=Path('/tmp/cps-import-bin-'+{trial!r});work=Path('/tmp/cps-import-work-'+{trial!r})
root.mkdir(mode=0o700);path=root/'native-imports'
with path.open('xb') as stream:stream.write(binary)
path.chmod(0o700)
class Capture(io.StringIO):
 def write(self,value):
  if self.tell()+len(value)>1000000:raise ValueError('Bounded import log required')
  return super().write(value)
output=Capture();error=None;cleaned=False
sys.argv=['trusted-same-parent','--execute','--gpu-uuid',{GPU!r},'--binary',str(path),'--directory',str(work),'--mode',{mode!r}]
try:
 with contextlib.redirect_stdout(output):exec(compile(helper,'trusted-same-parent','exec'),{{'__name__':'__main__'}})
except BaseException as caught:error=type(caught).__name__
finally:
 signal.alarm(0)
 try:
  path.unlink();root.rmdir()
  if work.exists():work.rmdir()
  cleaned=True
 except OSError:pass
packet={{'events':[json.loads(line) for line in output.getvalue().splitlines()],'stage_cleanup_confirmed':cleaned}}
if error:packet['error_type']=error
print(json.dumps(packet,sort_keys=True,allow_nan=False))
''').encode()


def assess(packet,peer,mode):
    require(isinstance(packet,dict) and packet.get('stage_cleanup_confirmed') is True and 'error_type' not in packet,'Native helper/ephemeral cleanup failed')
    events=packet.get('events',[]);found=[e for e in events if e.get('phase')=='receipt']
    require(len(found)==1 and found[0].get('state')=='bounded-same-parent-measurement-completed'
        and found[0].get('production_qualified') is False and found[0].get('cross_pod_import_isolation_qualified') is False,
        'Successful bounded same-parent measurement required')
    expected=['vmm-direct'] if mode=='vmm-direct' else [mode+'-export',mode+'-import']
    results=found[0].get('results',[])
    require([r.get('mode') for r in results]==expected and all(r.get('successful_raw_cuda_measurement') is True
        and r.get('production_qualified') is False for r in results),'Exact successful import participant results required')
    ticks=[e for e in peer if e.get('phase')=='peer_tick'];receipts=[e for e in peer if e.get('phase')=='receipt']
    require(len(receipts)==1 and receipts[0].get('case')=='peer' and receipts[0].get('state')=='measurement-completed'
        and receipts[0].get('peer_loop_passed') is True and receipts[0].get('production_qualified') is False
        and receipts[0].get('hardware',{}).get('gpu_uuid')==GPU
        and str(receipts[0].get('hardware',{}).get('torch_version','')).startswith('2.11.'),'Continuous approved peer receipt required')
    samples=[e['monotonic_ns'] for e in events if e.get('phase')=='native-event' and type(e.get('monotonic_ns')) is int]
    require(samples and len(ticks)>=2 and [e.get('tick') for e in ticks]==list(range(1,len(ticks)+1))
        and all(type(e.get('monotonic_ns')) is int for e in ticks)
        and ticks[0]['monotonic_ns']<min(samples)<=max(samples)<ticks[-1]['monotonic_ns']
        and all(0<b['monotonic_ns']-a['monotonic_ns']<=5000000000 for a,b in zip(ticks,ticks[1:])),
        'Peer kernels must continuously bracket import operations')
    return {'same_parent_measurement':True,'peer_continuity':True,'production_qualified':False,'cross_parent_isolation_qualified':False}

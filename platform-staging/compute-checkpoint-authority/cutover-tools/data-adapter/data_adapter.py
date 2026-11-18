"""Production DATA phases only. No controller CAS, observer, ACK generation or retries."""
import copy,hashlib,importlib.util,json,os,pathlib,re,signal,time
D=pathlib.Path(__file__).parent
PROTOCOL=pathlib.Path('/home/bjoern/artifacts/cps-upstream-sharing-20261116/full-platform-timing-gates-readonly-20261118/checkpoint-refresh-20261118/checkpoint_protocol.py')
PROTOCOL_SHA='ae81f0f2557c0c71b736fd1946efc5dc0a27579b438f7a5c13aaba8ec4d7a929'
STREAM=pathlib.Path('/home/bjoern/artifacts/cps-upstream-sharing-20261116/checkpoint-stream-preparation-20261118/I3')
STREAM_RUNNER_SHA='d08252f5578bddd69b01e5d69d735bdef4caa0d0a713b8e1112c6f01438c1a64'
WORKER_SHA='510ac0b16b0d70855bd0bb6891d9bacc52f604b4b14847f3e38207f7fee8dc0b'
GATE_FIELDS=('operation','rootRelease','expiresAt','bothServicesFenced','cronSuspended','allCallersQuiescent','currentCustodyClear','oldWritersStopped','liveWriterCount','sourcePVCUID','targetPVCUID','sourceNodeUID','targetNodeUID','targetEmpty')
def require(ok,message):
 if not ok:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def read_bound(path,expected):
 p=pathlib.Path(path);require(p.is_absolute()and p.is_file()and not p.is_symlink(),'Bound receipt file required');raw=p.read_bytes();require(sha(raw)==expected,'Receipt SHA changed');return json.loads(raw)
def protocol_source():
 raw=PROTOCOL.read_bytes();require(sha(raw)==PROTOCOL_SHA,'Original protocol changed');return raw.decode()
def stream_module():
 require(sha(PROTOCOL.read_bytes())==PROTOCOL_SHA,'Original protocol changed');require(sha((STREAM/'rehearse.py').read_bytes())==STREAM_RUNNER_SHA,'Reviewed stream runner changed');require(sha((STREAM/'stream_worker.py').read_bytes())==WORKER_SHA,'Reviewed stream worker changed')
 s=importlib.util.spec_from_file_location('reviewed_checkpoint_stream',STREAM/'rehearse.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def clock_check(clock,now_ns=None,boot=None):
 now_ns=time.monotonic_ns()if now_ns is None else now_ns;boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()if boot is None else boot
 require(clock['operation']=='planned-checkpoint-20261118'and clock['rootRelease'],'External clock release required');require(clock['hostBootID']==boot,'Root clock boot changed')
 start=clock['monotonicNs'];require(type(start)is int and 0<start<=now_ns,'Invalid original fence clock')
 earlier=clock.get('earlierRestrictionMonotonicNs')
 if earlier is None:require(clock.get('noEarlierRestrictionAttested')is True,'Earlier restriction not attested')
 else:require(type(earlier)is int and 0<earlier<=start,'Invalid earlier restriction');start=earlier
 elapsed=(now_ns-start)/1e9;require(elapsed<60,'Original cutover clock exceeded60s; reconcile, never reset clock');return elapsed

class DataAdapter:
 def __init__(self,inputs,transport=None):
  require(isinstance(inputs.get('rootRelease'),str)and inputs['rootRelease'],'UNARMED data release')
  require(re.fullmatch(r'production-checkpoint-[0-9a-f]{12}',inputs.get('caseID','')),'Fresh production case ID')
  require(inputs.get('manifestSHA256')==sha((D/'manifest.safe.json').read_bytes()),'Reviewed adapter manifest mismatch')
  for n,r in json.loads((D/'manifest.safe.json').read_text())['files'].items():require(sha((D/n).read_bytes())==r['sha256'],'Reviewed adapter payload changed')
  self.x=copy.deepcopy(inputs);self.stream=stream_module();self.transport=transport or NativeTransport(self.stream);self.d=pathlib.Path(inputs['caseDirectory']);require(self.d.is_absolute(),'Absolute adapter case directory');self.d.mkdir(mode=0o700);self._sync(self.d.parent)
  self._save('release.private.json',inputs);self.done={};self.target_may_be_written=False
  self.source='/work/'+inputs['caseID']+'-snapshot';self.received='/work/'+inputs['caseID']+'-received'
  require(re.fullmatch(r'/work/[A-Za-z0-9_.-]+\.py',inputs.get('workerScriptPath','')),'Existing exact staged worker required')
 def _sync(self,path):
  fd=os.open(path,os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
 def _save(self,name,data):
  fd=os.open(self.d/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'w')as f:json.dump(data,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
  self._sync(self.d)
 def _gate(self,proof_path,proof_sha):
  x=self.x;gate=read_bound(x['protocolGatePath'],x['protocolGateSHA256']);clock=read_bound(x['clockReceiptPath'],x['clockReceiptSHA256']);proof=read_bound(proof_path,proof_sha)
  require(not proof.get('offlineUnitOnly'),'Offline fixture proof forbidden for production')
  require(proof['gate']=='old-writers-stopped'and proof['passed']is True,'External genuine stopped-writer proof required')
  require(proof['clockReceiptSHA256']==x['clockReceiptSHA256'],'Proof clock differs');require(proof['operation']==clock['operation']==gate['operation']and proof['rootRelease']==clock['rootRelease']==gate['rootRelease']==self.x['rootRelease'],'Proof operation/release differs')
  for field in GATE_FIELDS:require(proof[field]==gate[field],'Stopped proof/native gate differs: '+field)
  require(gate['oldWritersStopped']==x['expectedOldWritersStopped'],'Old UID/CIDs differ from released preimage')
  for field in ['sourcePVCUID','targetPVCUID','sourceNodeUID','targetNodeUID']:require(gate[field]==x[field],'Released storage identity differs')
  now=time.time();require(type(proof['checkedAt'])in[int,float]and -2<=now-proof['checkedAt']<=10,'Stopped proof not fresh within10s')
  require(proof['expiresAt']>now,'Stopped proof expired');elapsed=clock_check(clock)
  ns={'__name__':'reviewed_gate_only'};exec(protocol_source(),ns);ns['gate'](gate)
  return gate,{'clockElapsedSeconds':elapsed,'stoppedProofSHA256':proof_sha,'clockReceiptSHA256':x['clockReceiptSHA256']}
 def _once(self,phase,proof_path,proof_sha,operation,target_write=False):
  require(not(self.d/(phase+'-intent.private.json')).exists(),'Prior phase intent: reconcile, never retry')
  gate,evidence=self._gate(proof_path,proof_sha);self.transport.guard(self.x);gate,evidence=self._gate(proof_path,proof_sha)
  self._save(phase+'-intent.private.json',{'state':'UNKNOWN','phase':phase,'time':time.time(),'monotonicNs':time.monotonic_ns(),'targetMayHaveBeenWritten':self.target_may_be_written or target_write,**evidence})
  if target_write:self.target_may_be_written=True
  try:
   result=operation(gate);self._checked_result(phase,gate,result);self.done[phase]=result;self._save(phase+'-reply.private.json',{'state':'REPLIED','result':result,'targetMayHaveBeenWritten':self.target_may_be_written,'time':time.time()});return result
  except BaseException as e:
   self._save(phase+'-HOLD.safe.json',{'state':'HOLD_UNKNOWN_RECONCILE_NO_RETRY','errorType':type(e).__name__,'targetMayHaveBeenWritten':self.target_may_be_written,'noControllerActionPermittedByThisReceipt':True});raise
 def _checked_result(self,phase,gate,result):
  require(isinstance(result,dict)and not result.get('offlineUnitOnly'),'Native result required')
  if phase=='snapshot':
   ns={'__name__':'reviewed_receipt_validation'};exec(protocol_source(),ns)
   require(result.get('receiptSHA256')==ns['digest'](ns['encode']({k:v for k,v in result.items()if k!='receiptSHA256'})),'Native snapshot receipt digest differs')
   require(result.get('gateSHA256')==ns['digest'](ns['encode'](gate)),'Native snapshot gate digest differs')
   require(result.get('sourcePVCUID')==self.x['sourcePVCUID']and result.get('targetPVCUID')==self.x['targetPVCUID'],'Snapshot storage identities differ')
   require(set(result.get('databases',{}))==set(ns['DATABASES']),'Native snapshot requires all4DB proofs')
   protected=read_bound(self.x['protectedInputsPath'],self.x['protectedInputsSHA256'])
   require(len(result.get('protected',[]))==len(protected)==13 and {p['path']:p['sha256']for p in result['protected']}=={p['path']:p['sha256']for p in protected},'Native snapshot13 protected proofs differ')
  elif phase=='install':
   require(all(result.get(k)is True for k in ['installed','all4LogicalExact','allDataFilesExact','noAuthorityProcessStarted']),'Native install did not fully pass')
   require(result.get('receiptSHA256')==self.done['snapshot']['receiptSHA256']and result.get('targetPVCUID')==self.x['targetPVCUID'],'Native install receipt or storage differs')
 def _code(self,action,gate):
  # Native original30s action budget, unchanged protocol/gates. Root clock is
  # independently checked before dispatch; helper wall-clock skew is bounded.
  prefix="import os,time,signal,pathlib,json;os.environ['TMPDIR']='/work'\nsignal.signal(signal.SIGALRM,lambda *a:(_ for _ in()).throw(TimeoutError('Original30s protocol action limit')));signal.alarm(30)\nassert abs(time.time()-"+repr(time.time())+")<=5,'Helper clock/dispatch skew'\nns={'__name__':'reviewed_production_protocol'}\nexec("+repr(protocol_source())+",ns)\ng="+repr(gate)+"\nns['gate'](g)\n"
  if action=='snapshot':
   protected=read_bound(self.x['protectedInputsPath'],self.x['protectedInputsSHA256']);require(isinstance(protected,list)and len(protected)==13,'Exactly13 released protected inputs required')
   return prefix+"print(json.dumps(ns['snapshot'](pathlib.Path('/source'),pathlib.Path("+repr(self.source)+"),g,"+repr(protected)+")))"
  require(action=='install','Unknown data phase');receipt=self.done['snapshot']['receiptSHA256']
  return prefix+"print(json.dumps(ns['install'](pathlib.Path("+repr(self.received)+"),pathlib.Path('/target'),g,"+repr(receipt)+")))"
 def snapshot(self,proof_path,proof_sha):
  require(not self.done,'Snapshot must be first')
  return self._once('snapshot',proof_path,proof_sha,lambda g:self.transport.rpc(self.d,'snapshot',self.stream.SOURCE,self._code('snapshot',g)))
 def transfer(self,proof_path,proof_sha):
  require('snapshot'in self.done and'install'not in self.done,'Snapshot reply required before transport')
  def operation(g):
   w=self.x['workerScriptPath'];producer=self.stream.cmd(self.stream.SOURCE,self.stream.load_worker_code(w,WORKER_SHA,'produce',self.source));extractor=self.stream.cmd(self.stream.TARGET,self.stream.load_worker_code(w,WORKER_SHA,'extract',self.received));return self.transport.relay(self.d,producer,extractor)
  return self._once('transfer',proof_path,proof_sha,operation)
 def install(self,proof_path,proof_sha):
  require('snapshot'in self.done and'transfer'in self.done,'Snapshot+transfer replies required before install')
  return self._once('install',proof_path,proof_sha,lambda g:self.transport.rpc(self.d,'install',self.stream.TARGET,self._code('install',g)),target_write=True)

class NativeTransport:
 def __init__(self,stream):self.stream=stream
 def guard(self,inputs):self.stream.guard(inputs)
 def rpc(self,d,phase,pod,code):
  # STDIN avoids exec URL limit; stdout/stderr never mixed with archive bytes.
  import subprocess
  out=d/(phase+'-stdout.private.txt');err=d/(phase+'-stderr.private.txt')
  with out.open('xb')as stdout,err.open('xb')as stderr:
   os.chmod(out,0o600);os.chmod(err,0o600);r=subprocess.run(self.stream.stdin_cmd(pod),input=code.encode(),stdout=stdout,stderr=stderr,timeout=35)
  require(r.returncode==0,'Remote data phase failed/unknown; reconcile, never retry');return json.loads(out.read_text())
 def relay(self,d,producer,extractor):return self.stream.relay(d,producer,extractor)

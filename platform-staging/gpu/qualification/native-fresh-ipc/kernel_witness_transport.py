"""Bounded local JSONL transport for the fixed protected Root marker helper."""
import hashlib,importlib.util,json,os,select,subprocess,threading,time
from pathlib import Path

ROOT='/var/lib/cps-native-gpu/qualification/1f7d941a-872d-4453-a1ba-fd489d8aff14/cohorts/6ba3353d-bf13-4cad-9c35-3119dd279a67/ipc-kmsg-witness'
def require(ok,message):
 if not ok:raise ValueError(message)
class KernelWitness:
 def __init__(self,argv,output,*,collector_sha256,validator_sha256):
  parent=Path(__file__).parent
  require(hashlib.sha256((parent/'kernel_witness_collector.py').read_bytes()).hexdigest()==collector_sha256
   and hashlib.sha256((parent/'kernel_witness_validator.py').read_bytes()).hexdigest()==validator_sha256,
   'Separately reviewed local collector/validator source pins required')
  spec=importlib.util.spec_from_file_location('ipc_sequence_validator',parent/'kernel_witness_validator.py')
  self.v=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.v)
  self.collector_sha256=collector_sha256;self.validator_sha256=validator_sha256
  self.events=[];self.error=None;self.condition=threading.Condition();self.attribution=None;self.completed=False;self.closed=False
  self.process=None;self.reader=None
  self.log=open(output/'kernel-witness.jsonl','xb');os.chmod(self.log.name,0o600)
  self.stderr=open(output/'kernel-witness.stderr','xb');os.chmod(self.stderr.name,0o600)
  try:
   self.process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr)
   def read():
    total=0
    try:
     while True:
      line=self.process.stdout.readline(1048577)
      if not line:break
      total+=len(line);require(len(line)<=1048576 and line.endswith(b'\n')and total<=2097152,'Bounded whole Root witness messages required')
      value=self.v.parse_json(line);require(isinstance(value,dict),'Typed Root witness event required')
      self.log.write(line);self.log.flush();os.fsync(self.log.fileno())
      with self.condition:self.events.append(value);self.condition.notify_all()
    except BaseException as error:self.error=type(error).__name__
    finally:
     with self.condition:self.condition.notify_all()
   self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
   ready=self.wait('witness-ready',15);self.v.canonical_uuid(ready.get('nonce'))
   require(set(ready)=={'phase','nonce','boot_id','driver_generation','collector_sha256','validator_sha256'}
    and ready['boot_id']==self.v.BOOT and ready['driver_generation']==self.v.GENERATION
    and ready['collector_sha256']==collector_sha256 and ready['validator_sha256']==validator_sha256,'Actual pinned Root witness session required')
   self.nonce=ready['nonce']
  except BaseException:
   self.close();raise
 def wait(self,phase,timeout):
  deadline=time.monotonic()+timeout
  with self.condition:
   while True:
    values=[v for v in self.events if v.get('phase')==phase]
    if values:require(len(values)==1 and not self.error,'Unique successful Root phase required');return values[0]
    require(not self.error and time.monotonic()<deadline,'Root witness phase failed or timed out')
    require(self.process.poll()is None or self.reader.is_alive(),'Root witness exited before phase')
    self.condition.wait(0.05)
 def send(self,value):
  raw=self.v.canonical(value)+b'\n';require(len(raw)<=65536,'Bounded Root command required')
  fd=self.process.stdin.fileno();os.set_blocking(fd,False);offset=0;deadline=time.monotonic()+5
  while offset<len(raw):
   require(time.monotonic()<deadline and self.process.poll()is None,'Root command transfer failed')
   if not select.select([],[fd],[],max(0,deadline-time.monotonic()))[1]:raise TimeoutError('Root command stalled')
   try:offset+=os.write(fd,raw[offset:])
   except BlockingIOError:continue
 def begin(self,attribution):
  require(self.attribution is None and not self.closed,'One fresh Root begin required')
  self.attribution=attribution;self.send({'op':'begin','trial_id':attribution['trial_id'],'nonce':self.nonce,'attribution':attribution})
  response=self.wait('witness-begin',10)
  require(response=={'phase':'witness-begin','trial_id':attribution['trial_id'],'nonce':self.nonce},'Actual begin marker acknowledgement required')
 def end(self,api_result):
  require(self.attribution is not None and not self.completed and not self.closed,'One exact current Root end required')
  self.send({'op':'end','trial_id':self.attribution['trial_id'],'nonce':self.nonce,'api_result':api_result})
  response=self.wait('witness-completed',15)
  require(set(response)=={'phase','trial_id','nonce','capture','correlation','root_capture_path','root_capture_raw_sha256'}
   and response['trial_id']==self.attribution['trial_id'] and response['nonce']==self.nonce,'Exact Root capture reply required')
  capture=response['capture'];result=self.v.validate_capture(capture,self.attribution,api_result,
   collector_sha256=self.collector_sha256,validator_sha256=self.validator_sha256)
  require(response['correlation']==result and response['root_capture_path']==ROOT+'/sessions/'+self.attribution['trial_id']+'/capture.json'
   and response['root_capture_raw_sha256']=='sha256:'+hashlib.sha256(self.v.canonical(capture)+b'\n').hexdigest(),'Actual protected Root archive reference required')
  require(self.process.wait(timeout=5)==0,'Root witness helper did not exit successfully')
  self.completed=True;self.close();return capture,result
 def close(self):
  if self.closed:return
  self.closed=True;errors=[]
  if self.process is not None:
   try:self.process.stdin.close()
   except BaseException as e:errors.append(type(e).__name__)
   try:self.process.wait(timeout=5)
   except BaseException as e:
    errors.append(type(e).__name__)
    try:self.process.kill();self.process.wait(timeout=3)
    except BaseException as e:errors.append(type(e).__name__)
   if self.reader is not None:
    self.reader.join(timeout=3)
    if self.reader.is_alive():errors.append('reader not reaped')
   try:self.process.stdout.close()
   except BaseException as e:errors.append(type(e).__name__)
  for stream in (self.log,self.stderr):
   try:stream.close()
   except BaseException as e:errors.append(type(e).__name__)
  require(not errors and not self.error and (not self.completed or self.process.returncode==0),'Root transport cleanup unresolved')

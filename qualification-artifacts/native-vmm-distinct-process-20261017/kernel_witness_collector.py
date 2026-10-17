#!/usr/bin/env python3
"""Root-only, qualification-only kmsg markers. Default inert; no GPU/cap/SQL calls."""
import argparse,base64,hashlib,json,os,select,socket,stat,sys,time,types,uuid
from pathlib import Path

ROOT=Path('/run/cps-native-gpu/operator/vmm-kmsg-witness')
COLLECTOR=ROOT/'kernel_witness_collector.py'
VALIDATOR=ROOT/'kernel_witness_validator.py'
BOOT='209f8bc9-a478-48e4-925a-6e07ffa56f7a'
GENERATION='b10498fc-9153-4394-875a-ea7cfb498625'

def require(ok,message):
 if not ok:raise ValueError(message)
def clocks():
 return {'monotonic_ns':time.monotonic_ns(),'monotonic_raw_ns':time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW),
         'boottime_ns':time.clock_gettime_ns(time.CLOCK_BOOTTIME),'realtime_ns':time.time_ns()}
def directory(path):
 info=Path(path).lstat();require(stat.S_ISDIR(info.st_mode) and info.st_uid==info.st_gid==0
  and stat.S_IMODE(info.st_mode)==0o700,'Protected Root700 directory required')
def protected(path,digest):
 directory(Path(path).parent)
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  a=os.fstat(fd);raw=os.read(fd,131073);b=os.fstat(fd)
  require(stat.S_ISREG(a.st_mode) and a.st_uid==a.st_gid==0 and a.st_nlink==1 and stat.S_IMODE(a.st_mode)==0o400
   and len(raw)<=131072 and all(getattr(a,k)==getattr(b,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
   and hashlib.sha256(raw).hexdigest()==digest,'Exact protected Root400 source required')
  return raw
 finally:os.close(fd)
def store(path,value):
 raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
 with os.fdopen(fd,'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
 parent=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(parent)
 finally:os.close(parent)
 return 'sha256:'+hashlib.sha256(raw).hexdigest()
def emit(value):
 raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
 require(len(raw)<=1048576,'Bounded Root reply required')
 deadline=time.monotonic()+5;offset=0;os.set_blocking(1,False)
 while offset<len(raw):
  require(time.monotonic()<deadline,'Root reply deadline exceeded')
  if not select.select([],[1],[],max(0,deadline-time.monotonic()))[1]:raise TimeoutError('Root reply stalled')
  try:offset+=os.write(1,raw[offset:])
  except BlockingIOError:continue
def receive(v,deadline):
 raw=bytearray();os.set_blocking(0,False)
 while not raw.endswith(b'\n'):
  require(time.monotonic()<deadline,'Root command deadline exceeded')
  if not select.select([0],[],[],max(0,deadline-time.monotonic()))[0]:raise TimeoutError('Root command stalled')
  try:part=os.read(0,65537-len(raw))
  except BlockingIOError:continue
  require(part and len(raw)+len(part)<=65536,'Complete bounded Root command required');raw.extend(part)
 require(raw.count(b'\n')==1,'One Root command per RPC required')
 return v.parse_json(raw)

class KernelStream:
 def __init__(self,fd,save):self.fd=fd;self.save=save;self.last=None;self.records=[];self.size=0
 def until(self,message,deadline):
  while True:
   if time.monotonic()>=deadline:raise TimeoutError('Kernel marker deadline exceeded')
   if not select.select([self.fd],[],[],max(0,deadline-time.monotonic()))[0]:continue
   try:raw=os.read(self.fd,65536)
   except BlockingIOError:continue
   require(raw and len(raw)<=65536 and raw.endswith(b'\n'),'Complete bounded kernel read required')
   first=raw.decode('utf-8',errors='strict').splitlines()[0];header,sep,text=first.partition(';');parts=header.split(',')
   require(sep and len(parts)>=4 and all(p.isdecimal()for p in parts[:3]),'Typed kernel record required')
   record={'priority':int(parts[0]),'sequence':int(parts[1]),'timestamp_us':int(parts[2]),'flags':parts[3],'message':text}
   require(self.last is None or record['sequence']==self.last+1,'Kernel ring gap/reorder detected')
   self.last=record['sequence'];self.size+=len(raw)
   require(self.size<=262144 and len(self.records)<4096,'Kernel stream exceeded bound')
   self.records.append(base64.b64encode(raw).decode());self.save(raw)
   if text==message:return record

def actual_identity(a):
 pid=a['host_tgid'];path=Path('/proc')/str(pid)
 def ticks():return int((path/'stat').read_text().rsplit(')',1)[1].split()[19])
 before=ticks();values=dict(line.split(':',1)for line in (path/'status').read_text().splitlines()if ':'in line)
 require(before==a['pid_start_ticks'] and values['Tgid'].strip()==str(pid)
  and values['Uid'].split()==['1000']*4 and values['Gid'].split()==['100']*4
  and list(map(int,values['NSpid'].split()))==a['nspid'],'Actual attributed ordinary-user process required')
 require((path/'cgroup').read_text().strip()=='0::'+a['process_cgroup_relative']
  and (Path('/sys/fs/cgroup')/a['process_cgroup_relative'].lstrip('/')).parent.stat().st_ino==a['pod_cgroup_inode'],
  'Actual sealed Pod parent required')
 require(hashlib.sha256((path/'cmdline').read_bytes()).hexdigest()==a['cmdline_sha256']
  and (path/'ns/pid').stat().st_ino==a['pid_namespace_inode'] and ticks()==before,'Attributed process replaced')
 require((path/'ns/time').stat().st_ino==Path('/proc/self/ns/time').stat().st_ino,'Root and importer must share monotonic time namespace')
def kmsg(flags):
 fd=os.open('/dev/kmsg',flags|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  info=os.fstat(fd)
  require(stat.S_ISCHR(info.st_mode) and info.st_uid==0 and (os.major(info.st_rdev),os.minor(info.st_rdev))==(1,11),'Actual host kmsg character device required')
  return fd
 except BaseException:os.close(fd);raise
def end_identity(a,pidfd):
 if select.select([pidfd],[],[],0)[0]:
  # A positively exited original process can be absent or still a zombie.
  # A replaced numeric PID is always rejected; the pidfd remains lifetime-bound.
  try:
   ticks=int((Path('/proc')/str(a['host_tgid'])/'stat').read_text().rsplit(')',1)[1].split()[19])
   require(ticks==a['pid_start_ticks'],'Numeric importer PID replaced after original exit')
  except FileNotFoundError:pass
 else:actual_identity(a)

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--qualification',action='store_true')
 p.add_argument('--source-sha256');p.add_argument('--validator-sha256');args=p.parse_args(argv)
 own=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 if not args.execute:
  print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False,'host_writes':False,'source_sha256':own}));return
 require(args.qualification and args.source_sha256==own and isinstance(args.validator_sha256,str)
  and len(args.validator_sha256)==64 and os.getuid()==os.geteuid()==os.getgid()==os.getegid()==0,'Pinned explicit Root qualification execution required')
 require(Path(__file__).resolve()==COLLECTOR and socket.gethostname()=='k3s-wk-gpu2'
  and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'Exact protected source/host/boot required')
 protected(COLLECTOR,args.source_sha256);raw=protected(VALIDATOR,args.validator_sha256)
 v=types.ModuleType('protected_witness_validator');exec(compile(raw,str(VALIDATOR),'exec'),v.__dict__)
 directory(ROOT/'sessions');nonce=str(uuid.uuid4());fd=wfd=pidfd=None;session=None;rawlog=None
 try:
  fd=kmsg(os.O_RDONLY);os.lseek(fd,0,os.SEEK_END)
  emit({'phase':'witness-ready','nonce':nonce,'boot_id':BOOT,'driver_generation':GENERATION,
        'collector_sha256':own,'validator_sha256':args.validator_sha256})
  request=receive(v,time.monotonic()+20)
  require(set(request)=={'op','trial_id','nonce','attribution'} and request['op']=='begin' and request['nonce']==nonce,'Closed begin command required')
  trial=request['trial_id'];v.canonical_uuid(trial);a=request['attribution']
  require(a['trial_id']==trial and a['boot_id']==BOOT and a['driver_generation']==GENERATION and a['gpu_uuid']==v.GPU,'Exact current Root attribution required')
  session=ROOT/'sessions'/trial;session.mkdir(mode=0o700);directory(session)
  parent=os.open(session.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  try:os.fsync(parent)
  finally:os.close(parent)
  store(session/'attribution.json',a)
  pidfd=os.pidfd_open(a['host_tgid'],0);actual_identity(a)
  rawlog=open(session/'raw-kmsg.jsonl','xb');os.chmod(rawlog.name,0o400)
  def save(raw):
   rawlog.write(base64.b64encode(raw)+b'\n');rawlog.flush();os.fsync(rawlog.fileno())
  stream=KernelStream(fd,save);wfd=kmsg(os.O_WRONLY)
  markers={}
  begin=v.marker_message(trial,nonce,'begin',a);markers['begin']={'clock_before':clocks()}
  payload=('<14>'+begin+'\n').encode();require(os.write(wfd,payload)==len(payload),'Whole begin marker write required')
  markers['begin']['clock_after']=clocks();stream.until(begin,time.monotonic()+5)
  emit({'phase':'witness-begin','trial_id':trial,'nonce':nonce})
  deadline=markers['begin']['clock_before']['monotonic_ns']/1e9+30
  end=receive(v,deadline)
  require(set(end)=={'op','trial_id','nonce','api_result'} and end['op']=='end' and end['trial_id']==trial and end['nonce']==nonce,'Closed end command required')
  end_identity(a,pidfd)
  message=v.marker_message(trial,nonce,'end',a);markers['end']={'clock_before':clocks()}
  payload=('<14>'+message+'\n').encode();require(os.write(wfd,payload)==len(payload),'Whole end marker write required')
  markers['end']['clock_after']=clocks();stream.until(message,min(deadline,time.monotonic()+5))
  require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'Boot changed during capture')
  capture={'version':1,'kind':'root-kernel-vmm-sequence-witness','trial_id':trial,'nonce':nonce,
   'node':v.NODE,'node_uid':v.NODE_UID,'boot_id':BOOT,'driver_generation':GENERATION,
   'collector_sha256':own,'validator_sha256':args.validator_sha256,'attribution_sha256':v.sha(a),
   'api_result_sha256':v.sha(end['api_result']),'overruns':0,'truncated':False,'same_time_namespace':True,
   'identity_verified':True,'markers':markers,'records_b64':stream.records}
  result=v.validate_capture(capture,a,end['api_result'],collector_sha256=own,validator_sha256=args.validator_sha256)
  store(session/'api-result.json',end['api_result']);file_sha=store(session/'capture.json',capture);store(session/'correlation.json',result)
  emit({'phase':'witness-completed','trial_id':trial,'nonce':nonce,'capture':capture,'correlation':result,
   'root_capture_path':str(session/'capture.json'),'root_capture_raw_sha256':file_sha})
 except BaseException as error:
  if session is not None:store(session/'error.json',{'error_type':type(error).__name__,'message':str(error),'complete':False})
  raise
 finally:
  if rawlog is not None:rawlog.close()
  for handle in (fd,wfd,pidfd):
   if handle is not None:os.close(handle)

if __name__=='__main__':main()

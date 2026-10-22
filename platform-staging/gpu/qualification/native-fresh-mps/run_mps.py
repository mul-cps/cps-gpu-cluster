#!/usr/bin/env python3
"""Default-inert fresh147 MPS OOM, opposite-Pod peer and Root process attribution."""
import argparse,hashlib,json,os,re,signal,stat,subprocess,time,traceback,types,uuid
from pathlib import Path

PROBE_SHA='a235f486239056bedf2afd6e48536c5024da5efa62340a6e7d3545dd0a1b4a8e'
CONTROL_SHA='7e91a303b67382a1377f63a4c862605a27e40ac590e91c431fe547308fb71868'
SERVER_SHA='1d49ca38a96799699118331f0c76a3fd7a76cafc25dbfc0c4d904a98d4e77176'
PREFLIGHT_SHA='07137f623f1a0c383597c90fbf485f4ea95597a553b433ffc388dcedcbd70d58'
PEER_RUNNER_SHA='1e8a0d398672842bd124a3bbe3fbde50817b76c5394714dfbd374695d220653a'
PEER_SHA='ea49812f2f68371a27f63e709534f08aa1b23028395c4b76b2efc07b88d86834'
ENGINE_SHA='a2dd364c6650336cbe2902f792bac625cbcbf074bb7971d38bcd9bd8027029df'
MAPPER_SHA='35b968c0d3291dc9d6b020c86a9ea0223662cb30a1211217f7e547374713273b'
GPU='GPU-16128952-b438-556a-00bb-93039ee24e56'
GENERATION='4ebffc96-e25e-4583-a3b8-0d853fd90efd'

def require(v,m):
 if not v:raise ValueError(m)

def checked(path,pin):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  a=os.fstat(fd);raw=os.read(fd,1048577);b=os.fstat(fd)
  require(stat.S_ISREG(a.st_mode) and a.st_uid==os.getuid() and a.st_nlink==1 and not a.st_mode&0o022
   and 0<len(raw)<=1048576 and all(getattr(a,k)==getattr(b,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
   and hashlib.sha256(raw).hexdigest()==pin,'Exact stable reviewed source/input required')
  return raw
 finally:os.close(fd)

def load(path,raw):
 m=types.ModuleType(path.stem);m.__file__=str(path);exec(compile(raw,str(path),'exec'),m.__dict__);return m

def write(path,value):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as f:json.dump(value,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def error_evidence(error,stage):
 require(stage in {'preflight','peer-start','mps-start','live-map','finish','assess','clean-map','postflight'},'Closed diagnostic stage required')
 return {'stage':stage,'type':type(error).__name__,'message':str(error)[:1024],
  'frames':[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno}
   for f in traceback.extract_tb(error.__traceback__,limit=8)]}

def unchanged(a,b,*,clean=False):
 require(a['pods']==b['pods'] and a['host']['processes']==b['host']['processes'],'Actual notebook lifetime changed')
 require(len(a['host']['targets'])==len(b['host']['targets'])==2,'Two original sealed targets required')
 for old,new in zip(a['host']['targets'],b['host']['targets']):
  require({k:v for k,v in old.items() if k!='limit'}=={k:v for k,v in new.items() if k!='limit'},'Actual authority/seal changed')
  require(old['limit']['soft']==new['limit']['soft'] and old['limit']['hard']==new['limit']['hard'],'Actual native cap changed')
  if clean:require(new['limit']['used']<=old['limit']['used'],'MPS charge not recovered')

def mapper_vector(raw):
 argv=json.loads(raw)
 require(type(argv) is list and 3<=len(argv)<=128 and all(type(x) is str and 0<len(x)<=4096
  and not any(c in x for c in '\x00\r\n') for x in argv) and Path(argv[0]).name in ('ssh','kubectl')
  and '--execute' in argv and '--source-sha256' in argv and MAPPER_SHA in argv
  and any(Path(x).name=='mapper.py' for x in argv),'Independently reviewed exact Root mapper argv required')
 return argv

def attribute(current,engine,targets,before,index,registered,started,trial,argv,*,original=None,diagnostics=None):
 pre=current.preflight({'manifest':targets});unchanged(before,pre)
 identity=before['host']['targets'][index]['identity']
 request={'identity':identity,'trial_id':trial,'pipe':started['pipe'],
  'probe_path':'/tmp/cps-mps-wrapper-'+trial+'/mps_probe.py',
  'processes':engine.registration_processes(registered),'mode':'cleaned' if original is not None else 'live','original':original or []}
 reply=subprocess.run(argv,input=json.dumps(request).encode(),capture_output=True,timeout=25)
 if reply.returncode!=0 and diagnostics is not None:
  write(diagnostics,{'returncode':reply.returncode,'stdout':reply.stdout[:65536].decode('utf-8',errors='replace'),
   'stderr':reply.stderr[:65536].decode('utf-8',errors='replace')})
 require(reply.returncode==0 and len(reply.stdout)<=1048576,'Actual bounded Root MPS mapping failed')
 actual=json.loads(reply.stdout)
 require(actual.get('kind')=='root-mps-process-attribution' and actual.get('mode')==request['mode']
  and actual.get('trial_id')==trial and actual.get('pod_uid')==identity['pod_uid']
  and actual.get('driver_generation')==GENERATION and type(actual.get('observed_time_ns')) is int
  and 0<=time.time_ns()-actual['observed_time_ns']<=30000000000,'Fresh exact Root mapper receipt required')
 processes=actual.get('processes');require(type(processes) is list and len(processes)==(0 if original is not None else 4),'Exact live/cleaned process roles required')
 if original is None:
  expected={p['role']:p for p in request['processes']}
  require({p.get('role') for p in processes}==set(expected),'Exact four Root process roles required')
  for p in processes:
   row=expected[p['role']];relative=identity['cgroup_relative']
   require(set(p)=={'role','host_pid','host_tgid','pid_start_ticks','namespace_pid','pid_namespace_inode','process_cgroup_relative','pod_cgroup_inode','cmdline_sha256'}
    and all(type(p.get(k)) is int and p[k]>0 for k in ('host_pid','host_tgid','pid_start_ticks','namespace_pid','pid_namespace_inode','pod_cgroup_inode'))
    and p['host_pid']==p['host_tgid'] and p['namespace_pid']==row['namespace_pid']
    and p['pid_start_ticks']==row['start_ticks'] and p['pod_cgroup_inode']==identity['cgroup_inode']
    and (p['process_cgroup_relative']==relative or p['process_cgroup_relative'].startswith(relative+'/'))
    and re.fullmatch('[a-f0-9]{64}',p['cmdline_sha256']),'Exact Root PID/start/cgroup/argv proof required')
  require(len({p['host_tgid'] for p in processes})==4 and len({p['pid_namespace_inode'] for p in processes})==1,'Distinct same-namespace processes required')
 post=current.preflight({'manifest':targets});unchanged(before,post)
 return {'mapping':actual,'before':pre,'after':post}

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
 for key in ('manifest','manifest-sha256','runner-sha256','mapper-argv','mapper-argv-sha256'):p.add_argument('--'+key)
 p.add_argument('--side',choices=('a','b'),default='a');p.add_argument('--output',type=Path);a=p.parse_args(argv)
 if not a.execute:print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False,'production_qualified':False}));return
 require(all((a.manifest,a.manifest_sha256,a.runner_sha256,a.mapper_argv,a.mapper_argv_sha256,a.output)),'Exact actual manifest/source/Root mapper argv/output required')
 here=Path(__file__).resolve().parent;common=here.parent/'native-fresh-domain'
 checked(Path(__file__),a.runner_sha256)
 raw={name:checked(here/name,pin) for name,pin in (('engine.py',ENGINE_SHA),('mapper.py',MAPPER_SHA),('mps_probe.py',PROBE_SHA))}
 current_raw=checked(common/'fresh_preflight.py',PREFLIGHT_SHA);transport_raw=checked(common/'run_peer_oom.py',PEER_RUNNER_SHA);peer_source=checked(common/'peer_probe.py',PEER_SHA)
 vector=mapper_vector(checked(a.mapper_argv,a.mapper_argv_sha256))
 engine=load(here/'engine.py',raw['engine.py']);current=load(common/'fresh_preflight.py',current_raw);transport=load(common/'run_peer_oom.py',transport_raw)
 targets=current.read_targets(a.manifest,a.manifest_sha256);a.output.mkdir(mode=0o700)
 sessions=[];registered=started=live=before=None;failure=None;values=[]
 receipt={'state':'inconclusive','production_qualified':False,'manifest_sha256':a.manifest_sha256,'mapper_sha256':MAPPER_SHA,'probe_sha256':PROBE_SHA,'engine_sha256':ENGINE_SHA,'mapper_argv_sha256':a.mapper_argv_sha256,'side':a.side}
 trial=str(uuid.uuid4());index=0 if a.side=='a' else 1
 def cancelled(*_):raise InterruptedError('Operator cancelled; cleanup required')
 previous={s:signal.signal(s,cancelled) for s in (signal.SIGINT,signal.SIGTERM)}
 stage='preflight'
 try:
  try:
   before=current.preflight({'manifest':targets});write(a.output/'before.json',before)
   stage='peer-start'
   peer=transport.ProbeRun(targets['pods']['b' if a.side=='a' else 'a'],'peer',145,peer_source,a.output);peer.finish=peer.complete;sessions.append(peer)
   peer.wait(lambda events:any(e.get('phase')=='peer_tick' for e in events),20)
   args=['--execute','--case','oom','--duration','120','--source-sha256',PROBE_SHA,'--control-sha256',CONTROL_SHA,'--server-sha256',SERVER_SHA,'--expected-gpu-uuid',GPU,'--expected-pod-uid',targets['pods'][a.side]['uid'],'--expected-driver-generation',GENERATION]
   stage='mps-start'
   mps=engine.Session(targets['pods'][a.side],args,raw['mps_probe.py'],a.output,trial);sessions.append(mps)
   started=mps.wait('daemon-started');registered=mps.wait('mps-registered')
   stage='live-map'
   live=attribute(current,engine,targets,before,index,registered,started,trial,vector,diagnostics=a.output/'live-mapper-failure.json');write(a.output/'live-processes.json',live)
  except BaseException as error:failure=error;receipt['error_type']=type(error).__name__;receipt['error']=error_evidence(error,stage)
  finally:
   values,errors=engine.finish_all(sessions)
   if errors:
    receipt['cleanup_errors']=errors;failure=failure or RuntimeError('Unresolved transport cleanup')
    receipt.setdefault('error',error_evidence(failure,'finish'))
  try:
   require(failure is None and len(values)==2 and live is not None,'Incomplete MPS or unresolved cleanup')
   stage='assess'
   receipt['measurement']=engine.assess(values[1],values[0])
   stage='clean-map'
   cleaned=attribute(current,engine,targets,before,index,registered,started,trial,vector,original=live['mapping']['processes'],diagnostics=a.output/'cleaned-mapper-failure.json');write(a.output/'host-cleaned.json',cleaned)
   stage='postflight'
   after=current.preflight({'manifest':targets});write(a.output/'after.json',after);unchanged(before,after,clean=True)
   receipt['state']='bounded-mps-peer-and-cleanup-measurements-passed'
  except BaseException as error:
   failure=error;receipt['state']='inconclusive';receipt['error_type']=type(error).__name__
   receipt.setdefault('error',error_evidence(error,stage))
  write(a.output/'receipt.json',receipt)
 finally:
  for sig,handler in previous.items():signal.signal(sig,handler)
 print(json.dumps({'state':receipt['state'],'receipt':str(a.output/'receipt.json'),'production_qualified':False}))
 if failure is not None:raise SystemExit(1)
if __name__=='__main__':main()

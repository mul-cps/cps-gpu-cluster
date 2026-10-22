#!/usr/bin/env python3
"""Default-inert trusted peer kernel continuity during held typed PyTorch OOM."""
import argparse,hashlib,json,os,stat,subprocess,threading,time
from pathlib import Path
import types
current=None
GPU='GPU-16128952-b438-556a-00bb-93039ee24e56'
def require(value,message):
 if not value:raise ValueError(message)

def private_file(path):
 return os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')
def write_json(path,value):
 with private_file(path) as output:output.write((json.dumps(value,sort_keys=True)+'\n').encode())

class ProbeRun:
    def __init__(self, target, case, duration, source, output):
        self.events, self.error, self.duration = [], None, duration
        self.condition = threading.Condition()
        self.started = time.monotonic()
        self.stdout = private_file(output / (case + '.jsonl'))
        self.stderr = private_file(output / (case + '.stderr'))
        self.process = subprocess.Popen(['kubectl', '-n', target['namespace'], 'exec', '-i', target['name'],
            '-c', 'notebook', '--', 'python', '-I', '-u', '-', '--execute', '--case', case,
            '--duration', str(duration), '--expected-device-uuid', GPU],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr)
        def collect():
            size = 0
            try:
                for line in self.process.stdout:
                    size += len(line)
                    require(size <= 4 * 1024 * 1024 and len(line) <= 65536, 'Bounded probe output required')
                    self.stdout.write(line); self.stdout.flush()
                    event = json.loads(line)
                    require(isinstance(event, dict), 'Structured probe event required')
                    with self.condition:
                        self.events.append(event); self.condition.notify_all()
            except Exception as error:
                self.error = type(error).__name__
            finally:
                self.stdout.close()
                with self.condition:
                    self.condition.notify_all()
        self.reader = threading.Thread(target=collect, daemon=True); self.reader.start()
        def send():
            try:
                self.process.stdin.write(source); self.process.stdin.close()
            except Exception as error:
                self.error = type(error).__name__
                with self.condition:
                    self.condition.notify_all()
        writer = threading.Thread(target=send, daemon=True); writer.start(); writer.join(timeout=25)
        if writer.is_alive() or self.error:
            # Bound API/transport stalls while streaming source as well as the
            # test runtime. This is solely our local kubectl child process.
            self.process.kill(); self.process.wait(timeout=5)
            writer.join(timeout=3); self.reader.join(timeout=3); self.stderr.close()
            raise ValueError('Bounded trusted source transfer failed')

    def wait(self, predicate, timeout):
        deadline = time.monotonic() + timeout
        with self.condition:
            while not predicate(self.events):
                require(not self.error, 'Probe stream failed: ' + str(self.error))
                require(self.process.poll() is None, 'Probe exited before required overlap')
                remaining = deadline - time.monotonic()
                require(remaining > 0, 'Probe overlap deadline exceeded')
                self.condition.wait(min(remaining, 0.5))

    def complete(self):
        try:
            code = self.process.wait(timeout=max(1, self.duration + 25 - (time.monotonic() - self.started)))
        except subprocess.TimeoutExpired:
            # Kill only this local transport process. Remote trusted probe has
            # its own <=180s watchdog; never stop/delete any cluster workload.
            self.process.kill(); self.process.wait(timeout=5); code = 124
        self.reader.join(timeout=3); self.stderr.close()
        require(not self.reader.is_alive() and not self.error and code == 0, 'Probe failed/timed out: ' + str(code))
        return self.events

def assess(peer,oom,samples):
 def one(events,phase):
  found=[e for e in events if e.get('phase')==phase]
  require(len(found)==1,'Exactly one '+phase+' event required');return found[0]
 def receipt(events,case):
  value=one(events,'receipt')
  require(value.get('case')==case and value.get('state')=='measurement-completed' and value.get('production_qualified')is False and value.get('hardware',{}).get('gpu_uuid')==GPU and str(value.get('hardware',{}).get('torch_version','')).startswith('2.11.'),'Successful exact runtime receipt required');return value
 pr,failure=receipt(peer,'peer'),receipt(oom,'oom')
 require(pr.get('peer_loop_passed')is True and failure.get('bounded_step_sequence_passed')is True and failure.get('over_denied')is True and failure.get('ordinary_byte')==19 and failure.get('recovery_byte')==37,'OOM and recovered kernel required')
 typed=failure.get('over_error')
 require(typed in ({'kind':'torch.OutOfMemoryError','cuda_error_code':None},{'kind':'torch.AcceleratorError','cuda_error_code':2}),'Typed OOM required')
 held=failure.get('held_before_oom_mib');require(type(held)is int and 4096<=held<=5120,'Meaningful bounded allocation required')
 start,end,error,recovery=[one(oom,p) for p in ('oom-held-start','oom-held-end','over-allocation-error','after-recovery-free64')]
 ticks=[e for e in peer if e.get('phase')=='peer_tick']
 require(all(type(e.get('monotonic_ns'))is int for e in [start,end,error,recovery,*ticks]),'Exact monotonic timestamps required')
 lo,hi=start['monotonic_ns'],end['monotonic_ns']
 require(error.get('typed_oom')is True and error['monotonic_ns']<lo and hi-lo>=8_000_000_000 and hi<recovery['monotonic_ns'] and start.get('held_tensor_mib')==end.get('held_tensor_mib')==held,'Full eight-second retained OOM pressure required')
 require(len(ticks)>=2 and [e.get('tick')for e in ticks]==list(range(1,len(ticks)+1)) and all(0<b['monotonic_ns']-a['monotonic_ns']<=5_000_000_000 for a,b in zip(ticks,ticks[1:])) and ticks[0]['monotonic_ns']<error['monotonic_ns']<recovery['monotonic_ns']<ticks[-1]['monotonic_ns'],'Continuous peer kernels must bracket OOM and recovery')
 inside=[e for e in ticks if lo<e['monotonic_ns']<hi]
 require(len(inside)>=2 and inside[-1]['monotonic_ns']-inside[0]['monotonic_ns']>=1_000_000_000,'Peer progress inside held OOM required')
 require(type(samples)is list and len(samples)>=2,'Independent Root physical samples required')
 for s in samples:
  require(type(s)is dict and s.get('gpu_uuid')==GPU and type(s.get('observed_monotonic_ns'))is int and lo<s['observed_monotonic_ns']<hi,'Physical sample must be inside held OOM on same GPU')
  require(type(s.get('physical_free_bytes'))is int and type(s.get('physical_total_bytes'))is int and 6*1024**3<s['physical_free_bytes']<=s['physical_total_bytes'] and s['physical_total_bytes']>30*1024**3,'Independent physical VRAM headroom greater than6GiB required; capped CUDA totals cannot qualify')
 require(all(a['observed_monotonic_ns']<b['observed_monotonic_ns']for a,b in zip(samples,samples[1:])) and samples[-1]['observed_monotonic_ns']-samples[0]['observed_monotonic_ns']>=1_000_000_000,'Repeated physical samples required')
 return {'measurement_passed':True,'peer_ticks_inside_oom_hold':len(inside),'held_before_oom_mib':held,'typed_oom':typed,'recovery_byte':37,'physical_samples':len(samples),'production_qualified':False}

def physical_samples(targets):
 value=current.command(targets['physical_argv'])
 require(type(value)is dict and set(value)=={'version','samples','hardware_qualified','production_qualified'}
         and type(value['version'])is int and value['version']==1 and value['hardware_qualified']is False
         and value['production_qualified']is False and type(value['samples'])is list and len(value['samples'])==4,
         'Four actual Root physical observations with closed provenance required')
 result=[]
 for row in value['samples']:
  require(type(row)is dict and set(row)=={'gpu_uuid','free_bytes','total_bytes','observed_monotonic_ns'}
          and row['gpu_uuid']==GPU and all(type(row[k])is int for k in ('free_bytes','total_bytes','observed_monotonic_ns'))
          and 0<=row['free_bytes']<=row['total_bytes'] and row['observed_monotonic_ns']>0,
          'Exact typed actual physical sample required')
  result.append({**row,'physical_free_bytes':row['free_bytes'],'physical_total_bytes':row['total_bytes']})
 return result

def verified_source(path,digest):
 require(isinstance(digest,str) and len(digest)==64 and all(c in '0123456789abcdef'for c in digest),'Reviewed source SHA256 required')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  before=os.fstat(fd);raw=os.read(fd,1024*1024+1);after=os.fstat(fd)
  require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1 and not before.st_mode&0o022 and 0<len(raw)<=1024*1024 and all(getattr(before,k)==getattr(after,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'Stable owned source required')
  require(hashlib.sha256(raw).hexdigest()==digest,'Source hash drift');return raw
 finally:os.close(fd)

def abandon(run):
 if run is None:return
 if hasattr(run,'close'):
  run.close();return
 try:
  if run.process.poll()is None:run.process.kill()
  run.process.wait(timeout=5)
 finally:
  run.reader.join(timeout=3);run.stderr.close()

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--execute',action='store_true');parser.add_argument('--manifest');parser.add_argument('--manifest-sha256');parser.add_argument('--output')
 parser.add_argument('--probe-sha256');parser.add_argument('--preflight-sha256');parser.add_argument('--runner-sha256');parser.add_argument('--direction',choices=('a-to-b','b-to-a'),default='a-to-b')
 args=parser.parse_args(argv)
 if not args.execute:
  print(json.dumps({'inert':True,'gpu_calls':False,'api_calls':False,'production_qualified':False}));return
 require(all((args.manifest,args.manifest_sha256,args.output,args.probe_sha256,args.preflight_sha256,args.runner_sha256)),'Exact reviewed source/manifest/output required')
 global current
 here=Path(__file__).resolve().parent
 verified_source(here/'run_peer_oom.py',args.runner_sha256)
 raw=verified_source(here/'fresh_preflight.py',args.preflight_sha256)
 current=types.ModuleType('fresh_qa_preflight');exec(compile(raw,str(here/'fresh_preflight.py'),'exec'),current.__dict__)
 source=verified_source(here/'peer_probe.py',args.probe_sha256)
 targets=current.read_targets(args.manifest,args.manifest_sha256)
 def launch(name,case,duration):
  return ProbeRun(targets['pods'][name],case,duration,source,output)
 output=Path(args.output);output.mkdir(mode=0o700);os.chmod(output,0o700)
 peer=oom=None
 try:
  before=current.preflight({'manifest':targets});write_json(output/'before.json',before)
  a,b=('a','b')if args.direction=='a-to-b'else('b','a')
  peer=launch(a,'peer',60)
  peer.wait(lambda events:sum(e.get('phase')=='peer_tick'for e in events)>=2,30)
  oom=launch(b,'oom',45)
  oom.wait(lambda events:any(e.get('phase')=='oom-held-start'for e in events),30)
  samples=physical_samples(targets);write_json(output/'physical-samples.json',samples)
  oom_events=oom.complete();peer_events=peer.complete()
  result=assess(peer_events,oom_events,samples)
  after=current.preflight({'manifest':targets});write_json(output/'after.json',after)
  require(before['pods']==after['pods'],'Current Pod/process drift')
  require(before['host']['processes']==after['host']['processes'],'Actual notebook process identity drift')
  for prior,latest in zip(before['host']['targets'],after['host']['targets']):
   require({k:v for k,v in prior.items()if k!='limit'}=={k:v for k,v in latest.items()if k!='limit'},'Seal/journal/identity drift')
   require(latest['limit']['used']<=prior['limit']['used'],'Probe charge not recovered to baseline')
  write_json(output/'assessment.json',{**result,'direction':args.direction,'transport':'kubectl','unchanged_seals_and_processes':True})
 finally:
  # Every local transport is cleaned even if another cleanup fails. Remote
  # trusted probes independently watchdog-exit within60seconds; no Pod deletion.
  errors=[]
  for run in (oom,peer):
   try:abandon(run)
   except Exception as error:errors.append(type(error).__name__)
  if errors:raise ValueError('Local transport cleanup failed: '+','.join(errors))
if __name__=='__main__':main()

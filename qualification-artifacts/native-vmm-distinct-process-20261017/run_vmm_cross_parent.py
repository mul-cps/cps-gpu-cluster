#!/usr/bin/env python3
"""Qualification-only existing-Pod VMM bridge trial; default inert."""
import argparse,hashlib,importlib.util,json,os,stat,subprocess,threading,time,uuid,signal,selectors
from pathlib import Path
BRIDGE_ROOT='/run/cps-native-gpu/operator/native-vmm-distinct-process-20261017'
def require(ok,message):
 if not ok:raise ValueError(message)
def write(path,value):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w')as f:json.dump(value,f,sort_keys=True,separators=(',',':'),allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def error_record(error):
 return {'type':type(error).__name__,'message':str(error).replace('\x00','?')[:512]}

def diagnostic_run(argv,source,output,label,timeout=25,stream_limit=2*1024*1024):
 """Bounded local Root transport; archive both streams before raising. No stdin content logged."""
 require(isinstance(source,bytes) and len(source)<=65536,'Bounded closed Root request required')
 streams={};buffers={'stdout':bytearray(),'stderr':bytearray()};process=None;selector=selectors.DefaultSelector()
 record={'argv':argv,'stdin_sha256':hashlib.sha256(source).hexdigest(),'stdin_bytes':len(source),'state':'spawn-failed','returncode':None}
 try:
  for name in buffers:
   fd=os.open(output/(label+'.'+name),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);streams[name]=os.fdopen(fd,'wb')
  process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  record['state']='completed';deadline=time.monotonic()+timeout;offset=0
  for name in buffers:
   pipe=getattr(process,name);os.set_blocking(pipe.fileno(),False);selector.register(pipe,selectors.EVENT_READ,name)
  if source:
   os.set_blocking(process.stdin.fileno(),False);selector.register(process.stdin,selectors.EVENT_WRITE,'stdin')
  else:process.stdin.close()
  while selector.get_map():
   remaining=deadline-time.monotonic()
   if remaining<=0:record['state']='timeout';break
   for key,_ in selector.select(min(.1,remaining)):
    pipe=key.fileobj;name=key.data
    if name=='stdin':
     try:offset+=os.write(pipe.fileno(),source[offset:offset+4096])
     except BrokenPipeError:offset=len(source)
     if offset==len(source):selector.unregister(pipe);pipe.close()
    else:
     piece=os.read(pipe.fileno(),65536)
     if not piece:selector.unregister(pipe);pipe.close();continue
     available=stream_limit-len(buffers[name]);kept=piece[:available];buffers[name].extend(kept);streams[name].write(kept)
     if len(piece)>available:record['state']='stream-bound-exceeded';break
   if record['state']!='completed':break
  if record['state']!='completed' and process.poll()is None:process.kill()
  try:record['returncode']=process.wait(timeout=max(.01,deadline-time.monotonic()))
  except subprocess.TimeoutExpired:
   record['state']='timeout';process.kill();record['returncode']=process.wait(timeout=5)
 except BaseException as error:
  record['state']='transport-failed';record['error']=error_record(error)
  if process is not None:
   if process.poll()is None:process.kill()
   record['returncode']=process.wait(timeout=5)
  raise
 finally:
  selector.close()
  if process is not None:
   for name in ('stdin','stdout','stderr'):
    pipe=getattr(process,name)
    if not pipe.closed:pipe.close()
  for stream in streams.values():stream.flush();os.fsync(stream.fileno());stream.close()
  record['streams']={name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}for name,raw in buffers.items()}
  write(output/(label+'.json'),record)
 require(record['state']=='completed','Root bridge transport '+record['state']+'; private command streams retained')
 require(record['returncode']==0,'Root bridge exit '+str(record['returncode'])+'; private command stdout/stderr retained')
 value=json.loads(buffers['stdout']);require(isinstance(value,dict),'Typed Root bridge response required');return value
LOADER="import os,sys,hashlib,uuid\nlimit=bytearray()\nwhile not limit.endswith(b'\\n'):\n piece=os.read(0,1)\n if not piece or len(limit)>=8:raise ValueError('Bounded source length required')\n limit.extend(piece)\nn=int(limit);assert 0<n<=100000\nraw=bytearray()\nwhile len(raw)<n:\n piece=os.read(0,n-len(raw))\n if not piece:raise ValueError('Incomplete endpoint source')\n raw.extend(piece)\ndef arg(flag):return sys.argv[sys.argv.index(flag)+1]\ntrial=arg('--trial-id');role=arg('--role');expected=arg('--source-sha256')\nassert hashlib.sha256(raw).hexdigest()==expected and str(uuid.UUID(trial))==trial and role in ('exporter','positive','importer')\ndirectory='/tmp/cpv-'+uuid.UUID(trial).hex[:16]+'-'+role+'-src';os.mkdir(directory,0o700);os.chmod(directory,0o700)\npath=directory+'/vmm_endpoint.py';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)\nwith os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())\nos.execv(sys.executable,[sys.executable,'-I','-S','-u',path,*sys.argv[1:]])\n"

class Session:
    def __init__(self, target, args, source, label, output):
        self.events, self.error, self.label = [], None, label
        self.condition = threading.Condition()
        self.log = open(output / (label + '.jsonl'), 'xb'); os.chmod(self.log.name, 0o600)
        self.stderr = open(output / (label + '.stderr'), 'xb'); os.chmod(self.stderr.name, 0o600)
        try:
            self.process = subprocess.Popen(['kubectl', '-n', target['namespace'], 'exec', '-i', target['name'],
                '-c', 'notebook', '--', 'python', '-u', '-c', LOADER, *args],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr)
        except BaseException:
            self.log.close(); self.stderr.close(); raise
        def reader():
            size = 0
            try:
                for line in self.process.stdout:
                    size += len(line); require(size <= 2 * 1024 * 1024 and len(line) <= 65536, 'Bounded endpoint log required')
                    event = json.loads(line); require(isinstance(event, dict), 'Typed endpoint event required')
                    self.log.write(line); self.log.flush()
                    with self.condition: self.events.append(event); self.condition.notify_all()
            except Exception as error: self.error = type(error).__name__
            finally:
                self.log.close()
                with self.condition: self.condition.notify_all()
        self.reader = threading.Thread(target=reader, daemon=True); self.reader.start()
        def writer():
            try:
                self.process.stdin.write(str(len(source)).encode() + b'\n' + source); self.process.stdin.flush()
            except Exception as error: self.error = type(error).__name__
        self.writer = threading.Thread(target=writer, daemon=True); self.writer.start(); self.writer.join(timeout=15)
        if self.writer.is_alive() or self.error:
            self.abandon()
            raise ValueError('Endpoint source transport failed')
    def wait(self, phase, timeout=15):
        return self.wait_matching(lambda e: e.get('phase') == phase, timeout)
    def wait_matching(self, predicate, timeout=15):
        end = time.monotonic() + timeout
        with self.condition:
            while True:
                values = [e for e in self.events if predicate(e)]
                if values: return values[0]
                require(not self.error and self.process.poll() is None and time.monotonic() < end, 'Endpoint phase absent/failed')
                self.condition.wait(0.1)
    def send(self, op, trial):
        self.process.stdin.write((json.dumps({'op': op, 'trial_id': trial}) + '\n').encode()); self.process.stdin.flush()
    def complete(self, timeout=20):
        code = self.process.wait(timeout=timeout); self.reader.join(timeout=2)
        self.stderr.close()
        require(not self.reader.is_alive() and not self.error and code == 0, 'Endpoint did not complete successfully')
        receipts = [e for e in self.events if e.get('phase') == 'receipt']
        require(len(receipts) == 1 and receipts[0].get('state') == 'measurement-completed'
            and receipts[0].get('explicit_native_cleanup_completed') is True, 'Explicit native endpoint cleanup required')
        return self.events
    def abandon(self):
        # Close only our local transport. The remote endpoint has a115s
        # watchdog; EOF makes the exporter clean up. No Pod/server signal.
        if self.writer.is_alive() and self.process.poll() is None:
            self.process.kill(); self.process.wait(timeout=5); self.writer.join(timeout=2)
        if not self.process.stdin.closed: self.process.stdin.close()
        if self.process.poll() is None:
            try: self.process.wait(timeout=5)
            except subprocess.TimeoutExpired: self.process.kill(); self.process.wait(timeout=5)
        self.reader.join(timeout=2)
        if not self.reader.is_alive() and not self.process.stdout.closed: self.process.stdout.close()
        if not self.stderr.closed: self.stderr.close()

def load_preflight():
    import current_preflight
    return current_preflight

def load_witness():
    path=Path(__file__).parent/'kernel_witness_transport.py'
    spec=importlib.util.spec_from_file_location('vmm_root_witness_transport',path);transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport);return transport

def unchanged(before,after):
    require(before['pods']==after['pods'],'Pod/container/restart changed')
    for old,new in zip(before['host']['targets'],after['host']['targets']):
        require(all(old[k]==new[k]for k in ('pod_uid','intent','identity','seal_id','journal_sha256','gate_sha256')),'Native seal changed')
        require(new['inventory_row']['used']<=old['inventory_row']['used'],'Charge remains after endpoint cleanup')

def open_denied(denied,trial,attribution,witness):
    witness.begin(attribution);denied.send('open',trial);result=denied.wait('import-result');kernel=witness.end(result)
    denied.send('finish',trial);return denied.complete(),kernel

def one(events,phase,trial):
    values=[e for e in events if e.get('phase')==phase];require(len(values)==1 and values[0].get('trial_id')==trial,'Unique actual trial phase required');return values[0]

def assess(exporter,positive,denied,bridges,trial,correlation):
    p=one(positive,'import-result',trial);d=one(denied,'import-result',trial)
    require(p.get('api')==d.get('api')=='cuMemImportFromShareableHandle' and p.get('expect')=='allow'
        and type(p.get('cuda_result'))is int and p['cuda_result']==0 and p.get('cuda_name')=='CUDA_SUCCESS'
        and d.get('expect')=='deny' and type(d.get('cuda_result'))is int and d['cuda_result']==800 and d.get('cuda_name')=='CUDA_ERROR_NOT_PERMITTED',
        'Exact raw VMM valid-positive and typed cross denial required')
    for events in (exporter,positive,denied):
        final=one(events,'receipt',trial);require(final.get('state')=='measurement-completed' and final.get('explicit_native_cleanup_completed')is True,'All participant cleanup required')
    for events in (positive,denied):
        for phase in ('importer-before-kernel','importer-after-kernel'):
            vector=one(events,phase,trial);require(vector.get('vector_verified')is True and vector.get('vector_elements')==256,'Own actual vector kernels must survive')
    ready=one(exporter,'exporter-ready',trial);require(ready.get('backing_bytes')==67108864 and len(bridges)==2,'Exact original64MiB backing required')
    require([b['transfer']for b in bridges]==['positive','cross'] and all(b.get('state')=='one-bounded-vmm-descriptor-forwarded'
        and type(b.get('descriptor_count'))is int and b['descriptor_count']==1 and type(b.get('backing_bytes'))is int and b['backing_bytes']==67108864 and b.get('network_namespace_entered')is False
        and b.get('fd_identity')==ready['fd_identity']for b in bridges),'Actual same one-FD bridge provenance required')
    ticks=[e for e in exporter if e.get('phase')=='exporter-tick'];recover=one(exporter,'exporter-recovery',trial)
    require(len(ticks)>=2 and all(e.get('trial_id')==trial and e.get('vector_verified')is True for e in ticks)
        and [e.get('tick')for e in ticks]==list(range(1,len(ticks)+1))
        and ticks[0]['monotonic_ns']<d['call_started_monotonic_ns']<=d['call_ended_monotonic_ns']<ticks[-1]['monotonic_ns']
        and recover['monotonic_ns']>d['call_ended_monotonic_ns'] and recover.get('vector_verified')is True
        and all(0<b['monotonic_ns']-a['monotonic_ns']<=5_000_000_000 for a,b in zip(ticks,ticks[1:])),
        'Exporter own vector continuity and recovery must bracket denial')
    require(correlation.get('kernel_witness_correlated')is True and correlation.get('trial_id')==trial
        and correlation.get('host_tgid')==bridges[1]['importer_attribution']['host_tgid'],'Exact actual importer kernel witness required')
    return {'state':'bounded-cross-parent-vmm-kernel-denial-measured','same_parent_positive_control':True,
        'kernel_witness_correlated':True,'peer_vector_continuity':True,'production_qualified':False,'cross_parent_isolation_qualified':False}

def bridge(h,args,config,ready,trial,transfer,index):
    request={'trial_id':trial,'transfer':transfer,'exporter':{'role':'exporter','expect':'allow','namespace_pid':ready[0]['namespace_pid'],'identity':ready[0]['identity']},
        'importer':{'role':'positive' if transfer=='positive' else 'importer','expect':'allow' if transfer=='positive' else 'deny','namespace_pid':ready[1]['namespace_pid'],'identity':ready[1]['identity']}}
    argv=[*h.OBSERVER_ARGV[:-1],BRIDGE_ROOT+'/vmm_bridge.py','--execute','--qualification','--source-sha256',args.bridge_source_sha256,'--endpoint-source-sha256',args.endpoint_source_sha256,'--targets-sha256',args.targets_sha256]
    proof=diagnostic_run(argv,(json.dumps(request,sort_keys=True,separators=(',',':'))+'\n').encode(),args.output,transfer+'-root-command',timeout=25)
    require(proof.get('state')=='one-bounded-vmm-descriptor-forwarded' and proof.get('trial_id')==trial and proof.get('transfer')==transfer
        and proof.get('bridge_source_sha256')==args.bridge_source_sha256 and proof.get('endpoint_source_sha256')==args.endpoint_source_sha256,
        'Actual pinned Root bridge reply required');return proof

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--observer-pod-uid');p.add_argument('--output',type=Path)
    p.add_argument('--direction',choices=['a-to-b','b-to-a'],default='a-to-b');p.add_argument('--targets',type=Path);p.add_argument('--targets-sha256');p.add_argument('--preflight-source-sha256')
    for name in ('wrapper-source-sha256','endpoint-source-sha256','bridge-source-sha256','witness-collector-sha256','witness-validator-sha256','witness-transport-sha256'):p.add_argument('--'+name)
    args=p.parse_args(argv)
    if not args.execute:print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False,'production_qualified':False}));return
    pins={'run_vmm_cross_parent.py':args.wrapper_source_sha256,'vmm_endpoint.py':args.endpoint_source_sha256,'vmm_bridge.py':args.bridge_source_sha256,
        'current_preflight.py':args.preflight_source_sha256,'kernel_witness_collector.py':args.witness_collector_sha256,'kernel_witness_validator.py':args.witness_validator_sha256,'kernel_witness_transport.py':args.witness_transport_sha256}
    parent=Path(__file__).parent
    require(all(isinstance(s,str) and hashlib.sha256((parent/f).read_bytes()).hexdigest()==s for f,s in pins.items()),'Explicit separately reviewed source pins required')
    require(args.output is not None and args.output.parent.is_dir(),'Private output required');info=args.output.parent.lstat()
    require(info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o700,'Owned private700 output parent required');args.output.mkdir(mode=0o700)
    h=load_preflight();manifest=h.read_targets(args.targets,args.targets_sha256);h.configure(manifest)
    require(manifest['observer']['uid']==args.observer_pod_uid,'Exact manifest observer UID required')
    config={'manifest':manifest,'targets':[dict(namespace=v['namespace'],name=v['name'],pod_uid=v['uid'])for v in [manifest['pods'][k]for k in ('a','b')]]}
    before=h.preflight(config);write(args.output/'before.json',before)
    require(len({t['identity']['cgroup_inode']for t in before['host']['targets']})==2,'Distinct actual finite parents required')
    transport=load_witness()
    source=(parent/'vmm_endpoint.py').read_bytes();trial=str(uuid.uuid4());sessions=[];witness=None;completed=set()
    index=0 if args.direction=='a-to-b' else 1
    targets=config['targets'];base=['--execute','--trial-id',trial,'--gpu-uuid',h.GPU,'--source-sha256',args.endpoint_source_sha256]
    receipt={'state':'inconclusive','trial_id':trial,'direction':args.direction,'config':config,'source_sha256':pins,'preflight_sha256':args.preflight_source_sha256,
        'targets_sha256':args.targets_sha256,'production_qualified':False,'cross_parent_isolation_qualified':False}
    def cancelled(signum,frame):raise InterruptedError('Operator cancelled; transport cleanup required')
    signal.signal(signal.SIGTERM,cancelled)
    try:
        exporter=Session(targets[index],[*base,'--role','exporter','--expect','allow','--expected-pod-uid',targets[index]['pod_uid']],source,'exporter',args.output);sessions.append(exporter)
        export_ready=exporter.wait('exporter-ready');exporter.wait('exporter-tick')
        positive=Session(targets[index],[*base,'--role','positive','--expect','allow','--expected-pod-uid',targets[index]['pod_uid']],source,'same-parent-positive',args.output);sessions.append(positive)
        positive_ready=positive.wait('socket-ready')
        def mapped(event,i):return {'namespace_pid':event['namespace_pid'],'identity':before['host']['targets'][i]['identity']}
        first=bridge(h,args,config,[mapped(export_ready,index),mapped(positive_ready,index)],trial,'positive',index);write(args.output/'positive-bridge.json',first)
        positive.wait('importer-ready');positive.send('open',trial);positive.wait('import-result');positive.send('finish',trial);positive_events=positive.complete();completed.add(positive.label)
        denied=Session(targets[1-index],[*base,'--role','importer','--expect','deny','--expected-pod-uid',targets[1-index]['pod_uid']],source,'cross-parent-importer',args.output);sessions.append(denied)
        denied_ready=denied.wait('socket-ready');second=bridge(h,args,config,[mapped(export_ready,index),mapped(denied_ready,1-index)],trial,'cross',index);write(args.output/'cross-bridge.json',second)
        denied.wait('importer-ready');attribution=second['importer_attribution'];write(args.output/'importer-host-attribution.json',attribution)
        root_argv=[*h.OBSERVER_ARGV[:-1],transport.ROOT+'/kernel_witness_collector.py','--execute','--qualification','--source-sha256',args.witness_collector_sha256,'--validator-sha256',args.witness_validator_sha256]
        witness=transport.KernelWitness(root_argv,args.output,collector_sha256=args.witness_collector_sha256,validator_sha256=args.witness_validator_sha256)
        denied_events,kernel=open_denied(denied,trial,attribution,witness);completed.add(denied.label);capture,correlation=kernel
        exporter.send('recover',trial);exporter.wait('exporter-recovery')
        last=one(denied_events,'import-result',trial)['call_ended_monotonic_ns']
        exporter.wait_matching(lambda e:e.get('phase')=='exporter-tick' and e.get('monotonic_ns',0)>last)
        exporter.send('finish',trial);exporter_events=exporter.complete();completed.add(exporter.label)
        measurement=assess(exporter_events,positive_events,denied_events,[first,second],trial,correlation)
        write(args.output/'kernel-witness-capture.json',capture);write(args.output/'kernel-witness-correlation.json',correlation)
        receipt.update(measurement,kernel_witness_correlation=correlation)
    except BaseException as error:
        receipt['state']='inconclusive';receipt['error_type']=type(error).__name__;receipt['error_message']=error_record(error)['message']
    finally:
        if witness is not None:
            try:witness.close()
            except BaseException as error:receipt['state']='inconclusive';receipt['witness_cleanup_error']=error_record(error)
        for session in reversed(sessions):
            try:session.abandon()
            except BaseException as error:
                receipt['state']='inconclusive';receipt.setdefault('transport_cleanup_errors',[]).append({'label':session.label,**error_record(error)})
        receipt['remote_endpoint_cleanup']='verified' if len(sessions)==3 and completed=={session.label for session in sessions} else 'unresolved'
        receipt['explicitly_completed_endpoints']=sorted(completed)
        if receipt['remote_endpoint_cleanup']!='verified':receipt['state']='inconclusive'
        receipt['final_postflight_observed']=False;receipt['unchanged_native_authorities']=False
        try:
            after=h.preflight(config);write(args.output/'final-postflight.json',after);receipt['final_postflight_observed']=True
            unchanged(before,after);receipt['unchanged_native_authorities']=True
        except BaseException as error:
            receipt['state']='inconclusive';receipt['final_postflight_error']=error_record(error)
        write(args.output/'receipt.json',receipt)
    print(json.dumps({'state':receipt['state'],'receipt':str(args.output/'receipt.json'),'production_qualified':False}))
    if receipt['state']=='inconclusive':raise SystemExit(1)
if __name__=='__main__':main()

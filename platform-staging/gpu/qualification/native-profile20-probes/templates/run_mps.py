#!/usr/bin/env python3
"""Inert Root operator wrapper; existing approved Pods only, no cap/release writes."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import threading
import time
import uuid

PREFLIGHT_SHA = 'a3a05481bbfbfa6de47bdf899ff1b051caad0b9f3a5399b627cbc98c940b4a5f'
PREFLIGHT_HOST_SHA = '67f7e050af19385b04afa60f6a2cd9af02fcdfd92f52732bcd8d85a4ec67290d'
PROBE_SHA = '336c036b1938ea272211a8f04b833e6d02d18351c6e5f7cbfae82a56da302893'
CONTROL_SHA = '7e91a303b67382a1377f63a4c862605a27e40ac590e91c431fe547308fb71868'
SERVER_SHA = '1d49ca38a96799699118331f0c76a3fd7a76cafc25dbfc0c4d904a98d4e77176'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
GENERATION = 'b10498fc-9153-4394-875a-ea7cfb498625'

# Installs only the unchanged, checksummed probe in its own ordinary-user tmp
# directory. No shell, Pod change, device operation or privilege override.
LAUNCH_SOURCE = r'''import hashlib,json,os,signal,stat,subprocess,sys,tempfile
from pathlib import Path
if os.getuid()!=1000 or os.getgid()!=100:raise ValueError('UID1000/GID100 launcher required')
raw=sys.stdin.buffer.read(100001)
if not 0<len(raw)<=100000 or hashlib.sha256(raw).hexdigest()!=sys.argv[1]:raise ValueError('Exact probe source required')
directory=Path('/tmp')/('cps-mps-wrapper-'+sys.argv[2]);directory.mkdir(mode=0o700)
path=directory/'mps_probe.py';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'wb') as f:f.write(raw)
cancelled=[]
def cancel(signum,frame):cancelled.append(signum)
signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)
code=None
try:
 child=subprocess.Popen([sys.executable,'-I','-S',str(path),*sys.argv[3:]],stdin=subprocess.DEVNULL)
 # A transport cancellation does not kill MPS or skip the probe's finally.
 code=child.wait(timeout=180)
finally:
 # If the reviewed probe did not exit, its cleanup is unknown and Root must
 # stop the owning Pod. Never forge a success or signal an unverified daemon.
 if code is not None:path.unlink();directory.rmdir()
print(json.dumps({'phase':'mps-launcher-complete','child_exit_code':code,'cancelled':bool(cancelled)}),flush=True)
if code!=0 or cancelled:raise SystemExit(1)
'''

# Read-only Root process mapping derived from the reviewed IPC mapper. Both
# sides run the exact retired-aware HOST_SOURCE, binding health/map/journals.
MAPPER_SOURCE = r'''import contextlib,hashlib,io,json,os,stat,sys,time
from pathlib import Path
r=json.loads(sys.argv[1])
def need(ok,message):
 if not ok:raise ValueError(message)
def snapshot():
 need(hashlib.sha256(r['preflight_source'].encode()).hexdigest()=='67f7e050af19385b04afa60f6a2cd9af02fcdfd92f52732bcd8d85a4ec67290d','Exact host preflight source required')
 output=io.StringIO();saved=sys.argv;sys.argv=['trusted-host',json.dumps(r['preflight'])]
 try:
  with contextlib.redirect_stdout(output):exec(compile(r['preflight_source'],'trusted-host-preflight','exec'),{'__name__':'mps_host_preflight'})
 finally:sys.argv=saved
 return json.loads(output.getvalue())
def fields(text):
 values={}
 for line in text.splitlines():
  key,sep,value=line.partition(':')
  if sep:need(key not in values,'Duplicate process field');values[key]=value.strip()
 return values
def identity_fields(values):
 keys=('Tgid','NSpid','Uid','Gid');need(all(key in values for key in keys),'Complete process identity fields required')
 return {key:values[key] for key in keys}
def start(text,pid):
 left,right=text.rsplit(')',1);parts=right.split()
 need(left.split('(',1)[0].strip()==str(pid) and len(parts)>=20 and parts[19].isdecimal(),'Actual host start ticks required')
 return int(parts[19])
def parent_path(text,relative):
 lines=text.splitlines();need(len(lines)==1 and lines[0].startswith('0::/'),'Actual unified cgroup required')
 value=lines[0][3:];need(value==relative or value.startswith(relative+'/'),'Process escaped sealed parent')
 return value
def bounded(path,limit=100000):
 raw=Path(path).read_bytes();need(len(raw)<=limit,'Bounded process input required');return raw
need(os.getuid()==0 and set(r)=={'preflight','preflight_source','identity','trial_id','pipe','probe_path','processes','mode','original'},'Closed Root attribution request required')
before=snapshot();identity=r['identity'];relative=identity['cgroup_relative']
need(any(t['identity']==identity for t in before['targets']),'Original sealed MPS parent required')
need(r['mode'] in ('live','cleaned') and isinstance(r['processes'],list) and len(r['processes'])==4,'Exactly two clients and private control/server required')
need(r['probe_path']=='/tmp/cps-mps-wrapper-'+r['trial_id']+'/mps_probe.py' and isinstance(r['pipe'],str) and r['pipe'].startswith('/tmp/cps-mps-') and r['pipe'].endswith('/pipe') and '..' not in r['pipe'].split('/'),'Private actual probe/pipe required')
need({p['role'] for p in r['processes']}=={'client0','client1','control','server'} and len({p['namespace_pid'] for p in r['processes']})==4,'Distinct actual MPS process roles required')
observed=[];deadline=time.monotonic()+8
if r['mode']=='live':
 for expected in r['processes']:
  matches=[]
  for item in Path('/proc').iterdir():
   need(time.monotonic()<deadline,'Bounded host attribution exceeded')
   if not item.name.isdecimal():continue
   pid=int(item.name)
   try:
    text=bounded(item/'cgroup').decode();lines=text.splitlines()
    need(len(lines)==1 and lines[0].startswith('0::/'),'Unknown host unified cgroup')
    current=lines[0][3:]
    if current!=relative and not current.startswith(relative+'/'):continue
    status=fields(bounded(item/'status').decode());nspid=status.get('NSpid','').split()
    need(nspid and all(p.isdecimal() for p in nspid) and int(nspid[0])==pid,'Actual host PID chain required')
    if int(nspid[-1])!=expected['namespace_pid']:continue
    need(status.get('Tgid')==str(pid) and status.get('Uid','').split()==['1000']*4 and status.get('Gid','').split()==['100']*4,'Actual non-root MPS TGID required')
    ticks=start(bounded(item/'stat').decode(),pid);need(ticks==expected['start_ticks'],'Namespace-reported process lifetime changed')
    argv_raw=bounded(item/'cmdline');argv=argv_raw.rstrip(b'\0').split(b'\0')
    env=bounded(item/'environ',262144).split(b'\0');pipe=('CUDA_MPS_PIPE_DIRECTORY='+r['pipe']).encode()
    need(env.count(pipe)==1,'MPS private pipe binding required')
    if expected['role'].startswith('client'):
     need(argv.count(r['probe_path'].encode())==1 and argv.count(b'--child')==1,'Actual approved client probe argv required')
     for flag,value in ((b'--source-sha256',b'336c036b1938ea272211a8f04b833e6d02d18351c6e5f7cbfae82a56da302893'),(b'--expected-pod-uid',identity['pod_uid'].encode()),(b'--expected-driver-generation',identity['driver_generation'].encode()),(b'--expected-gpu-uuid',identity['gpu_uuid'].encode())):
      need(argv.count(flag)==1 and argv.index(flag)+1<len(argv) and argv[argv.index(flag)+1]==value,'Exact current client argv required')
     path=item/'root'/r['probe_path'].lstrip('/');info=path.stat()
     need(stat.S_ISREG(info.st_mode) and info.st_uid==1000 and stat.S_IMODE(info.st_mode)==0o600 and hashlib.sha256(bounded(path)).hexdigest()=='336c036b1938ea272211a8f04b833e6d02d18351c6e5f7cbfae82a56da302893','Actual client probe source required')
    else:
     name='nvidia-cuda-mps-'+expected['role'];need(Path(argv[0].decode()).name==name,'Actual private MPS executable required')
     exe=item/'exe';info=exe.stat();need(stat.S_ISREG(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,'Root-owned MPS executable required')
     digest=hashlib.sha256(bounded(exe,1048576)).hexdigest()
     need(digest=={'control':'7e91a303b67382a1377f63a4c862605a27e40ac590e91c431fe547308fb71868','server':'1d49ca38a96799699118331f0c76a3fd7a76cafc25dbfc0c4d904a98d4e77176'}[expected['role']],'Exact injected MPS executable required')
    pidns=(item/'ns/pid').stat().st_ino
    need(identity_fields(fields(bounded(item/'status').decode()))==identity_fields(status) and start(bounded(item/'stat').decode(),pid)==ticks and parent_path(bounded(item/'cgroup').decode(),relative)==current and (item/'ns/pid').stat().st_ino==pidns,'Host process replaced during attribution')
    matches.append({'role':expected['role'],'host_pid':pid,'host_tgid':pid,'pid_start_ticks':ticks,'namespace_pid':int(nspid[-1]),'pid_namespace_inode':pidns,'process_cgroup_relative':current,'pod_cgroup_inode':identity['cgroup_inode'],'cmdline_sha256':hashlib.sha256(argv_raw).hexdigest()})
   except FileNotFoundError:continue
  need(len(matches)==1,'Exactly one live MPS process for each role required');observed+=matches
 need(len({p['host_tgid'] for p in observed})==4 and len({p['pid_namespace_inode'] for p in observed})==1,'Distinct same-namespace live MPS processes required')
else:
 need(isinstance(r['original'],list) and len(r['original'])==4,'Original actual host lifetimes required')
 for old in r['original']:
  path=Path('/proc')/str(old['host_tgid'])
  try:need(start(bounded(path/'stat').decode(),old['host_tgid'])!=old['pid_start_ticks'],'Original MPS process remains')
  except FileNotFoundError:pass
 for item in Path('/proc').iterdir():
  need(time.monotonic()<deadline,'Bounded cleanup observation exceeded')
  if not item.name.isdecimal():continue
  try:
   current=bounded(item/'cgroup').decode().strip()
   if current!='0::'+relative and not current.startswith('0::'+relative+'/'):continue
   need(('CUDA_MPS_PIPE_DIRECTORY='+r['pipe']).encode() not in bounded(item/'environ',262144).split(b'\0'),'Orphan private MPS process remains')
  except FileNotFoundError:continue
after=snapshot()
for old,new in zip(before['targets'],after['targets']):need(all(old[k]==new[k] for k in ('identity','intent','seal_id','journal_sha256','gate_sha256')),'Native seal changed across host mapping')
need(before['retired_caps']==after['retired_caps'],'Retired evidence changed during mapping')
print(json.dumps({'kind':'root-mps-process-attribution','mode':r['mode'],'trial_id':r['trial_id'],'pod_uid':identity['pod_uid'],'driver_generation':identity['driver_generation'],'processes':observed,'before':before,'after':after,'observed_time_ns':time.time_ns()},sort_keys=True,allow_nan=False))
'''


def require(ok, message):
    if not ok: raise ValueError(message)


def load_preflight():
    path = Path(__file__).parent.parent / 'run_group_acceptance.py'
    require(hashlib.sha256(path.read_bytes()).hexdigest() == PREFLIGHT_SHA, 'Reviewed preflight changed')
    spec = importlib.util.spec_from_file_location('mps_private_preflight', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    require(module.HOST_SHA == PREFLIGHT_HOST_SHA, 'Reviewed host source changed')
    return module


def unchanged(before, after):
    require(before['pods'] == after['pods'] and len(before['host']['targets']) == len(after['host']['targets']) == 2,
            'Both actual Pod lifetimes must remain unchanged')
    for old, new in zip(before['host']['targets'], after['host']['targets']):
        require(all(old[k] == new[k] for k in ('pod_uid', 'intent', 'identity', 'seal_id', 'journal_sha256', 'gate_sha256')),
                'Native sealed ownership changed')
        require(new['inventory_row']['used'] <= old['inventory_row']['used'], 'GPU charge remains after explicit cleanup')
    require(before['host']['retired_caps'] == after['host']['retired_caps'], 'Pinned retirement proof changed')
    zero_charge(after, 'final')


def zero_charge(snapshot, phase):
    targets = snapshot['host']['targets']
    require(len(targets) == 2 and all(type(t['inventory_row'].get('used')) is int
        and t['inventory_row']['used'] == 0 for t in targets), 'Exact ' + phase + ' zero native charges required')


def assess_bounded(mps, peer):
    def one(rows, key, value):
        values = [r for r in rows if r.get(key) == value]
        require(len(values) == 1, 'Exact single ' + value + ' event required'); return values[0]
    oversized = one(mps, 'phase', 'oversized-denial')
    require(oversized.get('cuda_result')==2 and oversized.get('attempted_mib')==10496,'Exact oversized CUDA OOM required')
    registered = one(mps, 'phase', 'mps-registered')
    oom = one(mps, 'phase', 'typed-oom'); recovery = one(mps, 'phase', 'recovery-passed')
    cleaned = one(mps, 'phase', 'daemon-cleanup-confirmed'); completed = one(mps, 'state', 'bounded-sequence-passed')
    require(all(type(oom.get(k)) is int for k in ('cuda_result', 'held_mib', 'attempted_mib'))
        and oom['cuda_result'] == 2 and 9216 <= oom['held_mib'] <= 10240
        and oom['attempted_mib'] == oom['held_mib'] + 256 <= 10496, 'Bounded typed aggregate CUDA OOM required')
    require(len({r.get('run_id') for r in (registered, oom, recovery, cleaned)}) == 1
        and registered['monotonic_ns'] < oom['monotonic_ns'] < recovery['monotonic_ns'] < cleaned['monotonic_ns'],
        'One ordered actual MPS session required')
    require(recovery.get('clients') == 2 and cleaned.get('completed') is True
        and cleaned.get('client_exit_codes') == [0, 0] and cleaned.get('cleanup_errors') == []
        and cleaned.get('private_mps_processes') == [], 'Explicit successful client and daemon cleanup required')
    require(completed.get('case') == 'oom' and completed.get('cap_mib') == 10240
        and completed.get('max_attempted_mib') == 10496 and completed.get('source_sha256') == PROBE_SHA
        and completed.get('aggregate_sequence_passed') is True and completed.get('recovery_clients') == 2
        and completed.get('typed_oom') == {k: oom[k] for k in ('cuda_result', 'held_mib', 'attempted_mib')}
        and completed.get('production_qualified') is False, 'Actual reviewed probe completion required')
    result = one(peer, 'phase', 'receipt')
    require(result.get('case') == 'peer' and result.get('state') == 'measurement-completed'
        and result.get('peer_loop_passed') is True and result.get('production_qualified') is False
        and all(result.get('hardware', {}).get(k) == v for k, v in {'gpu_uuid': GPU, 'uid': 1000, 'gid': 100}.items()),
        'Opposite-Hub peer verified-vector completion required')
    ticks = [r['monotonic_ns'] for r in peer if r.get('phase') == 'peer_tick']
    require(len(ticks) >= 3 and ticks[0] <= registered['monotonic_ns'] and ticks[-1] >= cleaned['monotonic_ns']
        and all(0 < b-a <= 3_000_000_000 for a, b in zip(ticks, ticks[1:])), 'Peer continuity must bracket MPS OOM/recovery/cleanup')
    return {'measurement_passed': True, 'production_qualified': False, 'held_mib': oom['held_mib'],
            'attempted_mib': oom['attempted_mib'], 'peer_ticks': len(ticks), 'pending': ['Root review of hardware receipts']}


def sealed_sample(before, sample):
    require(sample['pods'] == before['pods'], 'Charge sample changed actual Pod lifetimes')
    old = before['host']; host = sample['host']
    require(len(host['targets']) == len(old['targets']) == 2
        and host['retired_caps'] == old['retired_caps'], 'Complete unchanged historical charge sample required')
    for prior, current in zip(old['targets'], host['targets']):
        require(all(prior[k] == current[k] for k in ('pod_uid', 'intent', 'identity', 'seal_id',
            'journal_sha256', 'gate_sha256')), 'Native seal changed during charge sampling')
        row = current['inventory_row']; cap = current['intent']['cap_mib'] * 1048576
        require(row['offline'] is False and row['pinned'] is True and row['default_hierarchy'] is True
            and row['soft'] == row['hard'] == cap and type(row['used']) is int and 0 <= row['used'] <= cap,
            'Exact finite active native charge required')
    require(type(host.get('observed_at_ns')) is int, 'Actual trusted host charge timestamp required')


def assess(mps, peer, charges=None, before=None):
    def one(phase):
        found = [e for e in mps if e.get('phase') == phase]
        require(len(found) == 1, 'Exact single sustained ' + phase + ' event required')
        return found[0]
    start = one('sustained-work-started'); end = one('sustained-work-completed')
    result = assess_bounded(mps, peer)
    registered = one('mps-registered'); oom = one('typed-oom'); recovery = one('recovery-passed')
    cleaned = one('daemon-cleanup-confirmed')
    completion = [e for e in mps if e.get('state') == 'bounded-sequence-passed'][0]
    require(registered.get('environment_controls') == ['CUDA_MPS_LOG_DIRECTORY', 'CUDA_MPS_PIPE_DIRECTORY']
        and registered.get('control_sha256') == CONTROL_SHA and registered.get('server_sha256') == SERVER_SHA,
        'Exact ordinary private MPS binaries/environment required')
    require(completion.get('duration_seconds') == 120 and completion.get('total_budget_seconds') == 175
        and completion.get('cleanup_reserve_seconds') == 25,
        'Separate sustained work/cleanup budgets required')
    ordered = [registered, oom, start, end, recovery, cleaned]
    require(len({e.get('run_id') for e in ordered}) == 1
        and all(type(e.get(k)) is int for e in ordered for k in ('monotonic_ns', 'wall_ns'))
        and all(a['monotonic_ns'] < b['monotonic_ns'] for a, b in zip(ordered, ordered[1:]))
        and all(a['wall_ns'] < b['wall_ns'] for a, b in zip(ordered, ordered[1:])),
        'One ordered sustained OOM/work/recovery/cleanup required')
    ticks = [e for e in mps if e.get('phase') == 'sustained-kernel-tick']
    require(len(ticks) >= 41 and all(e.get('run_id') == start['run_id'] and e.get('clients') == 2
        and e.get('vector_verified') is True and e.get('held_mib') == oom['held_mib']
        and type(e.get('tick')) is int and e['tick'] == i + 1
        and type(e.get('monotonic_ns')) is int and type(e.get('wall_ns')) is int
        for i, e in enumerate(ticks)), 'Two actual verified kernel streams with held aggregate required')
    require(start['monotonic_ns'] <= ticks[0]['monotonic_ns'] <= start['monotonic_ns'] + 1_000_000_000
        and ticks[-1]['monotonic_ns'] <= end['monotonic_ns'] <= ticks[-1]['monotonic_ns'] + 1_000_000_000
        and ticks[-1]['monotonic_ns'] - ticks[0]['monotonic_ns'] >= 120_000_000_000
        and all(0 < b['monotonic_ns'] - a['monotonic_ns'] <= 3_000_000_000 for a, b in zip(ticks, ticks[1:]))
        and all(0 < b['wall_ns'] - a['wall_ns'] <= 3_000_000_000 for a, b in zip(ticks, ticks[1:])),
        'Minimum120s continuous verified GPU work required; sleep cannot qualify')
    work_ns = ticks[-1]['monotonic_ns'] - ticks[0]['monotonic_ns']
    require(end.get('actual_work_ns') == completion.get('sustained_work_ns') == work_ns
        and end.get('kernel_ticks') == completion.get('sustained_kernel_ticks') == len(ticks)
        and end.get('minimum_seconds') == start.get('minimum_seconds') == 120
        and end.get('clients') == start.get('clients') == 2
        and end.get('held_mib') == start.get('held_mib') == oom['held_mib']
        and cleaned['monotonic_ns'] - registered['monotonic_ns'] <= 175_000_000_000,
        'Actual sustained kernel counters/bounded completion required')
    require(isinstance(charges, list) and 8 <= len(charges) <= 100 and isinstance(before, dict),
        'Trusted continuous native charge samples required')
    selected = []
    for sample in charges:
        sealed_sample(before, sample)
        at = sample['host']['observed_at_ns']
        if ticks[0]['wall_ns'] <= at <= ticks[-1]['wall_ns']:
            targets = sample['host']['targets']
            require(targets[1]['inventory_row']['used'] >= oom['held_mib'] * 1048576
                and targets[0]['inventory_row']['used'] > 0, 'Held MPS aggregate and healthy peer charge required')
            selected.append(at)
    require(len(selected) >= 8 and selected[0] - ticks[0]['wall_ns'] <= 15_000_000_000
        and ticks[-1]['wall_ns'] - selected[-1] <= 15_000_000_000
        and all(0 < b - a <= 15_000_000_000 for a, b in zip(selected, selected[1:])),
        'Native charge samples must cover the full120s GPU work interval')
    return {**result, 'sustained_measurement_passed': True, 'actual_work_ns': work_ns,
        'sustained_kernel_ticks': len(ticks), 'held_charge_samples': len(selected),
        'minimum_gpu_work_seconds': 120, 'production_qualified': False}


class ChargeSampler:
    """Repeat the exact existing read-only authority preflight; retain every raw result."""
    def __init__(self, h, config, before, mps):
        self.samples = []; self.error = None; self.stop = threading.Event()
        def collect():
            try:
                while not self.stop.is_set() and mps.process.poll() is None:
                    sample = h.preflight(config); sealed_sample(before, sample)
                    require(len(self.samples) < 100, 'Bounded native charge sample count exceeded')
                    self.samples.append(sample)
                    self.stop.wait(2)
            except BaseException as error: self.error = type(error).__name__
        self.thread = threading.Thread(target=collect, daemon=True); self.thread.start()

    def finish(self):
        self.stop.set(); self.thread.join(timeout=30)
        require(not self.thread.is_alive() and self.error is None, 'Trusted native charge sampling failed')
        return self.samples


class Session:
    def __init__(self, target, argv, source, output, trial):
        self.events = []; self.error = None; self.condition = threading.Condition()
        self.log = open(output / 'mps.jsonl', 'xb'); os.chmod(self.log.name, 0o600)
        self.stderr = open(output / 'mps.stderr', 'xb'); os.chmod(self.stderr.name, 0o600)
        self.process = None; self.reader = None; self.writer = None; self.started = time.monotonic()
        try:
            self.process = subprocess.Popen(['kubectl', '-n', target['namespace'], 'exec', '-i', target['name'],
                '-c', 'notebook', '--', 'python', '-I', '-S', '-u', '-c', LAUNCH_SOURCE, PROBE_SHA, trial, *argv],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr)
            def read():
                size = 0
                try:
                    for line in self.process.stdout:
                        size += len(line); require(size <= 2*1024*1024 and len(line) <= 65536, 'Bounded MPS event log required')
                        event = json.loads(line); require(isinstance(event, dict), 'Typed MPS event required')
                        self.log.write(line); self.log.flush()
                        with self.condition: self.events.append(event); self.condition.notify_all()
                except BaseException as error: self.error = type(error).__name__
                finally:
                    with self.condition: self.condition.notify_all()
            self.reader = threading.Thread(target=read, daemon=True); self.reader.start()
            def send():
                try:
                    self.process.stdin.write(source); self.process.stdin.flush(); self.process.stdin.close()
                except BaseException as error:
                    self.error = type(error).__name__
                    with self.condition: self.condition.notify_all()
            self.writer = threading.Thread(target=send, daemon=True); self.writer.start(); self.writer.join(timeout=25)
            require(not self.writer.is_alive() and not self.error, 'Bounded MPS source transfer failed')
        except BaseException:
            if self.process is not None and self.process.poll() is None:
                try: self.process.kill(); self.process.wait(timeout=5)
                except BaseException: pass
            try: self.finish()
            except BaseException: pass
            raise

    def wait(self, phase, timeout=35):
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                values = [e for e in self.events if e.get('phase') == phase]
                if values: require(len(values) == 1, 'Duplicate MPS phase'); return values[0]
                require(not self.error and self.process.poll() is None and time.monotonic() < deadline, 'MPS phase absent/failed')
                self.condition.wait(0.05)

    def finish(self):
        errors = []
        if self.process is not None:
            try: require(self.process.wait(timeout=max(1, 200 - (time.monotonic() - self.started))) == 0, 'MPS transport/probe failed')
            except BaseException as error:
                errors.append(type(error).__name__)
                if self.process.poll() is None:
                    # Local kubectl only. Remote cleanup is unproven on timeout.
                    try: self.process.kill(); self.process.wait(timeout=5)
                    except BaseException as caught: errors.append(type(caught).__name__)
            if self.reader is not None:
                self.reader.join(timeout=3)
                if self.reader.is_alive(): errors.append('reader not reaped')
            if self.writer is not None:
                self.writer.join(timeout=3)
                if self.writer.is_alive(): errors.append('writer not reaped')
            for stream in (self.process.stdin, self.process.stdout):
                if stream is self.process.stdin and self.writer is not None and self.writer.is_alive(): continue
                try: stream.close()
                except BaseException as error: errors.append(type(error).__name__)
        for stream in (self.log, self.stderr):
            try: stream.close()
            except BaseException as error: errors.append(type(error).__name__)
        require(not errors and not self.error, 'MPS local transport/remote cleanup unresolved')
        launch = [e for e in self.events if e.get('phase') == 'mps-launcher-complete']
        require(len(launch) == 1 and launch[0].get('child_exit_code') == 0 and launch[0].get('cancelled') is False,
            'Actual unchanged probe process must exit and reap')
        return self.events


def finish_all(sessions):
    values, errors = [], []
    for session in sessions:
        try: values.append(session.finish())
        except BaseException as error: values.append(None); errors.append(type(error).__name__)
    return values, errors


def registration_processes(event):
    clients, daemons = event.get('clients'), event.get('daemon_processes')
    require(isinstance(clients, list) and len(clients) == 2 and isinstance(daemons, list) and len(daemons) == 2,
        'Exactly two actual clients and private control/server required')
    processes = []
    for role, value in [(f'client{i}', c['identity']) for i, c in enumerate(clients)] + [
            (d['executable'].removeprefix('nvidia-cuda-mps-'), d) for d in daemons]:
        require(role in ('client0', 'client1', 'control', 'server') and value.get('uid') == 1000 and value.get('gid') == 100
            and type(value.get('start_ticks')) is int and value['start_ticks'] > 0
            and isinstance(value.get('namespace_pids'), list) and value['namespace_pids']
            and all(type(pid) is int and pid > 0 for pid in value['namespace_pids']), 'Typed actual non-root MPS process identity required')
        processes.append({'role': role, 'namespace_pid': value['namespace_pids'][-1], 'start_ticks': value['start_ticks']})
    require({p['role'] for p in processes} == {'client0', 'client1', 'control', 'server'}
        and len({p['namespace_pid'] for p in processes}) == 4, 'Distinct private process lifetimes required')
    require(sorted(event.get('registered_clients', [])) == sorted(p['namespace_pid'] for p in processes if p['role'].startswith('client'))
        and event.get('registered_server') == next(p['namespace_pid'] for p in processes if p['role'] == 'server'),
        'Actual MPS server/client registration must match live process identities')
    return processes


def attribute(h, before, config, trial, target_index, registered, started, *, original=None):
    processes = registration_processes(registered)
    request = {'preflight': {'node': h.NODE, 'node_uid': h.NODE_UID, 'boot_id': h.BOOT, 'gpu_uuid': h.GPU,
        'driver_generation': config['driver_generation'], 'core_sha256': h.CORE, 'uvm_sha256': h.UVM,
        'health_sha256': h.HEALTH_SHA, 'cap_bytes': h.CAP, 'budget_bytes': h.BUDGET_BYTES, 'targets': before['pods'],
        'controller_sha256': h.CONTROLLER_SHA, 'retired_caps': h.retired_whitelist(config['driver_generation'])},
        'preflight_source': h.HOST_SOURCE, 'identity': before['host']['targets'][target_index]['identity'],
        'trial_id': trial, 'pipe': started['pipe'], 'probe_path': '/tmp/cps-mps-wrapper-' + trial + '/mps_probe.py',
        'processes': processes, 'mode': 'cleaned' if original is not None else 'live', 'original': original or []}
    if hasattr(h, 'TERMINAL_HISTORY'):
        # The reviewed v2 host reader authenticates its historical exception;
        # it is never reinterpreted as a finite normal retirement by MPS.
        request['preflight']['terminal_history'] = h.TERMINAL_HISTORY
    observed = h.checked_run(h.OBSERVER_ARGV, source=h.python_stdin_source(MAPPER_SOURCE, request), timeout=25)
    require(observed.get('kind') == 'root-mps-process-attribution' and observed.get('mode') == request['mode']
        and observed.get('trial_id') == trial and observed.get('pod_uid') == request['identity']['pod_uid']
        and observed.get('driver_generation') == config['driver_generation']
        and type(observed.get('observed_time_ns')) is int and 0 <= time.time_ns()-observed['observed_time_ns'] <= 30_000_000_000,
        'Fresh actual Root MPS attribution required')
    require(len(observed.get('processes', [])) == (0 if original is not None else 4), 'Complete Root process attribution required')
    for snapshot in (observed['before'], observed['after']):
        expected_targets = before['host']['targets']
        require(len(snapshot['targets']) == len(expected_targets) == 2
            and all(all(old[k] == current[k] for k in ('identity', 'intent', 'seal_id', 'journal_sha256', 'gate_sha256'))
                    for old, current in zip(expected_targets, snapshot['targets']))
            and snapshot['retired_caps'] == before['host']['retired_caps'], 'Root native attribution seals changed')
    if original is None:
        actual = observed['processes']; expected = {p['role']: p for p in processes}
        require({p.get('role') for p in actual} == set(expected), 'Exact Root MPS roles required')
        for p in actual:
            declared = expected[p['role']]
            require(set(p) == {'role', 'host_pid', 'host_tgid', 'pid_start_ticks', 'namespace_pid',
                              'pid_namespace_inode', 'process_cgroup_relative', 'pod_cgroup_inode', 'cmdline_sha256'}
                and all(type(p.get(k)) is int and p[k] > 0 for k in ('host_pid', 'host_tgid', 'pid_start_ticks',
                        'namespace_pid', 'pid_namespace_inode', 'pod_cgroup_inode'))
                and p['host_pid'] == p['host_tgid'] and p['namespace_pid'] == declared['namespace_pid']
                and p['pid_start_ticks'] == declared['start_ticks']
                and p['pod_cgroup_inode'] == request['identity']['cgroup_inode'], 'Exact Root process lifetime required')
            relative = request['identity']['cgroup_relative']; current = p['process_cgroup_relative']
            require(isinstance(current, str) and (current == relative or current.startswith(relative + '/'))
                and isinstance(p['cmdline_sha256'], str) and re.fullmatch('[a-f0-9]{64}', p['cmdline_sha256']),
                'Exact sealed Root process parent and argv hash required')
        require(len({p['host_tgid'] for p in actual}) == 4 and len({p['pid_namespace_inode'] for p in actual}) == 1,
                'Distinct same-namespace Root MPS lifetimes required')
    return observed


def run(args, h, output):
    config = {'observer_uid': args.observer_pod_uid, 'driver_generation': args.driver_generation,
        'targets': [{'namespace': 'jupyterhub', 'name': 'jupyter-cpsnativegroupb--rtc', 'pod_uid': args.cps_pod_uid},
                    {'namespace': 'cit-jhub', 'name': 'jupyter-citnativegroupa--rtc', 'pod_uid': args.cit_pod_uid}]}
    receipt = {'state': 'inconclusive', 'production_qualified': False, 'config': config,
        'probe_sha256': PROBE_SHA, 'preflight_sha256': PREFLIGHT_SHA, 'host_mapper_sha256': hashlib.sha256(MAPPER_SOURCE.encode()).hexdigest()}
    sessions = []; error = None; registered = started = live = before = sampler = None
    trial = str(uuid.uuid4()); index = 0 if args.mps_hub == 'cps' else 1
    try:
        before = h.preflight(config); h.write_json(output/'before.json', before)
        zero_charge(before, 'initial')
        probe = Path(__file__).with_name('mps_probe.py').read_bytes()
        peer_source = Path(__file__).parent.parent.joinpath('group_probe.py').read_bytes()
        require(hashlib.sha256(probe).hexdigest() == PROBE_SHA and hashlib.sha256(peer_source).hexdigest() == h.PROBE_SHA,
            'Exact reviewed MPS and peer sources required')
        peer = h.ProbeRun(before['pods'][1-index], 'peer', 180, peer_source, output)
        # Adapt only the local interface; peer.complete retains its own cleanup.
        peer.finish = peer.complete; sessions.append(peer)
        peer.wait(lambda rows: any(e.get('phase') == 'peer_tick' for e in rows), 20)
        argv = ['--execute', '--case', 'oom', '--duration', '120', '--total-budget', '175', '--source-sha256', PROBE_SHA,
            '--control-sha256', CONTROL_SHA, '--server-sha256', SERVER_SHA,
            '--expected-gpu-uuid', GPU, '--expected-pod-uid', config['targets'][index]['pod_uid'],
            '--expected-driver-generation', GENERATION]
        mps = Session(before['pods'][index], argv, probe, output, trial); sessions.append(mps)
        started = mps.wait('daemon-started'); registered = mps.wait('mps-registered')
        sampler = ChargeSampler(h, config, before, mps)
        live = attribute(h, before, config, trial, index, registered, started)
        h.write_json(output/'live-processes.json', live)
    except BaseException as caught:
        error = caught; receipt['error_type'] = type(caught).__name__
    finally:
        values, failures = finish_all(sessions)
        if failures: receipt['cleanup_errors'] = failures; error = error or RuntimeError('Transport cleanup failed')
    try:
        require(error is None and len(values) == 2 and live is not None, 'Incomplete MPS run or cleanup')
        charges = sampler.finish(); h.write_json(output/'native-charge-samples.json', charges)
        receipt['measurement'] = assess(values[1], values[0], charges, before)
        cleaned = attribute(h, before, config, trial, index, registered, started, original=live['processes'])
        h.write_json(output/'host-cleaned.json', cleaned)
        after = h.preflight(config); h.write_json(output/'after.json', after); unchanged(before, after)
        receipt['state'] = 'sustained120-mps-peer-charge-and-cleanup-measurements-passed'
    except BaseException as caught:
        error = caught; receipt['state'] = 'inconclusive'; receipt['error_type'] = type(caught).__name__
        if sampler is not None:
            sampler.stop.set(); sampler.thread.join(timeout=30)
            if not (output/'native-charge-samples.json').exists():
                h.write_json(output/'native-charge-samples.json', sampler.samples)
            receipt['charge_sampler_error'] = sampler.error
    h.write_json(output/'receipt.json', receipt)
    return receipt, error


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--execute', action='store_true')
    p.add_argument('--mps-hub', choices=('cps', 'cit'), default='cit')
    for name in ('cps-pod-uid', 'cit-pod-uid', 'observer-pod-uid', 'driver-generation', 'wrapper-source-sha256'):
        p.add_argument('--'+name)
    p.add_argument('--output', type=Path); args = p.parse_args(argv)
    own_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if not args.execute:
        print(json.dumps({'state': 'inert', 'gpu_calls': False, 'api_calls': False, 'production_qualified': False,
            'source_sha256': own_sha, 'host_mapper_sha256': hashlib.sha256(MAPPER_SOURCE.encode()).hexdigest()})); return
    require(args.wrapper_source_sha256 == own_sha and args.driver_generation == GENERATION
        and args.output is not None, 'Exact reviewed wrapper/current generation/output required')
    require(args.mps_hub=='cit','This controlled MPS probe requires the10GiB CIT target')
    h = load_preflight()
    for value in (args.cps_pod_uid, args.cit_pod_uid, args.observer_pod_uid): h.canonical_uuid(value)
    require(args.cps_pod_uid != args.cit_pod_uid, 'Distinct opposite-Hub actual Pods required')
    parent = args.output.parent.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and stat.S_IMODE(parent.st_mode) == 0o700,
        'Private owned output parent required'); args.output.mkdir(mode=0o700)
    def cancelled(signum, frame): raise InterruptedError('Operator cancelled; cleanup required')
    prior = {s: signal.signal(s, cancelled) for s in (signal.SIGINT, signal.SIGTERM)}
    try: receipt, error = run(args, h, args.output)
    finally:
        for sig, handler in prior.items(): signal.signal(sig, handler)
    print(json.dumps({'state': receipt['state'], 'production_qualified': False, 'receipt': str(args.output/'receipt.json')}))
    if error is not None: raise SystemExit(1)


if __name__ == '__main__': main()

"""Unchanged trusted MPS measurement/transport engine; no old authority loader."""
import json,os,subprocess,threading,time
from pathlib import Path
PROBE_SHA='a235f486239056bedf2afd6e48536c5024da5efa62340a6e7d3545dd0a1b4a8e'
GPU='GPU-16128952-b438-556a-00bb-93039ee24e56'
LAUNCH_SOURCE="import hashlib,json,os,signal,stat,subprocess,sys,tempfile\nfrom pathlib import Path\nif os.getuid()!=1000 or os.getgid()!=100:raise ValueError('UID1000/GID100 launcher required')\nraw=sys.stdin.buffer.read(100001)\nif not 0<len(raw)<=100000 or hashlib.sha256(raw).hexdigest()!=sys.argv[1]:raise ValueError('Exact probe source required')\ndirectory=Path('/tmp')/('cps-mps-wrapper-'+sys.argv[2]);directory.mkdir(mode=0o700)\npath=directory/'mps_probe.py';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)\nwith os.fdopen(fd,'wb') as f:f.write(raw)\ncancelled=[]\ndef cancel(signum,frame):cancelled.append(signum)\nsignal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)\ncode=None\ntry:\n child=subprocess.Popen([sys.executable,'-I','-S',str(path),*sys.argv[3:]],stdin=subprocess.DEVNULL)\n # A transport cancellation does not kill MPS or skip the probe's finally.\n code=child.wait(timeout=155)\nfinally:\n # If the reviewed probe did not exit, its cleanup is unknown and Root must\n # stop the owning Pod. Never forge a success or signal an unverified daemon.\n if code is not None:path.unlink();directory.rmdir()\nprint(json.dumps({'phase':'mps-launcher-complete','child_exit_code':code,'cancelled':bool(cancelled)}),flush=True)\nif code!=0 or cancelled:raise SystemExit(1)\n"

def require(ok, message):
    if not ok: raise ValueError(message)

def assess(mps, peer):
    def one(rows, key, value):
        values = [r for r in rows if r.get(key) == value]
        require(len(values) == 1, 'Exact single ' + value + ' event required'); return values[0]
    registered = one(mps, 'phase', 'mps-registered')
    oom = one(mps, 'phase', 'typed-oom'); recovery = one(mps, 'phase', 'recovery-passed')
    cleaned = one(mps, 'phase', 'daemon-cleanup-confirmed'); completed = one(mps, 'state', 'bounded-sequence-passed')
    require(all(type(oom.get(k)) is int for k in ('cuda_result', 'held_mib', 'attempted_mib'))
        and oom['cuda_result'] == 2 and 4096 <= oom['held_mib'] <= 5120
        and oom['attempted_mib'] == oom['held_mib'] + 256 <= 5376, 'Bounded typed aggregate CUDA OOM required')
    require(len({r.get('run_id') for r in (registered, oom, recovery, cleaned)}) == 1
        and registered['monotonic_ns'] < oom['monotonic_ns'] < recovery['monotonic_ns'] < cleaned['monotonic_ns'],
        'One ordered actual MPS session required')
    require(recovery.get('clients') == 2 and cleaned.get('completed') is True
        and cleaned.get('client_exit_codes') == [0, 0] and cleaned.get('cleanup_errors') == []
        and cleaned.get('private_mps_processes') == [], 'Explicit successful client and daemon cleanup required')
    require(completed.get('case') == 'oom' and completed.get('cap_mib') == 5120
        and completed.get('max_attempted_mib') == 5376 and completed.get('source_sha256') == PROBE_SHA
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
            try: require(self.process.wait(timeout=max(1, 175 - (time.monotonic() - self.started))) == 0, 'MPS transport/probe failed')
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


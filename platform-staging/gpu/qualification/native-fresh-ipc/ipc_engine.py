"""Reviewed IPC phases/assessment; no old cohort preflight or hardware result.

Session differs only by isolated Python -I; all original phase and cleanup guards remain.
"""
import base64
import hashlib
import json
import os
import subprocess
import threading
import time
import uuid
LOADER = ('import sys; n=int(sys.stdin.buffer.readline(32)); '
    'assert 0<n<=100000; s=sys.stdin.buffer.read(n); assert len(s)==n; '
    'exec(compile(s,"trusted-ipc-endpoint","exec"))')


def require(ok, message):
    if not ok: raise ValueError(message)


class Session:
    def __init__(self, target, args, source, label, output):
        self.events, self.error, self.label = [], None, label
        self.condition = threading.Condition()
        self.log = open(output / (label + '.jsonl'), 'xb'); os.chmod(self.log.name, 0o600)
        self.stderr = open(output / (label + '.stderr'), 'xb'); os.chmod(self.stderr.name, 0o600)
        try:
            self.process = subprocess.Popen(['kubectl', '-n', target['namespace'], 'exec', '-i', target['name'],
                '-c', 'notebook', '--', 'python', '-I', '-u', '-c', LOADER, *args],
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


def open_denied(denied,trial,attribution,witness=None):
    # Begin is acknowledged by Root before the exact controlled API command;
    # end captures the actual API result before waiting for endpoint completion.
    if witness is not None:witness.begin(attribution)
    denied.send('open',trial)
    result=denied.wait('import-result')
    kernel=witness.end(result) if witness is not None else None
    return denied.complete(),kernel


def assess_endpoint_events(exported, positive, denied, trial):
    require(str(uuid.UUID(trial)) == trial and uuid.UUID(trial).int != 0, 'Canonical current trial required')
    def one(events, phase):
        values = [e for e in events if e.get('phase') == phase]
        require(len(values) == 1 and values[0].get('trial_id') == trial, 'Exact trial phase required'); return values[0]
    handle = one(exported, 'handle-ready'); positive_result = one(positive, 'import-result'); denied_result = one(denied, 'import-result')
    raw_handle = base64.b64decode(handle['handle_b64'], validate=True)
    require(len(raw_handle) == 64 and base64.b64encode(raw_handle).decode() == handle['handle_b64']
        and hashlib.sha256(raw_handle).hexdigest() == handle['handle_sha256'], 'Exact canonical64-byte handle digest required')
    require(type(handle['buffer_bytes']) is int and handle['buffer_bytes'] == 67108864
        and positive_result['expect'] == 'allow' and type(positive_result['cuda_result']) is int and positive_result['cuda_result'] == 0
        and positive_result['api'] == 'cuIpcOpenMemHandle_v2'
        and one(positive, 'same-parent-positive')['imported_byte'] == 19, 'Same-Pod valid-handle positive control required')
    require(denied_result['expect'] == 'deny' and denied_result['api'] == 'cuIpcOpenMemHandle_v2'
        and type(denied_result['cuda_result']) is int and denied_result['cuda_result'] != 0
        and isinstance(denied_result['cuda_name'], str) and denied_result['cuda_name'].startswith('CUDA_ERROR_')
        and type(denied_result['expected_kernel_status']) is int and denied_result['expected_kernel_status'] == 27
        and type(denied_result['expected_kernel_reason']) is int and denied_result['expected_kernel_reason'] == 6
        and handle['handle_sha256'] == positive_result['handle_sha256'] == denied_result['handle_sha256'],
        'Same valid opaque handle and typed cross-Pod API result required')
    for events in (exported, positive, denied):
        completed = one(events, 'receipt')
        require(completed.get('state') == 'measurement-completed' and completed.get('explicit_native_cleanup_completed') is True
            and completed.get('cross_parent_isolation_qualified') is False, 'Explicit completed cleanup and no premature qualification required')
    for events in (positive, denied):
        require(one(events, 'importer-before-kernel')['kernel_byte'] == 11
            and one(events, 'importer-after-kernel')['kernel_byte'] == 17, 'Importer independent kernels must survive')
    recovery = one(exported, 'exporter-recovery'); one(exported, 'exporter-finished')
    require(type(denied_result['call_started_monotonic_ns']) is int and type(denied_result['call_ended_monotonic_ns']) is int
        and 0 < denied_result['call_started_monotonic_ns'] <= denied_result['call_ended_monotonic_ns']
        and type(denied_result['call_started_time_ns']) is int and type(denied_result['call_ended_time_ns']) is int
        and 0 < denied_result['call_started_time_ns'] <= denied_result['call_ended_time_ns']
        and type(denied_result['namespace_pid']) is int and denied_result['namespace_pid'] > 0, 'Actual typed call window and namespace PID required')
    require(recovery['recovery_byte'] == 37 and recovery['original_byte'] == 19
        and recovery['monotonic_ns'] > denied_result['call_ended_monotonic_ns'], 'Post-denial exporter recovery required')
    ticks = [e for e in exported if e.get('phase') == 'exporter-tick']
    require(len(ticks) >= 2 and all(e['kernel_byte'] == 19 for e in ticks)
        and [e['tick'] for e in ticks] == list(range(1, len(ticks) + 1))
        and all(e.get('trial_id') == trial and type(e['monotonic_ns']) is int and type(e['tick']) is int for e in ticks)
        and all(0 < z['monotonic_ns'] - a['monotonic_ns'] <= 5_000_000_000 for a, z in zip(ticks, ticks[1:]))
        and ticks[0]['monotonic_ns'] < denied_result['call_started_monotonic_ns']
        and ticks[-1]['monotonic_ns'] > denied_result['call_ended_monotonic_ns'], 'Exporter kernel continuity must bracket denial')
    return {'state': 'api-denial-observed-awaiting-kernel-witness', 'trial_id': trial,
        'cuda_result': denied_result['cuda_result'], 'cuda_name': denied_result['cuda_name'],
        'handle_sha256': handle['handle_sha256'], 'call_started_time_ns': denied_result['call_started_time_ns'],
        'call_ended_time_ns': denied_result['call_ended_time_ns'], 'importer_namespace_pid': denied_result['namespace_pid'],
        'same_parent_positive_control': True, 'exporter_kernel_continuity': True, 'exporter_recovery': True,
        'importer_kernels_survived': True, 'production_qualified': False, 'cross_parent_isolation_qualified': False}

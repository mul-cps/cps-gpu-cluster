#!/usr/bin/env python3
"""Inert, qualification-only per-workspace MPS probe; never sets a GPU cap."""
import argparse
import ctypes as C
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid

CONTROL = '/usr/bin/nvidia-cuda-mps-control'
SERVER = '/usr/bin/nvidia-cuda-mps-server'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
MIB, CAP_MIB, STEP_MIB, MAX_ATTEMPT_MIB = 1048576, 5120, 256, 5376
PTX = b'''.version 7.0
.target sm_70
.address_size 64
.visible .entry vector(.param .u64 output, .param .u32 bias) {
 .reg .b32 %r0, %r1, %r2; .reg .b64 %rd0, %rd1, %rd2;
 mov.u32 %r0, %tid.x; ld.param.u32 %r1, [bias]; add.u32 %r2, %r0, %r1;
 ld.param.u64 %rd0, [output]; mul.wide.u32 %rd1, %r0, 4;
 add.u64 %rd2, %rd0, %rd1; st.global.u32 [%rd2], %r2; ret;
}\n'''

def require(ok, message):
    if not ok: raise ValueError(message)

def emit(value):
    print(json.dumps({'utc': datetime.now(timezone.utc).isoformat(), 'wall_ns': time.time_ns(),
        'monotonic_ns': time.monotonic_ns(), **value}, sort_keys=True), flush=True)

def valid_uuid(value):
    try: return str(uuid.UUID(value)) == value and uuid.UUID(value).int != 0
    except (ValueError, AttributeError, TypeError): return False

def identity(pid):
    path = Path('/proc') / str(pid)
    before = path.joinpath('stat').read_text().rsplit(') ', 1)[1].split()[19]
    status = dict(line.split(':', 1) for line in path.joinpath('status').read_text().splitlines() if ':' in line)
    uid, gid = [int(x) for x in status['Uid'].split()], [int(x) for x in status['Gid'].split()]
    require(uid == [1000] * 4 and gid == [100] * 4, 'Exact non-root process UID/GID required')
    value = {'pid': pid, 'start_ticks': int(before), 'uid': 1000, 'gid': 100,
        'namespace_pids': [int(x) for x in status.get('NSpid', str(pid)).split()],
        'cgroup': path.joinpath('cgroup').read_text().strip()}
    require(before == path.joinpath('stat').read_text().rsplit(') ', 1)[1].split()[19], 'Process identity changed')
    return value

def binary_digest(path, *, executable=True):
    info = Path(path).stat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o6022
        and (not executable or os.access(path, os.X_OK)), 'Root-owned readonly injected object required')
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def pidfd_api():
    # The approved conda Python omits these bindings; its stock libc exports them.
    libc = C.CDLL(None, use_errno=True)
    require(hasattr(libc, 'pidfd_open') and hasattr(libc, 'pidfd_send_signal'),
        'Kernel-backed PID identity signalling required')
    libc.pidfd_open.argtypes = [C.c_int, C.c_uint]; libc.pidfd_open.restype = C.c_int
    libc.pidfd_send_signal.argtypes = [C.c_int, C.c_int, C.c_void_p, C.c_uint]
    libc.pidfd_send_signal.restype = C.c_int
    return libc

def open_pidfd(pid):
    fd = pidfd_api().pidfd_open(pid, 0)
    if fd < 0: raise OSError(C.get_errno(), 'pidfd_open failed')
    return fd

def send_pidfd(fd, sig):
    if pidfd_api().pidfd_send_signal(fd, sig, None, 0) < 0:
        raise OSError(C.get_errno(), 'pidfd_send_signal failed')

def preflight(args, *, child=False):
    require(os.getuid() == os.geteuid() == 1000 and os.getgid() == os.getegid() == 100,
        'Only ordinary UID1000/GID100 execution is permitted')
    pidfd_api()
    require(args.expected_gpu_uuid == GPU and valid_uuid(args.expected_pod_uid)
        and valid_uuid(args.expected_driver_generation), 'Exact reviewed GPU, Pod UID and declared generation required')
    require(not os.environ.get('LD_PRELOAD') and not os.environ.get('LD_AUDIT'), 'Raw CUDA without loader injection required')
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '0' and os.environ.get('NVIDIA_VISIBLE_DEVICES') == GPU,
        'Compiler-owned single device environment required')
    controls = {key for key in os.environ if key.startswith('CUDA_MPS_')}
    require(controls == ({'CUDA_MPS_PIPE_DIRECTORY', 'CUDA_MPS_LOG_DIRECTORY'} if child else set()),
        'Inherited shared daemon or MPS overrides forbidden')
    if child:
        pipe, logs = (Path(os.environ[key]) for key in ('CUDA_MPS_PIPE_DIRECTORY', 'CUDA_MPS_LOG_DIRECTORY'))
        require(pipe.name == 'pipe' and logs.name == 'logs' and pipe.parent == logs.parent
            and pipe.parent.parent == Path('/tmp') and pipe.parent.name.startswith('cps-mps-'),
            'Only a private per-workspace /tmp MPS session is permitted')
        for path in (pipe.parent, pipe, logs):
            info = path.lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == 1000 and stat.S_IMODE(info.st_mode) == 0o700,
                'Private ordinary-user700 MPS directories required')
    require(binary_digest(CONTROL) == args.control_sha256 and binary_digest(SERVER) == args.server_sha256,
        'Exact Root-reviewed injected MPS binary hashes required')

def aggregate_sequence(clients, mark):
    """Two held contexts alternate allocations; only actual CUDA error2 is OOM."""
    held = 0; oom = None
    try:
        require(clients[0].request('allocate', mib=64)['cuda_result'] == 0, 'Ordinary allocation failed')
        clients[0].request('free'); clients[0].request('tick'); clients[1].request('tick')
        for step in range(1, MAX_ATTEMPT_MIB // STEP_MIB + 1):
            attempted = held + STEP_MIB
            mark('before-allocation', {'held_mib': held, 'attempted_mib': attempted, 'client_index': (step - 1) % 2})
            result = clients[(step - 1) % 2].request('allocate', mib=STEP_MIB, touch=attempted <= CAP_MIB)
            if result['cuda_result'] == 2:
                oom = {'cuda_result': 2, 'held_mib': held, 'attempted_mib': attempted}; mark('typed-oom', oom); break
            require(result['cuda_result'] == 0, 'Unclassified CUDA allocation failure')
            held = attempted
            require(held <= CAP_MIB, 'Unexpected aggregate allocation above5GiB; no over-cap touch')
            mark('aggregate-held', {'held_mib': held})
            for client in clients: client.request('tick')
            time.sleep(0.2)
        require(oom is not None and held >= 4096, 'Meaningful aggregate cap exhaustion was not proved')
    finally:
        for client in clients: client.request('free')
        mark('after-aggregate-free', {})
    for client in clients:
        require(client.request('allocate', mib=64)['cuda_result'] == 0, 'Recovery allocation failed')
        client.request('tick'); client.request('free')
    mark('recovery-passed', {'clients': 2})
    return {'typed_oom': oom, 'recovery_clients': 2, 'aggregate_sequence_passed': True}

class DlInfo(C.Structure):
    _fields_ = [('filename', C.c_char_p), ('base', C.c_void_p), ('symbol', C.c_char_p), ('address', C.c_void_p)]

class Cuda:
    def __init__(self):
        self.lib = C.CDLL('libcuda.so.1'); self.held = []; self.context = C.c_void_p(); self.module = C.c_void_p()
        signatures = {'cuInit': [C.c_uint], 'cuDriverGetVersion': [C.POINTER(C.c_int)],
            'cuDeviceGetCount': [C.POINTER(C.c_int)], 'cuDeviceGetUuid_v2': [C.c_void_p, C.c_int],
            'cuCtxCreate_v2': [C.POINTER(C.c_void_p), C.c_uint, C.c_int], 'cuCtxDestroy_v2': [C.c_void_p],
            'cuMemAlloc_v2': [C.POINTER(C.c_uint64), C.c_size_t], 'cuMemFree_v2': [C.c_uint64],
            'cuMemsetD8_v2': [C.c_uint64, C.c_ubyte, C.c_size_t], 'cuMemcpyDtoH_v2': [C.c_void_p, C.c_uint64, C.c_size_t],
            'cuModuleLoadDataEx': [C.POINTER(C.c_void_p), C.c_void_p, C.c_uint, C.c_void_p, C.c_void_p],
            'cuModuleGetFunction': [C.POINTER(C.c_void_p), C.c_void_p, C.c_char_p], 'cuModuleUnload': [C.c_void_p],
            'cuLaunchKernel': [C.c_void_p, C.c_uint, C.c_uint, C.c_uint, C.c_uint, C.c_uint, C.c_uint,
                               C.c_uint, C.c_void_p, C.c_void_p, C.c_void_p], 'cuCtxSynchronize': []}
        for name, types in signatures.items():
            getattr(self.lib, name).argtypes = types; getattr(self.lib, name).restype = C.c_int
        dl = C.CDLL(None); dl.dladdr.argtypes = [C.c_void_p, C.POINTER(DlInfo)]; dl.dladdr.restype = C.c_int
        info = DlInfo()
        require(dl.dladdr(C.cast(self.lib.cuMemAlloc_v2, C.c_void_p), C.byref(info)) != 0 and info.filename,
            'Actual raw CUDA symbol object required')
        self.driver_object = str(Path(info.filename.decode()).resolve())
        require(Path(self.driver_object).name.startswith('libcuda.so'), 'Raw CUDA driver symbol must not resolve to an interposer')
        self.driver_object_sha256 = binary_digest(self.driver_object, executable=False)
        self.check(self.lib.cuInit(0)); count = C.c_int(); self.check(self.lib.cuDeviceGetCount(C.byref(count)))
        require(count.value == 1, 'Exactly one visible CUDA device required')
        raw = (C.c_ubyte * 16)(); self.check(self.lib.cuDeviceGetUuid_v2(raw, 0))
        require('GPU-' + str(uuid.UUID(bytes=bytes(raw))) == GPU, 'Wrong physical GPU')
        version = C.c_int(); self.check(self.lib.cuDriverGetVersion(C.byref(version))); require(version.value >= 13040, 'R615 CUDA driver API required')
        self.driver_version = version.value
        self.check(self.lib.cuCtxCreate_v2(C.byref(self.context), 0, 0))
        self.work = C.c_uint64(); self.check(self.lib.cuMemAlloc_v2(C.byref(self.work), 1024))
        self.ptx = C.create_string_buffer(PTX)
        self.check(self.lib.cuModuleLoadDataEx(C.byref(self.module), self.ptx, 0, None, None))
        self.function = C.c_void_p(); self.check(self.lib.cuModuleGetFunction(C.byref(self.function), self.module, b'vector'))
        self.tick()

    @staticmethod
    def check(code): require(code == 0, 'CUDA operation failed: ' + str(code))

    def allocate(self, mib, touch=True):
        require(type(mib) is int and mib in (64, STEP_MIB) and len(self.held) <= 20, 'Fixed bounded allocation required')
        pointer = C.c_uint64(); result = self.lib.cuMemAlloc_v2(C.byref(pointer), mib * MIB)
        if result == 0:
            self.held.append(pointer)
            if touch: self.check(self.lib.cuMemsetD8_v2(pointer, 19, mib * MIB)); self.check(self.lib.cuCtxSynchronize())
        return {'cuda_result': result, 'mib': mib, 'held_allocations': len(self.held)}

    def free(self):
        while self.held:
            self.check(self.lib.cuMemFree_v2(self.held[-1])); self.held.pop()
        return {'cuda_result': 0}

    def tick(self):
        bias = C.c_uint32(37); params = (C.c_void_p * 2)(C.cast(C.byref(self.work), C.c_void_p), C.cast(C.byref(bias), C.c_void_p))
        self.check(self.lib.cuLaunchKernel(self.function, 1, 1, 1, 256, 1, 1, 0, None, params, None))
        self.check(self.lib.cuCtxSynchronize()); result = (C.c_uint32 * 256)()
        self.check(self.lib.cuMemcpyDtoH_v2(result, self.work, 1024)); require(list(result) == [i + 37 for i in range(256)], 'Vector kernel mismatch')
        return {'cuda_result': 0, 'vector_elements': 256, 'vector_verified': True}

    def close(self):
        self.free(); self.check(self.lib.cuModuleUnload(self.module)); self.check(self.lib.cuMemFree_v2(self.work)); self.check(self.lib.cuCtxDestroy_v2(self.context))

def worker():
    cuda = Cuda()
    try:
        print(json.dumps({'event': 'ready', 'identity': identity(os.getpid()), 'cuda_driver_version': cuda.driver_version,
            'raw_cuda_object': cuda.driver_object, 'raw_cuda_object_sha256': cuda.driver_object_sha256}), flush=True)
        for line in sys.stdin:
            request = json.loads(line); op = request.pop('op')
            require(op in ('tick', 'allocate', 'free', 'close'), 'Closed client operation required')
            if op == 'close': require(not request, 'Closed close request'); break
            value = getattr(cuda, op)(**request); print(json.dumps({'event': op, **value}), flush=True)
    finally: cuda.close()

class Client:
    def __init__(self, argv, env, deadline, index, directory, *, registry=None):
        self.deadline = deadline; self.log = open(directory / ('client-' + str(index) + '.stderr'), 'xb')
        self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, env=env)
        # Retain the actual direct child before any readiness operation can fail.
        if registry is not None: registry.append(self)
        self.buffer = b''
        try:
            self.ready = self.receive(); require(self.ready.get('event') == 'ready', 'Actual CUDA client readiness required')
        except BaseException:
            close_client(self); raise

    def receive(self):
        deadline = min(time.monotonic() + 20, self.deadline)
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            require(remaining > 0 and select.select([self.process.stdout], [], [], remaining)[0], 'Client deadline exceeded')
            chunk = os.read(self.process.stdout.fileno(), 4096)
            require(chunk and len(self.buffer) + len(chunk) <= 65536, 'Client EOF/oversized reply')
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b'\n', 1)
        require(not self.buffer, 'Unsolicited client reply')
        return json.loads(line)

    def request(self, op, **values):
        require(self.process.poll() is None, 'Client exited')
        self.process.stdin.write((json.dumps({'op': op, **values}) + '\n').encode()); self.process.stdin.flush()
        value = self.receive(); require(value.get('event') == op, 'Unexpected client reply'); return value

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.write(b'{"op":"close"}\n'); self.process.stdin.flush(); self.process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired): self.process.kill(); self.process.wait(timeout=3)
        self.process.stdin.close(); self.process.stdout.close(); self.log.close()
        return self.process.returncode

def owned_processes(pipe):
    values = []
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal(): continue
        try:
            args = p.joinpath('cmdline').read_bytes().split(b'\0')
            if not args or Path(args[0].decode()).name not in (Path(CONTROL).name, Path(SERVER).name): continue
            proof = identity(int(p.name)); env = p.joinpath('environ').read_bytes().split(b'\0')
            if ('CUDA_MPS_PIPE_DIRECTORY=' + str(pipe)).encode() in env:
                values.append({**proof, 'executable': Path(args[0].decode()).name})
        except (FileNotFoundError, ProcessLookupError): continue
    return values

def control(env, command):
    result = subprocess.run([CONTROL], input=command + '\n', env=env, text=True, capture_output=True, timeout=3, check=True)
    return result.stdout.strip()

def numeric_ids(value):
    require(not value or all(re.fullmatch(r'[1-9][0-9]*', token) for token in value.split()), 'Unrecognized MPS registration output')
    return [int(token) for token in value.split()]

def registered_clients(server, ids, clients):
    require(len(ids) == 2 and len(set(ids)) == 2 and server not in ids, 'Exactly two distinct registered MPS clients required')
    matches = [[pid for pid in ids if pid in c.ready['identity']['namespace_pids']] for c in clients]
    require(all(len(row) == 1 for row in matches) and len({row[0] for row in matches}) == 2,
        'Actual worker PIDs not uniquely registered with MPS')

def close_client(client):
    errors = []
    try: client.close()
    except BaseException as error: errors.append(type(error).__name__ + ': client close failed')
    # A close error must never skip independent reaping of this direct child.
    try:
        if client.process.poll() is None: client.process.kill(); client.process.wait(timeout=3)
    except BaseException as error: errors.append(type(error).__name__ + ': client fallback failed')
    for stream in (client.process.stdin, client.process.stdout, client.log):
        try: stream.close()
        except BaseException as error: errors.append(type(error).__name__ + ': client stream close failed')
    return client.process.poll(), errors

def signal_owned(process, sig):
    # The descriptor targets this process lifetime even if the numeric PID is reused.
    fd = open_pidfd(process['pid'])
    try:
        require(identity(process['pid']) == {k: v for k, v in process.items() if k != 'executable'},
            'MPS PID replaced during cleanup')
        send_pidfd(fd, sig)
    finally: os.close(fd)

def cleanup_session(env, pipe, clients, completed, mark):
    errors = []; client_exits = []
    for client in clients:
        try:
            code, failures = close_client(client); client_exits.append(code); errors.extend(failures)
        except BaseException as error: errors.append(type(error).__name__ + ': independent child cleanup failed')
    try: control(env, 'quit')
    except BaseException as error: errors.append(type(error).__name__ + ': daemon quit failed')
    # Attempt the independent identity-fenced daemon path even after client/quit errors.
    try:
        until = time.monotonic() + 5
        while owned_processes(pipe) and time.monotonic() < until: time.sleep(0.1)
        for p in owned_processes(pipe):
            signal_owned(p, signal.SIGTERM)
        until = time.monotonic() + 3
        while owned_processes(pipe) and time.monotonic() < until: time.sleep(0.1)
        for p in owned_processes(pipe):
            signal_owned(p, signal.SIGKILL)
        until = time.monotonic() + 1
        while owned_processes(pipe) and time.monotonic() < until: time.sleep(0.1)
        require(not owned_processes(pipe), 'Private MPS processes remain; Root cleanup required')
    except BaseException as error: errors.append(type(error).__name__ + ': daemon fallback failed')
    mark('daemon-cleanup-confirmed' if not errors else 'daemon-cleanup-failed',
        {'completed': completed, 'client_exit_codes': client_exits, 'cleanup_errors': errors,
         **({'private_mps_processes': []} if not errors else {})})
    require(not errors and (not completed or client_exits == [0, 0]), 'Cleanup failed; no passing result; Root cleanup required')

def execute(args, child_argv):
    preflight(args); directory = Path(tempfile.mkdtemp(prefix='cps-mps-', dir='/tmp')); directory.chmod(0o700)
    pipe, logs = directory / 'pipe', directory / 'logs'; pipe.mkdir(mode=0o700); logs.mkdir(mode=0o700)
    env = {**os.environ, 'CUDA_MPS_PIPE_DIRECTORY': str(pipe), 'CUDA_MPS_LOG_DIRECTORY': str(logs)}
    clients = []; completed = False; deadline = time.monotonic() + args.duration - 25
    def mark(phase, value): emit({'phase': phase, 'run_id': directory.name, **value})
    try:
        started = subprocess.run([CONTROL, '-d'], env=env, capture_output=True, text=True, timeout=5, check=True)
        mark('daemon-started', {'pipe': str(pipe), 'log_directory': str(logs)})
        for index in range(2): Client(child_argv, env, deadline, index, directory, registry=clients)
        servers = numeric_ids(control(env, 'get_server_list')); require(len(servers) == 1, 'Exactly one private MPS server required')
        ids = numeric_ids(control(env, 'get_client_list ' + str(servers[0]))); registered_clients(servers[0], ids, clients)
        processes = owned_processes(pipe); server = [p for p in processes if p['executable'] == Path(SERVER).name]
        require(len(server) == 1 and servers[0] in server[0]['namespace_pids'], 'Actual non-root private server required')
        require(all(c.ready['identity']['cgroup'] == server[0]['cgroup'] for c in clients), 'Server and clients must share this workload cgroup')
        mark('mps-registered', {'server': server[0], 'registered_server': servers[0], 'registered_clients': ids,
            'clients': [c.ready for c in clients], 'daemon_processes': processes})
        # Root's independent native-cap sampler can bracket this held registration.
        time.sleep(3)
        if args.case == 'oom': result = aggregate_sequence(clients, mark)
        else:
            ticks = 0
            while time.monotonic() < deadline:
                for c in clients: c.request('tick')
                ticks += 1; mark('peer_tick', {'tick': ticks, 'clients': 2, 'vector_verified': True}); time.sleep(0.25)
            require(ticks >= 2, 'Peer coverage too short'); result = {'peer_ticks': ticks, 'peer_passed': True}
        completed = True; return result
    finally:
        cleanup_session(env, pipe, clients, completed, mark)

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--execute', action='store_true')
    p.add_argument('--case', choices=('oom', 'peer'), default='oom'); p.add_argument('--duration', type=int, default=120)
    for flag in ('source-sha256', 'control-sha256', 'server-sha256', 'expected-gpu-uuid', 'expected-pod-uid', 'expected-driver-generation'): p.add_argument('--' + flag)
    p.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = p.parse_args(argv); require(60 <= args.duration <= 120, 'Bounded60-120second probe required')
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    plan = {'kind': 'qualification-mps', 'case': args.case, 'cap_mib': CAP_MIB, 'max_attempted_mib': MAX_ATTEMPT_MIB,
        'duration_seconds': args.duration, 'source_sha256': source, 'production_qualified': False,
        'native_cap_verified_by_probe': False, 'driver_generation_verified_by_probe': False}
    if not args.execute: emit({**plan, 'state': 'inert', 'gpu_calls': False, 'api_calls': False}); return
    require(args.source_sha256 == source, 'Exact Root-reviewed probe source required')
    preflight(args, child=args.child)
    if args.child: worker(); return
    emit({**plan, 'phase': 'root-observation-required', 'declared_pod_uid': args.expected_pod_uid,
        'declared_driver_generation': args.expected_driver_generation, 'gpu_calls': False})
    forwarded = [sys.executable, str(Path(__file__).resolve()), '--execute', '--child', '--duration', str(args.duration)]
    for flag in ('source-sha256', 'control-sha256', 'server-sha256', 'expected-gpu-uuid', 'expected-pod-uid', 'expected-driver-generation'):
        forwarded += ['--' + flag, getattr(args, flag.replace('-', '_'))]
    result = execute(args, forwarded); emit({**plan, **result, 'state': 'bounded-sequence-passed', 'gpu_calls': True, 'api_calls': False})

if __name__ == '__main__': main()

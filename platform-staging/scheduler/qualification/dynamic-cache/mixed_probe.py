#!/usr/bin/env python3
"""Bounded operator-gated mixed-profile CUDA test; import never loads CUDA.

The existing compiled probe supplies the CUDA driver API and private-cache
identity checks. This module changes neither that source nor any GPU/MPS
setting. Its reports are evidence for ordinary software quotas, not proof of
hostile isolation or production readiness.
"""
import ctypes
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
import tempfile
import time

import mixed_contract as contract
import probe_compiled as core

HOLD_TICKS = 40
PEER_SECONDS = 45
PEER_TICKS = 90
PEER_MIB = 256
TARGET_DELAY_SECONDS = 30
WORKSPACE_ORDINARY_DELAY_SECONDS = 10
MAX_RUNTIME_SECONDS = 115
REVIEW_PATH = Path('/review/operator-approved.json')
PROOF_PATH = Path('/probe/preflight.json')
ROLE = None


def emit(value):
    print(json.dumps({'observedNs': time.time_ns(),
        'podUid': os.environ.get('FIXTURE_POD_UID'),
        'runId': os.environ.get('FIXTURE_RUN_ID'), 'role': ROLE,
        'profileGiB': contract.ROLES.get(ROLE), **value}, allow_nan=False), flush=True)


def configure(role):
    """Closed profile selection; children inherit the reviewed environment."""
    global ROLE
    if role not in contract.ROLES or os.environ.get('FIXTURE_ROLE') != role:
        raise RuntimeError('Exact fixture role is required')
    gib = contract.ROLES[role]
    if os.environ.get('FIXTURE_PROFILE_GIB') != str(gib):
        raise RuntimeError('Fixture role/profile mismatch')
    ROLE = role
    core.REQUESTED_MIB = core.CANONICAL_LIMIT_MIB = gib * 1024
    core.SCHEDULER_INJECTED_MIB = contract.QUOTAS[gib]['globalMiB']
    core.ALLOCATION_MIB = contract.ALLOCATIONS[gib]
    core.COMPILER_SOURCE = contract.SOURCE
    core.COMPILER_MODULE_SHA256 = contract.MODULE_SHA
    core.REVIEWED_IDENTITIES = {(contract.UID, contract.GID)}
    core.hami_provenance = hami_provenance


def compiler_provenance():
    distribution = importlib.metadata.distribution('cps-compute')
    module = distribution.locate_file('cps_compute/gpu_runtime.py')
    module_sha = hashlib.sha256(module.read_bytes()).hexdigest()
    if distribution.version != '0.1.0' or module_sha != contract.MODULE_SHA:
        raise RuntimeError('Installed compiler bytes/version differ from the pinned package')
    return {'sourceCommit': contract.SOURCE, 'moduleSha256': module_sha,
            'version': distribution.version}


def preparation(role, *, require_fresh=True):
    """Check the CPU approval again before the first CUDA child exists."""
    configure(role)
    if core.runtime_identity() != (contract.UID, contract.GID):
        raise RuntimeError('Reviewed workload identity is required')
    proof = json.loads(PROOF_PATH.read_text())
    hashes = {}
    for name in ('mixed_probe.py', 'mixed_contract.py', 'probe_compiled.py'):
        hashes[name] = hashlib.sha256((PROOF_PATH.parent / name).read_bytes()).hexdigest()
    if proof.get('sources') != hashes or proof.get('probeSha256') != contract.digest(hashes):
        raise RuntimeError('Immutable fixture source bytes changed')
    info = REVIEW_PATH.stat(follow_symlinks=False)
    if (not stat.S_ISREG(info.st_mode) or (info.st_uid, info.st_gid) != (contract.UID, contract.GID)
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or info.st_size > 16384):
        raise RuntimeError('Private regular operator marker required')
    approval = json.loads(REVIEW_PATH.read_text())
    contract.validate_approval(approval, proof, role, os.environ['FIXTURE_POD_UID'], require_fresh=require_fresh)
    if time.time_ns() >= approval['mps']['windowEndsAtNs']:
        raise TimeoutError('Reviewed MPS window expired before child initialization')
    if core.normalized_uuid(approval['gpuUuid']) != core.normalized_uuid(os.environ['EXPECTED_GPU_UUID']):
        raise RuntimeError('Reviewed/scheduler GPU identity mismatch')
    if approval['mps']['activeThreadPercentage'] != 100:
        raise RuntimeError('Mixed test requires independently reviewed active-thread ceiling 100')
    return proof, approval, compiler_provenance()


def hami_provenance():
    """Verify loaded binary/inode and the selected canonical per-device quota."""
    gib = contract.ROLES[ROLE]
    quotas = contract.QUOTAS[gib]
    expected = os.environ.get('EXPECTED_HAMI_SHA256', '')
    if (os.environ.get('EXPECTED_HAMI_REVISION') != core.HAMI_REVISION or not contract.sha(expected)
            or os.environ.get('CUDA_DEVICE_MEMORY_LIMIT') != str(quotas['globalMiB']) + 'm'
            or os.environ.get('GPU_PORTION') != quotas['portion']
            or os.environ.get('CUDA_DEVICE_MEMORY_LIMIT_0') != str(gib * 1024) + 'm'
            or os.environ.get('EXPECTED_HAMI_LIMIT_MIB') != str(gib * 1024)):
        raise RuntimeError('Reviewed scheduler metadata and canonical indexed quota required')
    path = Path(core.HAMI_PATH)
    before = path.stat()
    binary_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    after = path.stat()
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    if identity(before) != identity(after) or binary_sha != expected:
        raise RuntimeError('HAMi byte identity changed')
    mappings = []
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5] == core.HAMI_PATH:
            major, minor = (int(value, 16) for value in fields[3].split(':'))
            mappings.append((os.makedev(major, minor), int(fields[4])))
    if not mappings or any(value != (after.st_dev, after.st_ino) for value in mappings):
        raise RuntimeError('Reviewed HAMi inode is not loaded')
    configured = os.environ.get('LD_PRELOAD', '').replace(':', ' ').split()
    preload = Path('/etc/ld.so.preload')
    if preload.exists():
        contents = preload.read_text()
        if len(contents) > 4096:
            raise RuntimeError('Unexpected preload configuration')
        configured.extend(word for line in contents.splitlines()
                          for word in line.split('#', 1)[0].split())
    if core.HAMI_PATH not in configured:
        raise RuntimeError('Reviewed HAMi preload is absent')
    library = ctypes.CDLL(core.HAMI_PATH, mode=os.RTLD_NOLOAD | os.RTLD_NOW)
    library.get_current_device_memory_limit.argtypes = [ctypes.c_int]
    library.get_current_device_memory_limit.restype = ctypes.c_uint64
    limit = library.get_current_device_memory_limit(0)
    if limit != gib * 1024**3:
        raise RuntimeError('Effective HAMi quota does not match the selected profile')
    return library, {'referenceSourceRevision': core.HAMI_REVISION, 'sourceRevisionVerified': False,
        'libraryPath': core.HAMI_PATH, 'sha256': binary_sha, 'loaded': True, 'preloadVerified': True,
        'schedulerInjectedLimitBytes': quotas['globalMiB'] * 1024**2,
        'canonicalLimitBytes': gib * 1024**3, 'perDeviceLimitVerified': True,
        'effectiveLimitBytes': limit, 'device': after.st_dev, 'inode': after.st_ino}


class Cuda(core.Cuda):
    """Reuse driver/context core and write the complete allocation initially."""

    def __init__(self):
        self.sizes = {}
        self.full_write = set()
        self.last_write = {}
        super().__init__()

    def allocate(self, label, mib):
        if type(mib) is not int or mib <= 0 or label in self.sizes:
            raise ValueError('Positive integer allocation and fresh label required')
        self.sizes[label] = mib * 1024**2
        self.full_write.add(label)
        try:
            value = super().allocate(label, mib)
            if value['cudaResult'] == 0:
                value.update(self.last_write[label])
            else:
                del self.sizes[label]
                self.full_write.discard(label)
            return value
        except BaseException:
            if label not in self.allocations:
                self.sizes.pop(label, None)
                self.full_write.discard(label)
            raise

    def tick(self, label):
        count = self.sizes[label] if label in self.full_write else min(self.sizes[label], 1024**2)
        started = time.time_ns()
        self.check(self.lib.cuMemsetD8_v2(self.allocations[label], 17, count), 'cuMemsetD8')
        self.check(self.lib.cuCtxSynchronize(), 'cuCtxSynchronize')
        receipt = {'writeBytes': count, 'writeStartedNs': started, 'writeFinishedNs': time.time_ns()}
        self.full_write.discard(label)
        self.last_write[label] = receipt
        return {'label': label, 'cudaResult': 0, **receipt}

    def free(self, label):
        value = super().free(label)
        self.sizes.pop(label, None)
        self.last_write.pop(label, None)
        self.full_write.discard(label)
        return value


def child():
    role = os.environ['FIXTURE_ROLE']
    proof, approval, compiler = preparation(role, require_fresh=False)
    before = core.cache_identity()
    cuda = Cuda()
    try:
        cache = core.cache_identity(require_mapping=True)
        if (before['device'], before['inode']) != (cache['device'], cache['inode']):
            raise RuntimeError('Cache inode changed during CUDA initialization')
        emit({'event': 'ready', 'pid': os.getpid(), 'gpu': cuda.gpu,
              'cache': cache, 'hami': cuda.hami, 'compiler': compiler})
        for line in sys.stdin:
            if time.time_ns() >= approval['mps']['windowEndsAtNs']:
                raise TimeoutError('Reviewed MPS window expired')
            request = json.loads(line)
            action = request['action']
            if action == 'stop':
                break
            started = time.time_ns()
            if action == 'allocate':
                value = cuda.allocate(request['label'], request['mib'])
            elif action == 'tick':
                value = cuda.tick(request['label'])
            elif action == 'free':
                value = cuda.free(request['label'])
            else:
                raise ValueError('Unknown controlled child operation')
            current = core.cache_identity(require_mapping=True)
            if current != cache:
                raise RuntimeError('Private cache identity changed')
            emit({'event': 'response', 'id': request['id'], 'action': action,
                'pid': os.getpid(), 'gpu': cuda.gpu, 'cache': current, 'hami': cuda.hami,
                'compiler': compiler, 'operationStartedNs': started,
                'operationFinishedNs': time.time_ns(), **value})
    finally:
        cuda.close()


class Child(core.Child):
    """Same ordinary process protocol, executed through this fixed module."""

    def __init__(self, name):
        self.name = name
        self.stderr = tempfile.TemporaryFile(mode='w+')
        self.process = subprocess.Popen([sys.executable, '-u', __file__, 'child'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            text=True, bufsize=1)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        try:
            self.ready = self.receive()
            if self.ready.get('event') != 'ready':
                raise RuntimeError('Controlled CUDA child did not initialize')
        except BaseException:
            self.close()
            raise

    def receive(self, timeout=10):
        if not self.selector.select(timeout):
            raise TimeoutError('Controlled mixed CUDA child timed out')
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f'Controlled mixed CUDA child exited {self.process.poll()}')
        value = json.loads(line)
        emit({'event': 'mixed-child-evidence', 'child': self.name, 'value': value})
        return value

    def request(self, ident, action, label='ordinary', **extra):
        value = super().request(ident, action, label, **extra)
        if not valid_response(value, self.ready, ident, action, label,
                              allocation_mib=extra.get('mib')):
            raise RuntimeError('Child response identity/action/write evidence mismatch')
        return value


def valid_response(value, ready, ident, action, label, *, allocation_mib=None):
    """Do not count a code alone as a successful CUDA write or OOM receipt."""
    try:
        if (value['event'] != 'response' or value['id'] != ident or value['action'] != action
                or value['label'] != label or type(value['cudaResult']) is not int
                or value['cudaResult'] not in (0, 2)):
            return False
        if any(value[key] != ready[key] for key in ('pid', 'gpu', 'cache', 'hami', 'compiler',
                                                   'podUid', 'runId', 'role', 'profileGiB')):
            return False
        start, end = value['operationStartedNs'], value['operationFinishedNs']
        if type(start) is not int or type(end) is not int or not 0 < start <= end:
            return False
        if action == 'allocate':
            if type(allocation_mib) is not int or value['allocationMiB'] != allocation_mib:
                return False
            intervals = (value['startMonotonicNs'], value['endMonotonicNs'])
            if any(type(item) is not int for item in intervals) or not 0 < intervals[0] <= intervals[1]:
                return False
            if value['cudaResult'] == 2:
                return not any(key in value for key in ('writeBytes', 'writeStartedNs', 'writeFinishedNs'))
        elif value['cudaResult'] != 0:
            return False
        if action in ('allocate', 'tick'):
            expected_bytes = allocation_mib * 1024**2 if action == 'allocate' else 1024**2
            write_start, write_end = value['writeStartedNs'], value['writeFinishedNs']
            if (type(value['writeBytes']) is not int or value['writeBytes'] != expected_bytes
                    or type(write_start) is not int or type(write_end) is not int
                    or not start <= write_start <= write_end <= end):
                return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def ordinary_verdict(results, ready, mib):
    expected = {'aHold': ('a-hold', 'allocate', 0, 0),
        'bDenied': ('b-denied', 'allocate', 1, 2),
        'aContinued': ('a-continued', 'tick', 0, 0), 'aFree': ('a-free', 'free', 0, 0),
        'bAfterFree': ('b-after-free', 'allocate', 1, 0),
        'bContinued': ('b-continued', 'tick', 1, 0), 'bFree': ('b-free', 'free', 1, 0)}
    try:
        if set(results) != set(expected) or len(ready) != 2 or ready[0]['pid'] == ready[1]['pid']:
            return False
        previous = 0
        for key, (ident, action, index, code) in expected.items():
            value = results[key]
            if (not valid_response(value, ready[index], ident, action, 'ordinary',
                                   allocation_mib=mib if action == 'allocate' else None)
                    or value['cudaResult'] != code or value['operationStartedNs'] < previous):
                return False
            previous = value['operationFinishedNs']
        return True
    except (KeyError, TypeError):
        return False


class Clock:
    def now_ns(self):
        return time.time_ns()

    def sleep(self, seconds):
        time.sleep(seconds)


def check_window(clock, deadline):
    if clock.now_ns() >= deadline:
        raise TimeoutError('Bounded mixed-profile runtime window expired')


def wait_until(clock, target, deadline):
    while clock.now_ns() < target:
        check_window(clock, deadline)
        clock.sleep(min(0.2, (target - clock.now_ns()) / 1e9))
    check_window(clock, deadline)


def validate_children(values, role, proof, approval, compiler, *, expected_count=2):
    if len(values) != expected_count or len({value.get('pid') for value in values}) != expected_count:
        raise RuntimeError('Distinct reviewed ordinary CUDA processes required')
    cache = None
    for value in values:
        current = value['cache']; hami = value['hami']
        if (value['event'] != 'ready' or type(value['pid']) is not int or value['pid'] <= 0
                or value['role'] != role or value['profileGiB'] != contract.ROLES[role]
                or value['podUid'] != approval['podUid'] or value['runId'] != proof['runId']
                or value['compiler'] != compiler or value['gpu'] != core.normalized_uuid(approval['gpuUuid'])
                or (current['uid'], current['gid']) != (contract.UID, contract.GID)
                or current['path'] != core.CACHE_PATH or current['mappingVerified'] is not True
                or current['noTmpFallback'] is not True
                or hami['sha256'] != proof['hami']['sha256'] or hami['loaded'] is not True
                or hami['preloadVerified'] is not True or hami['perDeviceLimitVerified'] is not True
                or hami['singleVisibleDeviceVerified'] is not True
                or hami['sourceRevisionVerified'] is not False
                or hami['effectiveLimitBytes'] != contract.ROLES[role] * 1024**3
                or hami['canonicalLimitBytes'] != contract.ROLES[role] * 1024**3):
            raise RuntimeError('Actual CUDA/compiler/HAMi/cache identity differs from review')
        if cache is not None and current != cache:
            raise RuntimeError('Workspace children do not share exactly one private cache inode')
        cache = current


def ordinary(workers, mib):
    a, b = workers
    result = {}
    result['aHold'] = a.request('a-hold', 'allocate', mib=mib)
    if result['aHold']['cudaResult'] != 0:
        raise RuntimeError('First ordinary allocation failed')
    result['bDenied'] = b.request('b-denied', 'allocate', mib=mib)
    result['aContinued'] = a.request('a-continued', 'tick')
    if result['bDenied']['cudaResult'] != 2:
        raise RuntimeError('Second ordinary allocation did not return actual CUDA OOM 2')
    result['aFree'] = a.request('a-free', 'free')
    result['bAfterFree'] = b.request('b-after-free', 'allocate', mib=mib)
    if result['bAfterFree']['cudaResult'] != 0:
        raise RuntimeError('Ordinary allocation failed to recover after freeing its peer')
    result['bContinued'] = b.request('b-continued', 'tick')
    result['bFree'] = b.request('b-free', 'free')
    if not ordinary_verdict(result, [worker.ready for worker in workers], mib):
        raise RuntimeError('Ordinary OOM/write/recovery evidence is incomplete')
    return result


def hold(workers, role, target, deadline, clock, output):
    sizes = contract.HOLD_ALLOCATIONS[contract.ROLES[role]]
    allocations = [worker.request(f'hold-{index}-allocate', 'allocate', 'mixed-hold', mib=mib)
                   for index, (worker, mib) in enumerate(zip(workers, sizes))]
    if any(value['cudaResult'] != 0 for value in allocations):
        raise RuntimeError('Mixed-profile payload allocation failed')
    if clock.now_ns() >= target:
        raise TimeoutError('All payloads must be ready before the common hold target')
    output({'event': 'mixed-hold-ready', 'startTargetNs': target, 'allocations': allocations,
            'childPids': [worker.ready['pid'] for worker in workers]})
    wait_until(clock, target, deadline)
    started = clock.now_ns()
    output({'event': 'mixed-hold-start', 'startedNs': started, 'startTargetNs': target,
            'durationSeconds': contract.HOLD_SECONDS, 'payloadMiB': sum(sizes),
            'childPids': [worker.ready['pid'] for worker in workers], 'mpsThreeClientQualified': False})
    ticks = []
    for tick in range(HOLD_TICKS):
        check_window(clock, deadline)
        values = [worker.request(f'hold-{tick}-{index}', 'tick', 'mixed-hold')
                  for index, worker in enumerate(workers[:len(sizes)])]
        if any(value['cudaResult'] != 0 for value in values):
            raise RuntimeError('Mixed-profile CUDA writer stopped progressing')
        record = {'tick': tick, 'observedNs': clock.now_ns(), 'values': values}
        ticks.append(record)
        output({'event': 'mixed-hold-progress', **record})
        wait_until(clock, started + int((tick + 1) * contract.HOLD_SECONDS / HOLD_TICKS * 1e9), deadline)
    finished = clock.now_ns()
    frees = [worker.request(f'hold-{index}-free', 'free', 'mixed-hold')
             for index, worker in enumerate(workers[:len(sizes)])]
    if any(value['cudaResult'] != 0 for value in frees):
        raise RuntimeError('Mixed-profile payload cleanup failed')
    result = {'startTargetNs': target, 'startedNs': started, 'finishedNs': finished,
        'durationSeconds': contract.HOLD_SECONDS, 'payloadMiB': sum(sizes),
        'allocations': allocations, 'ticks': ticks, 'frees': frees}
    output({'event': 'mixed-hold-finished', 'startedNs': started, 'finishedNs': finished,
            'payloadMiB': sum(sizes), 'mpsThreeClientQualified': False})
    return result


def peer_progress(worker, deadline, clock, output):
    value = worker.request('peer-alive-allocate', 'allocate', 'peer-heartbeat', mib=PEER_MIB)
    if value['cudaResult'] != 0:
        raise RuntimeError('Independent peer heartbeat allocation failed')
    started = clock.now_ns()
    values = []
    try:
        for tick in range(PEER_TICKS):
            check_window(clock, deadline)
            receipt = worker.request(f'peer-alive-{tick}', 'tick', 'peer-heartbeat')
            if receipt['cudaResult'] != 0:
                raise RuntimeError('Independent peer CUDA write failed')
            record = {'tick': tick, 'observedNs': clock.now_ns(), 'value': receipt}
            values.append(record)
            output({'event': 'mixed-peer-alive', **record})
            wait_until(clock, started + int((tick + 1) * PEER_SECONDS / PEER_TICKS * 1e9), deadline)
    finally:
        free = worker.request('peer-alive-free', 'free', 'peer-heartbeat')
        if free['cudaResult'] != 0:
            raise RuntimeError('Independent peer heartbeat cleanup failed')
    return values


def run_role(role, *, child_factory=Child, clock=None, prepare=preparation, output=emit):
    """Dependency injection enables offline failure tests; CLI uses fixed APIs."""
    clock = clock or Clock()
    workers = []
    report = {'event': 'mixed-result', 'role': role, 'profileGiB': contract.ROLES[role],
        'startedNs': clock.now_ns(), 'requestedMiB': contract.ROLES[role] * 1024,
        'allocationMiB': contract.ALLOCATIONS[contract.ROLES[role]], 'compiler': None, 'approval': None,
        'children': [], 'ordinary': {}, 'ordinaryPassed': False, 'hold': None, 'peerProgress': [],
        'status': 'mixed-role-incomplete', 'productionQualified': False,
        'hostileIsolationQualified': False, 'mpsThreeClientQualified': False}
    try:
        proof, approval, compiler = prepare(role)
        report.update(compiler=compiler, approval=approval)
        deadline = min(approval['mps']['windowEndsAtNs'], report['startedNs'] + MAX_RUNTIME_SECONDS * 10**9)
        target = int(contract.instant(approval['mps']['observedAt']).timestamp() * 1e9) + TARGET_DELAY_SECONDS * 10**9
        if target + (contract.HOLD_SECONDS + WORKSPACE_ORDINARY_DELAY_SECONDS + 45) * 10**9 >= deadline:
            raise TimeoutError('Review window cannot cover the complete bounded test')
        names = ('a',) if role == 'peer5' else ('a', 'b')
        for name in names:
            check_window(clock, deadline)
            workers.append(child_factory(name))
        report['children'] = [worker.ready for worker in workers]
        validate_children(report['children'], role, proof, approval, compiler, expected_count=len(names))
        report['hold'] = hold(workers, role, target, deadline, clock, output)
        if role == 'peer5':
            # One peer context during the high-payload hold, then two ordinary
            # processes share its same private cache for the 3+3 GiB test.
            workers.append(child_factory('b'))
            report['children'] = [worker.ready for worker in workers]
            validate_children(report['children'], role, proof, approval, compiler)
        if role != 'peer5':
            wait_until(clock, target + (contract.HOLD_SECONDS + WORKSPACE_ORDINARY_DELAY_SECONDS) * 10**9, deadline)
        check_window(clock, deadline)
        report['ordinaryStartedNs'] = clock.now_ns()
        report['ordinary'] = ordinary(workers, report['allocationMiB'])
        report['ordinaryFinishedNs'] = clock.now_ns()
        report['ordinaryPassed'] = True
        if role == 'peer5':
            report['peerProgress'] = peer_progress(workers[0], deadline, clock, output)
        check_window(clock, deadline)
        report['status'] = 'bounded-mixed-role-passed'
    except Exception as error:
        report.update(errorType=type(error).__name__, error=str(error))
    finally:
        cleanup_errors = []
        for worker in workers:
            try:
                worker.close()
            except Exception as error:
                cleanup_errors.append(type(error).__name__)
        if cleanup_errors:
            report.update(status='mixed-role-incomplete', cleanupErrors=cleanup_errors)
        report['finishedNs'] = clock.now_ns()
        output(report)
    return 0 if report['status'] == 'bounded-mixed-role-passed' else 1


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in {*contract.ROLES, 'child'}:
        raise SystemExit('Use a fixed mixed fixture role')
    try:
        if sys.argv[1] == 'child':
            child()
        else:
            raise SystemExit(run_role(sys.argv[1]))
    except Exception as error:
        emit({'event': 'mixed-probe-error', 'errorType': type(error).__name__, 'error': str(error),
              'productionQualified': False, 'hostileIsolationQualified': False})
        raise SystemExit(1)

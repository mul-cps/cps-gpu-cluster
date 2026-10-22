#!/usr/bin/env python3
"""Inert default; Root streams this only after current native-cap preflight."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import threading
import time

BINARY_SHA = '0e19d4ec396dd64cabe364607fee151c001821cdcb2da5e5b181d7f902a76f69'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
CAP = 5368709120

def require(ok, message):
    if not ok: raise ValueError(message)

def emit(phase, **values):
    print(json.dumps({'kind': 'controlled-import-wrapper', 'phase': phase,
        'time_ns': time.time_ns(), 'monotonic_ns': time.monotonic_ns(),
        'production_qualified': False, **values}, sort_keys=True, allow_nan=False), flush=True)

def assess(events, code, mode):
    require(code == 0, 'Trusted participant did not exit successfully')
    identity = [e for e in events if e.get('kind') == 'identity']
    initial = [e for e in events if e.get('kind') == 'initial-cap-info']
    final = [e for e in events if e.get('kind') == 'final']
    require(len(identity) == len(initial) == len(final) == 1
        and identity[0].get('gpu_uuid') == GPU and identity[0].get('uid') == 1000 and identity[0].get('gid') == 100
        and type(identity[0].get('driver_api_version')) is int and identity[0]['driver_api_version'] >= 13040
        and type(initial[0].get('total_bytes')) is int and initial[0]['total_bytes'] == CAP
        and type(initial[0].get('free_bytes')) is int and 0 <= initial[0]['free_bytes'] < CAP
        and final[0].get('status') == 'bounded-measurement-completed'
        and final[0].get('production_qualified') is False, 'Exact capped raw-CUDA participant receipt required')
    phases = [e for e in events if e.get('kind') == 'cuda']
    require(phases and all(type(e.get('result')) is int and type(e.get('pid')) is int and e['pid'] > 0
        and type(e.get('time_ns')) is int and e['time_ns'] > 0 for e in phases), 'Typed native events required')
    require(all(e['result'] == (2 if e['phase'] == 'vmm-over-cap-never-touch' else 0) for e in phases),
        'Unexpected native CUDA result')
    names = [e['phase'] for e in phases]
    needed = {'vmm-direct': ('vmm-create-64', 'vmm-map', 'vmm-set-access', 'vmm-over-cap-never-touch', 'readback', 'vmm-unmap', 'vmm-release'),
        'ipc-export': ('ipc-allocate', 'ipc-export', 'ordinary-free'),
        'ipc-import': ('importer-own-fill-allocate', 'ipc-import', 'import-readback', 'ipc-close', 'ordinary-free'),
        'vmm-export': ('vmm-export', 'exporter-references-released-importer-retains', 'vmm-unmap', 'vmm-release'),
        'vmm-import': ('importer-own-fill-allocate', 'vmm-import', 'vmm-map', 'vmm-set-access', 'import-readback',
            'importer-retained-backing-start', 'importer-retained-backing-end', 'vmm-unmap', 'vmm-release', 'ordinary-free')}
    require(all(n in names for n in needed[mode]), 'Required native phases missing')
    if mode == 'vmm-direct':
        i = names.index('vmm-over-cap-never-touch')
        require(names.count('vmm-over-cap-never-touch') == 1 and 'vmm-create-64' in names[i + 1:]
            and 'fill-64' in names[i + 1:] and 'readback' in names[i + 1:], 'Typed OOM must precede successful recovery')
    if mode == 'vmm-import':
        require(names.index('importer-retained-backing-start') < names.index('importer-retained-backing-end')
            and 'fill-64' in names[names.index('importer-retained-backing-start') + 1:names.index('importer-retained-backing-end')],
            'Importer must touch retained backing after exporter releases references')
    return {'mode': mode, 'successful_raw_cuda_measurement': True, 'same_parent_only': mode != 'vmm-direct',
            'cross_pod_import_isolation_qualified': False, 'production_qualified': False}

class Child:
    def __init__(self, argv, label):
        self.label, self.events, self.error = label, [], None
        self.process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def collect(stream, output):
            size = 0
            try:
                for raw in stream:
                    size += len(raw); require(size <= 2 * 1024 * 1024 and len(raw) <= 65536, 'Bounded child log required')
                    if output:
                        event = json.loads(raw); require(isinstance(event, dict), 'Native JSON event required')
                        self.events.append(event); emit('native-event', participant=label, event=event)
            except Exception as error: self.error = type(error).__name__
        self.readers = [threading.Thread(target=collect, args=(stream, output), daemon=True)
                       for stream, output in ((self.process.stdout, True), (self.process.stderr, False))]
        for reader in self.readers: reader.start()
    def finish(self, deadline):
        code = self.process.wait(timeout=max(0.1, deadline - time.monotonic()))
        for reader in self.readers: reader.join(timeout=2)
        require(not self.error and all(not t.is_alive() for t in self.readers), 'Complete bounded child log required')
        return code

def run(binary, directory, mode):
    require((os.getuid(), os.getgid()) == (1000, 100) and not os.environ.get('LD_PRELOAD'), 'UID1000/GID100 raw CUDA required')
    info = binary.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 1000 and info.st_nlink == 1
        and stat.S_IMODE(info.st_mode) == 0o700 and hashlib.sha256(binary.read_bytes()).hexdigest() == BINARY_SHA,
        'Exact owned approved binary required')
    require(directory.parent == Path('/tmp') and len(str(directory / 'vmm.sock')) < 108, 'Fresh bounded private tmp socket path required')
    directory.mkdir(mode=0o700)
    children = []
    deadline = time.monotonic() + 90
    try:
        def argv(which):
            return [str(binary), '--execute', '--mode', which, '--gpu-uuid', GPU, '--cap-mib', '5120']
        if mode == 'vmm-direct': children.append(Child(argv(mode), mode))
        else:
            socket = directory / (mode + '.sock')
            children.append(Child([*argv(mode + '-export'), '--socket', str(socket)], mode + '-export'))
            waiting = time.monotonic() + 10
            while not socket.exists():
                require(children[0].process.poll() is None and time.monotonic() < waiting, 'Approved exporter socket unavailable')
                time.sleep(0.05)
            inode = socket.lstat()
            require(stat.S_ISSOCK(inode.st_mode) and inode.st_uid == 1000 and stat.S_IMODE(inode.st_mode) == 0o600,
                    'Exact private exporter socket required')
            args = [*argv(mode + '-import'), '--socket', str(socket), '--importer-fill-mib', '64']
            if mode == 'vmm': args += ['--retain-seconds', '9']
            children.append(Child(args, mode + '-import'))
        results = [assess(child.events, child.finish(deadline), child.label) for child in children]
        require(not any((directory / (m + '.sock')).exists() for m in ('ipc', 'vmm')), 'Successful exporter must remove its socket')
        emit('receipt', state='bounded-same-parent-measurement-completed', results=results,
             cross_pod_import_isolation_qualified=False, native_preflight_verified_by_wrapper=False,
             pending=['cross-Pod import denial', 'exporter-process death', 'MPS', 'restart and native cleanup'])
    finally:
        # Only our trusted importer/exporter children; never a Pod/server/peer.
        # Quiesce importer first. Timeout is never proof of native cleanup.
        for child in reversed(children):
            if child.process.poll() is None:
                child.process.kill()
                try: child.process.wait(timeout=3)
                except subprocess.TimeoutExpired: pass

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true'); p.add_argument('--gpu-uuid')
    p.add_argument('--binary', type=Path, default=Path('/tmp/cps-native-imports'))
    p.add_argument('--directory', type=Path); p.add_argument('--mode', choices=('vmm-direct', 'ipc', 'vmm'), default='vmm-direct')
    args = p.parse_args(argv)
    if not args.execute:
        emit('inert', gpu_calls=False, binary_sha256=BINARY_SHA); return
    require(args.gpu_uuid == GPU and args.directory is not None, 'Explicit reviewed GPU and fresh private directory required')
    try: run(args.binary, args.directory, args.mode)
    except Exception as error:
        emit('receipt', state='inconclusive', error_type=type(error).__name__, cleanup_confirmed=False)
        raise SystemExit(1)

if __name__ == '__main__': main()

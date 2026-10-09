"""Root-only, inert-by-default observation fence for one legacy canary teardown.

This helper never unloads modules, changes GPU caps, or calls Kubernetes. The
reviewed publisher checks Kubernetes independently; Root performs unload in a
separate operation while this helper retains all three maintenance locks.
"""
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import socket
import stat
import subprocess
import sys
import time
import uuid

ROOT = Path('/run/cps-native-gpu')
OLD_HEALTH_SHA = '22107515ecdc2ffe18afbafa8f15432ed9439aa6fc56ed9531649f790b29e769'
OLD_MODULES = {
    'nvidia': '59f623fe5fdc89ef06f8055ee4dbfafeabe70b1d0bcabc487bc6fe04b78d6e77',
    'nvidia_uvm': 'b2ae67722e9e21a70c319aeed2184f5b2d1f23b8e32dea00816cfd5cd2c3ee61',
}
LEGACY_UID = '696bab5d-30c7-4476-bb97-19b300c45302'
OLD_GENERATION = '761311d1-da22-46ab-83fe-811e66f00c46'
NODE_UID = '3336cdd5-d245-436e-b57c-2f66c6dcaa41'
BOOT_ID = '209f8bc9-a478-48e4-925a-6e07ffa56f7a'
MAX_FILE = 131072
DEVICE_IDS = set()
RPC_BUFFER = b''


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def directory(path):
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0
            and stat.S_IMODE(info.st_mode) == 0o700, 'Root0700 maintenance directory required')
    return info


def read_protected(path, mode=0o400, *, optional=False):
    directory(path.parent)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        if optional:
            return None
        raise
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == 0
                and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == mode,
                'Protected exact-mode root file required')
        raw = os.read(fd, MAX_FILE + 1)
        after = os.fstat(fd)
        require(len(raw) <= MAX_FILE and all(getattr(before, key) == getattr(after, key)
                for key in ('st_dev', 'st_ino', 'st_mtime_ns', 'st_ctime_ns', 'st_size')),
                'Bounded stable root file required')
        return raw
    finally:
        os.close(fd)


def load_protected(path, expected, name):
    raw = read_protected(path)
    require(hashlib.sha256(raw).hexdigest() == expected, 'Exact protected source hash required')
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def protected_module_sha(path):
    directory(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_nlink == 1
                and stat.S_IMODE(before.st_mode) == 0o400 and 0 < before.st_size <= 128 * 1024 * 1024,
                'Protected bounded original module required')
        digest = hashlib.sha256()
        while True:
            data = os.read(fd, 1024 * 1024)
            if not data:
                break
            digest.update(data)
        after = os.fstat(fd)
        require(all(getattr(before, key) == getattr(after, key)
                for key in ('st_dev', 'st_ino', 'st_mtime_ns', 'st_ctime_ns', 'st_size')),
                'Stable original module input required')
        return digest.hexdigest()
    finally:
        os.close(fd)


def acquire_lock(path):
    directory(path.parent)
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600, 'Private root lock required')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require((info.st_dev, info.st_ino) == (path.lstat().st_dev, path.lstat().st_ino),
                'Current lock path identity required')
        return fd
    except BaseException:
        os.close(fd)
        raise


def lock_proof(fds):
    paths = {'journal': ROOT / 'journal/.writer.lock',
             'driver': ROOT / 'authority/.driver-loader.lock',
             'maintenance': ROOT / 'operator/.teardown.lock'}
    result = {}
    for name, fd in fds.items():
        info = os.fstat(fd)
        path = paths[name].lstat()
        require((info.st_dev, info.st_ino) == (path.st_dev, path.st_ino)
                and info.st_uid == 0 and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600, 'Unchanged private lock inode required')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result[name] = {'device': info.st_dev, 'inode': info.st_ino}
    return result


def modules():
    sysfs = sorted(p.name for p in Path('/sys/module').glob('nvidia*'))
    proc = sorted(line.split()[0] for line in Path('/proc/modules').read_text().splitlines()
                  if line.split()[0].startswith('nvidia'))
    return sysfs, proc


def pci_inventory():
    result = []
    for device in Path('/sys/bus/pci/devices').iterdir():
        if (device / 'vendor').read_text().strip() == '0x10de':
            result.append(device.name)
    return sorted(result)


def gpu_fd_clients():
    paths = [*Path('/dev').glob('nvidia*'), *Path('/dev/nvidia-caps').glob('*')]
    for path in paths:
        try:
            info = path.stat()
        except FileNotFoundError:
            # Device removal can race observation during unload. Retain every
            # previously observed ID so surviving descriptors remain visible.
            continue
        if stat.S_ISCHR(info.st_mode):
            DEVICE_IDS.add(info.st_rdev)
    ids = DEVICE_IDS
    require(bool(ids), 'Actual NVIDIA device inventory required')
    clients = set()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal():
            continue
        try:
            for fd in (proc / 'fd').iterdir():
                try:
                    info = fd.stat()
                    if stat.S_ISCHR(info.st_mode) and info.st_rdev in ids:
                        clients.add(int(proc.name))
                except (FileNotFoundError, ProcessLookupError):
                    pass
        except (FileNotFoundError, ProcessLookupError):
            pass
    return len(clients)


def quiescence(scope):
    writers = set()
    writer_names = {'node_agent.py', 'poll.py', 'pod_cap.py', 'driver_loader.py'}
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal():
            continue
        try:
            args = (proc / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError):
            continue
        if any(Path(arg.decode(errors='strict')).name in writer_names for arg in args if arg):
            writers.add(int(proc.name))
    tasks = set()
    uids = [p['pod_uid'] for p in scope['pilot_pods']]
    base = Path('/sys/fs/cgroup/kubepods.slice')
    require(base.is_dir(), 'Actual kubelet cgroup2 hierarchy required')
    def traversal_error(error):
        raise error
    for folder, _, files in os.walk(base, onerror=traversal_error):
        if any(uid in folder or uid.replace('-', '_') in folder for uid in uids):
            require('cgroup.procs' in files, 'Complete selected cgroup task inventory required')
            try:
                tasks.update(int(pid) for pid in (Path(folder) / 'cgroup.procs').read_text().split())
            except FileNotFoundError:
                # Disappearance is safe only if the selected directory is gone.
                require(not Path(folder).exists(), 'Selected task file vanished in a live cgroup')
    return not writers, len(tasks)


def gate_hash(plan, recovery):
    raw = read_protected(ROOT / 'receipts' / (LEGACY_UID + '.json'), mode=0o600, optional=True)
    return recovery.raw_sha256(raw) if raw is not None else None


def read_rpc(timeout=120):
    global RPC_BUFFER
    deadline = time.monotonic() + timeout
    while b'\n' not in RPC_BUFFER:
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'Root RPC deadline exceeded')
        require(select.select([sys.stdin.fileno()], [], [], remaining)[0], 'Root RPC deadline exceeded')
        data = os.read(sys.stdin.fileno(), 65536)
        require(data and len(RPC_BUFFER) + len(data) <= 262144, 'Root RPC EOF or size bound exceeded')
        RPC_BUFFER += data
    line, RPC_BUFFER = RPC_BUFFER.split(b'\n', 1)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate Root RPC field')
            result[key] = value
        return result
    return json.loads(line, object_pairs_hook=unique)


def stable_base(plan, fds, recovery):
    scope = plan['scope']
    require(socket.gethostname() == scope['node'] == 'k3s-wk-gpu2'
            and scope['node_uid'] == NODE_UID and scope['boot_id'] == BOOT_ID
            and Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT_ID
            and scope['driver_generation'] == OLD_GENERATION
            and plan['journal']['record']['intent']['pod_uid'] == LEGACY_UID,
            'Only the reviewed legacy canary recovery is supported')
    info = directory(ROOT / 'journal')
    require(scope['journal_directory'] == {'device': info.st_dev, 'inode': info.st_ino},
            'Unchanged journal directory required')
    require(pci_inventory() == sorted(p['pci_bdf'] for p in scope['nvidia_gpus']),
            'Complete unchanged NVIDIA PCI inventory required')
    raw = read_protected(ROOT / 'journal' / (LEGACY_UID + '.json'), mode=0o600)
    writers_quiet, task_count = quiescence(scope)
    return recovery.raw_sha256(raw), writers_quiet, task_count, lock_proof(fds)


def before_proof(plan, digest, fds, recovery, health):
    journal_sha, quiet, tasks, locks = stable_base(plan, fds, recovery)
    require(journal_sha == plan['journal']['sha256'], 'Original journal bytes required')
    require(health.validate_native_driver_health() == OLD_GENERATION, 'Original exact healthy driver epoch required')
    manifest = read_protected(ROOT / 'authority/driver-load-manifest.json')
    require(recovery.raw_sha256(manifest) == plan['review']['load_manifest_sha256'], 'Original load manifest required')
    require(modules() == (plan['scope']['loaded_modules'], plan['scope']['loaded_modules']),
            'Complete exact loaded NVIDIA module inventory required')
    require(plan['scope']['module_sha256'] == {name: 'sha256:' + sha for name, sha in OLD_MODULES.items()},
            'Exact original protected module identities required')
    require(plan['review']['old_module_source_sha256'] == 'sha256:' + OLD_HEALTH_SHA,
            'Reviewed original health source required')
    for name, filename in [('nvidia', 'nvidia.ko'), ('nvidia_uvm', 'nvidia-uvm.ko')]:
        require(protected_module_sha(ROOT / 'driver-inputs' / filename) == OLD_MODULES[name],
                'Actual protected original module input hash required')
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = '/run/nvidia/driver/usr/lib/x86_64-linux-gnu'
    def query(args):
        result = subprocess.run(['/run/nvidia/driver/usr/bin/nvidia-smi', *args],
                env=env, capture_output=True, text=True, timeout=15, check=True)
        return result.stdout.strip()
    memory = {}
    gpus = []
    for line in query(['--query-gpu=uuid,pci.bus_id,memory.used', '--format=csv,noheader,nounits']).splitlines():
        uid, bdf, used = (part.strip() for part in line.split(','))
        bdf = bdf.lower()[-12:]
        memory[uid] = int(used) * 1024 * 1024
        gpus.append({'gpu_uuid': uid, 'pci_bdf': bdf})
    require(sorted(gpus, key=lambda item: item['pci_bdf']) == plan['scope']['nvidia_gpus'],
            'Complete NVIDIA UUID/PCI mapping required')
    apps = query(['--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'])
    proof = {'stage': 'before', 'operation_id': plan['operation_id'], 'plan_sha256': digest,
        'scope': plan['scope'], 'journal_sha256': journal_sha, 'locks': locks,
        'native_writers_quiesced': quiet, 'locks_held': True, 'driver_healthy': True,
        'gpu_memory_bytes': memory, 'gpu_fd_clients': gpu_fd_clients(),
        'compute_apps': len(apps.splitlines()) if apps else 0, 'pod_runtime_tasks': tasks,
        'gate_sha256': gate_hash(plan, recovery)}
    recovery.validate_before(proof, plan, digest)
    return proof


def teardown_proof(plan, digest, fds, recovery, before, *, final=False):
    journal_sha, quiet, tasks, locks = stable_base(plan, fds, recovery)
    sysfs, proc = modules()
    require(not sysfs and not proc, 'Every NVIDIA module must be positively absent')
    require(not os.path.lexists(ROOT / 'authority/driver-generation')
            and not os.path.lexists(ROOT / 'authority/driver-load-manifest.json'), 'Old load authority must remain invalidated')
    bdfs = pci_inventory()
    require(all(not os.path.lexists(Path('/sys/bus/pci/devices') / bdf / 'driver') for bdf in bdfs),
            'Every prior NVIDIA GPU PCI function must be unbound')
    proof = {'stage': 'teardown', 'operation_id': plan['operation_id'], 'plan_sha256': digest,
        'node_uid': NODE_UID, 'boot_id': BOOT_ID, 'old_driver_generation': OLD_GENERATION,
        'old_generation_invalidated': True, 'sysfs_modules': sysfs, 'proc_modules': proc,
        'pci_unbound': bdfs, 'gpu_fd_clients': gpu_fd_clients(), 'pod_runtime_tasks': tasks,
        'locks': locks, 'journal_sha256': journal_sha, 'gate_sha256': gate_hash(plan, recovery),
        'native_writers_quiesced': quiet, 'locks_held': True, 'new_load_absent': True}
    if final:
        recovery.validate_teardown(proof, plan, digest, before, journal_sha256=journal_sha, gate_sha256=None)
    else:
        recovery.validate_teardown(proof, plan, digest, before)
    return proof


def invalidate_old_authority(plan, recovery):
    # Root already holds the same writer lock used by the protected loader.
    directory(ROOT / 'authority')
    require(read_protected(ROOT / 'authority/driver-generation', mode=0o600).decode().strip()
            == OLD_GENERATION, 'Original generation required at invalidation')
    require(recovery.raw_sha256(read_protected(ROOT / 'authority/driver-load-manifest.json'))
            == plan['review']['load_manifest_sha256'], 'Original manifest required at invalidation')
    for name, mode in [('driver-generation', 0o600), ('driver-load-manifest.json', 0o400)]:
        read_protected(ROOT / 'authority' / name, mode=mode)
        (ROOT / 'authority' / name).unlink()
        fd = os.open(ROOT / 'authority', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--qualification', action='store_true')
    parser.add_argument('--fence-source-sha256')
    parser.add_argument('--recovery-source-sha256')
    parser.add_argument('--dependency-manifest-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'state': 'inert', 'module_actions': False, 'cap_actions': False}))
        return
    require(os.geteuid() == 0 and args.qualification, 'Explicit Root qualification required')
    for path in (ROOT, ROOT / 'operator', ROOT / 'driver-inputs', ROOT / 'receipts',
                 ROOT / 'published-cleanup', ROOT / 'authority', ROOT / 'journal'):
        directory(path)
    require(hashlib.sha256(read_protected(Path(__file__))).hexdigest() == args.fence_source_sha256,
            'Exact protected fence source required')
    dependency_raw = read_protected(ROOT / 'operator/dependencies.json')
    require(hashlib.sha256(dependency_raw).hexdigest() == args.dependency_manifest_sha256,
            'Exact protected dependency manifest required')
    dependencies = json.loads(dependency_raw)
    require(isinstance(dependencies, dict)
            and set(dependencies) == {'node_agent.py', 'abort_before_gate.py', 'source-snapshot.json'}
            and all(isinstance(value, str) and len(value) == 64 for value in dependencies.values()),
            'Closed exact recovery dependency closure required')
    for name, digest in dependencies.items():
        require(hashlib.sha256(read_protected(ROOT / 'operator' / name)).hexdigest() == digest,
                'Changed protected recovery dependency')
    load_protected(ROOT / 'operator/node_agent.py', dependencies['node_agent.py'], 'node_agent')
    load_protected(ROOT / 'operator/abort_before_gate.py', dependencies['abort_before_gate.py'], 'abort_before_gate')
    recovery = load_protected(ROOT / 'operator/teardown_recovery.py', args.recovery_source_sha256, 'teardown_recovery')
    request = read_rpc()
    resumed = request.get('op') == 'resume-after-audit'
    if resumed:
        require(set(request) == {'op', 'nonce', 'plan', 'plan_sha256', 'audit', 'resume'},
                'Closed resume-after-audit RPC required')
    else:
        require(set(request) == {'op', 'nonce', 'plan', 'plan_sha256'}
                and request['op'] == 'acquire', 'Closed acquire RPC required')
    plan, digest, nonce = request['plan'], request['plan_sha256'], request['nonce']
    require(isinstance(nonce, str) and str(uuid.UUID(nonce)) == nonce, 'Fresh canonical RPC nonce required')
    historical_payload = None
    resume = None
    if resumed:
        recovery.validate_historical_plan(plan, digest)
        resume = request['resume']
        historical_payload = recovery.validate_resume(resume, plan, request['audit'])
    else:
        recovery.validate_plan(plan, digest)
    fds = {}
    try:
        for name, path in [('journal', ROOT / 'journal/.writer.lock'),
                           ('driver', ROOT / 'authority/.driver-loader.lock'),
                           ('maintenance', ROOT / 'operator/.teardown.lock')]:
            fds[name] = acquire_lock(path)
        def emit(event, proof):
            print(json.dumps({'event': event, 'nonce': nonce,
                'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z'),
                'proof': proof}, sort_keys=True), flush=True)
        if resumed:
            # The original observations come only from the real immutable
            # audit. No unloaded driver is queried to recreate a before proof.
            before = historical_payload['before']
            require(lock_proof(fds) == before['locks'], 'Historical lock inode continuity required')
            teardown = teardown_proof(plan, digest, fds, recovery, before)
            emit('fence-resumed', teardown)
            explicitly_verified = False
        else:
            health = load_protected(ROOT / 'driver-inputs/native_gpu_health.py', OLD_HEALTH_SHA, 'old_native_gpu_health')
            before = before_proof(plan, digest, fds, recovery, health)
            emit('fence-acquired', before)
            request = read_rpc()
            require(request == {'op': 'verify-teardown', 'nonce': nonce}, 'Closed ordered teardown RPC required')
            # Recheck zero memory/apps/FDs/tasks immediately before invalidation.
            require(before_proof(plan, digest, fds, recovery, health) == before, 'Original quiescence must remain exact')
            invalidate_old_authority(plan, recovery)
            deadline = time.monotonic() + 120
            while any(modules()):
                require(time.monotonic() < deadline, 'External Root module unload timed out; retain maintenance evidence')
                require(gpu_fd_clients() == 0 and quiescence(plan['scope']) == (True, 0), 'New GPU client or native writer appeared')
                time.sleep(0.2)
            teardown = teardown_proof(plan, digest, fds, recovery, before)
            emit('fence-teardown-verified', teardown)
            explicitly_verified = True
        while True:
            request = read_rpc()
            if request != {'op': 'verify-teardown', 'nonce': nonce}:
                break
            require(teardown_proof(plan, digest, fds, recovery, before) == teardown,
                    'Unchanged positive teardown required at reverification')
            emit('fence-teardown-verified', teardown)
            explicitly_verified = True
        require(explicitly_verified, 'Explicit current teardown verification required before publication')
        require(set(request) == {'op', 'nonce', 'plan_sha256', 'audit', 'cleanup'}
                and request['op'] == 'publish-local' and request['nonce'] == nonce
                and request['plan_sha256'] == digest, 'Closed ordered local publication RPC required')
        require(teardown_proof(plan, digest, fds, recovery, before) == teardown, 'Unchanged positive teardown required before completion')
        if resumed:
            require(recovery.validate_resume(resume, plan, request['audit']) == historical_payload,
                    'Original immutable audit required at completion')
        local = recovery.complete_local(ROOT, plan, request['audit'], request['cleanup'],
            before=before, teardown=teardown, lock_fds=fds, trusted_uid=0)
        def completion():
            proof = teardown_proof(plan, digest, fds, recovery, before, final=True)
            return {'stage': 'complete', 'operation_id': plan['operation_id'], 'plan_sha256': digest,
                    'teardown': proof, **recovery.read_local_completion(ROOT, plan, request['audit'], request['cleanup'], trusted_uid=0)}
        emit('fence-local-published', completion())
        next_request = read_rpc()
        require(next_request == {'op': 'verify-completion', 'nonce': nonce}, 'Closed ordered completion RPC required')
        emit('fence-completion-verified', completion())
        require(read_rpc() == {'op': 'release', 'nonce': nonce}, 'Closed final release RPC required')
    finally:
        for fd in reversed(list(fds.values())):
            os.close(fd)


if __name__ == '__main__':
    main()

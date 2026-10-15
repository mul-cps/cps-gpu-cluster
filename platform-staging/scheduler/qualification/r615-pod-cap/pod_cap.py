#!/usr/bin/env python3
"""Inert R615 misc-backend Pod-parent cap prototype; never release a Pod itself."""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

MAX = (1 << 64) - 1
GATE = 'cps-driver-cap-gate'
HEADER_SHA256 = 'c9b494b7c8015b6ae7aca62b2ce98e6b13f3277a2bec80de528371e725d54012'


def require(ok, message):
    if not ok: raise ValueError(message)


class SetLimits(C.Structure):
    _fields_ = [('nameSpace', C.c_char_p), ('softLimit', C.c_ulonglong), ('hardLimit', C.c_ulonglong)]


class GetLimits(C.Structure):
    _fields_ = SetLimits._fields_ + [('currentUsed', C.c_ulonglong)]


class Nvml:
    """ABI from official cuda-nvml-dev-13-4_13.4.92-1 nvml.h, not prose snippets."""
    def __init__(self):
        self.lib = C.CDLL('libnvidia-ml.so.1')
        self.check(self.lib.nvmlInit_v2())
        buf = C.create_string_buffer(80)
        self.check(self.lib.nvmlSystemGetDriverVersion(buf, len(buf)))
        self.version = buf.value.decode('ascii')
        require(int(self.version.split('.')[0]) >= 615, 'R615 or newer required')
        self.lib.nvmlDeviceGetHandleByUUID.argtypes = [C.c_char_p, C.POINTER(C.c_void_p)]
        self.lib.nvmlDeviceSetMemoryLimits_v1.argtypes = [C.c_void_p, C.POINTER(SetLimits)]
        self.lib.nvmlDeviceGetMemoryLimits_v1.argtypes = [C.c_void_p, C.POINTER(GetLimits)]
        self.lib.nvmlDeviceGetMigMode.argtypes = [C.c_void_p, C.POINTER(C.c_uint), C.POINTER(C.c_uint)]

    @staticmethod
    def check(code):
        require(code == 0, 'NVML operation failed with code ' + str(code))

    def handle(self, gpu):
        handle = C.c_void_p()
        self.check(self.lib.nvmlDeviceGetHandleByUUID(gpu.encode(), C.byref(handle)))
        current, pending = C.c_uint(), C.c_uint()
        result = self.lib.nvmlDeviceGetMigMode(handle, C.byref(current), C.byref(pending))
        require(result == 3 or (result == 0 and current.value == 0 and pending.value == 0), 'Non-MIG device required')
        return handle

    def get(self, gpu, path):
        limits = GetLimits(str(path).encode(), 0, 0, 0)
        result = self.lib.nvmlDeviceGetMemoryLimits_v1(self.handle(gpu), C.byref(limits))
        if result == 6: return None  # NVML_ERROR_NOT_FOUND: no exact limit
        # R615's misc getter also returns3 when no nearest limit exists.
        # Preserve the ambiguity; only an actual setter and exact readback can
        # distinguish a virgin group from an unsupported backend.
        if result == 3: return {'nvml_result': 3, 'state': 'unset-or-unsupported'}
        self.check(result)
        return {'soft': limits.softLimit, 'hard': limits.hardLimit, 'used': limits.currentUsed}

    def set(self, gpu, path, soft, hard):
        limits = SetLimits(str(path).encode(), soft, hard)
        self.check(self.lib.nvmlDeviceSetMemoryLimits_v1(self.handle(gpu), C.byref(limits)))

    def close(self): self.check(self.lib.nvmlShutdown())


def validate_intent(intent):
    require(set(intent) == {'pod_uid', 'namespace', 'name', 'node', 'gpu_uuid', 'cap_mib', 'spec_sha256'}, 'Exact operator-reviewed intent required')
    require(str(uuid.UUID(intent['pod_uid'])) == intent['pod_uid'], 'Canonical exact Pod UID required')
    require(re.fullmatch(r'GPU-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', intent['gpu_uuid']) is not None, 'Exact physical GPU UUID required')
    require(type(intent['cap_mib']) is int and intent['cap_mib'] in (64, 128, 512, 5120, 10240, 20480), 'Reviewed integer MiB cap required')
    require(re.fullmatch('[a-f0-9]{64}', intent['spec_sha256']) is not None, 'Reviewed full Pod spec SHA256 required')
    for key in ('namespace', 'name', 'node'):
        require(re.fullmatch('[a-z0-9][a-z0-9.-]*', intent[key]) is not None, 'Exact Kubernetes reference required')


def safe_path(root, relative):
    root = Path(root).resolve(strict=True)
    path = root / relative.lstrip('/')
    require('..' not in Path(relative).parts and path.resolve(strict=True) == path, 'Symlink/traversal cgroup rejected')
    require(path.is_relative_to(root) and path.is_dir(), 'Actual cgroup directory required')
    return path


def discover(intent, pod, cri, proc_root, cgroup_root):
    validate_intent(intent)
    meta, spec = pod['metadata'], pod['spec']
    require(not meta.get('deletionTimestamp') and all(meta.get(k) == intent[v] for k, v in
        [('uid', 'pod_uid'), ('namespace', 'namespace'), ('name', 'name')]), 'Actual exact live Pod identity required')
    require(spec.get('nodeName') == intent['node'], 'Actual selected node required')
    require(hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == intent['spec_sha256'], 'Reviewed Pod specification changed')
    require(spec.get('initContainers', [{}])[0].get('name') == GATE, 'Trusted first init gate required')
    for status in pod.get('status', {}).get('containerStatuses', []):
        require(not status.get('containerID') and not status.get('restartCount', 0)
                and 'running' not in status.get('state', {}) and 'terminated' not in status.get('state', {})
                and not status.get('lastState'), 'A user container already started; before-main gate refused')
    status = cri['status']; labels = status['labels']; cid = status['id']
    require(status['state'] == 'CONTAINER_RUNNING' and re.fullmatch('[a-f0-9]{64}', cid), 'Actual running CRI gate container required')
    require(all(labels.get(k) == value for k, value in {
        'io.kubernetes.pod.uid': intent['pod_uid'], 'io.kubernetes.pod.namespace': intent['namespace'],
        'io.kubernetes.pod.name': intent['name'], 'io.kubernetes.container.name': GATE}.items()), 'Foreign CRI identity refused')
    pid = cri['info']['pid']; require(type(pid) is int and pid > 0, 'Actual host PID required')
    proc = Path(proc_root)
    stat = (proc/str(pid)/'stat').read_text().rsplit(') ', 1)[1].split()
    start = int(stat[19])  # /proc/PID/stat field22, after arbitrary spaced comm
    cgroups = (proc/str(pid)/'cgroup').read_text().splitlines()
    require(len(cgroups) == 1 and cgroups[0].startswith('0::/'), 'Actual unified host cgroup required')
    relative = cgroups[0][3:]
    require(Path(relative).name == 'cri-containerd-' + cid + '.scope', 'Actual container scope/CID mismatch')
    parent = Path(relative).parent
    require(re.fullmatch(r'kubepods(?:-(?:besteffort|burstable))?-pod' + re.escape(intent['pod_uid'].replace('-', '_')) + r'\.slice', parent.name), 'Actual Pod-parent UID mismatch')
    leaf = safe_path(cgroup_root, relative); group = safe_path(cgroup_root, str(parent))
    require('misc' in (Path(cgroup_root)/'cgroup.controllers').read_text().split() and not (group/'dmem.max').exists(), 'Only reviewed misc fallback backend supported')
    identity = group.stat()
    return dict(intent, resource_version=meta['resourceVersion'], container_id=cid, host_pid=pid,
                pid_start_ticks=start, cgroup_relative=str(parent), cgroup_path=str(group),
                cgroup_device=identity.st_dev, cgroup_inode=identity.st_ino, leaf_path=str(leaf),
                boot_id=(proc/'sys/kernel/random/boot_id').read_text().strip(), backend='misc',
                cap_bytes=intent['cap_mib']*1048576, nvml_header_sha256=HEADER_SHA256,
                hostile_isolation_qualified=False, managed_memory_qualified=False)


def unlimited(value): return value is None or (value.get('soft') == 0 and value.get('hard') == MAX)


def unset_candidate(value):
    return unlimited(value) or value == {'nvml_result': 3, 'state': 'unset-or-unsupported'}


def write_receipt(path, value, *, create=False):
    path = Path(path)
    require(path.parent.stat().st_uid == os.geteuid() and path.parent.stat().st_mode & 0o777 == 0o700, 'Operator-owned private0700 receipt directory required')
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    if create:
        fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    else:
        require(path.is_file() and not path.is_symlink() and path.stat().st_uid == os.geteuid() and path.stat().st_mode & 0o777 == 0o600, 'Exact private owned receipt required')
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name); stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def apply(intent, get_pod, get_cri, proc_root, cgroup_root, driver, receipt):
    require(int(driver.version.split('.')[0]) >= 615, 'R615 or newer required')
    proof = discover(intent, get_pod(), get_cri(), proc_root, cgroup_root)
    require(unset_candidate(driver.get(intent['gpu_uuid'], proof['cgroup_path'])), 'Existing parent limit requires separate reconciliation')
    for child in Path(proof['cgroup_path']).rglob('*'):
        if child.is_dir():
            safe_path(cgroup_root, '/'+str(child.relative_to(cgroup_root)))
            require(unset_candidate(driver.get(intent['gpu_uuid'], str(child))), 'Existing descendant override prevents aggregate authority')
    proof.update(state='prepared-before-set', driver_version=driver.version)
    write_receipt(receipt, proof, create=True)  # durable exact cleanup authority before mutation
    try:
        driver.set(intent['gpu_uuid'], proof['cgroup_path'], proof['cap_bytes'], proof['cap_bytes'])
        value = driver.get(intent['gpu_uuid'], proof['cgroup_path'])
        require(value is not None and value.get('soft') == proof['cap_bytes'] and value.get('hard') == proof['cap_bytes'], 'Exact driver cap readback required')
        after = discover(intent, get_pod(), get_cri(), proc_root, cgroup_root)
        require(all(after[k] == v for k, v in proof.items() if k in after), 'Concurrent Pod/PID/cgroup generation changed')
        proof.update(state='applied-before-main', readback=value)
        write_receipt(receipt, proof)
        return proof
    except Exception:
        proof.update(state='failed-cap-retained')  # never clear a possible cap and release main on error
        write_receipt(receipt, proof)
        raise


def cleanup(proof, get_pod, cgroup_root, driver, proc_root=Path('/proc')):
    validate_intent({k: proof[k] for k in ('pod_uid','namespace','name','node','gpu_uuid','cap_mib','spec_sha256')})
    require((Path(proc_root)/'sys/kernel/random/boot_id').read_text().strip() == proof['boot_id'], 'Old boot/driver generation cleanup refused')
    require(re.fullmatch(r'kubepods(?:-(?:besteffort|burstable))?-pod' + re.escape(proof['pod_uid'].replace('-', '_')) + r'\.slice', Path(proof['cgroup_relative']).name), 'Exact tracked Pod parent required')
    pod = get_pod()
    require(pod is None or (pod['metadata']['uid'] == proof['pod_uid'] and pod.get('status', {}).get('phase') in ('Succeeded','Failed')), 'Cleanup requires exact Pod gone or terminal')
    candidate = Path(cgroup_root)/proof['cgroup_relative'].lstrip('/')
    if not candidate.exists(): return dict(proof, state='already-cleared-cgroup-removed')
    group = safe_path(cgroup_root, proof['cgroup_relative'])
    require(str(group) == proof['cgroup_path'] and group.stat().st_dev == proof['cgroup_device']
            and group.stat().st_ino == proof['cgroup_inode'], 'Cgroup generation changed; never clear replacement')
    require(dict(line.split() for line in (group/'cgroup.events').read_text().splitlines()).get('populated') == '0', 'Live tasks remain; cannot remove driver protection')
    value = driver.get(proof['gpu_uuid'], str(group))
    if unlimited(value): return dict(proof, state='already-cleared')
    require(value.get('soft') == proof['cap_bytes'] and value.get('hard') == proof['cap_bytes'], 'Foreign/changed/uncertain limit must not be cleared')
    driver.set(proof['gpu_uuid'], str(group), 0, MAX)
    require(unlimited(driver.get(proof['gpu_uuid'], str(group))), 'Cleanup readback failed')
    return dict(proof, state='cleared')


def private_json(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_uid == os.geteuid()
            and path.stat().st_mode & 0o777 == 0o600, 'Private operator-owned0600 input required')
    return json.loads(path.read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=('inspect','apply','cleanup'))
    p.add_argument('--intent', type=Path, required=True)
    p.add_argument('--container-id', required=True)
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--proc-root', type=Path, default=Path('/proc'))
    p.add_argument('--cgroup-root', type=Path, default=Path('/sys/fs/cgroup'))
    p.add_argument('--runtime-endpoint', default='unix:///run/k3s/containerd/containerd.sock')
    p.add_argument('--execute', action='store_true')
    args = p.parse_args(); intent = private_json(args.intent); validate_intent(intent)
    require(re.fullmatch('[a-f0-9]{64}', args.container_id), 'Exact CRI container ID required')
    def pod():
        raw = subprocess.check_output(['kubectl','-n',intent['namespace'],'get','pod',intent['name'],'--ignore-not-found','-o','json'])
        return json.loads(raw) if raw.strip() else None
    def cri():
        return json.loads(subprocess.check_output(['crictl','--runtime-endpoint',args.runtime_endpoint,'inspect',args.container_id]))
    if not args.execute:
        print(json.dumps({'state':'inert','operation':args.operation,'gpu_writes':False,'hostile_isolation_qualified':False})); return
    require(os.geteuid() == 0, 'Explicit native trusted operator required')
    if args.operation == 'inspect':
        print(json.dumps(discover(intent,pod(),cri(),args.proc_root,args.cgroup_root),indent=2)); return
    tracked = private_json(args.receipt) if args.operation == 'cleanup' else None
    if tracked is not None:
        require(all(tracked[k] == value for k, value in intent.items()), 'Cleanup intent and exact tracked receipt disagree')
    driver = Nvml()
    try:
        result = (apply(intent,pod,cri,args.proc_root,args.cgroup_root,driver,args.receipt) if args.operation == 'apply'
                  else cleanup(tracked,pod,args.cgroup_root,driver,args.proc_root))
        if args.operation == 'cleanup': write_receipt(args.receipt,result)
        print(json.dumps(result,indent=2))
    finally: driver.close()


if __name__ == '__main__': main()

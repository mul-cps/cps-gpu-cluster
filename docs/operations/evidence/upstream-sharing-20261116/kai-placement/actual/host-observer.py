#!/usr/bin/env python3
"""Read-only root host observation; prints no CRI environment or credentials."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time


def command(args):
    environment=dict(os.environ)
    if args[0].startswith('/run/nvidia/driver/'):
        environment['LD_LIBRARY_PATH']=':'.join(str(p) for p in
            (Path('/run/nvidia/driver/usr/lib/x86_64-linux-gnu'),Path('/run/nvidia/driver/usr/lib64')) if p.is_dir())
    return subprocess.check_output(args, text=True, timeout=12, env=environment).strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--node', required=True)
    p.add_argument('--gpu-uuid', required=True)
    p.add_argument('--container-id')
    p.add_argument('--retired-cgroup')
    p.add_argument('--skip-limits', action='store_true')
    a = p.parse_args()
    if socket.gethostname() != a.node:
        raise RuntimeError('SSH host name does not match selected Kubernetes node')
    # Driver-container installations may not expose nvidia-smi on the host PATH.
    smi = next((str(x) for x in (Path('/usr/bin/nvidia-smi'), Path('/run/nvidia/driver/usr/bin/nvidia-smi')) if x.exists()), None)
    if smi is None: raise RuntimeError('Host nvidia-smi unavailable')
    gpu = command([smi,'--query-gpu=uuid,driver_version,memory.used,memory.total','--format=csv,noheader,nounits','-i',a.gpu_uuid])
    if gpu.split(',')[0].strip() != a.gpu_uuid: raise RuntimeError('Host GPU UUID mismatch')
    result = dict(time=time.time(), node=a.node, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                  gpu=gpu, compute_processes=command([smi,'--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader,nounits','-i',a.gpu_uuid]))
    # Read actual loaded identity/settings, not just the unchanged driver version.
    uvm = Path('/sys/module/nvidia_uvm')
    result['uvm'] = {name: (uvm / name).read_text().strip() for name in
                     ('srcversion', 'parameters/uvm_reject_managed_memory',
                      'parameters/uvm_disable_hmm') if (uvm / name).exists()}
    source = Path('/run/nvidia/driver/usr/src/nvidia-620.70.06/nvidia-uvm/uvm_va_range.c')
    if source.is_file():
        result['uvm_source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    if a.retired_cgroup:
        if not a.retired_cgroup.startswith('/') or '..' in Path(a.retired_cgroup).parts:
            raise RuntimeError('Absolute retired cgroup path required')
        retired=Path('/sys/fs/cgroup')/a.retired_cgroup.lstrip('/')
        result.update(retired_cgroup=a.retired_cgroup,retired_cgroup_exists=retired.exists())
        if (retired/'misc.current').exists():result['retired_misc_current']=(retired/'misc.current').read_text()
    if a.container_id:
        body = json.loads(command(['k3s','crictl','inspect',a.container_id]))
        pid = int(body['info']['pid'])
        if pid <= 0: raise RuntimeError('CRI process is not live')
        cgroup = Path(f'/proc/{pid}/cgroup').read_text()
        rows = [line.split(':',2)[2] for line in cgroup.splitlines() if line.startswith('0::')]
        if len(rows) != 1: raise RuntimeError('Unified cgroup identity required')
        root = Path('/sys/fs/cgroup')/rows[0].lstrip('/')
        files = {}
        for name in ('misc.current','misc.max','memory.current','memory.max','cgroup.events'):
            f = root/name
            if f.exists(): files[name] = f.read_text()
        processes = []
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit(): continue
            try:
                if (entry/'cgroup').read_text() != cgroup: continue
                processes.append(dict(pid=int(entry.name), stat=(entry/'stat').read_text(),
                                      nspid=[x for x in (entry/'status').read_text().splitlines() if x.startswith('NSpid:')]))
            except (FileNotFoundError, ProcessLookupError, PermissionError): pass
        result.update(container_id=a.container_id, init_pid=pid, cgroup=cgroup,
                      cgroup_inode=root.stat().st_ino, accounting=files, processes=processes)
    outer = Path('/usr/local/bin/k3s')
    pids = [p for p in Path('/proc').iterdir() if p.name.isdigit() and (p/'comm').exists() and (p/'comm').read_text().strip() == 'containerd']
    if len(pids) != 1: raise RuntimeError('Exactly one running containerd required')
    exe = pids[0]/'exe'
    result['runtime'] = {'outer_sha256': hashlib.sha256(outer.read_bytes()).hexdigest(),
        'containerd_pid': int(pids[0].name), 'containerd_exe': str(exe.resolve()),
        'inner_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
        'kernel': os.uname().release, 'k3s_version': command(['k3s','--version']),
        'mem_available_bytes': int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024}
    if a.container_id:
        if not a.skip_limits:
            result['memory_limits'] = command([smi,'memory-limits','--get','-n','/sys/fs/cgroup'+rows[0],'-i',a.gpu_uuid])
        spec = body['info'].get('runtimeSpec', {})
        result['oci_devices'] = spec.get('linux', {}).get('devices', [])
        result['oci_gpu_annotations'] = {k:v for k,v in spec.get('annotations',{}).items() if k.startswith(('cdi.','nvidia.','required-plugins.'))}
    print(json.dumps(result))


if __name__ == '__main__': main()

#!/usr/bin/env python3
"""Root read-only process attribution; inert unless --execute is explicit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import uuid

BOOT = '209f8bc9-a478-48e4-925a-6e07ffa56f7a'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'

def require(ok, message):
    if not ok: raise ValueError(message)

def parse_start(value, host_pid):
    prefix, suffix = value.rsplit(')', 1)
    require(prefix.split('(', 1)[0].strip() == str(host_pid), 'Actual host PID stat required')
    fields = suffix.split(); require(len(fields) >= 20 and fields[19].isdecimal(), 'Readable actual PID start ticks required')
    return int(fields[19])

def status_fields(value):
    fields = {}
    for line in value.splitlines():
        key, separator, rest = line.partition(':')
        if separator:
            require(key not in fields, 'Duplicate process status field')
            fields[key] = rest.strip()
    return fields

def normalized_cgroup(value):
    lines = value.splitlines(); require(len(lines) == 1 and lines[0].startswith('0::/'), 'Exact default unified cgroup required')
    path = lines[0][3:]
    require('..' not in path.split('/') and '//' not in path, 'Canonical process cgroup required'); return path

def validate_request(request):
    require(isinstance(request,dict) and set(request)=={'trial_id','namespace_pid','identity','role','expect','cap_mib','exporter_pod_uid'},
            'Closed read-only endpoint attribution request required')
    trial=request['trial_id'];require(isinstance(trial,str) and str(uuid.UUID(trial))==trial and uuid.UUID(trial).int!=0,
            'Canonical current trial required')
    require(type(request['namespace_pid']) is int and request['namespace_pid']>0,'Positive actual namespace PID required')
    require(request['role'] in ('exporter','importer') and type(request['cap_mib']) is int and request['cap_mib'] in (5120,20480),
            'Exact bounded endpoint role and cap required')
    if request['role']=='exporter':require(request['expect'] is None and request['exporter_pod_uid'] is None,'Exporter cannot request importer fields')
    else:
        uid=request['exporter_pod_uid'];require(request['expect'] in ('allow','deny') and isinstance(uid,str)
            and str(uuid.UUID(uid))==uid and uuid.UUID(uid).int!=0,'Exact importer expectation and exporter required')
    return request

def observe(request, proc=Path('/proc'), cgroup=Path('/sys/fs/cgroup')):
    validate_request(request)
    trial, namespace_pid, identity = request['trial_id'], request['namespace_pid'], request['identity']
    require(str(uuid.UUID(trial)) == trial and uuid.UUID(trial).int != 0 and type(namespace_pid) is int and namespace_pid > 0,
        'Canonical current trial and actual namespace PID required')
    relative = identity['cgroup_relative']
    require(isinstance(relative, str) and relative.startswith('/kubepods.slice/') and '..' not in relative.split('/')
        and identity['cgroup_path'] == '/sys/fs/cgroup' + relative and identity['boot_id'] == BOOT
        and identity['gpu_uuid'] == GPU, 'Exact preflight sealed Pod authority required')
    parent = cgroup / relative.lstrip('/'); before = parent.stat(follow_symlinks=False)
    require(stat.S_ISDIR(before.st_mode) and (before.st_dev, before.st_ino) == (identity['cgroup_device'], identity['cgroup_inode']),
        'Actual finite parent inode required')
    matches = []
    deadline = time.monotonic() + 8
    for item in proc.iterdir():
        require(time.monotonic() < deadline, 'Bounded process observation exceeded')
        if not item.name.isdecimal(): continue
        host_pid = int(item.name)
        try:
            current = normalized_cgroup((item / 'cgroup').read_text())
            if current != relative and not current.startswith(relative + '/'): continue
            status = status_fields((item / 'status').read_text())
            nspids = status.get('NSpid', '').split()
            require(nspids and all(p.isdecimal() for p in nspids) and int(nspids[0]) == host_pid, 'Actual host namespace PID chain required')
            if int(nspids[-1]) != namespace_pid: continue
            require(status.get('Uid', '').split() == ['1000'] * 4 and status.get('Gid', '').split() == ['100'] * 4,
                'Actual notebook process UID/GID required')
            require(status.get('Tgid') == item.name, 'Importing process must be the actual thread-group leader')
            cmdline = (item / 'cmdline').read_bytes()
            require(len(cmdline) <= 100000, 'Bounded probe argv required')
            argv = cmdline.rstrip(b'\0').split(b'\0')
            flags=[(b'--trial-id',trial.encode()),(b'--role',request['role'].encode()),(b'--gpu-uuid',GPU.encode()),(b'--cap-mib',str(request['cap_mib']).encode())]
            if request['role']=='importer':flags.extend([(b'--expect',request['expect'].encode()),(b'--exporter-pod-uid',request['exporter_pod_uid'].encode())])
            else:require(b'--expect' not in argv and b'--exporter-pod-uid' not in argv,'Exporter has unexpected importer arguments')
            for flag,value in flags:
                require(argv.count(flag) == 1 and argv.index(flag) + 1 < len(argv) and argv[argv.index(flag) + 1] == value,
                    'Actual trusted endpoint argv must match current trial')
            start = parse_start((item / 'stat').read_text(), host_pid)
            pidns = (item / 'ns/pid').stat()
            # Read status independently again; no PID-reuse inference from stale text.
            status_after = status_fields((item / 'status').read_text())
            require(status_after.get('NSpid') == status.get('NSpid') and status_after.get('Tgid') == status.get('Tgid')
                and status_after.get('Uid') == status.get('Uid') and status_after.get('Gid') == status.get('Gid')
                and normalized_cgroup((item / 'cgroup').read_text()) == current
                and parse_start((item / 'stat').read_text(), host_pid) == start
                and (item / 'ns/pid').stat().st_ino == pidns.st_ino, 'Live process identity changed during observation')
            matches.append({'host_pid': host_pid, 'host_tgid': host_pid, 'pid_start_ticks': start,
                'namespace_pid': namespace_pid, 'nspid': [int(v) for v in nspids], 'pid_namespace_inode': pidns.st_ino,
                'process_cgroup_relative': current, 'pod_cgroup_inode': before.st_ino,
                'cmdline_sha256': hashlib.sha256(cmdline).hexdigest()})
        except FileNotFoundError:
            # Other processes may naturally exit; the held importer must be found uniquely.
            continue
    after = parent.stat(follow_symlinks=False)
    require(len(matches) == 1 and stat.S_ISDIR(after.st_mode) and (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino),
        'One unchanged actual importing process required')
    inventory_raw = (proc / 'driver/nvidia/gpus/0000:06:10.0/cps_native_caps').read_bytes()
    require(len(inventory_raw) <= 262144, 'Bounded native inventory required')
    inventory = json.loads(inventory_raw)
    require(isinstance(inventory, dict) and set(inventory) == {'version','backend','gpu_uuid','gpu_id','entries'}
        and type(inventory['version']) is int and inventory['version'] == 1 and inventory['backend'] == 'misc-fallback'
        and inventory['gpu_uuid'] == GPU and type(inventory['gpu_id']) is int and 0 <= inventory['gpu_id'] < 2**32
        and isinstance(inventory['entries'], list) and len(inventory['entries']) <= 256,
        'Actual GPU ID for kernel denial attribution required')
    rows = {}
    for row in inventory['entries']:
        require(isinstance(row, dict) and set(row) == {'cgroup_id','kernfs_id','inode','offline','pinned','default_hierarchy','soft','hard','used'}
            and all(type(row[k]) is int and 0 <= row[k] < 2**64 for k in ('cgroup_id','kernfs_id','inode','soft','hard','used'))
            and all(type(row[k]) is bool for k in ('offline','pinned','default_hierarchy'))
            and row['cgroup_id'] == row['kernfs_id'] == row['inode'] > 0 and row['inode'] not in rows,
            'Closed unique actual native cap rows required')
        rows[row['inode']] = row
    actual = rows.get(identity['cgroup_inode'])
    require(actual is not None and actual['offline'] is False and actual['pinned'] is True
        and actual['default_hierarchy'] is True and actual['soft'] == actual['hard'] == (request['cap_mib']*1048576)
        and actual['used'] <= (request['cap_mib']*1048576), 'Importing parent must still have an active finite selected cap')
    return {'kind': 'root-read-only-importer-attribution', 'trial_id': trial, 'boot_id': BOOT, 'gpu_uuid': GPU,
        'gpu_id': inventory['gpu_id'], 'pod_uid': identity['pod_uid'], 'driver_generation': identity['driver_generation'],
        'observed_time_ns': time.time_ns(), 'observed_monotonic_ns': time.monotonic_ns(), **matches[0], 'gpu_calls': False}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--execute', action='store_true'); parser.add_argument('--request')
    args = parser.parse_args(argv)
    if not args.execute: print(json.dumps({'state': 'inert', 'proc_reads': False, 'gpu_calls': False})); return
    require(os.getuid() == 0 and Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'Exact Root host observer required')
    require(isinstance(args.request, str) and len(args.request) <= 65536, 'Bounded actual attribution request required')
    print(json.dumps(observe(json.loads(args.request)), sort_keys=True, allow_nan=False))

if __name__ == '__main__': main()

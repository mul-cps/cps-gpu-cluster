"""One-time same-version outer-artifact maintenance; no version controller.

Run as root on the explicitly selected, fenced worker after operator checks.
Original outer binary and configuration hashes are retained. Lost replies mean
reconcile this operation and actual process hashes; never retry a restart blindly.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess

STOCK = '80eebb578e36a04ca460575fab419a3336b32c84205a0ae954ff16636181d9f7'
CANDIDATE = '6ce276301723a902da671058730611591c59b5f016b816f57f2d97b05c88fe2c'
INNER = '0ca3be05fd3fcdd9682e68bbff5821ea15027773404a7e47517b822bcb57387a'
ARCHIVE = '2277a2c458beda093f8367b944c2fbb2e5f53a00f17776759721fb781b3874fa'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True, choices=['k3s-wk-gpu'+str(i) for i in range(1, 5)])
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--operation', required=True)
    a = parser.parse_args()
    if os.geteuid() or socket.gethostname() != a.node:
        raise RuntimeError('root and exact selected host required')
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', a.operation):
        raise ValueError('invalid operation identity')
    directory = Path('/var/lib/cps-runtime-artifacts') / a.operation
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = (directory / 'operation.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX)
    state_path = directory / 'operation.json'
    if state_path.exists():
        raise RuntimeError('existing operation: reconcile status and hashes before another action')
    target = Path('/usr/local/bin/k3s')
    fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        original_stat = os.fstat(stream.fileno())
        if not stat.S_ISREG(original_stat.st_mode) or original_stat.st_uid != 0:
            raise RuntimeError('original must be a regular root-owned outer executable')
        original = stream.read()
    if digest(original) != STOCK:
        raise RuntimeError('original outer artifact differs; do not overwrite unknown state')
    fd = os.open(a.artifact, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise RuntimeError('candidate must be regular')
        payload = stream.read()
    if digest(payload) != CANDIDATE:
        raise RuntimeError('candidate artifact checksum mismatch')
    subprocess.run(['systemctl', 'is-active', '--quiet', 'k3s-agent'], check=True)
    configs = [Path('/etc/systemd/system/k3s-agent.service'),
               Path('/etc/systemd/system/k3s-agent.service.env'),
               Path('/etc/rancher/k3s/config.yaml'),
               Path('/var/lib/rancher/k3s/agent/etc/containerd/config-v3.toml.tmpl'),
               *sorted(Path('/etc/systemd/system/k3s-agent.service.d').glob('*.conf'))]
    hashes = {str(p): digest(p.read_bytes()) for p in configs if p.is_file()}
    backup = directory / 'k3s.stock'
    with backup.open('xb') as stream:
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())
    backup.chmod(stat.S_IMODE(original_stat.st_mode))
    state = {'operation': a.operation, 'node': a.node,
             'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'nominal_version': 'v1.34.9+k3s1', 'stock_outer_sha256': STOCK,
             'candidate_outer_sha256': CANDIDATE, 'candidate_inner_sha256': INNER,
             'candidate_archive': ARCHIVE, 'original_configuration_hashes': hashes,
             'status': 'backup complete; replacement not yet submitted'}

    def save():
        with state_path.open('w') as stream:
            json.dump(state, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        sync_directory(directory)

    save()
    temporary = target.with_name('.k3s-' + a.operation + '.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(payload)
        os.fchown(stream.fileno(), original_stat.st_uid, original_stat.st_gid)
        os.fchmod(stream.fileno(), stat.S_IMODE(original_stat.st_mode))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, target)
    sync_directory(target.parent)
    state['status'] = 'outer artifact replaced; reconcile restart submission next'
    save()
    unit = 'cps-' + a.operation
    state['restart_unit'] = unit + '.service'
    save()
    subprocess.run(['systemd-run', '--unit=' + unit, '--property=Type=oneshot',
        '--property=RemainAfterExit=yes', '/bin/systemctl', 'restart', 'k3s-agent'],
        check=True, capture_output=True, text=True)
    state['status'] = 'restart submitted; worker acceptance not established'
    save()
    assert {str(p): digest(p.read_bytes()) for p in configs if p.is_file()} == hashes
    print(json.dumps({'operation': a.operation, 'restart_unit': state['restart_unit'],
                      'status': state['status'], 'configuration_unchanged': True}))


if __name__ == '__main__':
    main()

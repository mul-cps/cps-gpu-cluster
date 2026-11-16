#!/usr/bin/env python3
"""One-shot Canonical release upgrade, supervised by host systemd, never retried.

Only OS execution/status is owned here. Kubernetes orchestration belongs to SUC;
worker acceptance, reboot, recovery and promotion remain explicit operations.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

GATES = (
    'compatibility', 'rollout_authorization', 'recovery_backup', 'console',
    'prerequisites', 'jobs_finished', 'custody_cleanup', 'storage_evacuated',
    'maintenance_lock', 'peer_health',
)
BASE = 'var/lib/cps-os-upgrade'


def operation_path(root, operation):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', operation):
        raise ValueError('invalid operation identity')
    return root / BASE / operation


def read_state(root, operation):
    return json.loads((operation_path(root, operation) / 'state.json').read_text())


def write_state(root, operation, changes):
    directory = operation_path(root, operation)
    path = directory / 'state.json'
    state = json.loads(path.read_text()) if path.exists() else {}
    state.update(changes, updated_at=time.time())
    temporary = directory / 'state.json.tmp'
    with temporary.open('w') as stream:
        json.dump(state, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return state


@contextmanager
def locked(root):
    base = root / BASE
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (base / '.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def boot_id(root):
    return (root / 'proc/sys/kernel/random/boot_id').read_text().strip()


def release(root):
    values = {}
    for line in (root / 'etc/os-release').read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            values[key] = shlex.split(value)[0] if value else ''
    return values


def launch(root, operation, node):
    directory = operation_path(root, operation)
    if not re.fullmatch(r'k3s-wk-gpu[1-4]', node) or (root / 'etc/hostname').read_text().strip() != node:
        raise ValueError('expected GPU worker hostname does not match')
    with locked(root):
        if directory.exists():
            raise RuntimeError('operation exists; reconcile before any further action')
        digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        auth = root / BASE / 'authorization' / (operation + '.json')
        try:
            receipt = json.loads(auth.read_text())
            valid = (auth.stat().st_uid == os.geteuid() and auth.stat().st_mode & 0o077 == 0
                     and receipt.get('node') == node and receipt.get('target') == '26.04.1'
                     and receipt.get('payload_sha256') == digest
                     and all(isinstance(receipt.get('evidence', {}).get(gate), str)
                             and receipt['evidence'][gate].strip() for gate in GATES))
        except (OSError, ValueError, TypeError):
            valid = False
        if not valid:
            raise RuntimeError('missing or mismatched root-owned authorization evidence receipt')
        directory.mkdir(mode=0o700)
        descriptor = os.open(directory.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        (directory / 'authorization.json').write_bytes(auth.read_bytes())
        write_state(root, operation, dict(status='submitted', operation=operation,
                    node=node, target='26.04.1', boot_id=boot_id(root), payload_sha256=digest))
        # Persist before submission: loss of a reply is unknown, never permission to retry.
        try:
            subprocess.run([
                'systemd-run', '--unit=cps-os-upgrade-' + operation, '--service-type=exec',
                '--property=Restart=no', '--property=TimeoutStartSec=infinity',
                '--property=StandardOutput=append:/' + BASE + '/' + operation + '/systemd.log',
                '--property=StandardError=inherit',
                '/usr/bin/python3', str(Path(__file__).resolve()), 'execute', '--operation', operation,
            ], check=True)
        except Exception as error:
            # execute also takes this lock, so a service whose submission reply
            # was lost cannot start upgrading after we mark it ambiguous.
            write_state(root, operation, {'status': 'unknown', 'reason': 'systemd submission reply lost', 'error': str(error)})
            raise


def execute(root, operation):
    with locked(root):
        state = read_state(root, operation)
        if state['status'] != 'submitted' or state['boot_id'] != boot_id(root):
            raise RuntimeError('not an untouched submission; reconcile required')
        write_state(root, operation, {'status': 'running'})
        try:
            current = release(root)
            if current.get('ID') != 'ubuntu' or current.get('VERSION_ID') != '24.04':
                raise RuntimeError('source must be Ubuntu 24.04')
            if (root / 'var/run/reboot-required').exists():
                raise RuntimeError('prerequisite reboot has not completed')
            if not re.search(r'^Prompt=lts\s*$', (root / 'etc/update-manager/release-upgrades').read_text(), re.M):
                raise RuntimeError('Canonical LTS upgrade channel must be configured')
            audit = subprocess.run(['dpkg', '--audit'], check=True, capture_output=True, text=True)
            if audit.stdout.strip():
                raise RuntimeError('package database needs repair: ' + audit.stdout)
            with (operation_path(root, operation) / 'upgrade.log').open('a', buffering=1) as log:
                subprocess.run(['do-release-upgrade', '-f', 'DistUpgradeViewNonInteractive'],
                               check=True, stdout=log, stderr=subprocess.STDOUT)
            write_state(root, operation, {'status': 'reboot-required'})
        except Exception as error:
            write_state(root, operation, {'status': 'failed', 'error': str(error)})
            raise


def reconcile(root, operation):
    with locked(root):
        state = read_state(root, operation)
        if state['status'] == 'os-verified':
            return state
        if state['boot_id'] != boot_id(root):
            if state['status'] != 'reboot-required':
                return write_state(root, operation, {'status': 'unknown', 'reason': 'reboot before confirmed upgrade completion'})
            current = release(root)
            audit = subprocess.run(['dpkg', '--audit'], check=True, capture_output=True, text=True)
            if (current.get('ID') == 'ubuntu' and current.get('VERSION_ID') == '26.04'
                    and current.get('PRETTY_NAME') == 'Ubuntu 26.04.1 LTS' and not audit.stdout.strip()):
                return write_state(root, operation, {'status': 'os-verified', 'verified_boot_id': boot_id(root)})
            return write_state(root, operation, {'status': 'unknown', 'reason': 'target release or package consistency not verified'})
        if state['status'] in ('submitted', 'running'):
            try:
                unit = subprocess.run(['systemctl', 'show', '--value', '--property=ActiveState',
                                       'cps-os-upgrade-' + operation + '.service'],
                                      check=True, capture_output=True, text=True)
                live = unit.stdout.strip() in ('active', 'activating')
            except (OSError, subprocess.SubprocessError):
                live = False
            if not live:
                return write_state(root, operation, {'status': 'unknown', 'reason': 'host unit missing or no longer active'})
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['launch', 'execute', 'status', 'reconcile'])
    parser.add_argument('--operation', required=True)
    parser.add_argument('--node')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('must run as root on the host')
    root = Path('/')
    if args.action == 'launch':
        launch(root, args.operation, args.node or '')
    elif args.action == 'execute':
        execute(root, args.operation)
    else:
        state = reconcile(root, args.operation) if args.action == 'reconcile' else read_state(root, args.operation)
        print(json.dumps(state, indent=2))


if __name__ == '__main__':
    main()

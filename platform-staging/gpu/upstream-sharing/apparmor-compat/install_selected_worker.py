#!/usr/bin/env python3
"""Prepare the unchanged two-rule AppArmor fix for one explicitly fenced worker.

Inputs are reviewable operator selections, not a new authorization protocol.
Default: local preparation only. --apply is a separate, explicit maintenance step.
"""
import argparse
import hashlib
import inspect
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import uuid

ROOT = Path(__file__).resolve().parent
BASELINE_SHA256 = '21888f007c25c39922acc64267b277ae6f43255e7314fd2a52dcf675c8533994'
PROFILE_SHA256 = '30e2fc1210fc99c4e7060ea6bf7f931f6d6c03fbdc499f5f0584fb5c01c92875'
RAW_SHA256 = '8fd644921ce685e50f6dc8f57db6adb3fa0433d3fae7fa39cfdd673bd951dd82'
SSH_KEY = Path('/home/bjoern/.ssh/id_ed25519')
MAINTENANCE = 'cps.unileoben.ac.at/maintenance'
QUALIFIED = 'cps.unileoben.ac.at/upstream-gpu-sharing'
KERNEL_RELEASE = '7.0.0-43-generic'
OS_VERSION = '26.04'
OS_IMAGE = 'Ubuntu 26.04.1 LTS'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_profiles(payload):
    require(digest(payload['baseline'].encode()) == BASELINE_SHA256, 'source baseline hash mismatch')
    require(digest(payload['profile'].encode()) == PROFILE_SHA256, 'current source profile hash mismatch')
    require(payload['selection']['profile_sha256'] == PROFILE_SHA256, 'selected source profile hash mismatch')


def validate_target(selection):
    require(selection['expected_kernel'] == KERNEL_RELEASE and selection['expected_os_version'] == OS_VERSION,
            'qualified Ubuntu26.04 kernel7.0.0-43-generic target required')


def validate_node(selection, node, parent_release):
    fields = {'node', 'node_uid', 'ip', 'expected_boot', 'expected_kernel', 'expected_os_version',
              'k3s_version', 'containerd_version', 'parent_release', 'profile_sha256'}
    require(set(selection) == fields and all(isinstance(v, str) and v for v in selection.values()),
            'exact nonempty selected-worker fields required')
    validate_target(selection)
    require(re.fullmatch(r'k3s-wk-gpu[1-4]', selection['node']), 'selected worker name required')
    require(selection['parent_release'] == parent_release and parent_release.strip(), 'parent release mismatch')
    for name in ('node_uid', 'expected_boot'):
        require(str(uuid.UUID(selection[name])) == selection[name], 'canonical selected identity required')
    require(isinstance(ipaddress.ip_address(selection['ip']), ipaddress.IPv4Address), 'selected IPv4 required')
    require(selection['k3s_version'] == 'v1.34.9+k3s1' and selection['containerd_version'] == 'v2.2.5-k3s2',
            'reviewed stock runtime versions required')
    metadata = node['metadata']; spec = node['spec']; status = node['status']; info = status['nodeInfo']
    require(metadata.get('deletionTimestamp') is None, 'deleting Node is not eligible')
    require([c.get('status') for c in status.get('conditions', []) if c.get('type') == 'Ready'] == ['True'],
            'exact Ready=True Node required')
    require(info.get('osImage') == OS_IMAGE, 'qualified Ubuntu26.04.1 Node image required')
    require(metadata['name'] == selection['node'] and metadata['uid'] == selection['node_uid'], 'selected Node identity mismatch')
    require([a['address'] for a in status['addresses'] if a['type'] == 'InternalIP'] == [selection['ip']], 'selected Node IP mismatch')
    require(info['bootID'] == selection['expected_boot'] and info['kernelVersion'] == selection['expected_kernel'], 'Node boot/kernel mismatch')
    require(info['kubeletVersion'] == selection['k3s_version'] and
            info['containerRuntimeVersion'] == 'containerd://' + selection['containerd_version'].removeprefix('v'), 'Node runtime mismatch')
    require(spec.get('unschedulable') is True and QUALIFIED not in metadata.get('labels', {}), 'cordoned unqualified Node required')
    require(any(t.get('key') == MAINTENANCE and t.get('value') == 'upstream-pilot' and t.get('effect') == 'NoSchedule'
                for t in spec.get('taints', [])), 'selected maintenance taint required')


def prepare_payload(selection, node, parent_release):
    validate_node(selection, node, parent_release)
    payload = {'selection': selection, 'baseline': (ROOT/'baseline.profile').read_bytes().decode('utf-8'),
               'profile': (ROOT/'cri-containerd.apparmor.d').read_bytes().decode('utf-8')}
    validate_profiles(payload)
    return payload


def checked_key(path):
    path = Path(path)
    require(path == SSH_KEY, 'explicit authorized SSH key path required')
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_mode & 0o777 == 0o600,
            'SSH key must be current-user owned regular mode0600 file')
    return path


def loaded_raw(root):
    profiles = list((root/'sys/kernel/security/apparmor/policy/profiles').glob('cri-containerd.apparmor.d.*'))
    require(len(profiles) == 1, 'exact single loaded containerd profile required')
    return (profiles[0]/'raw_data').read_bytes()


def exclusive_write(path, data, mode, created=None):
    with path.open('xb') as stream:
        if created is not None:
            created.add(path)
        os.fchmod(stream.fileno(), mode)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def host_install(payload, root, observed, command):
    """Real filesystem transaction; command is the OS execution boundary."""
    validate_profiles(payload)
    selection = payload['selection']
    validate_target(selection)
    require(observed['hostname'] == selection['node'], 'selected host mismatch')
    require(observed['kernel'] == selection['expected_kernel'], 'host kernel mismatch')
    boot = root/'proc/sys/kernel/random/boot_id'
    require(boot.read_text().strip() == selection['expected_boot'], 'host boot mismatch')
    os_release = dict(line.split('=', 1) for line in (root/'etc/os-release').read_text().splitlines() if '=' in line)
    require(os_release.get('ID', '').strip('"') == 'ubuntu' and
            os_release.get('VERSION_ID', '').strip('"') == selection['expected_os_version'], 'host OS release mismatch')
    def execute(args, **kwargs):
        return command(args, check=True, capture_output=True, **kwargs).stdout
    version = execute(['/usr/local/bin/k3s', '--version']).decode()
    found = re.search(r'^k3s version (\S+)', version)
    require(found is not None and found.group(1) == selection['k3s_version'], 'host K3s version mismatch')
    runtime = execute(['/usr/local/bin/k3s', 'crictl', 'version']).decode()
    found = re.search(r'^RuntimeVersion:\s*(\S+)', runtime, re.M)
    require(found is not None and found.group(1) == selection['containerd_version'], 'host containerd version mismatch')
    require((root/'proc/sys/kernel/apparmor_restrict_unprivileged_unconfined').read_text().strip() == '1', 'hardening sysctl must remain1')
    raw = loaded_raw(root)
    require(digest(raw) == RAW_SHA256, 'loaded stock raw baseline hash mismatch')
    compiled = execute(['apparmor_parser', '-S', '-K', '-c0'], input=payload['baseline'].encode())
    require(compiled == raw, 'compiled baseline differs from loaded stock policy')
    execute(['apparmor_parser', '-Q', '-K'], input=payload['profile'].encode())
    candidate = execute(['apparmor_parser', '-S', '-K', '-c0'], input=payload['profile'].encode())
    target = root/'etc/apparmor.d/cri-containerd.apparmor.d'
    dropin = root/'etc/systemd/system/k3s-agent.service.d/30-apparmor-compat.conf'
    backup = root/'var/lib/cps-apparmor-compat'
    for path in (target, dropin, backup):
        require(not path.exists() and not path.is_symlink(), 'existing installation/state: reconcile before another action')
    for destination in (target, dropin, backup):
        for parent in destination.parents:
            if parent == root:
                break
            require(not parent.is_symlink(), 'protected parent must not be a symlink')
            if parent.exists():
                info = parent.stat()
                require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and not info.st_mode & 0o022,
                        'protected parent must be owned and not writable by others')
    backup.mkdir(mode=0o700)
    exclusive_write(backup/'original.raw', raw, 0o600)
    exclusive_write(backup/'baseline.profile', payload['baseline'].encode(), 0o600)
    state = {**selection, 'status': 'backup-complete', 'stock_raw_sha256': RAW_SHA256,
             'baseline_sha256': BASELINE_SHA256, 'service_restarted': False}
    exclusive_write(backup/'operation.json', json.dumps(state, indent=2).encode(), 0o600)
    created = set()
    attempted_load = False
    try:
        exclusive_write(target, payload['profile'].encode(), 0o644, created)
        dropin.parent.mkdir(parents=True, exist_ok=True)
        exclusive_write(dropin, b'[Unit]\nRequires=apparmor.service\nAfter=apparmor.service\n', 0o644, created)
        require(boot.read_text().strip() == selection['expected_boot'] and loaded_raw(root) == raw,
                'host boot or loaded baseline changed before replacement')
        attempted_load = True
        execute(['apparmor_parser', '-r', '-K', str(target)])
        require(loaded_raw(root) == candidate, 'loaded candidate differs from compiled policy')
        execute(['systemctl', 'daemon-reload'])
        require(boot.read_text().strip() == selection['expected_boot'], 'host boot changed during operation')
    except BaseException:
        try:
            if attempted_load:
                execute(['apparmor_parser', '-r', '-B', str(backup/'original.raw')])
                require(loaded_raw(root) == raw, 'rollback loaded policy differs from original')
            if dropin in created:
                dropin.unlink()
            if target in created:
                target.unlink()
            if dropin in created:
                execute(['systemctl', 'daemon-reload'])
            state['status'] = 'rolled-back' if attempted_load else 'failed-before-load'
        except BaseException:
            state['status'] = 'rollback-incomplete: reconcile retained backup and files'
            (backup/'operation.json').write_text(json.dumps(state, indent=2))
            raise
        (backup/'operation.json').write_text(json.dumps(state, indent=2))
        raise
    state['status'] = 'installed: acceptance not established'
    (backup/'operation.json').write_text(json.dumps(state, indent=2))
    return state


def render_remote():
    imports = 'import hashlib,json,os,re,stat,subprocess,platform\nfrom pathlib import Path\n'
    constants = '\n'.join(name+' = '+repr(globals()[name]) for name in ('BASELINE_SHA256', 'PROFILE_SHA256', 'RAW_SHA256', 'KERNEL_RELEASE', 'OS_VERSION'))
    functions = '\n'.join(inspect.getsource(f) for f in (require, digest, validate_profiles, validate_target, loaded_raw, exclusive_write, host_install))
    entry = "\nrequire(os.geteuid()==0,'root required')\np=json.load(__import__('sys').stdin)\nprint(json.dumps(host_install(p,Path('/'),{'hostname':platform.node(),'kernel':platform.release()},subprocess.run)))\n"
    return imports + constants + '\n' + functions + entry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--node-json', type=Path, required=True, help='read-only selected Node snapshot')
    parser.add_argument('--ssh-key', type=Path, required=True)
    parser.add_argument('--parent-release', required=True, help='operator correlation ID, not authorization')
    parser.add_argument('--output', type=Path, required=True, help='new local mode0600 review bundle')
    parser.add_argument('--apply', action='store_true', help='requires separately authorized selected-host maintenance')
    args = parser.parse_args(argv)
    selection = json.loads(args.selection.read_text()); node = json.loads(args.node_json.read_text())
    key = checked_key(args.ssh_key)
    payload = prepare_payload(selection, node, args.parent_release)
    remote = render_remote()
    ssh = ['ssh', '-i', str(key), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=3',
           'ubuntu@'+selection['ip'], 'sudo -n python3 -c '+shlex.quote(remote)]
    exclusive_write(args.output, json.dumps({'apply': args.apply, 'payload': payload, 'remote_python': remote,
                                           'ssh_argv': ssh}, indent=2).encode(), 0o600)
    if args.apply:
        current = subprocess.run(['kubectl', 'get', 'node', selection['node'], '-o', 'json'], check=True, capture_output=True, text=True)
        validate_node(selection, json.loads(current.stdout), args.parent_release)
        subprocess.run(ssh, input=json.dumps(payload), text=True, check=True)
    print(json.dumps({'prepared': True, 'apply': args.apply, 'node': selection['node'],
                      'node_uid': selection['node_uid'], 'bundle': str(args.output)}))


if __name__ == '__main__':
    main()

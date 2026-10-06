#!/usr/bin/env python3
"""Forced SSH command: retained datasets only, never arbitrary NAS commands."""
import base64
import hashlib
import json
import os
import shlex
import subprocess
import sys

ROOT = 'persistent1/cps_persistent1_shared/compute'
ROOTS = {1: ROOT, 2: 'persistent1/cps_compute_workspaces'}


def request(command):
    words = shlex.split(command)
    if len(words) != 2 or words[0] != 'cps-workspace-rpc' or len(words[1]) > 32768:
        raise ValueError('Restricted workspace RPC required')
    data = json.loads(base64.b64decode(words[1], validate=True))
    if set(data) != {'version', 'action', 'source', 'group_id', 'actor', 'workspaces'}:
        raise ValueError('Unexpected RPC fields')
    if type(data['version']) is not int or data['version'] not in ROOTS or data['source'] not in ('cps', 'cit') or data['action'] not in ('provision', 'archive', 'status'):
        raise ValueError('Unsupported RPC')
    if not isinstance(data['group_id'], str) or not data['group_id'].strip() or len(data['group_id']) > 256:
        raise ValueError('Invalid group')
    if not isinstance(data['actor'], str) or not data['actor'] or len(data['actor']) > 256:
        raise ValueError('Actor required')
    if not isinstance(data['workspaces'], list) or len(data['workspaces']) > 256 or any(not isinstance(x, str) or len(x) > 256 for x in data['workspaces']):
        raise ValueError('Invalid workspace evidence')
    digest = hashlib.sha256((data['source'] + '\0' + data['group_id']).encode()).hexdigest()
    return data, ROOTS[data['version']] + '/' + data['source'] + '/' + digest


def middleware(method, *args):
    result = subprocess.run(['midclt', 'call', method] + [json.dumps(x) for x in args], check=True, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)


def lookup(dataset, call):
    rows = call('pool.dataset.query', [['id', '=', dataset]])
    if len(rows) > 1:
        raise ValueError('Ambiguous dataset')
    return rows[0] if rows else None


def verify_private_permissions(row, path, call):
    """Read-only gate; never repair existing data or inherited ACLs implicitly."""
    if (row.get('acltype', {}).get('value') != 'POSIX'
            or row.get('aclmode', {}).get('value') != 'DISCARD'):
        raise ValueError('Private POSIX/DISCARD workspace dataset required')
    metadata = call('filesystem.stat', path)
    if (metadata.get('realpath') != path or metadata.get('type') != 'DIRECTORY'
            or metadata.get('uid') != 1000 or metadata.get('gid') != 1000
            or not isinstance(metadata.get('mode'), int) or metadata['mode'] & 0o7777 != 0o770):
        raise ValueError('Verified workspace ownership and mode 0770 required')
    acl = call('filesystem.getacl', path)
    entries = acl.get('acl', [])
    if (acl.get('acltype') != 'POSIX1E' or acl.get('trivial') is not True
            or acl.get('uid') != 1000 or acl.get('gid') != 1000
            or len(entries) != 3 or {e.get('tag') for e in entries} != {'USER_OBJ', 'GROUP_OBJ', 'OTHER'}):
        raise ValueError('Trivial private workspace ACL required')
    for entry in entries:
        expected = {key: entry['tag'] != 'OTHER' for key in ('READ', 'WRITE', 'EXECUTE')}
        if entry.get('id') != -1 or entry.get('default') is not False or entry.get('perms') != expected:
            raise ValueError('Inherited or extended workspace ACL not qualified')
    return {'permissions_verified': True, 'acltype': 'POSIX1E', 'aclmode': 'DISCARD',
            'uid': 1000, 'gid': 1000, 'mode': '0770', 'default_acl': False}


def execute(data, dataset, call=middleware):
    if type(data.get('version')) is not int or data['version'] not in ROOTS:
        raise ValueError('Unsupported storage version')
    root = ROOTS[data['version']]
    digest = hashlib.sha256((data['source'] + '\0' + data['group_id']).encode()).hexdigest()
    if dataset != root + '/' + data['source'] + '/' + digest:
        raise ValueError('Storage version/path mismatch')
    row = lookup(dataset, call)
    if data['action'] == 'provision' and row is None:
        for parent in (root, root + '/' + data['source']):
            if lookup(parent, call) is None:
                call('pool.dataset.create', {'name': parent, 'type': 'FILESYSTEM', 'acltype': 'POSIX', 'aclmode': 'DISCARD'})
        call('pool.dataset.create', {'name': dataset, 'type': 'FILESYSTEM', 'acltype': 'POSIX', 'aclmode': 'DISCARD'})
        # New empty datasets only; never change permissions on existing files.
        job = call('filesystem.setperm', {'path': '/mnt/' + dataset, 'uid': 1000, 'gid': 1000, 'mode': '0770', 'options': {'recursive': False, 'stripacl': True}})
        if isinstance(job, int):
            completed = call('core.job_wait', job)
            if isinstance(completed, dict) and completed.get('error'):
                raise ValueError('Dataset permissions failed')
        row = lookup(dataset, call)
    if row is None:
        raise ValueError('Workspace dataset absent')
    if row.get('mountpoint') != '/mnt/' + dataset:
        raise ValueError('Unexpected dataset mountpoint')
    if data['action'] == 'archive':
        call('pool.dataset.update', dataset, {'readonly': 'ON'})
        row = lookup(dataset, call)
    readonly = row.get('readonly', {}).get('value') == 'ON'
    if data['action'] == 'provision' and readonly:
        raise ValueError('Archived workspace cannot become writable')
    permissions = {}
    if data['action'] == 'provision':
        path = '/mnt/' + dataset
        permissions = verify_private_permissions(row, path, call)
        shares = call('sharing.nfs.query', [['path', '=', path]])
        if not shares:
            call('sharing.nfs.create', {'path': path, 'networks': ['10.71.1.0/24', '10.21.0.0/16'], 'enabled': True, 'ro': False, 'comment': 'CPS compute retained group workspace'})
        elif len(shares) != 1 or shares[0].get('ro') or not shares[0].get('enabled') or set(shares[0].get('networks', [])) != {'10.71.1.0/24', '10.21.0.0/16'} or shares[0].get('hosts'):
            raise ValueError('Unexpected workspace NFS export')
    if data['action'] == 'archive' and not readonly:
        raise ValueError('Read-only property was not verified')
    return {'path': '/mnt/' + dataset, 'read_only': readonly, 'immutable': readonly,
            'files_preserved': True, 'evidence': {'dataset': dataset, 'readonly': readonly, 'mechanism': 'zfs-readonly', **permissions}}


if __name__ == '__main__':
    try:
        payload, name = request(os.environ.get('SSH_ORIGINAL_COMMAND', ''))
        print(json.dumps(execute(payload, name)))
    except Exception:
        print('Workspace RPC rejected or NAS operation failed', file=sys.stderr)
        sys.exit(1)

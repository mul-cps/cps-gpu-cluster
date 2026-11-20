#!/usr/bin/env python3
"""Assemble two private scheduled captures for the existing isolated DB restore.

No Kubernetes calls, credentials, image pulls or restore execution. Linux
renameat2 is required to publish atomically without replacing an existing path.
"""
import argparse
import ctypes
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

FILES = ('hub.pgdump', 'roles.sql', 'workloads.json', 'configmaps.json', 'secrets.json', 'running-images.txt')
OWNERS = {'cps': 'jupyterhub', 'cit': 'cit-jhub'}
DIGEST = re.compile(r'[^\s@]+@sha256:[a-f0-9]{64}')


def private_directory(path):
    path = Path(path)
    if not path.is_absolute(): path = Path.cwd() / path
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink paths are not supported')
    path = path.resolve(strict=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Operator-owned mode 0700 directory required')
    if any((p / '.git').exists() for p in (path, *path.parents)):
        raise ValueError('Capture data must remain outside Git')
    return path


def read_private(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Private regular capture file required')
    # A racing replacement with a FIFO must fail the fstat check, not block.
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600:
            raise ValueError('Operator-owned mode 0600 capture file required')
        data = stream.read()
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('Capture changed during reading')
        return data


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('Duplicate manifest field')
        result[key] = value
    return result


def read_capture(path, owner):
    root = private_directory(path)
    if {p.name for p in root.iterdir()} != set(FILES) | {'manifest.json'}:
        raise ValueError('Exactly six capture files and their manifest required')
    raw_manifest = read_private(root / 'manifest.json')
    manifest = json.loads(raw_manifest, object_pairs_hook=unique_object)
    if (not isinstance(manifest, dict) or manifest.get('owner') != owner
            or manifest.get('capture_mode') != 'roles-acls-configuration'
            or manifest.get('recovery_qualified') is not False):
        raise ValueError('Correct owner and unqualified role/ACL capture required')
    image = manifest.get('image')
    if not isinstance(image, str) or not DIGEST.fullmatch(image):
        raise ValueError('Immutable capture database image required')
    for key in ('created_at', 'client_version'):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            raise ValueError('Declared capture time and client version required')
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*', manifest['client_version']):
        raise ValueError('Numeric PostgreSQL client version required')
    snapshot = manifest.get('configuration_snapshot')
    if (not isinstance(snapshot, dict) or snapshot.get('source') != 'operator-supplied-secret-snapshot'
            or snapshot.get('observed_live') is not False
            or any(not isinstance(snapshot.get(k), str) or not snapshot[k] for k in ('secret_ref', 'uid', 'resource_version', 'captured_at'))):
        raise ValueError('Declared operator snapshot metadata required')
    hub = manifest.get('hub')
    if (not isinstance(hub, dict) or set(hub) != {'image', 'chart_version', 'app_version'}
            or any(value is not None and (not isinstance(value, str) or not value) for value in hub.values())):
        raise ValueError('Declared Hub metadata or explicit unknown values required')
    checksums = manifest.get('sha256')
    if not isinstance(checksums, dict) or set(checksums) != set(FILES):
        raise ValueError('Exact capture checksum set required')
    data = {}
    for name in FILES:
        data[name] = read_private(root / name)
        checksum = checksums[name]
        if not data[name] or not isinstance(checksum, str) or not re.fullmatch(r'[a-f0-9]{64}', checksum) or hashlib.sha256(data[name]).hexdigest() != checksum:
            raise ValueError('Capture checksum mismatch or empty file')
    if not data['hub.pgdump'].startswith(b'PGDMP'):
        raise ValueError('PostgreSQL custom dump required')
    return manifest, raw_manifest, data


def write_private(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def publish(staging, output):
    # A pre-check plus plain rename could overwrite a concurrently created empty
    # directory. Fail closed if the platform cannot provide no-replace rename.
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    if rename is None: raise OSError('Atomic no-replace publication unavailable')
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(staging), -100, os.fsencode(output), 1):
        raise OSError(ctypes.get_errno(), 'Atomic no-replace publication failed')


def validate_restore_contract(path):
    helper = Path(__file__).resolve().parents[2] / 'scripts/compute-platform/restore-hub-backups.py'
    spec = importlib.util.spec_from_file_location('hub_restore_contract', helper)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.validate_bundle(path)


def convert(cps_bundle, cit_bundle, output):
    output = Path(output)
    parent = private_directory(output.parent)
    if output.name in ('', '.', '..'): raise ValueError('New output directory required')
    output = parent / output.name
    if output.exists() or output.is_symlink(): raise ValueError('Output must not already exist')
    inputs = {owner: read_capture(path, owner) for owner, path in [('cps', cps_bundle), ('cit', cit_bundle)]}
    staging = Path(tempfile.mkdtemp(prefix='.partial-conversion-', dir=parent))
    staged_identity = (staging.stat().st_dev, staging.stat().st_ino)
    published = False
    try:
        files = {}; sources = {}
        for owner, (source, raw_manifest, data) in inputs.items():
            namespace = OWNERS[owner]
            renamed = {namespace + ('.pgdump' if name == 'hub.pgdump' else '-' + name): body for name, body in data.items()}
            original_name = namespace + '-capture-manifest.json'
            renamed[original_name] = raw_manifest
            sources[namespace] = {'owner': owner, 'manifest': original_name}
            for name, body in renamed.items():
                write_private(staging / name, body)
                files[name] = {'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}
        manifest = {'conversion_version': 1, 'assembled_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'files': files, 'scheduled_sources': sources, 'recovery_qualified': False,
                    'productionQualified': False, 'coordinated_capture': False,
                    'limitations': ['Byte-preserving assembly only; no restore executed',
                        'Original operator-declared snapshots are not verified live or coordinated',
                        'Hub versions remain as declared or unknown; no connected Hub/NFS or off-host qualification']}
        write_private(staging / 'manifest.json', (json.dumps(manifest, indent=2) + '\n').encode())
        plan = validate_restore_contract(staging)
        for owner, (source, _, _) in inputs.items():
            if plan[OWNERS[owner]]['image'] != source['image']:
                raise ValueError('Snapshot database image disagrees with capture image')
        sync_directory(staging)
        publish(staging, output); published = True
        sync_directory(parent)
        return output
    except BaseException:
        if published:
            info = output.lstat()
            if (info.st_dev, info.st_ino) == staged_identity:
                shutil.rmtree(output)
        raise
    finally:
        if staging.exists(): shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cps-bundle', type=Path, required=True)
    parser.add_argument('--cit-bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try: convert(args.cps_bundle, args.cit_bundle, args.output)
    except (OSError, ValueError):
        parser.exit(1, 'Capture conversion failed; no complete bundle published\n')
    print('Dual-Hub capture bundle assembled; recovery remains unqualified')


if __name__ == '__main__': main()

#!/usr/bin/env python3
"""Capture private CPS/CIT Hub PostgreSQL and Kubernetes configuration backups.

Run with an operator's kubectl access. Bundles contain Secrets and token records.
Keep them outside every Git checkout, and copy to an approved encrypted off-host
backup destination. This command neither schedules backups nor proves recovery.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def capture(args, destination):
    # stdout and stderr can contain credentials; neither reaches the terminal.
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as output:
        result = subprocess.run(['kubectl', '--request-timeout=120s', *args],
                                stdout=output, stderr=subprocess.PIPE, timeout=300)
        if result.returncode:
            raise RuntimeError('Kubernetes backup capture failed; no bundle published')
        output.flush()
        os.fsync(output.fileno())


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def backup(destination):
    destination = Path(destination).resolve()
    if any((parent / '.git').exists() for parent in (destination, *destination.parents)):
        raise ValueError('Backups contain credentials and must be outside Git checkouts')
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.stat().st_uid != os.getuid() or destination.stat().st_mode & 0o777 != 0o700:
        raise ValueError('Backup destination must be owned by the operator with mode 0700')
    staging = Path(tempfile.mkdtemp(prefix='.partial-', dir=destination))
    published = None
    try:
        for namespace, workload, db_var in (
            ('jupyterhub', 'deploy/postgresql', 'POSTGRES_DB'),
            ('cit-jhub', 'statefulset/jupyterhub-postgresql', 'POSTGRES_DATABASE'),
        ):
            for resources, suffix in (
                ('deployments,statefulsets', 'workloads'),
                ('configmaps', 'configmaps'), ('secrets', 'secrets'),
            ):
                capture(['get', resources, '-n', namespace, '-o', 'json'],
                        staging / f'{namespace}-{suffix}.json')
            # Retain exact running imageIDs without exporting pod env/token data.
            pod_file = staging / f'{namespace}-running-images.txt'
            capture(['get', 'pods', '-n', namespace, '-o',
                     'jsonpath={range .items[*]}{.metadata.name}{"\\t"}{range .status.containerStatuses[*]}{.name}{"="}{.imageID}{" "}{end}{"\\n"}{end}'], pod_file)
            # Role/password-hash export requires the existing PostgreSQL admin.
            # Credentials stay inside their database pod and private bundle.
            admin = ('export PGPASSWORD="$POSTGRES_PASSWORD"; user="$POSTGRES_USER"; '
                     if namespace == 'jupyterhub' else
                     'export PGPASSWORD="$POSTGRES_POSTGRES_PASSWORD"; user=postgres; ')
            dump = staging / f'{namespace}.pgdump'
            capture(['exec', '-n', namespace, workload, '--', 'sh', '-ec',
                     admin + 'exec pg_dump --format=custom --create --username="$user" '
                     f'--dbname="${db_var}"'], dump)
            capture(['exec', '-n', namespace, workload, '--', 'sh', '-ec',
                     admin + 'exec pg_dumpall --roles-only --username="$user"'],
                    staging / f'{namespace}-roles.sql')
            with dump.open('rb') as source:
                if source.read(5) != b'PGDMP':
                    raise ValueError('Expected a PostgreSQL custom-format dump; no bundle published')
        manifest = {
            'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'files': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size}
                      for p in sorted(staging.iterdir())},
            'limitations': ['Sequential captures, not a cluster-wide atomic snapshot',
                            'Role and database captures are sequential; changes require a coordinated window',
                            'Tablespaces and cluster-wide configuration are excluded',
                            'No NFS data or volume backup', 'No off-host copy',
                            'Successful capture is not demonstrated recovery'],
        }
        with (staging / 'manifest.json').open('x') as output:
            os.chmod(output.name, 0o600)
            json.dump(manifest, output, indent=2)
            output.write('\n'); output.flush(); os.fsync(output.fileno())
        sync_directory(staging)
        name = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex
        target = destination / name
        staging.rename(target)
        published = target
        sync_directory(destination)
        return published
    except BaseException:
        if published is not None and published.exists():
            shutil.rmtree(published)
        raise
    finally:
        if staging.exists(): shutil.rmtree(staging)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    try:
        result = backup(args.destination)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        parser.exit(1, 'Backup failed; no complete bundle published. Check access and private destination permissions.\n')
    print(f'Protected Hub backup bundle: {result}')

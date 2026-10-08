#!/usr/bin/env python3
"""Validate current private Hub bundles and exercise isolated logical recovery.

No cluster writes, published ports, or production authentication. Execution
requires locally cached exact images; a passed exercise is not full recovery.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time

NAMESPACES = ('jupyterhub', 'cit-jhub')
SUFFIXES = ('.pgdump', '-roles.sql', '-workloads.json', '-configmaps.json', '-secrets.json', '-running-images.txt')


def private_directory(path):
    path = Path(path)
    if path.is_symlink(): raise ValueError('Symlink directories are not supported')
    path = path.resolve(strict=True)
    if not path.is_dir() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o777 != 0o700:
        raise ValueError('Operator-owned mode 0700 directory required')
    if any((p / '.git').exists() for p in (path, *path.parents)):
        raise ValueError('Private recovery data must remain outside Git')
    return path


def validate_bundle(path):
    root = private_directory(path)
    manifest_path = root / 'manifest.json'
    if manifest_path.is_symlink() or manifest_path.stat().st_mode & 0o077:
        raise ValueError('Private regular manifest required')
    manifest = json.loads(manifest_path.read_text())
    files = manifest.get('files', {})
    required = {ns + suffix for ns in NAMESPACES for suffix in SUFFIXES}
    if not required <= files.keys(): raise ValueError('Incomplete current Hub bundle')
    for name, record in files.items():
        if not isinstance(name, str) or Path(name).name != name or name in ('.', '..'):
            raise ValueError('Invalid manifest filename')
        p = root / name
        if not p.exists() or p.is_symlink() or not p.is_file() or p.stat().st_uid != os.getuid() or p.stat().st_mode & 0o077:
            raise ValueError('Missing or nonprivate regular backup file')
        if p.stat().st_size != record.get('bytes') or hashlib.sha256(p.read_bytes()).hexdigest() != record.get('sha256'):
            raise ValueError('Backup checksum mismatch')
    plan = {}
    for ns in NAMESPACES:
        if not (root / (ns + '.pgdump')).read_bytes().startswith(b'PGDMP'):
            raise ValueError('PostgreSQL custom dump required')
        prefix = 'postgresql-' if ns == 'jupyterhub' else 'jupyterhub-postgresql-'
        images = set()
        for line in (root / (ns + '-running-images.txt')).read_text().splitlines():
            fields = line.split()
            if not fields or not fields[0].startswith(prefix): continue
            for entry in fields[1:]:
                container, separator, image = entry.partition('=')
                if separator and container == 'postgresql':
                    image = image.removeprefix('docker-pullable://')
                    if not re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}', image):
                        raise ValueError('Immutable recorded database image required')
                    images.add(image)
        if len(images) != 1: raise ValueError('One unambiguous database image per Hub required')
        image = images.pop()
        repository = image.split('@')[0]
        if repository not in ('docker.io/library/postgres', 'docker.io/bitnami/postgresql'):
            raise ValueError('Unsupported PostgreSQL image initialization')
        plan[ns] = {'image': image, 'bitnami': repository.endswith('/bitnami/postgresql')}
    return plan


def role_sql(data, bootstrap):
    if bootstrap.encode() in data: raise ValueError('Bootstrap role collides with source roles')
    if data.count(b'CREATE ROLE postgres;') > 1: raise ValueError('Ambiguous postgres role creation')
    # Images may precreate postgres. Preserve every source ALTER and membership.
    return data.replace(b'CREATE ROLE postgres;', b"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='postgres') THEN CREATE ROLE postgres; END IF; END $$;")


def restore(bundle, output):
    plan = validate_bundle(bundle)  # Validate everything before any container.
    root = private_directory(bundle)
    output = Path(output)
    if output.exists(): raise ValueError('Use a new private evidence destination')
    if any((p / '.git').exists() for p in (output.resolve(), *output.resolve().parents)):
        raise ValueError('Recovery evidence must remain outside Git')
    output.mkdir(mode=0o700, parents=True)
    manifest = json.loads((root / 'manifest.json').read_text())
    snapshots = {}
    # Freeze reverified inputs before running any restore; never mutate backups.
    for ns in NAMESPACES:
        for suffix in ('.pgdump', '-roles.sql'):
            name = ns + suffix; data = (root / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != manifest['files'][name]['sha256']:
                raise ValueError('Backup changed after validation')
            snapshots[name] = data
    reports = {}
    for ns, settings in plan.items():
        name = 'cps-hub-restore-' + secrets.token_hex(8)
        user = 'restore_' + secrets.token_hex(8); password = secrets.token_urlsafe(32)
        roles = role_sql(snapshots[ns + '-roles.sql'], user)
        env = {'POSTGRES_USER': user, 'POSTGRES_PASSWORD': password, 'POSTGRES_DB': 'restore_bootstrap'}
        if settings['bitnami']:
            env.update(POSTGRESQL_USERNAME=user, POSTGRESQL_PASSWORD=password,
                       POSTGRESQL_DATABASE='restore_bootstrap', POSTGRESQL_POSTGRES_PASSWORD=password)
        envfile = output / (ns + '-bootstrap.env')
        with envfile.open('x') as stream:
            os.chmod(envfile, 0o600); stream.write(''.join(k + '=' + v + '\n' for k, v in env.items()))
        def command(args, data=None):
            result = subprocess.run(['podman', *args], input=data, capture_output=True, timeout=120)
            if result.returncode:
                p = output / (ns + '-private-error.log')
                with p.open('ab') as stream: os.chmod(p, 0o600); stream.write(result.stderr)
                raise RuntimeError('Isolated restore failed; private diagnostic retained')
            return result.stdout
        def sql(tool, *args, data=None):
            return command(['exec', '-i', name, 'sh', '-ec', 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec "$@"',
                            'sh', tool, '-h', '127.0.0.1', '-U', user, *args], data)
        try:
            command(['run', '-d', '--pull=never', '--name', name, '--network', 'none',
                     '--memory', '1g', '--cpus', '1', '--env-file', str(envfile), settings['image']])
            # Authenticate against the final bootstrap database, not Bitnami's temporary init server.
            for attempt in range(60):
                try: sql('psql', '-X', '-d', 'restore_bootstrap', '-Atc', 'SELECT 1'); break
                except RuntimeError:
                    if attempt == 59: raise
                    time.sleep(1)
            if settings['bitnami']:
                command(['exec', name, 'sh', '-ec', 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -X -h 127.0.0.1 -U postgres -d postgres -v ON_ERROR_STOP=1 -c "$1"',
                         'sh', 'ALTER ROLE ' + user + ' WITH SUPERUSER'])
            sql('psql', '-X', '-d', 'restore_bootstrap', '-v', 'ON_ERROR_STOP=1', data=roles)
            sql('pg_restore', '-d', 'restore_bootstrap', '--create', '--exit-on-error', data=snapshots[ns + '.pgdump'])
            databases = sql('psql', '-X', '-d', 'restore_bootstrap', '-Atc', "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname NOT IN ('postgres','restore_bootstrap')").decode().splitlines()
            if len(databases) != 1: raise ValueError('One restored Hub database required')
            summary = json.loads(sql('psql', '-X', '-d', databases[0], '-Atc', "SELECT json_build_object('schema',(SELECT version_num FROM alembic_version),'users',(SELECT count(*) FROM users),'databaseVersion',current_setting('server_version'))"))
            reports[ns] = {**summary, 'image': settings['image'], 'logicalRestorePassed': True}
        finally:
            # No volumes/host mounts or published ports exist. Delete only this unique fixture.
            result = subprocess.run(['podman', 'rm', '-f', name], capture_output=True, timeout=60)
            envfile.unlink(missing_ok=True)
            if result.returncode: raise RuntimeError('Restore fixture cleanup failed')
    report = {'hubs': reports, 'productionQualified': False,
              'limitations': ['Database logical restore only; source row equality and role/ACL fingerprints require separate comparisons',
                              'No connected Hub OAuth/spawning, NFS, coordinated snapshot or off-host recovery']}
    p = output / 'report.json'
    with p.open('x') as stream: os.chmod(p, 0o600); json.dump(report, stream, indent=2); stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle'); parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', help='New private evidence directory, required with --execute')
    args = parser.parse_args()
    try:
        if args.execute:
            if not args.output: parser.error('--execute requires --output')
            print(json.dumps(restore(args.bundle, args.output)))
        else: print(json.dumps({'validated': True, 'plan': validate_bundle(args.bundle), 'restoreExecuted': False}))
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired):
        parser.exit(1, 'Hub recovery failed; verify private inputs or inspect private diagnostics.\n')


if __name__ == '__main__': main()

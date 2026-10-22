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


def bootstrap_role(data):
    def closed_object(pairs):
        result = dict(pairs)
        if len(result) != len(pairs): raise ValueError('Duplicate bootstrap metadata key')
        return result
    if len(data) > 4096: raise ValueError('Bounded bootstrap metadata required')
    value = json.loads(data, object_pairs_hook=closed_object)
    if (type(value) is not dict or set(value) != {'version', 'builtin_membership_grantors'}
            or type(value['version']) is not int or value['version'] != 1):
        raise ValueError('Closed version 1 bootstrap metadata required')
    roles = value['builtin_membership_grantors']
    if (type(roles) is not list or len(roles) != 1 or type(roles[0]) is not str
            or not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}', roles[0]) or roles[0].startswith('pg_')):
        raise ValueError('One unambiguous safe builtin membership grantor required')
    return roles[0]


def validate_bundle(path, *, require_bootstrap=False):
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
        metadata_name = ns + '-bootstrap.json'
        initial_role = bootstrap_role((root / metadata_name).read_bytes()) if metadata_name in files else None
        if initial_role is None and require_bootstrap:
            raise ValueError('Fresh source bootstrap metadata required for fingerprints')
        bitnami = repository.endswith('/bitnami/postgresql')
        if bitnami and initial_role not in (None, 'postgres'):
            raise ValueError('Unsupported Bitnami initial bootstrap role')
        plan[ns] = {'image': image, 'bitnami': bitnami, 'initial_role': initial_role}
    return plan


def role_sql(data, bootstrap, initial_role=None):
    if bootstrap.encode() in data: raise ValueError('Bootstrap role collides with source roles')
    if initial_role is not None:
        statements = {('CREATE ROLE ' + initial_role + ';').encode(),
                      ('CREATE ROLE "' + initial_role + '";').encode()}
        lines = data.splitlines(keepends=True)
        matches = [line for line in lines if line.rstrip(b'\r\n') in statements]
        if len(matches) != 1: raise ValueError('Exactly one observed initial role CREATE required')
        return b''.join(line for line in lines if line.rstrip(b'\r\n') not in statements)
    if data.count(b'CREATE ROLE postgres;') > 1: raise ValueError('Ambiguous postgres role creation')
    # Images may precreate postgres. Preserve every source ALTER and membership.
    return data.replace(b'CREATE ROLE postgres;', b"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='postgres') THEN CREATE ROLE postgres; END IF; END $$;")


def restore(bundle, output, *, fingerprint_probe=None):
    plan = validate_bundle(bundle, require_bootstrap=fingerprint_probe is not None)  # Validate everything before any container.
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
        for suffix in ('.pgdump', '-roles.sql', '-bootstrap.json'):
            if suffix == '-bootstrap.json' and plan[ns]['initial_role'] is None: continue
            name = ns + suffix; data = (root / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != manifest['files'][name]['sha256']:
                raise ValueError('Backup changed after validation')
            snapshots[name] = data
    reports = {}
    for ns, settings in plan.items():
        name = 'cps-hub-restore-' + secrets.token_hex(8)
        user = 'restore_' + secrets.token_hex(8); password = secrets.token_urlsafe(32)
        initial_role = settings['initial_role']
        roles = role_sql(snapshots[ns + '-roles.sql'], user, initial_role)
        initial_user = initial_role or user
        # initdb's initial role is also the grantor of built-in memberships.
        # Use its observed identity; legacy bundles remain logical-only.
        env = {'POSTGRES_USER': initial_user, 'POSTGRES_PASSWORD': password, 'POSTGRES_DB': 'restore_bootstrap'}
        if settings['bitnami']:
            env.update(POSTGRESQL_USERNAME=initial_user, POSTGRESQL_PASSWORD=password,
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
        def sql(tool, *args, data=None, read_only=False, as_user=None):
            options = ['--env', 'PGOPTIONS=-c default_transaction_read_only=on'] if read_only else []
            return command(['exec', '-i', *options, name, 'sh', '-ec', 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec "$@"',
                            'sh', tool, '-h', '127.0.0.1', '-U', user if as_user is None else as_user, *args], data)
        try:
            command(['run', '-d', '--pull=never', '--name', name, '--network', 'none',
                     '--memory', '1g', '--cpus', '1', '--env-file', str(envfile), settings['image']])
            # Authenticate against the final bootstrap database, not Bitnami's temporary init server.
            for attempt in range(60):
                try: sql('psql', '-X', '-d', 'restore_bootstrap', '-Atc', 'SELECT 1', as_user=initial_user); break
                except RuntimeError:
                    if attempt == 59: raise
                    time.sleep(1)
            # The independent login survives source ALTER ROLE password replay.
            if initial_role is not None:
                sql('psql', '-X', '-d', 'restore_bootstrap', '-v', 'ON_ERROR_STOP=1', as_user=initial_user,
                    data=("CREATE ROLE " + user + " WITH LOGIN SUPERUSER PASSWORD '" + password + "';\n").encode())
            elif settings['bitnami']:
                sql('psql', '-X', '-d', 'restore_bootstrap', '-v', 'ON_ERROR_STOP=1', as_user='postgres',
                    data=('ALTER ROLE ' + user + ' WITH SUPERUSER;\n').encode())
            sql('psql', '-X', '-d', 'restore_bootstrap', '-v', 'ON_ERROR_STOP=1', data=roles)
            sql('pg_restore', '-d', 'restore_bootstrap', '--create', '--exit-on-error', data=snapshots[ns + '.pgdump'])
            databases = sql('psql', '-X', '-d', 'restore_bootstrap', '-Atc', "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname NOT IN ('postgres','restore_bootstrap')").decode().splitlines()
            if len(databases) != 1: raise ValueError('One restored Hub database required')
            if fingerprint_probe is not None:
                fingerprint_probe(ns, user, lambda query: sql('psql', '-X', '-qAt', '-d', databases[0],
                    '-v', 'ON_ERROR_STOP=1', data=query, read_only=True))
            summary = json.loads(sql('psql', '-X', '-d', databases[0], '-Atc', "SELECT json_build_object('schema',(SELECT version_num FROM alembic_version),'users',(SELECT count(*) FROM users),'databaseVersion',current_setting('server_version'))"))
            reports[ns] = {**summary, 'image': settings['image'], 'logicalRestorePassed': True}
        finally:
            # No volumes/host mounts or published ports exist. Delete only this unique fixture.
            try:
                result = subprocess.run(['podman', 'rm', '-f', name], capture_output=True, timeout=60)
            finally:
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
    parser.add_argument('--fingerprint-output', help='Optional new private logical fingerprint directory; requires admin recovery e442f43577c44be9fab60d5aa9a29e98f491eec5')
    parser.add_argument('--cps-source-fingerprint', help='Optional contemporaneous CPS source fingerprint; requires the CIT pair')
    parser.add_argument('--cit-source-fingerprint', help='Optional contemporaneous CIT source fingerprint; requires the CPS pair')
    args = parser.parse_args()
    if args.fingerprint_output and not args.execute:
        parser.error('--fingerprint-output requires --execute')
    if (args.cps_source_fingerprint or args.cit_source_fingerprint) and not args.fingerprint_output:
        parser.error('Source fingerprints require --fingerprint-output')
    if bool(args.cps_source_fingerprint) != bool(args.cit_source_fingerprint):
        parser.error('Supply both CPS and CIT source fingerprints')
    try:
        if args.execute:
            if not args.output: parser.error('--execute requires --output')
            probe = None
            if args.fingerprint_output:
                validate_bundle(args.bundle, require_bootstrap=True)
                try:
                    from e2x_course_hub.cps.recovery import LogicalRestoreProbe
                except ImportError:
                    parser.error('--fingerprint-output requires e2x_course_hub.cps.recovery from reviewed admin commit e442f43577c44be9fab60d5aa9a29e98f491eec5 on PYTHONPATH')
                expected = {'cps':args.cps_source_fingerprint, 'cit':args.cit_source_fingerprint} if args.cps_source_fingerprint else None
                probe = LogicalRestoreProbe(args.fingerprint_output, expected)
            report = restore(args.bundle, args.output, fingerprint_probe=probe)
            if probe is not None: probe.finish()
            print(json.dumps(report))
        else: print(json.dumps({'validated': True, 'plan': validate_bundle(args.bundle), 'restoreExecuted': False}))
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired):
        parser.exit(1, 'Hub recovery failed; verify private inputs or inspect private diagnostics.\n')


if __name__ == '__main__': main()

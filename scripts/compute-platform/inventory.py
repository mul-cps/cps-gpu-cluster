#!/usr/bin/env python3
"""Read-only inventory and consistent Hub database dumps into a private directory.

Never exports Kubernetes Secrets or Hub tokens. Database dumps are sensitive and
must remain outside the Git repository. This is not an NFS data backup.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess


def kubectl(*args):
    return subprocess.check_output(['kubectl', '--request-timeout=30s', *args])


def collect(output):
    root = Path(__file__).resolve().parents[2]
    output = output.resolve()
    if output == root or root in output.parents:
        raise ValueError('Evidence contains private identity data; choose a directory outside the repository')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(output, 0o700)
    manifest = {'collected_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'context': kubectl('config', 'current-context').decode().strip(), 'files': {},
                'limitations': ['No NFS file backup', 'No canonical identity mapping established',
                                'A dump is not a demonstrated restore', 'Snapshots taken sequentially']}
    resources = {'nodes': ['nodes'], 'volumes': ['pv'], 'fleet': ['gitrepo', '-A'],
                 'queues': ['queues'], 'priorities': ['priorityclasses']}
    for namespace in ('jupyterhub', 'cit-jhub'):
        resources[f'{namespace}-storage'] = ['pvc', '-n', namespace]
        # Only retain deployment names/images/replicas, never env or full specs.
        deployments = json.loads(kubectl('get', 'deploy,statefulset', '-n', namespace, '-o', 'json'))
        resources[f'{namespace}-versions'] = None
        version_file = output / f'{namespace}-versions.json'
        version_file.write_text(json.dumps([{'kind': d['kind'], 'name': d['metadata']['name'],
                                            'replicas': d['spec'].get('replicas'),
                                            'images': [c['image'] for c in d['spec']['template']['spec']['containers']]}
                                           for d in deployments['items']], indent=2))
    for name, args in resources.items():
        if args is not None:
            data = json.loads(kubectl('get', *args, '-o', 'json'))
            for item in data.get('items', []):
                item.get('metadata', {}).pop('managedFields', None)
            (output / f'{name}.json').write_text(json.dumps(data, indent=2))
    databases = [('jupyterhub', 'deploy/postgresql', 'POSTGRES_DB'),
                 ('cit-jhub', 'statefulset/jupyterhub-postgresql', 'POSTGRES_DATABASE')]
    for namespace, target, db_var in databases:
        dump = kubectl('exec', '-n', namespace, target, '--', 'sh', '-ec',
                       f'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump -Fc -U "$POSTGRES_USER" -d "${db_var}"')
        if not dump.startswith(b'PGDMP'):
            raise RuntimeError(f'{namespace}: expected a PostgreSQL custom-format dump')
        (output / f'{namespace}.pgdump').write_bytes(dump)
        # Grants and named server options are in this dump; export only nonsecret
        # identity/storage mapping rows separately for human mapping review.
        query = "COPY (SELECT id, name, admin FROM users ORDER BY id) TO STDOUT WITH CSV HEADER"
        identities = kubectl('exec', '-n', namespace, target, '--', 'sh', '-ec',
                             f'export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "${db_var}" -c "$1"',
                             'sh', query)
        (output / f'{namespace}-identities.csv').write_bytes(identities)
    for path in sorted(output.iterdir()):
        os.chmod(path, 0o600)
        manifest['files'][path.name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                       'bytes': path.stat().st_size}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    os.chmod(output / 'manifest.json', 0o600)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = collect(args.output)
    print(f'Collected {len(result["files"])} private evidence files in {args.output}')

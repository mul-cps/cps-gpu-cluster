"""Back up the single gateway's databases while holding both writer locks."""
import datetime
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile


EXPECTED_SCHEMAS = {
    'control.sqlite': {
        '117209e08648798e0366d4407c38d7e490fc477ce5e350e76391926996dad412',
        '1c71ddfca87431eba59b42101a29a5be9e0b93896737492706cd4c7ee2fd3e73',
    },
    'reservations.sqlite': {
        '0de338b8ba6bce77e4c99005027a15b0e2afaab20cb2803e8077b9e8da39dcb9',
        'e844d75f7f66c2a874e536320adce770cf50e00a412322dbe8b65ca140a78e51',
    },
    'native-kai-private/custody.sqlite': 'a0f7451cc7b7913b9805642f2ceab1dadb83525521ee57a3ac1751f39752057b',
    'native-kai-runtime-private/custody.sqlite': 'a0f7451cc7b7913b9805642f2ceab1dadb83525521ee57a3ac1751f39752057b',
}


def schema_digest(connection):
    schema = connection.execute(
        'SELECT type, name, sql FROM sqlite_master ORDER BY type, name'
    ).fetchall()
    return hashlib.sha256(json.dumps(schema).encode()).hexdigest()


def backup(source, destination, image, policy_hash):
    source, destination = Path(source), Path(destination)
    os.umask(0o077)
    destination.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.partial-', dir=destination))
    locks = []
    try:
        # Acquire every writer lock before taking either snapshot. Separate
        # read connections let the SQLite backup API read committed WAL pages.
        for name in EXPECTED_SCHEMAS:
            lock = sqlite3.connect(f'file:{source / name}?mode=rw', uri=True, timeout=30)
            locks.append(lock)
            lock.execute('BEGIN IMMEDIATE')
        hashes = {}
        schemas = {}
        for name in EXPECTED_SCHEMAS:
            (staging / name).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with closing(sqlite3.connect(f'file:{source / name}?mode=ro', uri=True)) as reader:
                with closing(sqlite3.connect(staging / name)) as writer:
                    reader.backup(writer)
                    if writer.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise RuntimeError(f'Invalid backup: {name}')
                    schemas[name] = schema_digest(writer)
                    allowed = EXPECTED_SCHEMAS[name]
                    if isinstance(allowed, str):
                        allowed = {allowed}
                    if schemas[name] not in allowed:
                        raise RuntimeError(f'Unexpected backup schema: {name}')
            hashes[name] = hashlib.sha256((staging / name).read_bytes()).hexdigest()
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        (staging / 'manifest.json').write_text(json.dumps({
            'created_at': stamp, 'application_image': image,
            'policy_hash': policy_hash, 'sha256': hashes, 'schema_sha256': schemas,
            'scope': 'gateway control, reservation and custody databases; inputs/config backed up separately',
        }, indent=2) + '\n')
        target = destination / stamp
        staging.rename(target)
        return target
    finally:
        for lock in reversed(locks):
            lock.rollback()
            lock.close()
        if staging.exists():
            shutil.rmtree(staging)


if __name__ == '__main__':
    backup('/data', '/backup', os.environ['BACKUP_IMAGE'], os.environ['BACKUP_POLICY_HASH'])

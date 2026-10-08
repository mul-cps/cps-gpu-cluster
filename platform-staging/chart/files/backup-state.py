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


def backup(source, destination, image, policy_hash):
    source, destination = Path(source), Path(destination)
    os.umask(0o077)
    destination.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.partial-', dir=destination))
    locks = []
    try:
        names = ('control.sqlite', 'reservations.sqlite')
        # Acquire every writer lock before taking either snapshot. Separate
        # read connections let the SQLite backup API read committed WAL pages.
        for name in names:
            lock = sqlite3.connect(f'file:{source / name}?mode=rw', uri=True, timeout=30)
            locks.append(lock)
            lock.execute('BEGIN IMMEDIATE')
        hashes = {}
        for name in names:
            with closing(sqlite3.connect(f'file:{source / name}?mode=ro', uri=True)) as reader:
                with closing(sqlite3.connect(staging / name)) as writer:
                    reader.backup(writer)
                    if writer.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise RuntimeError(f'Invalid backup: {name}')
            hashes[name] = hashlib.sha256((staging / name).read_bytes()).hexdigest()
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        (staging / 'manifest.json').write_text(json.dumps({
            'created_at': stamp, 'application_image': image,
            'policy_hash': policy_hash, 'sha256': hashes,
            'scope': 'gateway control and reservation databases; inputs/config backed up separately',
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

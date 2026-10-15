"""Consistent console SQLite backup with private atomic provenance publication."""
from contextlib import closing
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import uuid


def backup(source, destination, image, owner, policy_hash):
    if owner not in ('cps','cit'):
        raise ValueError('Explicit console owner cps/cit required')
    if any(not isinstance(value,str) or not value.strip() for value in (image,policy_hash)):
        raise ValueError('Application image and central policy provenance required')
    source=Path(source).resolve(strict=True)
    if not source.is_file():raise ValueError('Existing console database file required')
    destination=Path(destination)
    old_umask=os.umask(0o077)
    staging=None
    published=None
    complete=False
    try:
        destination.mkdir(parents=True,exist_ok=True)
        staging=Path(tempfile.mkdtemp(prefix='.partial-',dir=destination))
        database=staging/'console.sqlite'
        # SQLite online backup reads a consistent snapshot, including committed
        # WAL pages. Never use immutable=1: it would ignore a live WAL.
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=30)) as reader:
            with closing(sqlite3.connect(database)) as writer:
                reader.backup(writer)
                checks=writer.execute('PRAGMA integrity_check').fetchall()
                if checks!=[('ok',)]:raise RuntimeError('Console backup integrity check failed')
                schema_version=writer.execute('PRAGMA schema_version').fetchone()[0]
                user_version=writer.execute('PRAGMA user_version').fetchone()[0]
                schema=writer.execute('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name').fetchall()
        schema_hash=hashlib.sha256(json.dumps(schema,separators=(',',':')).encode()).hexdigest()
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        manifest={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'owner':owner,'application_image':image,'policy_hash':policy_hash,
            'schema_version':schema_version,'user_version':user_version,'schema_sha256':schema_hash,
            'sha256':{'console.sqlite':hashlib.sha256(database.read_bytes()).hexdigest()},
            'scope':'Single console SQLite database; mounted configuration and central gateway state require matching independent backups'}
        (staging/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        # Durably finish every file and the private staging directory before its
        # atomic rename makes a complete snapshot visible to restore tooling.
        for path in (database,staging/'manifest.json'):
            with path.open('rb') as stream:os.fsync(stream.fileno())
        descriptor=os.open(staging,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        target=destination/(stamp+'-'+uuid.uuid4().hex)
        staging.rename(target)
        published=target
        descriptor=os.open(destination,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        complete=True
        return target
    finally:
        if published is not None and not complete and published.exists():shutil.rmtree(published)
        if staging is not None and staging.exists():shutil.rmtree(staging)
        os.umask(old_umask)


if __name__=='__main__':
    backup(os.environ.get('BACKUP_SOURCE','/state/console.sqlite'),
        os.environ.get('BACKUP_DESTINATION','/backup'),os.environ['BACKUP_IMAGE'],
        os.environ['BACKUP_OWNER'],os.environ['BACKUP_POLICY_HASH'])

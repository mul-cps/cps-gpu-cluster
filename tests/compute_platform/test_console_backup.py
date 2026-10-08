import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('console_backup',ROOT/'platform-staging/chart/files/backup-console.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class ConsoleBackup(unittest.TestCase):
    def test_readonly_backup_restores_committed_wal_and_private_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'live.sqlite'
            with closing(sqlite3.connect(source)) as live:
                live.execute('PRAGMA journal_mode=WAL');live.execute('PRAGMA wal_autocheckpoint=0')
                live.execute('PRAGMA user_version=7')
                live.execute('CREATE TABLE example (person TEXT, value TEXT)')
                live.execute("INSERT INTO example VALUES ('private-person','preserved')");live.commit()
                self.assertTrue(Path(str(source)+'-wal').exists())
                # Inspect the source opener to ensure no writable mode is used.
                original=sqlite3.connect;opens=[]
                def connect(path,*args,**kwargs):opens.append((path,kwargs));return original(path,*args,**kwargs)
                with patch.object(module.sqlite3,'connect',connect):
                    first=module.backup(source,root/'backups','image@sha256:fixture','cps','sha256:policy')
                self.assertTrue(any(str(path).endswith('?mode=ro') and kw.get('uri') for path,kw in opens))
                manifest=json.loads((first/'manifest.json').read_text())
                self.assertEqual(manifest['owner'],'cps');self.assertEqual(manifest['application_image'],'image@sha256:fixture')
                self.assertEqual(manifest['policy_hash'],'sha256:policy');self.assertEqual(manifest['user_version'],7)
                self.assertGreater(manifest['schema_version'],0);self.assertEqual(len(manifest['schema_sha256']),64)
                self.assertNotIn('private-person',(first/'manifest.json').read_text());self.assertNotIn(str(source),(first/'manifest.json').read_text())
                restored_path=first/'console.sqlite'
                self.assertEqual(hashlib.sha256(restored_path.read_bytes()).hexdigest(),manifest['sha256']['console.sqlite'])
                with closing(sqlite3.connect(restored_path)) as restored:
                    self.assertEqual(restored.execute('SELECT * FROM example').fetchall(),[('private-person','preserved')])
                    self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone(),('ok',))
                self.assertEqual(first.stat().st_mode&0o777,0o700)
                for name in ('console.sqlite','manifest.json'):self.assertEqual((first/name).stat().st_mode&0o777,0o600)
                second=module.backup(source,root/'backups','image@sha256:fixture','cit','sha256:policy')
                self.assertNotEqual(first,second);self.assertFalse(list((root/'backups').glob('.partial-*')))

    def test_missing_and_corrupt_sources_never_publish_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);destination=root/'backups';destination.mkdir()
            with self.assertRaises(FileNotFoundError):module.backup(root/'missing',destination,'image','cps','policy')
            corrupt=root/'corrupt.sqlite';corrupt.write_bytes(b'not a SQLite database')
            with self.assertRaises(sqlite3.DatabaseError):module.backup(corrupt,destination,'image','cps','policy')
            self.assertEqual(list(destination.iterdir()),[])
            self.assertFalse((root/'missing').exists())

    def test_failed_manifest_write_does_not_finalize_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.sqlite'
            with closing(sqlite3.connect(source)) as connection:connection.execute('CREATE TABLE example (value TEXT)')
            with patch.object(module.Path,'write_text',side_effect=OSError('simulated destination failure')):
                with self.assertRaises(OSError):module.backup(source,root/'backups','image','cps','policy')
            self.assertEqual(list((root/'backups').iterdir()),[])

    def test_final_directory_flush_failure_removes_published_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.sqlite'
            with closing(sqlite3.connect(source)) as connection:connection.execute('CREATE TABLE example (value TEXT)')
            with patch.object(module.os,'fsync',side_effect=[None,None,None,OSError('directory flush failed')]):
                with self.assertRaises(OSError):module.backup(source,root/'backups','image','cps','policy')
            self.assertEqual(list((root/'backups').iterdir()),[])

    def test_frozen_clock_still_publishes_unique_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.sqlite'
            with closing(sqlite3.connect(source)) as connection:connection.execute('CREATE TABLE example (value TEXT)')
            instant=module.datetime.datetime(2026,10,5,tzinfo=module.datetime.timezone.utc)
            with patch.object(module.datetime,'datetime') as clock:
                clock.now.return_value=instant
                first=module.backup(source,root/'backups','image','cps','policy')
                second=module.backup(source,root/'backups','image','cps','policy')
            self.assertNotEqual(first,second)
            self.assertEqual(first.name.split('-')[0],second.name.split('-')[0])

    def test_owner_and_provenance_are_explicit(self):
        with self.assertRaises(ValueError):module.backup('/missing','/unused','image','other','policy')
        with self.assertRaises(ValueError):module.backup('/missing','/unused','','cps','policy')

if __name__=='__main__':unittest.main()

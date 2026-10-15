import hashlib
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('state_backup', ROOT / 'platform-staging/chart/files/backup-state.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Backup(unittest.TestCase):
    def test_restores_both_wal_databases_and_records_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            connections = []
            try:
                for name in ('control.sqlite', 'reservations.sqlite'):
                    connection = sqlite3.connect(source / name)
                    connections.append(connection)
                    connection.execute('PRAGMA journal_mode=WAL')
                    connection.execute('CREATE TABLE example (value TEXT)')
                    connection.execute("INSERT INTO example VALUES ('preserved')")
                    connection.commit()
                target = module.backup(source, root / 'backups', 'image@sha256:fixture', 'sha256:policy')
                manifest = json.loads((target / 'manifest.json').read_text())
                self.assertEqual(manifest['application_image'], 'image@sha256:fixture')
                self.assertEqual(manifest['policy_hash'], 'sha256:policy')
                for name, digest in manifest['sha256'].items():
                    self.assertEqual(hashlib.sha256((target / name).read_bytes()).hexdigest(), digest)
                    with closing(sqlite3.connect(target / name)) as restored:
                        self.assertEqual(restored.execute('SELECT value FROM example').fetchone(), ('preserved',))
                    self.assertEqual((target / name).stat().st_mode & 0o777, 0o600)
                self.assertFalse(list((root / 'backups').glob('.partial-*')))
            finally:
                for connection in connections:
                    connection.close()

    def test_missing_database_never_publishes_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            with closing(sqlite3.connect(source / 'control.sqlite')) as connection:
                connection.execute('CREATE TABLE example (value TEXT)')
            with self.assertRaises(sqlite3.OperationalError):
                module.backup(source, root / 'backups', 'image', 'policy')
            self.assertEqual(list((root / 'backups').iterdir()), [])

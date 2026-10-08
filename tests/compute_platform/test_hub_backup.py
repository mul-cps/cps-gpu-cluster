import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hub_backup', ROOT / 'scripts/compute-platform/backup-hubs.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class HubBackup(unittest.TestCase):
    def fixture(self, args, destination):
        destination.write_bytes((b'-- PostgreSQL roles fixture' if 'pg_dumpall' in args[-1] else b'PGDMPfixture') if args[0] == 'exec' else json.dumps({'items': []}).encode())
        os.chmod(destination, 0o600)

    def test_publishes_private_checksummed_complete_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(module, 'capture', side_effect=self.fixture):
                target = module.backup(Path(directory) / 'backups')
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)
            manifest = json.loads((target / 'manifest.json').read_text())
            self.assertEqual(len(manifest['files']), 12)
            self.assertIn('cit-jhub-roles.sql', manifest['files'])
            self.assertIn('jupyterhub-roles.sql', manifest['files'])
            for name, record in manifest['files'].items():
                path = target / name
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(module.digest(path), record['sha256'])
            self.assertFalse(list(target.parent.glob('.partial-*')))

    def test_failed_capture_does_not_publish_or_expose_error(self):
        with tempfile.TemporaryDirectory() as directory:
            def fail(args, destination):
                self.fixture(args, destination)
                raise RuntimeError('fixture failure')
            root = Path(directory) / 'backups'
            with patch.object(module, 'capture', side_effect=fail):
                with self.assertRaises(RuntimeError):
                    module.backup(root)
            self.assertEqual(list(root.iterdir()), [])

    def test_invalid_dump_does_not_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            def invalid(args, destination):
                self.fixture(args, destination)
                if args[0] == 'exec': destination.write_bytes(b'not a dump')
            root = Path(directory) / 'backups'
            with patch.object(module, 'capture', side_effect=invalid):
                with self.assertRaises(ValueError): module.backup(root)
            self.assertEqual(list(root.iterdir()), [])

    def test_rejects_public_destination_and_git_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / 'public'; public.mkdir(mode=0o755); public.chmod(0o755)
            with self.assertRaises(ValueError): module.backup(public)
            repo = root / 'repo'; repo.mkdir(); (repo / '.git').mkdir()
            with self.assertRaises(ValueError): module.backup(repo / 'backup')

    def test_role_export_failure_never_publishes_and_preserves_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'backups'
            commands = []
            def capture(args, destination):
                commands.append(args)
                if 'pg_dumpall' in args[-1]: raise RuntimeError('role export denied')
                self.fixture(args, destination)
            with patch.object(module, 'capture', side_effect=capture):
                with self.assertRaises(RuntimeError): module.backup(root)
            self.assertEqual(list(root.iterdir()), [])
            self.assertTrue(any('pg_dumpall' in a[-1] for a in commands))
            for args in commands:
                if args[0] == 'exec' and 'pg_dump ' in args[-1]:
                    self.assertNotIn('--no-owner', args[-1])
                    self.assertNotIn('--no-acl', args[-1])

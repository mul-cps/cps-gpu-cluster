"""Synthetic scheduled captures; no credentials, containers or cluster access."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
ADAPTER = ROOT / 'platform-staging/hub-backups/convert_capture_bundles.py'
FILES = ('hub.pgdump', 'roles.sql', 'workloads.json', 'configmaps.json', 'secrets.json', 'running-images.txt')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


converter = load('capture_conversion', ADAPTER)
restore = load('existing_hub_restore', ROOT / 'scripts/compute-platform/restore-hub-backups.py')


class CaptureConversion(unittest.TestCase):
    def fixture(self, root, owner):
        path = root / owner; path.mkdir(mode=0o700)
        image = ('docker.io/library/postgres' if owner == 'cps' else 'docker.io/bitnami/postgresql') + '@sha256:' + ('a' if owner == 'cps' else 'b') * 64
        prefix = 'postgresql-fixture' if owner == 'cps' else 'jupyterhub-postgresql-fixture'
        bodies = {'hub.pgdump': b'PGDMPsynthetic', 'roles.sql': b'CREATE ROLE fixture;\nALTER ROLE fixture WITH LOGIN;\n',
                  'workloads.json': b'{"items":[]}', 'configmaps.json': b'{}', 'secrets.json': b'{"synthetic":true}',
                  'running-images.txt': (prefix + '\tpostgresql=docker-pullable://' + image + '\n').encode()}
        for name, data in bodies.items():
            p = path / name; p.write_bytes(data); p.chmod(0o600)
        manifest = {'owner': owner, 'image': image, 'capture_mode': 'roles-acls-configuration',
                    'created_at': '20261007T120000Z', 'client_version': '15.17' if owner == 'cps' else '18.4',
                    'recovery_qualified': False, 'hub': {'image': None, 'chart_version': None, 'app_version': None},
                    'configuration_snapshot': {'source': 'operator-supplied-secret-snapshot', 'observed_live': False,
                        'secret_ref': 'synthetic-snapshot', 'uid': 'synthetic-uid', 'resource_version': '123', 'captured_at': '2026-10-07T12:00:00Z'},
                    'sha256': {name: hashlib.sha256(data).hexdigest() for name, data in bodies.items()}}
        self.write_manifest(path, manifest)
        return path

    def write_manifest(self, path, manifest):
        p = path / 'manifest.json'; p.write_text(json.dumps(manifest)); p.chmod(0o600)

    def test_byte_identical_dual_bundle_is_accepted_by_unchanged_restore_validator(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory); cps = self.fixture(root, 'cps'); cit = self.fixture(root, 'cit')
            before = {owner: {p.name: p.read_bytes() for p in source.iterdir()} for owner, source in [('cps', cps), ('cit', cit)]}
            output = root / 'converted'; converter.convert(cps, cit, output)
            plan = restore.validate_bundle(output)
            manifest = json.loads((output / 'manifest.json').read_bytes())
            self.assertFalse(manifest['recovery_qualified']); self.assertFalse(manifest['coordinated_capture'])
            self.assertFalse(manifest['productionQualified'])
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
            self.assertEqual(len(manifest['files']), 14)
            for owner, namespace in [('cps', 'jupyterhub'), ('cit', 'cit-jhub')]:
                source_manifest = json.loads(before[owner]['manifest.json'])
                self.assertEqual(plan[namespace]['image'], source_manifest['image'])
                source_reference = manifest['scheduled_sources'][namespace]
                self.assertEqual(source_reference['owner'], owner)
                self.assertEqual((output / source_reference['manifest']).read_bytes(), before[owner]['manifest.json'])
                self.assertIsNone(source_manifest['hub']['image'])
                self.assertIs(source_manifest['configuration_snapshot']['observed_live'], False)
                for name in FILES:
                    target = namespace + ('.pgdump' if name == 'hub.pgdump' else '-' + name)
                    self.assertEqual((output / target).read_bytes(), before[owner][name])
                self.assertEqual({p.name: p.read_bytes() for p in (root / owner).iterdir()}, before[owner])
            for name, record in manifest['files'].items():
                p = output / name
                self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
                self.assertEqual(record, {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})

    def test_logical_swapped_owners_forged_live_claims_and_bad_checksums_are_rejected(self):
        cases = [('owner', 'cit'), ('capture_mode', 'logical'), ('recovery_qualified', 'false'),
                 ('image', 'docker.io/library/postgres:15'), ('client_version', 'unknown'), ('sha256', {}),
                 ('configuration_snapshot', {'observed_live': True}), ('hub', {'image': None})]
        for key, value in cases:
            with self.subTest(key=key), tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
                root = Path(directory); cps = self.fixture(root, 'cps'); cit = self.fixture(root, 'cit')
                manifest = json.loads((cps / 'manifest.json').read_bytes()); manifest[key] = value; self.write_manifest(cps, manifest)
                with self.assertRaises(ValueError): converter.convert(cps, cit, root / 'output')
                self.assertFalse((root / 'output').exists())

    def test_missing_corrupt_nonprivate_nonregular_and_symlink_sources_are_rejected(self):
        for case in ('missing', 'corrupt', 'public-file', 'public-directory', 'symlink-file', 'symlink-directory', 'nonregular', 'extra-file'):
            with self.subTest(case=case), tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
                root = Path(directory); cps = self.fixture(root, 'cps'); cit = self.fixture(root, 'cit'); p = cps / 'roles.sql'
                if case == 'missing': p.unlink()
                if case == 'corrupt': p.write_bytes(b'changed')
                if case == 'public-file': p.chmod(0o644)
                if case == 'public-directory': cps.chmod(0o755)
                if case == 'symlink-file': p.rename(root / 'original-role'); p.symlink_to(root / 'original-role')
                if case == 'symlink-directory': cps.rename(root / 'original'); cps.symlink_to(root / 'original')
                if case == 'nonregular': p.unlink(); p.mkdir(mode=0o700)
                if case == 'extra-file': (cps / 'private-error').write_bytes(b'error')
                with self.assertRaises(ValueError): converter.convert(cps, cit, root / 'output')
                self.assertFalse((root / 'output').exists())

    def test_snapshot_database_image_disagreement_is_rejected_without_inventing_image_rows(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory); cps = self.fixture(root, 'cps'); cit = self.fixture(root, 'cit')
            manifest = json.loads((cps / 'manifest.json').read_bytes()); manifest['image'] = 'docker.io/library/postgres@sha256:' + 'c' * 64; self.write_manifest(cps, manifest)
            original = (cps / 'running-images.txt').read_bytes()
            with self.assertRaises(ValueError): converter.convert(cps, cit, root / 'output')
            self.assertEqual((cps / 'running-images.txt').read_bytes(), original)
            self.assertEqual({p.name for p in root.iterdir()}, {'cps', 'cit'})

    def test_output_collision_and_copy_failure_leave_inputs_and_existing_output_unchanged(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory); cps = self.fixture(root, 'cps'); cit = self.fixture(root, 'cit')
            output = root / 'existing'; output.mkdir(mode=0o700); (output / 'keep').write_bytes(b'keep')
            with self.assertRaises(ValueError): converter.convert(cps, cit, output)
            self.assertEqual((output / 'keep').read_bytes(), b'keep')
            with patch.object(converter, 'write_private', side_effect=OSError('synthetic copy failure')):
                with self.assertRaises(OSError): converter.convert(cps, cit, root / 'new')
            self.assertEqual({p.name for p in root.iterdir()}, {'cps', 'cit', 'existing'})
            self.assertEqual((cps / 'roles.sql').read_bytes(), b'CREATE ROLE fixture;\nALTER ROLE fixture WITH LOGIN;\n')

    def test_sources_inside_git_and_symlink_parent_paths_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory); cps = self.fixture(root, 'cps'); cit = self.fixture(root, 'cit')
            alias = root / 'alias'; alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError): converter.convert(alias / 'cps', cit, root / 'output')
            (root / '.git').write_text('gitdir: synthetic')
            with self.assertRaises(ValueError): converter.convert(cps, cit, root / 'output')

    def test_wrong_file_owner_and_duplicate_manifest_fields_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory); cps = self.fixture(root, 'cps'); cit = self.fixture(root, 'cit')
            with patch.object(converter.os, 'fstat', return_value=SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=os.getuid()+1)):
                with self.assertRaises(ValueError): converter.convert(cps, cit, root / 'output')
            p = cps / 'manifest.json'
            p.write_bytes(p.read_bytes().replace(b'{', b'{"owner":"cit",', 1))
            with self.assertRaises(ValueError): converter.convert(cps, cit, root / 'output')
            self.assertEqual({p.name for p in root.iterdir()}, {'cps', 'cit'})

    def test_concurrent_empty_destination_is_not_replaced(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory); cps = self.fixture(root, 'cps'); cit = self.fixture(root, 'cit')
            output = root / 'output'; real_publish = converter.publish
            def create_destination(staging, target):
                target.mkdir(mode=0o700)
                real_publish(staging, target)
            with patch.object(converter, 'publish', side_effect=create_destination):
                with self.assertRaises(OSError): converter.convert(cps, cit, output)
            self.assertTrue(output.is_dir()); self.assertEqual(list(output.iterdir()), [])
            self.assertEqual({p.name for p in root.iterdir()}, {'cps', 'cit', 'output'})

    def test_parent_sync_failure_removes_only_the_newly_published_bundle(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory); cps = self.fixture(root, 'cps'); cit = self.fixture(root, 'cit')
            real_sync = converter.sync_directory
            def fail_parent(path):
                if path == root: raise OSError('synthetic parent sync failure')
                real_sync(path)
            with patch.object(converter, 'sync_directory', side_effect=fail_parent):
                with self.assertRaises(OSError): converter.convert(cps, cit, root / 'output')
            self.assertEqual({p.name for p in root.iterdir()}, {'cps', 'cit'})

    def test_cli_never_prints_capture_bytes_hashes_or_private_diagnostics(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory); cps = self.fixture(root, 'cps'); cit = self.fixture(root, 'cit')
            command = ['python', str(ADAPTER), '--cps-bundle', str(cps), '--cit-bundle', str(cit), '--output', str(root / 'output')]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('recovery remains unqualified', result.stdout)
            self.assertNotIn('CREATE ROLE', result.stdout + result.stderr)
            self.assertNotIn(hashlib.sha256((cps / 'roles.sql').read_bytes()).hexdigest(), result.stdout + result.stderr)
            command[-1] = str(root / 'failed')
            manifest = json.loads((cps / 'manifest.json').read_bytes()); manifest['owner'] = 'synthetic-private-diagnostic'; self.write_manifest(cps, manifest)
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr, 'Capture conversion failed; no complete bundle published\n')
            self.assertNotIn('synthetic-private-diagnostic', result.stdout + result.stderr)
            self.assertFalse((root / 'failed').exists())

    def test_failure_cleanup_does_not_remove_a_concurrently_replaced_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            root = Path(directory); cps = self.fixture(root, 'cps'); cit = self.fixture(root, 'cit')
            output = root / 'output'; real_sync = converter.sync_directory
            def replace_output(path):
                if path == root:
                    output.rename(root / 'moved-complete-bundle')
                    output.mkdir(mode=0o700); (output / 'other-owner-file').write_bytes(b'preserve')
                    raise OSError('synthetic parent sync failure')
                real_sync(path)
            with patch.object(converter, 'sync_directory', side_effect=replace_output):
                with self.assertRaises(OSError): converter.convert(cps, cit, output)
            self.assertEqual((output / 'other-owner-file').read_bytes(), b'preserve')
            self.assertTrue((root / 'moved-complete-bundle' / 'manifest.json').is_file())


if __name__ == '__main__': unittest.main()

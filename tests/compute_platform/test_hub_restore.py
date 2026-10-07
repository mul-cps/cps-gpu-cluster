import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hub_restore', ROOT / 'scripts/compute-platform/restore-hub-backups.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class HubRestore(unittest.TestCase):
    def fixture(self, root):
        for ns, prefix, image in (
            ('jupyterhub', 'postgresql-abc', 'docker.io/library/postgres@sha256:' + 'a' * 64),
            ('cit-jhub', 'jupyterhub-postgresql-0', 'docker.io/bitnami/postgresql@sha256:' + 'b' * 64),
        ):
            for suffix, body in (
                ('.pgdump', b'PGDMPfixture'), ('-roles.sql', b'CREATE ROLE postgres;\n'),
                ('-workloads.json', b'{"items":[]}'), ('-configmaps.json', b'{}'),
                ('-secrets.json', b'{}'), ('-running-images.txt', f'{prefix}\tpostgresql={image} \n'.encode()),
            ):
                p = root / (ns + suffix); p.write_bytes(body); p.chmod(0o600)
        manifest = {'files': {p.name: {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size} for p in root.iterdir()}}
        p = root / 'manifest.json'; p.write_text(json.dumps(manifest)); p.chmod(0o600)

    def test_current_bundle_selects_distinct_immutable_database_images(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as tmp:
            root = Path(tmp); self.fixture(root)
            plan = module.validate_bundle(root)
            self.assertEqual(plan['jupyterhub']['image'], 'docker.io/library/postgres@sha256:' + 'a' * 64)
            self.assertEqual(plan['cit-jhub']['image'], 'docker.io/bitnami/postgresql@sha256:' + 'b' * 64)

    def test_corrupt_missing_public_and_symlink_inputs_are_rejected(self):
        for case in ('corrupt', 'missing', 'public', 'symlink'):
            with self.subTest(case=case), tempfile.TemporaryDirectory(dir=ROOT.parent) as tmp:
                root = Path(tmp); self.fixture(root); p = root / 'jupyterhub.pgdump'
                if case == 'corrupt': p.write_bytes(b'PGDMPchanged')
                if case == 'missing': p.unlink()
                if case == 'public': root.chmod(0o755)
                if case == 'symlink': p.rename(root / 'actual'); p.symlink_to(root / 'actual')
                with self.assertRaises(ValueError): module.validate_bundle(root)

    def test_mutable_and_ambiguous_database_images_are_rejected(self):
        for image in ('docker.io/library/postgres:15', 'docker.io/library/postgres@sha256:' + 'a' * 64 + ' postgresql=docker.io/library/postgres@sha256:' + 'c' * 64):
            with self.subTest(image=image), tempfile.TemporaryDirectory(dir=ROOT.parent) as tmp:
                root = Path(tmp); self.fixture(root)
                p = root / 'jupyterhub-running-images.txt'; p.write_text('postgresql-abc\tpostgresql=' + image + '\n')
                manifest = json.loads((root / 'manifest.json').read_text()); manifest['files'][p.name] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
                (root / 'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError): module.validate_bundle(root)

    def test_role_replay_preserves_alter_statements_and_rejects_bootstrap_collision(self):
        roles = b'CREATE ROLE postgres;\nALTER ROLE postgres WITH SUPERUSER;\nCREATE ROLE instructor;\n'
        result = module.role_sql(roles, 'restore_abc')
        self.assertIn(b'IF NOT EXISTS', result)
        self.assertIn(b'ALTER ROLE postgres WITH SUPERUSER;', result)
        self.assertIn(b'CREATE ROLE instructor;', result)
        with self.assertRaises(ValueError): module.role_sql(roles, 'instructor')


if __name__ == '__main__': unittest.main()

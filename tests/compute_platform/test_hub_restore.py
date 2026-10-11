import hashlib
import importlib.util
import builtins
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hub_restore', ROOT / 'scripts/compute-platform/restore-hub-backups.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakePostgres:
    """Only the existing Podman boundary is replaced; no real process runs."""
    def __init__(self, *, cleanup_timeout=False, query_failure=False):
        self.calls = []
        self.sources = {}
        self.cleanup_timeout = cleanup_timeout
        self.query_failure = query_failure

    def __call__(self, args, *, input=None, capture_output=True, timeout=None):
        self.calls.append((list(args), input))
        stdout = b''
        if args[1] == 'run':
            name = args[args.index('--name') + 1]
            source = Path(args[args.index('--env-file') + 1]).name.removesuffix('-bootstrap.env')
            self.sources[name] = source
        elif args[1] == 'rm' and self.cleanup_timeout:
            raise subprocess.TimeoutExpired(args, timeout)
        elif args[1] == 'exec':
            name = next(value for value in args if value in self.sources)
            if 'SELECT datname' in args[-1]:
                stdout = ('hub_' + self.sources[name] + '\n').encode()
            elif 'json_build_object' in args[-1]:
                stdout = b'{"schema":"schema-fixture","users":12,"databaseVersion":"15.17"}'
            elif input == b'fingerprint-query':
                if self.query_failure:
                    return subprocess.CompletedProcess(args, 1, b'', b'private diagnostic')
                stdout = b'fingerprint-result'
        return subprocess.CompletedProcess(args, 0, stdout, b'')


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
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            plan = module.validate_bundle(root)
            self.assertEqual(plan['jupyterhub']['image'], 'docker.io/library/postgres@sha256:' + 'a' * 64)
            self.assertEqual(plan['cit-jhub']['image'], 'docker.io/bitnami/postgresql@sha256:' + 'b' * 64)

    def test_corrupt_missing_public_and_symlink_inputs_are_rejected(self):
        for case in ('corrupt', 'missing', 'public', 'symlink'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); self.fixture(root); p = root / 'jupyterhub.pgdump'
                if case == 'corrupt': p.write_bytes(b'PGDMPchanged')
                if case == 'missing': p.unlink()
                if case == 'public': root.chmod(0o755)
                if case == 'symlink': p.rename(root / 'actual'); p.symlink_to(root / 'actual')
                with self.assertRaises(ValueError): module.validate_bundle(root)

    def test_mutable_and_ambiguous_database_images_are_rejected(self):
        for image in ('docker.io/library/postgres:15', 'docker.io/library/postgres@sha256:' + 'a' * 64 + ' postgresql=docker.io/library/postgres@sha256:' + 'c' * 64):
            with self.subTest(image=image), tempfile.TemporaryDirectory() as tmp:
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

    def test_default_restore_keeps_logical_only_report_and_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root); runner = FakePostgres()
            with mock.patch.object(module.subprocess, 'run', runner):
                report = module.restore(root, root / 'result')
            self.assertEqual(set(report), {'hubs', 'productionQualified', 'limitations'})
            self.assertFalse(report['productionQualified'])
            self.assertEqual(set(report['hubs']), set(module.NAMESPACES))
            self.assertFalse(any('--env' in args for args, _ in runner.calls))
            self.assertFalse(list((root / 'result').glob('*-bootstrap.env')))
            self.assertEqual(len([args for args, _ in runner.calls if args[1] == 'rm']), 2)

    def test_probe_runs_after_database_selection_with_scoped_read_only_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root); runner = FakePostgres(); seen = []
            def probe(namespace, role, read_only_sql):
                self.assertIn('SELECT datname', runner.calls[-1][0][-1])
                self.assertRegex(role, r'^restore_[a-f0-9]{16}$')
                self.assertEqual(read_only_sql(b'fingerprint-query'), b'fingerprint-result')
                query_args = runner.calls[-1][0]
                self.assertIn('PGOPTIONS=-c default_transaction_read_only=on', query_args)
                self.assertIn('hub_' + namespace, query_args)
                self.assertIn('-X', query_args); self.assertIn('-qAt', query_args)
                self.assertIn('ON_ERROR_STOP=1', query_args)
                seen.append(namespace)
            with mock.patch.object(module.subprocess, 'run', runner):
                module.restore(root, root / 'result', fingerprint_probe=probe)
            self.assertEqual(seen, list(module.NAMESPACES))
            created = list(runner.sources)
            self.assertEqual(len(set(created)), 2)
            self.assertEqual([args[-1] for args, _ in runner.calls if args[1] == 'rm'], created)

    def test_probe_and_query_failures_remove_only_owned_fixture_and_private_environment(self):
        for failure in ('probe', 'query', 'interrupt'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); self.fixture(root)
                runner = FakePostgres(query_failure=failure == 'query')
                def probe(namespace, role, read_only_sql):
                    if failure == 'query': read_only_sql(b'fingerprint-query')
                    elif failure == 'interrupt': raise KeyboardInterrupt()
                    else: raise ValueError('private callback detail')
                expected = {'probe':ValueError, 'query':RuntimeError, 'interrupt':KeyboardInterrupt}[failure]
                with mock.patch.object(module.subprocess, 'run', runner), self.assertRaises(expected):
                    module.restore(root, root / 'result', fingerprint_probe=probe)
                self.assertEqual(len(runner.sources), 1)
                self.assertEqual([args[-1] for args, _ in runner.calls if args[1] == 'rm'], list(runner.sources))
                self.assertFalse(list((root / 'result').glob('*-bootstrap.env')))
                self.assertFalse((root / 'result/report.json').exists())
                self.assertTrue((root / 'jupyterhub.pgdump').exists())

    def test_cleanup_timeout_still_removes_private_bootstrap_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root); runner = FakePostgres(cleanup_timeout=True)
            with mock.patch.object(module.subprocess, 'run', runner), self.assertRaises(subprocess.TimeoutExpired):
                module.restore(root, root / 'result')
            self.assertFalse(list((root / 'result').glob('*-bootstrap.env')))
            self.assertEqual(len(runner.sources), 1)

    def test_fingerprint_cli_requires_execution_and_complete_optional_source_pair(self):
        for extra, message in (
            (['--fingerprint-output', '/private/fingerprints'], '--execute'),
            (['--execute', '--output', '/private/restore', '--cps-source-fingerprint', '/private/cps.json'], '--fingerprint-output'),
            (['--execute', '--output', '/private/restore', '--fingerprint-output', '/private/fingerprints', '--cps-source-fingerprint', '/private/cps.json'], 'both'),
        ):
            with self.subTest(extra=extra):
                stderr = io.StringIO()
                with mock.patch.object(sys, 'argv', ['restore', '/private/bundle', *extra]), mock.patch.object(module.subprocess, 'run') as process, contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
                    module.main()
                self.assertIn(message, stderr.getvalue())
                process.assert_not_called()

    def test_missing_optional_admin_dependency_fails_before_any_restore_with_fixed_explanation(self):
        original_import = builtins.__import__
        def unavailable(name, *args, **kwargs):
            if name == 'e2x_course_hub.cps.recovery': raise ImportError('private dependency path')
            return original_import(name, *args, **kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root); stderr = io.StringIO()
            argv = ['restore', str(root), '--execute', '--output', str(root / 'result'), '--fingerprint-output', str(root / 'fingerprints')]
            with mock.patch.object(sys, 'argv', argv), mock.patch.object(builtins, '__import__', unavailable), mock.patch.object(module.subprocess, 'run') as process, contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
                module.main()
            self.assertIn('a0d1bd1', stderr.getvalue())
            self.assertNotIn('private dependency path', stderr.getvalue())
            self.assertFalse((root / 'result').exists()); self.assertFalse((root / 'fingerprints').exists())
            process.assert_not_called()

    def test_fingerprint_cli_composes_both_sources_then_finishes_after_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root); runner = FakePostgres(); events = []
            class Probe:
                def __init__(self, output, source_fingerprints=None):
                    self.output = output; events.append(('expected', source_fingerprints))
                def __call__(self, namespace, role, read_only_sql):
                    self.result = read_only_sql(b'fingerprint-query'); events.append(namespace)
                def finish(self):
                    self.cleanup_count = len([args for args, _ in runner.calls if args[1] == 'rm'])
                    events.append(('finish', self.cleanup_count))
            original_import = builtins.__import__
            def available(name, *args, **kwargs):
                if name == 'e2x_course_hub.cps.recovery': return types.SimpleNamespace(LogicalRestoreProbe=Probe)
                return original_import(name, *args, **kwargs)
            argv = ['restore', str(root), '--execute', '--output', str(root / 'result'), '--fingerprint-output', str(root / 'fingerprints'), '--cps-source-fingerprint', '/private/cps.json', '--cit-source-fingerprint', '/private/cit.json']
            with mock.patch.object(sys, 'argv', argv), mock.patch.object(builtins, '__import__', available), mock.patch.object(module.subprocess, 'run', runner), contextlib.redirect_stdout(io.StringIO()):
                module.main()
            self.assertEqual(events, [('expected', {'cps':'/private/cps.json', 'cit':'/private/cit.json'}), 'jupyterhub', 'cit-jhub', ('finish', 2)])


if __name__ == '__main__': unittest.main()

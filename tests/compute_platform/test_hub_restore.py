import hashlib
import importlib.util
import builtins
import contextlib
import io
import json
import re
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


class BootstrapPostgres(FakePostgres):
    """Model login continuity and initdb grantors at the existing process boundary."""
    def __init__(self, *, bootstrap_failure=False):
        super().__init__()
        self.environments = {}
        self.passwords = {}
        self.grantors = {}
        self.bootstrap_failure = bootstrap_failure

    def __call__(self, args, *, input=None, capture_output=True, timeout=None):
        if args[1] == 'run':
            name = args[args.index('--name') + 1]
            env = dict(line.split('=', 1) for line in Path(args[args.index('--env-file') + 1]).read_text().splitlines())
            self.environments[name] = env
            self.passwords[name] = {env['POSTGRES_USER']:env['POSTGRES_PASSWORD']}
            if 'POSTGRESQL_POSTGRES_PASSWORD' in env:
                self.passwords[name]['postgres'] = env['POSTGRESQL_POSTGRES_PASSWORD']
            self.grantors[name] = 'postgres' if 'POSTGRESQL_USERNAME' in env else env['POSTGRES_USER']
        elif args[1] == 'exec' and '-U' in args:
            name = next(value for value in args if value in self.environments)
            user = args[args.index('-U') + 1]
            if self.passwords[name].get(user) != self.environments[name]['POSTGRES_PASSWORD']:
                return subprocess.CompletedProcess(args, 1, b'', b'fixture authentication failed')
            if input:
                match = re.fullmatch(rb"CREATE ROLE (restore_[a-f0-9]{16}) WITH LOGIN SUPERUSER PASSWORD '([^']+)';\n", input)
                if match:
                    if self.bootstrap_failure:
                        return subprocess.CompletedProcess(args, 1, b'', b'fixture bootstrap failed')
                    self.passwords[name][match[1].decode()] = match[2].decode()
                for role in tuple(self.passwords[name]):
                    if ('ALTER ROLE ' + role + " WITH PASSWORD 'restored-source-password';").encode() in input:
                        self.passwords[name][role] = 'restored-source-password'
        return super().__call__(args, input=input, capture_output=capture_output, timeout=timeout)


class HubRestore(unittest.TestCase):
    def fixture(self, root, *, metadata=True):
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
        if metadata:
            for ns, role in (('jupyterhub', 'jhub'), ('cit-jhub', 'postgres')):
                p = root / (ns + '-bootstrap.json')
                p.write_text(json.dumps({'version':1, 'builtin_membership_grantors':[role]})); p.chmod(0o600)
                roles = root / (ns + '-roles.sql'); roles.write_text('CREATE ROLE ' + role + ';\n')
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

    def test_postgres_init_preserves_builtin_grantors_and_independent_login_survives_role_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            manifest = json.loads((root / 'manifest.json').read_text())
            for ns in module.NAMESPACES:
                initial = 'jhub' if ns == 'jupyterhub' else 'postgres'
                source_roles = ('CREATE ROLE ' + initial + ';\nALTER ROLE ' + initial + " WITH PASSWORD 'restored-source-password';\n").encode()
                path = root / (ns + '-roles.sql'); path.write_bytes(source_roles)
                manifest['files'][path.name] = {'sha256':hashlib.sha256(source_roles).hexdigest(), 'bytes':len(source_roles)}
            (root / 'manifest.json').write_text(json.dumps(manifest))
            runner = BootstrapPostgres()
            with mock.patch.object(module.subprocess, 'run', runner):
                module.restore(root, root / 'result')
            for name, env in runner.environments.items():
                initial = 'jhub' if runner.sources[name] == 'jupyterhub' else 'postgres'
                self.assertEqual(env['POSTGRES_USER'], initial)
                if 'POSTGRESQL_USERNAME' in env:
                    self.assertEqual(env['POSTGRESQL_USERNAME'], initial)
                self.assertEqual(runner.grantors[name], initial)
                calls = [(args, data) for args, data in runner.calls if args[1] == 'exec' and name in args]
                created = [(args, data) for args, data in calls if data and data.startswith(b'CREATE ROLE restore_')]
                self.assertEqual(len(created), 1)
                create_args, create_data = created[0]
                self.assertEqual(create_args[create_args.index('-U') + 1], initial)
                self.assertTrue(env['POSTGRES_PASSWORD'].encode() in create_data)
                replay_index = next(i for i, (_, data) in enumerate(calls) if data and b'ALTER ROLE ' + initial.encode() in data)
                self.assertLess(calls.index(created[0]), replay_index)
                for args, _ in calls[replay_index:]:
                    self.assertRegex(args[args.index('-U') + 1], r'^restore_[a-f0-9]{16}$')
            self.assertFalse(list((root / 'result').glob('*-bootstrap.env')))

    def test_metadata_is_closed_unambiguous_safe_and_manifest_bound(self):
        invalid = [
            {'version':True,'builtin_membership_grantors':['jhub']},
            {'version':1,'builtin_membership_grantors':[]},
            {'version':1,'builtin_membership_grantors':['jhub','postgres']},
            {'version':1,'builtin_membership_grantors':['jhub'],'extra':1},
            {'version':1,'builtin_membership_grantors':['unsafe;role']},
            {'version':1,'builtin_membership_grantors':['pg_monitor']},
            {'version':1,'builtin_membership_grantors':'jhub'},
            {'version':1,'builtin_membership_grantors':[None]},
        ]
        for body in invalid:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); self.fixture(root)
                path=root/'jupyterhub-bootstrap.json'; raw=json.dumps(body).encode(); path.write_bytes(raw)
                manifest=json.loads((root/'manifest.json').read_text())
                manifest['files'][path.name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
                (root/'manifest.json').write_text(json.dumps(manifest))
                with mock.patch.object(module.subprocess,'run') as process, self.assertRaises(ValueError):
                    module.restore(root,root/'result')
                process.assert_not_called()
        with self.assertRaises(ValueError):
            module.bootstrap_role(b'{"version":1,"version":1,"builtin_membership_grantors":["jhub"]}')
        with self.assertRaises(ValueError): module.bootstrap_role(b' ' * 4097)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.fixture(root)
            (root/'jupyterhub-bootstrap.json').write_text('{"version":1,"builtin_membership_grantors":["postgres"]}')
            with self.assertRaises(ValueError): module.validate_bundle(root)

    def test_legacy_bundle_is_logical_only_and_strict_probe_requires_fresh_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.fixture(root,metadata=False)
            runner=FakePostgres()
            with mock.patch.object(module.subprocess,'run',runner):
                report=module.restore(root,root/'legacy')
            self.assertFalse(report['productionQualified'])
            with mock.patch.object(module.subprocess,'run') as process, self.assertRaisesRegex(ValueError,'bootstrap'):
                module.restore(root,root/'strict',fingerprint_probe=lambda *args: None)
            process.assert_not_called()
            self.assertFalse((root/'strict').exists())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.fixture(root)
            manifest=json.loads((root/'manifest.json').read_text())
            del manifest['files']['jupyterhub-bootstrap.json']
            (root/'manifest.json').write_text(json.dumps(manifest))
            with mock.patch.object(module.subprocess,'run') as process, self.assertRaises(ValueError):
                module.restore(root,root/'strict',fingerprint_probe=lambda *args: None)
            process.assert_not_called()

    def test_observed_role_create_only_is_removed_and_quoted_safe_name_is_supported(self):
        for spelling in ('jhub','"jhub"'):
            source=('CREATE ROLE '+spelling+';\nALTER ROLE '+spelling+' WITH SUPERUSER;\n'
                    'CREATE ROLE postgres;\nGRANT pg_monitor TO '+spelling+';\n').encode()
            transformed=module.role_sql(source,'restore_abc','jhub')
            self.assertEqual(transformed, source.split(b'\n',1)[1])
        with self.assertRaises(ValueError):
            module.role_sql(b'CREATE ROLE jhub;\nCREATE ROLE "jhub";\n','restore_abc','jhub')
        with self.assertRaises(ValueError):
            module.role_sql(b'CREATE ROLE someone_else;\n','restore_abc','jhub')

    def test_source_role_collision_fails_before_container_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            path = root / 'jupyterhub-roles.sql'; path.write_bytes(b'CREATE ROLE restore_' + b'1' * 16 + b';\n')
            manifest = json.loads((root / 'manifest.json').read_text())
            manifest['files'][path.name] = {'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes':path.stat().st_size}
            (root / 'manifest.json').write_text(json.dumps(manifest))
            with mock.patch.object(module.secrets, 'token_hex', return_value='1' * 16), mock.patch.object(module.subprocess, 'run') as process:
                with self.assertRaisesRegex(ValueError, 'Bootstrap role collides'):
                    module.restore(root, root / 'result')
            process.assert_not_called()

    def test_failed_independent_bootstrap_stops_before_source_replay_and_cleans_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root); runner = BootstrapPostgres(bootstrap_failure=True)
            with mock.patch.object(module.subprocess, 'run', runner), self.assertRaises(RuntimeError):
                module.restore(root, root / 'result')
            self.assertFalse(any('pg_restore' in args for args, _ in runner.calls))
            self.assertEqual(len([args for args, _ in runner.calls if args[1] == 'rm']), 1)
            self.assertFalse(list((root / 'result').glob('*-bootstrap.env')))

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
            self.assertIn('e442f43577c44be9fab60d5aa9a29e98f491eec5', stderr.getvalue())
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

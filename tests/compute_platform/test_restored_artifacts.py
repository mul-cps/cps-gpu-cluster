"""In-memory restored-artifact HTTP qualification; no network or fixture files."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock
from urllib.parse import urlsplit

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/compute-platform/verify-restored-artifacts.py'


def module():
    spec = importlib.util.spec_from_file_location('restored_artifacts', SCRIPT)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def fixture():
    capture = '11111111-1111-4111-8111-111111111111'
    policy = 'sha256:' + 'a' * 64
    manifest = {'version': 1, 'capture_id': capture, 'coordinated_capture': False,
        'sources': {s: {'policy_hash': policy} for s in ('cps', 'cit')}}
    inputs = {'version': 1, 'bucket': 'restored-artifact-fixtures', 'sources': {}}
    tokens, replies, reads, calls = {}, {}, [], []
    for index, source in enumerate(('cps', 'cit')):
        target = {'namespace': 'restore-' + source + '-11111111',
            'hub_origin': 'http://127.0.0.1:' + str(18100 + index),
            'gateway_origin': 'http://127.0.0.1:' + str(18200 + index),
            'owner_label': 'compute.cps.unileoben.ac.at/owner', 'actors': {}, 'artifacts': {}}
        inputs['sources'][source] = target
        for n, actor in enumerate(('own', 'foreign')):
            person = source + '-' + actor + '-canonical'
            token = source + '-' + actor + '-PRIVATE-TOKEN-DO-NOT-PRINT'
            path = '/PRIVATE/' + source + '-' + actor + '.token'
            target['actors'][actor] = {'person': person, 'hub_user': source + '-' + actor, 'token_file': path}
            tokens[path] = token.encode()
            replies[(target['hub_origin'], '/hub/api/user', token)] = (200, {}, json.dumps({'name': source + '-' + actor, 'admin': False, 'roles': ['user']}).encode())
            replies[(target['gateway_origin'], '/v1/me', token)] = (200, {}, json.dumps({'identity': person, 'principal_kind': 'person', 'policy_hash': policy}).encode())
            workflow = source + '-restored-' + actor
            uid = ('2' if n == 0 else '3') * 8 + '-2222-4222-8222-' + ('2' if n == 0 else '3') * 12
            body = (source + '-' + actor + '-restored-notebook').encode()
            metadata = {'name': 'executed-notebook', 's3': {'bucket': inputs['bucket'],
                'key': 'run-artifacts/' + uid + '/executed.ipynb', 'endpoint': 'restored-s3.invalid'}}
            f = {'workflow': workflow, 'workflow_uid': uid, 'artifact': 'executed-notebook',
                'metadata_pointer': '/status/outputs/artifacts/0', 'metadata': metadata,
                'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
            target['artifacts'][actor] = f
            detail = {'metadata': {'name': workflow, 'uid': uid, 'namespace': target['namespace'],
                'labels': {target['owner_label']: hashlib.sha256(person.encode()).hexdigest()[:63]}},
                'status': {'outputs': {'artifacts': [metadata]}}}
            base = '/v1/workflows/' + workflow
            replies[(target['gateway_origin'], base, token)] = (200, {}, json.dumps(detail).encode())
            replies[(target['gateway_origin'], base + '/artifacts?download=executed-notebook', token)] = (
                200, {'cache-control': 'no-store', 'content-security-policy': 'sandbox',
                    'x-content-type-options': 'nosniff'}, body)
        for actor, other in (('own', 'foreign'), ('foreign', 'own')):
            token = tokens[target['actors'][other]['token_file']].decode()
            base = '/v1/workflows/' + target['artifacts'][actor]['workflow']
            for suffix in ('', '/artifacts?download=executed-notebook'):
                replies[(target['gateway_origin'], base + suffix, token)] = (403, {}, b'')

    class Recovery:
        @staticmethod
        def _bundle(path): return Path(path), copy.deepcopy(manifest), {}
        @staticmethod
        def _origin(value):
            p = urlsplit(value)
            if (p.scheme not in ('http', 'https') or p.hostname not in ('127.0.0.1', '::1') or
                    p.username or p.password or p.path or p.query or p.fragment or not p.port):
                raise ValueError('isolated loopback origin required')
            return value
        @staticmethod
        def _read(path): reads.append(path); return tokens[path]
        @staticmethod
        def _json(raw):
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result: raise ValueError('duplicate key')
                    result[key] = value
                return result
            return json.loads(raw, object_pairs_hook=unique)

    def fetch(origin, path, *, token, source=None, maximum):
        calls.append((origin, path, token, source, maximum))
        return copy.deepcopy(replies[(origin, path, token)])
    return inputs, manifest, tokens, replies, reads, calls, Recovery, fetch


class RestoredArtifactsTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'Restored artifact verifier is not implemented')
        self.m = module(); self.f = fixture()
    def run_probe(self):
        return self.m.verify('/PRIVATE/composed', self.f[0], recovery=self.f[6], fetch=self.f[7])

    def test_actual_owner_bytes_and_both_foreign_denials_for_each_source(self):
        result = self.run_probe()
        self.assertTrue(result['artifact_restore_ownership_passed'])
        self.assertFalse(result['productionQualified'])
        self.assertFalse(result['coordinated_capture'])
        self.assertEqual(len(result['checks']), 4)
        self.assertEqual(sum('/artifacts?download=' in c[1] for c in self.f[5]), 8)
        rendered = json.dumps(result)
        for token in self.f[2].values(): self.assertNotIn(token.decode(), rendered)
        self.assertNotIn('/PRIVATE/', rendered)
        self.assertTrue(all(c[1].startswith(('/v1/', '/hub/api/user')) for c in self.f[5]))

    def test_production_and_malformed_inputs_fail_before_token_reads_or_http(self):
        cases = ('namespace', 'origin', 'userinfo', 'redirect-path', 'bucket', 'same-actor', 'metadata-bucket', 'metadata-key', 'bad-uid')
        for fault in cases:
            with self.subTest(fault=fault):
                self.f = fixture(); target = self.f[0]['sources']['cps']
                if fault == 'namespace': target['namespace'] = 'jupyterhub'
                elif fault == 'origin': target['gateway_origin'] = 'https://compute.cps.unileoben.ac.at'
                elif fault == 'userinfo': target['gateway_origin'] = 'http://secret@127.0.0.1:18200'
                elif fault == 'redirect-path': target['gateway_origin'] += '/production'
                elif fault == 'bucket': self.f[0]['bucket'] = ''
                elif fault == 'same-actor': target['actors']['foreign']['person'] = target['actors']['own']['person']
                elif fault == 'metadata-bucket': target['artifacts']['own']['metadata']['s3']['bucket'] = 'wrong'
                elif fault == 'metadata-key': target['artifacts']['own']['metadata']['s3']['key'] = '../production'
                else: target['artifacts']['own']['workflow_uid'] = 'not-a-uid'
                with self.assertRaises(ValueError): self.run_probe()
                self.assertEqual(self.f[4], []); self.assertEqual(self.f[5], [])

    def test_private_token_guard_failure_never_reaches_http(self):
        def deny(path): raise ValueError('nonprivate token file')
        self.f[6]._read = staticmethod(deny)
        with self.assertRaises(ValueError): self.run_probe()
        self.assertEqual(self.f[5], [])

    def test_admin_identity_and_wrong_person_are_denied(self):
        for fault in ('admin', 'person', 'policy'):
            with self.subTest(fault=fault):
                self.f = fixture(); t = self.f[0]['sources']['cps']; a = t['actors']['own']; token = self.f[2][a['token_file']].decode()
                key = (t['hub_origin'], '/hub/api/user', token) if fault == 'admin' else (t['gateway_origin'], '/v1/me', token)
                status, headers, body = self.f[3][key]; value = json.loads(body)
                value['admin' if fault == 'admin' else 'identity' if fault == 'person' else 'policy_hash'] = True if fault == 'admin' else 'wrong'
                self.f[3][key] = (status, headers, json.dumps(value).encode())
                with self.assertRaises(ValueError): self.run_probe()

    def test_foreign_200_even_with_empty_body_is_not_a_denial(self):
        t = self.f[0]['sources']['cps']; token = self.f[2][t['actors']['foreign']['token_file']].decode()
        path = '/v1/workflows/' + t['artifacts']['own']['workflow'] + '/artifacts?download=executed-notebook'
        self.f[3][(t['gateway_origin'], path, token)] = (200, {}, b'')
        with self.assertRaises(ValueError): self.run_probe()

    def test_redirect_is_not_followed_or_accepted(self):
        t = self.f[0]['sources']['cps']; token = self.f[2][t['actors']['own']['token_file']].decode()
        self.f[3][(t['hub_origin'], '/hub/api/user', token)] = (302, {'location': 'https://production.invalid'}, b'')
        with self.assertRaises(ValueError): self.run_probe()
        self.assertEqual(len(self.f[5]), 1)

    def test_wrong_actual_hash_uid_owner_namespace_bucket_key_and_metadata_fail(self):
        for fault in ('hash', 'uid', 'owner', 'namespace', 'bucket', 'key', 'metadata'):
            with self.subTest(fault=fault):
                self.f = fixture(); t = self.f[0]['sources']['cps']; a = t['actors']['own']; f = t['artifacts']['own']; token = self.f[2][a['token_file']].decode()
                path = '/v1/workflows/' + f['workflow']; key = (t['gateway_origin'], path, token)
                if fault == 'hash':
                    key = (t['gateway_origin'], path + '/artifacts?download=executed-notebook', token)
                    status, headers, body = self.f[3][key]; self.f[3][key] = (status, headers, b'wrong')
                else:
                    status, headers, body = self.f[3][key]; value = json.loads(body)
                    if fault in ('uid', 'owner', 'namespace'):
                        if fault == 'owner': value['metadata']['labels'][t['owner_label']] = 'f' * 63
                        else: value['metadata'][fault] = 'wrong'
                    else: value['status']['outputs']['artifacts'][0]['s3'][fault if fault != 'metadata' else 'endpoint'] = 'wrong'
                    self.f[3][key] = (status, headers, json.dumps(value).encode())
                with self.assertRaises(ValueError): self.run_probe()

    def test_no_bearer_token_is_placed_in_url(self):
        self.run_probe()
        for origin, path, token, source, maximum in self.f[5]:
            self.assertNotIn(token, origin + path)
            self.assertIn(source, (None, 'cps', 'cit'))
            self.assertGreater(maximum, 0)

    def test_metadata_requires_a_json_object_without_duplicate_fields(self):
        for body in (b'[]', b'{"name":"bad","name":"cps-own","admin":false,"roles":[]}'):
            with self.subTest(body=body):
                self.f = fixture(); t = self.f[0]['sources']['cps']
                token = self.f[2][t['actors']['own']['token_file']].decode()
                self.f[3][(t['hub_origin'], '/hub/api/user', token)] = (200, {}, body)
                with self.assertRaises(ValueError): self.run_probe()

    def test_full_metadata_equality_preserves_json_value_types(self):
        t = self.f[0]['sources']['cps']; f = t['artifacts']['own']
        f['metadata']['archive'] = {'none': True}
        token = self.f[2][t['actors']['own']['token_file']].decode()
        key = (t['gateway_origin'], '/v1/workflows/' + f['workflow'], token)
        status, headers, body = self.f[3][key]; value = json.loads(body)
        value['status']['outputs']['artifacts'][0]['archive'] = {'none': 1}
        self.f[3][key] = (status, headers, json.dumps(value).encode())
        with self.assertRaises(ValueError): self.run_probe()

    def test_actual_transport_is_bounded_get_without_proxy_or_redirect(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200; response.headers = {'Cache-Control': 'no-store'}
        response.read.return_value = b'raw-bytes'
        opener = mock.Mock(); opener.open.return_value = response
        for source, prefix in ((None, 'token '), ('cps', 'Bearer ')):
            with self.subTest(source=source), mock.patch.object(self.m.urllib.request, 'build_opener', return_value=opener) as build:
                self.assertEqual(self.m.fetch('http://127.0.0.1:18100', '/v1/me', token='PRIVATE', source=source, maximum=20)[2], b'raw-bytes')
                proxy, redirect = build.call_args.args
                self.assertEqual(proxy.proxies, {})
                self.assertIsNone(redirect.redirect_request(None, None, 302, '', {}, 'https://production.invalid'))
                request = opener.open.call_args.args[0]
                self.assertEqual(request.get_method(), 'GET')
                self.assertEqual(request.full_url, 'http://127.0.0.1:18100/v1/me')
                self.assertEqual(request.get_header('Authorization'), prefix + 'PRIVATE')
                self.assertEqual(request.get_header('X-cps-hub'), source)
                self.assertEqual(opener.open.call_args.kwargs, {'timeout': 15})
                response.read.assert_called_with(21)
        response.read.return_value = b'x' * 21
        with mock.patch.object(self.m.urllib.request, 'build_opener', return_value=opener), self.assertRaises(ValueError):
            self.m.fetch('http://127.0.0.1:18100', '/v1/me', token='PRIVATE', maximum=20)

    def test_http_error_body_is_not_read_and_connection_is_closed(self):
        body = mock.Mock()
        error = self.m.urllib.error.HTTPError('http://127.0.0.1:18100', 302, 'PRIVATE ERROR', {'Location': 'https://production.invalid'}, body)
        opener = mock.Mock(); opener.open.side_effect = error
        with mock.patch.object(self.m.urllib.request, 'build_opener', return_value=opener):
            self.assertEqual(self.m.fetch('http://127.0.0.1:18100', '/v1/me', token='PRIVATE', maximum=20), (302, {}, b''))
        body.read.assert_not_called(); body.close.assert_called_once()

    def test_cli_is_inert_and_suppresses_private_failure_details(self):
        output = io.StringIO()
        with mock.patch('sys.stdout', output): self.assertEqual(self.m.main([]), 0)
        self.assertEqual(json.loads(output.getvalue()), {'inert': True, 'requests_made': False, 'files_written': False})
        recovery = self.f[6]
        recovery._read = mock.Mock(side_effect=ValueError('PRIVATE-TOKEN-FILE-CONTENTS'))
        parent = mock.Mock(); parent.recovery = recovery
        output = io.StringIO()
        with mock.patch.dict('sys.modules', {'e2x_course_hub': mock.Mock(), 'e2x_course_hub.cps': parent}), mock.patch('sys.stdout', output):
            self.assertEqual(self.m.main(['--execute', '--bundle', '/PRIVATE/bundle', '--input', '/PRIVATE/input', '--output', '/PRIVATE/new-output']), 1)
        self.assertNotIn('PRIVATE', output.getvalue())

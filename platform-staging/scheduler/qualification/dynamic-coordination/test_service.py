import copy
import io
import json
from pathlib import Path
import ssl
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import fence
import service
from test_fence import fixture, review


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.cert, cls.key = root / 'cert.pem', root / 'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-nodes', '-newkey', 'rsa:2048', '-days', '1',
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost',
                        '-keyout', str(cls.key), '-out', str(cls.cert)], check=True, capture_output=True)
        cls.context = ssl.create_default_context(cafile=str(cls.cert))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.registry, self.objects = fixture()
        self.mode = ''
        outer = self
        class API:
            def get(self, resource, namespace, name, *, deadline):
                if outer.mode == 'error': raise OSError('API unavailable')
                if outer.mode == 'slow': time.sleep(0.06)
                return copy.deepcopy(outer.objects.get((resource, namespace, name)))
        self.server = service.AdmissionServer(('127.0.0.1', 0), self.registry, API(), workers=1)
        self.server.tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.server.tls_context.load_cert_chain(str(self.cert), str(self.key))
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start()
        self.url = 'https://localhost:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=1)

    def post(self, value, path='/validate', content_type='application/json'):
        request = Request(self.url + path, data=json.dumps(value).encode(), headers={'Content-Type': content_type})
        with urlopen(request, context=self.context, timeout=3) as response:
            return response.status, json.load(response)

    def test_real_tls_admission_review_roundtrip_preserves_uid(self):
        status, response = self.post(review())
        self.assertEqual(status, 200)
        self.assertEqual(response['apiVersion'], 'admission.k8s.io/v1')
        self.assertEqual(response['response']['uid'], 'admission-review-id')
        self.assertTrue(response['response']['allowed'])

    def test_decision_receipt_is_bounded_and_omits_object_secrets(self):
        events = []
        self.server.decision_log = events.append
        incoming = review()
        incoming['request']['object']['metadata']['annotations'] = {'secret': 'DO-NOT-LOG'}
        self.post(incoming)
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]['allowed'])
        self.assertEqual(events[0]['reviewUid'], 'admission-review-id')
        self.assertNotIn('DO-NOT-LOG', json.dumps(events))
        self.assertLess(len(json.dumps(events[0])), 1800)

    def test_health_and_no_seal_or_enrollment_endpoints(self):
        with urlopen(self.url + '/healthz', context=self.context, timeout=2) as response:
            self.assertEqual(response.status, 200)
        for path in ('/seal', '/enroll', '/not-validate'):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error: self.post(review(), path)
            self.assertEqual(error.exception.code, 404)

    def test_apiserver_timeout_query_routes_to_validate(self):
        status, response = self.post(review(), '/validate?timeout=5s')
        self.assertEqual(status, 200)
        self.assertTrue(response['response']['allowed'])

    def test_api_error_and_total_deadline_return_uid_bound_denial(self):
        for mode in ('error', 'slow'):
            self.mode = mode
            with self.subTest(mode=mode), patch.object(service, 'REQUEST_SECONDS', 0.05):
                status, response = self.post(review())
                self.assertEqual(status, 200)
                self.assertFalse(response['response']['allowed'])
                self.assertEqual(response['response']['uid'], 'admission-review-id')

    def test_invalid_protocol_and_oversized_body_reject(self):
        for value, content_type in (([], 'application/json'), (review(), 'text/plain'), ('x' * fence.MAX_BYTES, 'application/json')):
            with self.subTest(content_type=content_type), self.assertRaises(HTTPError) as error:
                self.post(value, content_type=content_type)
            self.assertEqual(error.exception.code, 400)

    def test_worker_cap_rejects_parallel_request_without_creating_unbounded_threads(self):
        self.server.slots.acquire()
        try:
            with self.assertRaises(HTTPError) as error: self.post(review())
            self.assertEqual(error.exception.code, 503)
        finally: self.server.slots.release()

    def test_partial_body_is_bounded_and_cannot_hold_worker(self):
        start = time.monotonic()
        with patch.object(service, 'SOCKET_SECONDS', 0.05), patch.object(service, 'REQUEST_SECONDS', 0.05):
            with socket.create_connection(('localhost', self.server.server_port), timeout=1) as raw:
                with self.context.wrap_socket(raw, server_hostname='localhost') as channel:
                    channel.sendall(b'POST /validate HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n{')
                    channel.recv(4096)
        self.assertLess(time.monotonic() - start, 1)

    def test_http_api_absence_is_only_404_and_patch_uses_json_patch(self):
        token = Path(self.tmp.name) / 'token'
        token.write_text('synthetic-test-token')
        api = service.KubernetesAPI('https://kubernetes.invalid', token, self.cert)
        for status in (404, 403, 500):
            error = HTTPError('https://kubernetes.invalid', status, 'test', {}, None)
            with self.subTest(status=status), patch.object(service, 'urlopen', side_effect=error):
                if status == 404: self.assertIsNone(api.get('pods', 'qa', 'pod', deadline=time.monotonic() + 1))
                else:
                    with self.assertRaises(OSError): api.get('pods', 'qa', 'pod', deadline=time.monotonic() + 1)
        class Response:
            def __enter__(self): self.stream = io.BytesIO(b'{"kind":"ConfigMap"}'); return self
            def __exit__(self, *args): pass
            def read1(self, size): return self.stream.read(size)
        with patch.object(service, 'urlopen', return_value=Response()) as opened:
            api.patch('configmaps', 'qa', 'map', [{'op': 'test', 'path': '/metadata/uid', 'value': 'uid'}], deadline=time.monotonic() + 1)
            request = opened.call_args.args[0]
            self.assertEqual(request.method, 'PATCH')
            self.assertEqual(request.headers['Content-type'], 'application/json-patch+json')
        with self.assertRaises(TimeoutError): api.get('pods', 'qa', 'pod', deadline=time.monotonic() - 1)


if __name__ == '__main__': unittest.main()

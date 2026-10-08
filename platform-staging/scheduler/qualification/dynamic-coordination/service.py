"""Small bounded TLS AdmissionReview service; no registry enrollment endpoints."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import socket
import threading
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import fence

REQUEST_SECONDS = 2.0
SOCKET_SECONDS = 2.0


class KubernetesAPI:
    """Current GETs (never resourceVersion=0); only 404 proves absence."""
    def __init__(self, server, token_file, ca_file):
        if not server.startswith('https://') or server.endswith('/'):
            raise ValueError('Explicit HTTPS API endpoint without trailing slash required')
        self.server, self.token_file = server, Path(token_file)
        self.context = ssl.create_default_context(cafile=str(ca_file))

    def _request(self, resource, namespace, name, *, deadline, patch=None):
        remaining = deadline - time.monotonic()
        if remaining <= 0: raise TimeoutError('API deadline exceeded')
        if resource not in ('pods', 'configmaps', 'workflows', 'nodes'):
            raise ValueError('Unsupported API read')
        root = '/apis/argoproj.io/v1alpha1' if resource == 'workflows' else '/api/v1'
        if resource == 'nodes':
            if namespace: raise ValueError('Node scope must be cluster scope')
        else:
            root += '/namespaces/' + quote(namespace, safe='')
        path = root + '/' + resource + '/' + quote(name, safe='')
        headers = {'Authorization': 'Bearer ' + self.token_file.read_text().strip(), 'Accept': 'application/json'}
        if patch is not None:
            if resource != 'configmaps': raise ValueError('Sealer may PATCH only exact ConfigMaps')
            headers['Content-Type'] = 'application/json-patch+json'
        request = Request(self.server + path, data=None if patch is None else fence.canonical(patch),
                          headers=headers, method='GET' if patch is None else 'PATCH')
        try:
            with urlopen(request, context=self.context, timeout=min(remaining, 0.5)) as response:
                chunks, size = [], 0
                while True:
                    if time.monotonic() >= deadline: raise TimeoutError('API response exceeded deadline')
                    chunk = response.read1(min(65536, fence.MAX_BYTES + 1 - size))
                    if not chunk: break
                    chunks.append(chunk); size += len(chunk)
                    if size > fence.MAX_BYTES: raise ValueError('Oversized API response')
                raw = b''.join(chunks)
            if len(raw) > fence.MAX_BYTES: raise ValueError('Oversized API response')
            if time.monotonic() >= deadline: raise TimeoutError('API response exceeded deadline')
            result = json.loads(raw)
            if not isinstance(result, dict): raise ValueError('Object API response required')
            return result
        except HTTPError as error:
            if error.code == 404 and patch is None: return None
            raise OSError('Kubernetes API request failed') from error

    def get(self, resource, namespace, name, *, deadline):
        return self._request(resource, namespace, name, deadline=deadline)

    def patch(self, resource, namespace, name, patch, *, deadline):
        return self._request(resource, namespace, name, deadline=deadline, patch=patch)


class AdmissionServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, registry, api, *, workers=4):
        if type(workers) is not int or not 1 <= workers <= 8:
            raise ValueError('At most eight request workers permitted')
        self.registry = fence.validate_registry(registry)
        self.api = api
        self.slots = threading.BoundedSemaphore(workers)
        super().__init__(address, Handler)

    def get_request(self):
        socket, address = super().get_request()
        socket.settimeout(SOCKET_SECONDS)
        if hasattr(self, 'tls_context'):
            socket = self.tls_context.wrap_socket(socket, server_side=True)
        return socket, address

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        def expire():
            try: request.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            request.close()
        timer = threading.Timer(SOCKET_SECONDS + REQUEST_SECONDS, expire)
        timer.daemon = True
        timer.start()
        try:
            super().process_request_thread(request, client_address)
        finally:
            timer.cancel()
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, code, value):
        raw = fence.canonical(value)
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.send_json(200 if self.path == '/healthz' else 404, {'ready': self.path == '/healthz', 'qualification': 'qa-only'})

    def do_POST(self):
        if self.path != '/validate':
            self.send_json(404, {'error': 'Only /validate is available'})
            return
        try:
            if self.headers.get('Transfer-Encoding'): raise ValueError('Chunked requests are not modeled')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json': raise ValueError('JSON content type required')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= fence.MAX_BYTES: raise ValueError('Bounded Content-Length required')
            raw = self.rfile.read(length)
            if len(raw) != length: raise ValueError('Incomplete body')
            review = json.loads(raw)
            if not isinstance(review, dict): raise ValueError('AdmissionReview object required')
            deadline = time.monotonic() + REQUEST_SECONDS
            def read(resource, namespace, name):
                result = self.server.api.get(resource, namespace, name, deadline=deadline)
                if time.monotonic() >= deadline: raise TimeoutError('Admission deadline exceeded')
                return result
            self.send_json(200, fence.authorize(review, self.server.registry, read))
        except (ValueError, OSError, TimeoutError):
            self.send_json(400, {'error': 'Invalid, oversized or timed-out admission protocol'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--tls-cert', required=True)
    parser.add_argument('--tls-key', required=True)
    parser.add_argument('--api-server', required=True)
    parser.add_argument('--token-file', default='/var/run/secrets/kubernetes.io/serviceaccount/token')
    parser.add_argument('--api-ca', default='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')
    parser.add_argument('--port', type=int, default=8443)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535: parser.error('Bounded unprivileged port required')
    raw = args.registry.read_bytes()
    if len(raw) > fence.MAX_BYTES: parser.error('Oversized protected registry')
    api = KubernetesAPI(args.api_server, args.token_file, args.api_ca)
    server = AdmissionServer(('0.0.0.0', args.port), json.loads(raw), api)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.tls_cert, args.tls_key)
    server.tls_context = context
    server.serve_forever()


if __name__ == '__main__': main()

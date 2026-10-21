#!/usr/bin/env python3
"""Read-only artifact ownership acceptance for an isolated paired restore.

Uses the existing e2x recovery bundle/private-file contract. Nothing runs by
import or without --execute. Root must independently verify restored backend
routing: a bucket name and loopback origin do not prove storage isolation.
"""
import argparse
import hashlib
import json
from pathlib import PurePosixPath
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

MAX_BYTES = 32 * 1024 * 1024
SOURCES = ('cps', 'cit')
ACTORS = ('own', 'foreign')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def closed(value, fields):
    require(isinstance(value, dict) and set(value) == set(fields), 'Closed restored-artifact input required')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def canonical_name(value):
    return isinstance(value, str) and re.fullmatch(r'[a-z0-9](?:[-a-z0-9.]{0,251}[a-z0-9])?', value)


def origin(value, recovery):
    require(isinstance(value, str), 'Explicit isolated origin required')
    recovery._origin(value)
    parsed = urllib.parse.urlsplit(value)
    host = '[' + parsed.hostname + ']' if parsed.hostname == '::1' else parsed.hostname
    require(value == parsed.scheme + '://' + host + ':' + str(parsed.port), 'Canonical isolated loopback origin required')
    return value


def validate(manifest, inputs, recovery):
    closed(inputs, ('version', 'bucket', 'sources'))
    require(type(inputs['version']) is int and inputs['version'] == 1, 'Version 1 required')
    capture = manifest['capture_id']
    require(str(uuid.UUID(capture)) == capture and set(manifest['sources']) == set(SOURCES), 'Paired recovery capture required')
    bucket = inputs['bucket']
    require(isinstance(bucket, str) and 3 <= len(bucket) <= 63 and canonical_name(bucket)
        and '..' not in bucket, 'Explicit restored bucket required')
    closed(inputs['sources'], SOURCES)
    origins = []
    for source in SOURCES:
        target = inputs['sources'][source]
        closed(target, ('namespace', 'gateway_origin', 'hub_origin', 'owner_label', 'actors', 'artifacts'))
        require(target['namespace'] == 'restore-' + source + '-' + capture[:8], 'Exact isolated source namespace required')
        for field in ('hub_origin', 'gateway_origin'):
            origins.append(origin(target[field], recovery))
        require(isinstance(target['owner_label'], str) and re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?', target['owner_label']), 'Explicit owner label required')
        require(re.fullmatch(r'sha256:[a-f0-9]{64}', manifest['sources'][source]['policy_hash']), 'Captured source policy required')
        closed(target['actors'], ACTORS); closed(target['artifacts'], ACTORS)
        for actor in ACTORS:
            identity = target['actors'][actor]
            closed(identity, ('person', 'hub_user', 'token_file'))
            require(all(isinstance(identity[k], str) and identity[k] and len(identity[k]) <= 4096
                and not any(ord(c) < 32 for c in identity[k]) for k in identity), 'Explicit fixture identity required')
            require(identity['token_file'].startswith('/'), 'Absolute private token-file reference required')
            fixture = target['artifacts'][actor]
            closed(fixture, ('workflow', 'workflow_uid', 'artifact', 'metadata_pointer', 'metadata', 'bytes', 'sha256'))
            require(canonical_name(fixture['workflow']) and str(uuid.UUID(fixture['workflow_uid'])) == fixture['workflow_uid'], 'Exact workflow name and UUID required')
            require(fixture['artifact'] in ('snapshot', 'executed-notebook'), 'Fixed notebook artifact required')
            require(type(fixture['bytes']) is int and 0 < fixture['bytes'] <= MAX_BYTES
                and isinstance(fixture['sha256'], str) and re.fullmatch('[a-f0-9]{64}', fixture['sha256']), 'Bounded original artifact bytes/hash required')
            pointer = fixture['metadata_pointer']
            require(isinstance(pointer, str) and re.fullmatch(r'(?:/[A-Za-z0-9_.-]+)+', pointer), 'Explicit artifact metadata pointer required')
            metadata = fixture['metadata']; s3 = metadata.get('s3', {}) if isinstance(metadata, dict) else {}
            require(isinstance(s3, dict) and metadata.get('name') == fixture['artifact']
                and s3.get('bucket') == bucket, 'Artifact metadata bucket/name differs')
            key = s3.get('key')
            require(isinstance(key, str) and 0 < len(key) <= 1024 and not key.startswith('/')
                and '..' not in key.split('/') and str(PurePosixPath(key)) == key
                and not any(ord(c) < 32 for c in key), 'Canonical restored artifact key required')
            digest(metadata)
        for field in ('person', 'hub_user', 'token_file'):
            require(target['actors']['own'][field] != target['actors']['foreign'][field], 'Distinct fixture owners required')
        require(target['artifacts']['own']['workflow_uid'] != target['artifacts']['foreign']['workflow_uid']
            and target['artifacts']['own']['workflow'] != target['artifacts']['foreign']['workflow'], 'Distinct own/foreign workflows required')
    require(len(set(origins)) == len(origins), 'Distinct isolated Hub/Gateway origins required')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(origin, path, *, token, source=None, maximum):
    """Bounded GET only; no ambient proxy, redirect or error body disclosure."""
    headers = {'Authorization': ('Bearer ' if source else 'token ') + token, 'Accept': 'application/json'}
    if source:
        headers['X-CPS-Hub'] = source
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(origin + path, headers=headers, method='GET')
    try:
        with opener.open(request, timeout=15) as response:
            body = response.read(maximum + 1)
            require(len(body) <= maximum, 'Bounded restored response required')
            return response.status, dict(response.headers.items()), body
    except urllib.error.HTTPError as error:
        error.close()
        return error.code, {}, b''
    except (OSError, urllib.error.URLError):
        raise ValueError('Isolated artifact request failed') from None


def metadata_at(value, pointer):
    try:
        for field in pointer.split('/')[1:]:
            value = value[int(field)] if isinstance(value, list) and field.isdecimal() else value[field]
        return value
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError('Restored artifact metadata missing') from None


def verify(bundle, inputs, *, recovery=None, fetch=None):
    if recovery is None:
        from e2x_course_hub.cps import recovery
    _, manifest, _ = recovery._bundle(bundle)
    validate(manifest, inputs, recovery)  # Complete preflight before credentials or HTTP.
    request = fetch or globals()['fetch']
    tokens = {}
    for source in SOURCES:
        tokens[source] = {}
        for actor in ACTORS:
            raw = recovery._read(inputs['sources'][source]['actors'][actor]['token_file'])
            token = raw.decode('ascii').strip()
            require(0 < len(token) <= 4096 and all(32 < ord(c) < 127 for c in token), 'Bounded private Hub token required')
            tokens[source][actor] = token
        require(tokens[source]['own'] != tokens[source]['foreign'], 'Distinct fixture credentials required')
    checks = []
    for source in SOURCES:
        target = inputs['sources'][source]
        def get(path, actor, *, hub=False):
            status, headers, body = request(target['hub_origin' if hub else 'gateway_origin'], path,
                token=tokens[source][actor], source=None if hub else source, maximum=MAX_BYTES)
            require(type(status) is int and isinstance(body, bytes) and len(body) <= MAX_BYTES, 'Bounded HTTP observation required')
            return status, {k.lower(): v for k, v in headers.items()}, body
        def get_json(path, actor, *, hub=False):
            status, _, body = get(path, actor, hub=hub)
            require(status == 200, 'Isolated authenticated metadata GET failed')
            try:
                value = recovery._json(body)
            except (ValueError, UnicodeError):
                raise ValueError('Restored JSON response invalid') from None
            require(isinstance(value, dict), 'Restored JSON object required')
            return value
        for actor in ACTORS:
            expected = target['actors'][actor]
            user = get_json('/hub/api/user', actor, hub=True)
            require(user.get('name') == expected['hub_user'] and user.get('admin') is False
                and isinstance(user.get('roles'), list) and 'admin' not in user['roles'], 'Normal isolated Hub identity required')
            identity = get_json('/v1/me', actor)
            require(identity.get('identity') == expected['person'] and identity.get('principal_kind') == 'person'
                and identity.get('policy_hash') == manifest['sources'][source]['policy_hash'], 'Restored Gateway identity/policy differs')
        for actor in ACTORS:
            fixture = target['artifacts'][actor]; other = 'foreign' if actor == 'own' else 'own'
            base = '/v1/workflows/' + urllib.parse.quote(fixture['workflow'], safe='')
            workflow = get_json(base, actor); meta = workflow.get('metadata', {})
            require((meta.get('namespace'), meta.get('name'), meta.get('uid')) ==
                (target['namespace'], fixture['workflow'], fixture['workflow_uid'])
                and meta.get('labels', {}).get(target['owner_label']) == hashlib.sha256(target['actors'][actor]['person'].encode()).hexdigest()[:63], 'Restored workflow owner/identity differs')
            require(digest(metadata_at(workflow, fixture['metadata_pointer'])) == digest(fixture['metadata']), 'Restored artifact metadata differs')
            download = base + '/artifacts?download=' + fixture['artifact']
            status, headers, body = get(download, actor)
            require(status == 200 and len(body) == fixture['bytes'] and hashlib.sha256(body).hexdigest() == fixture['sha256'], 'Restored artifact bytes differ')
            require(headers.get('cache-control') == 'no-store' and headers.get('content-security-policy') == 'sandbox'
                and headers.get('x-content-type-options') == 'nosniff', 'Private download headers required')
            for path in (base, download):
                denied, _, _ = get(path, other)
                require(denied == 403, 'Foreign artifact request was not denied')
            checks.append({'source': source, 'fixture': actor, 'owner_allowed': True, 'foreign_denied': True,
                'workflow_uid_sha256': hashlib.sha256(fixture['workflow_uid'].encode()).hexdigest(),
                'metadata_sha256': digest(fixture['metadata']), 'bytes': len(body), 'sha256': fixture['sha256']})
    return {'version': 1, 'capture_id': manifest['capture_id'], 'artifact_restore_ownership_passed': True,
        'coordinated_capture': manifest['coordinated_capture'], 'productionQualified': False,
        'browser_oauth_qualified': False, 'off_host_recovery_qualified': False,
        'routing_isolation_requires_independent_evidence': True, 'checks': checks}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    for field in ('bundle', 'input', 'output'):
        parser.add_argument('--' + field)
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'inert': True, 'requests_made': False, 'files_written': False})); return 0
    try:
        require(all((args.bundle, args.input, args.output)), 'Explicit restored inputs required')
        from e2x_course_hub.cps import recovery
        inputs = recovery._json(recovery._read(args.input))
        result = verify(args.bundle, inputs, recovery=recovery)
        recovery._write(recovery._path(args.output), recovery._encode(result))
        print(json.dumps({'artifact_restore_ownership_passed': True, 'productionQualified': False}))
        return 0
    except Exception:
        print('Isolated artifact verification failed; private inputs and response bodies suppressed')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

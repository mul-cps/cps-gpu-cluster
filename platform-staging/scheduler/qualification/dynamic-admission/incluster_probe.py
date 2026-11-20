#!/usr/bin/env python3
"""CPU qualification runner: authenticated admission requests always use dryRun."""
import json
from pathlib import Path
import time

from kubernetes import client, config
from kubernetes.client.rest import ApiException

NAMESPACE = 'cps-dynamic-admission-live-20261008'


def request_path(obj):
    if obj.get('metadata', {}).get('namespace') != NAMESPACE:
        raise ValueError('Every fixture must target the single qualification namespace')
    kind = obj.get('kind')
    if kind == 'Pod':
        return '/api/v1/namespaces/' + NAMESPACE + '/pods'
    if kind == 'ConfigMap':
        return '/api/v1/namespaces/' + NAMESPACE + '/configmaps'
    if kind == 'Binding':
        name = obj['metadata']['name']
        if not name or '/' in name or name in ('.', '..'):
            raise ValueError('Exact fixture Pod name required')
        return '/api/v1/namespaces/' + NAMESPACE + '/pods/' + name + '/binding'
    raise ValueError('Only Pod, ConfigMap and Binding dry-run fixtures are supported')


def main():
    config.load_incluster_config()
    api = client.ApiClient()
    identity = client.AuthenticationV1Api(api).create_self_subject_review(
        client.V1SelfSubjectReview(api_version='authentication.k8s.io/v1', kind='SelfSubjectReview'))
    print(json.dumps({'event': 'identity', 'username': identity.status.user_info.username,
        'groups': identity.status.user_info.groups}), flush=True)
    completed = set()
    failed = False
    deadline = time.monotonic() + 270
    while time.monotonic() < deadline:
        phase = json.loads(Path('/qualification/phase.json').read_text())
        name = phase['name']
        if name not in completed and name != 'waiting':
            for case in phase['cases']:
                obj = case['object']
                result = {'event': 'result', 'phase': name, 'name': case['name'],
                    'expectedAllow': case['allow'], 'username': identity.status.user_info.username}
                try:
                    value = api.call_api(request_path(obj), 'POST', body=obj,
                        query_params=[('dryRun', 'All')], response_type='object',
                        auth_settings=['BearerToken'], _return_http_data_only=True,
                        _request_timeout=15)
                    result.update(status=201, admitted=True, response=value)
                except ApiException as error:
                    result.update(status=error.status, admitted=False,
                        response=json.loads(error.body) if error.body else {'message': error.reason})
                message = str(result['response'].get('message', ''))
                result['matchedExpectation'] = (result['admitted'] if case['allow'] else
                    not result['admitted'] and 'cps-dynamic-admission-live-20261008-' in message)
                failed = failed or not result['matchedExpectation']
                print(json.dumps(result), flush=True)
            completed.add(name)
            print(json.dumps({'event': 'phase-complete', 'phase': name}), flush=True)
        if phase.get('finish'):
            break
        time.sleep(2)
    print(json.dumps({'event': 'runner-finished', 'phases': sorted(completed)}), flush=True)
    if failed or not completed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

"""Read-only normal Source contract check; existing Pod credentials stay in memory."""
import hashlib
import json
import os
import ssl
import urllib.error
import urllib.request

source = os.environ['PROBE_SOURCE']
assert source in ('cps', 'cit')
workspace = 'upstream-registry-qualification-20261116-' + source
context = ssl.create_default_context(cafile='/trust/ca.crt')

def get(path):
    request = urllib.request.Request(
        'https://compute-gateway.cps-compute.svc.cluster.local:8000' + path,
        headers={'Authorization': 'Bearer ' + os.environ['COMPUTE_POLICY_TOKEN']})
    try:
        with urllib.request.urlopen(request, context=context, timeout=5) as response:
            raw = response.read(1048577)
            assert len(raw) <= 1048576
            return response.status, json.loads(raw), hashlib.sha256(raw).hexdigest()
    except urllib.error.HTTPError as error:
        return error.code, None, None

status, reservation, reservation_hash = get('/internal/v1/reservations/' + workspace)
assert status == 200 and reservation == {'workspace': workspace, 'active': False, 'attempt': None}
status, record, workspace_hash = get('/internal/v1/workspaces/' + workspace)
assert status == 200 and record['workspace'] == workspace
assert record['namespace'] == ('jupyterhub' if source == 'cps' else 'cit-jhub')
# Compare the real policy identifier, including its documented digest prefix.
assert record['policy_hash'] == 'sha256:2b2ad6ce656db38a0e9cc2a0d3365c48d6061a835d317236a322776c11dc3fcb'
status, profiles, profiles_hash = get('/internal/v1/profiles')
assert status == 200 and {'interactive-shared-5', 'interactive-shared-10', 'interactive-shared-20'} <= set(profiles)
assert record['profiles'] and set(record['profiles']) <= set(profiles)
other = 'cit' if source == 'cps' else 'cps'
status, _, _ = get('/internal/v1/workspaces/upstream-registry-qualification-20261116-' + other)
assert status in (403, 404), status
print(json.dumps({'source': source, 'strictTLS': True, 'reservationExactInactive': True,
    'workspaceExact': True, 'namespaceExact': True, 'profileCatalogHas5_10_20': True,
    'workspaceProfilesInCatalog': True, 'policyHashExact': True,
    'sourceIsolationStatus': status, 'bodySHA256': {'reservation': reservation_hash,
    'workspace': workspace_hash, 'profiles': profiles_hash}, 'noWritesOrNewCredentials': True}))

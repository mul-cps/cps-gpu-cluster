"""In-cluster CPU-only native API protocol probe; no GPU preBind claim.

Only fixed QA object names/endpoints are permitted. Token stays in memory and is
never printed. Workstation/proxy impersonation is deliberately not supported.
"""
import copy
import json
import os
from pathlib import Path
import ssl
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import fence
import lifecycle

NAMESPACE = 'cps-dynamic-admission-coord-live-20261008'
NODE = 'k3s-cp3'
IMAGE = 'ghcr.io/mul-cps/cps-compute@sha256:627f093c3c96038c7ecd9e9b99f0138198c23c9460cabb7bd11b19e94f465096'
PODS = ('native-bind', 'native-stale', 'native-cancel', 'kai-cpu-allow', 'kai-cpu-deny')
MAPS = ('native-cap', 'native-evar', 'unregistered-map')


def cpu_pod(name, *, kai=False, finalizer=False):
    if name not in PODS: raise ValueError('Fixed reviewed Pod name required')
    metadata = {'name': name, 'namespace': NAMESPACE}
    if kai: metadata['labels'] = {'kai.scheduler/queue': 'default'}
    if finalizer: metadata['finalizers'] = ['qa.compute.cps.unileoben.ac.at/hold']
    return {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': metadata, 'spec': {
        'schedulerName': 'kai-scheduler' if kai else 'coordination-native-no-scheduler',
        'nodeSelector': {'kubernetes.io/hostname': NODE}, 'serviceAccountName': 'cpu-workload',
        'tolerations': [{'key': 'node-role.kubernetes.io/control-plane', 'operator': 'Exists', 'effect': 'NoSchedule'}],
        'automountServiceAccountToken': False, 'restartPolicy': 'Never', 'activeDeadlineSeconds': 120,
        'terminationGracePeriodSeconds': 1,
        'securityContext': {'runAsNonRoot': True, 'runAsUser': 1000, 'seccompProfile': {'type': 'RuntimeDefault'}},
        'containers': [{'name': 'main', 'image': IMAGE, 'command': ['python', '-B', '-c',
            'print("cpu-only-coordination-receipt", flush=True)'],
            'resources': {'requests': {'cpu': '50m', 'memory': '64Mi'}, 'limits': {'cpu': '250m', 'memory': '128Mi'}},
            'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                'capabilities': {'drop': ['ALL']}}}]}}


class API:
    def __init__(self):
        self.root = 'https://kubernetes.default.svc'
        self.token = Path('/var/run/secrets/kubernetes.io/serviceaccount/token')
        self.context = ssl.create_default_context(cafile='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')
        self.deadline = time.monotonic() + 180
    def request(self, method, resource, name='', data=None, *, deadline=None, subresource='', patch=False):
        end = min(self.deadline, deadline or self.deadline)
        if time.monotonic() >= end: raise TimeoutError('CPU probe deadline exceeded')
        if resource == 'selfsubjectreviews':
            if method != 'POST': raise ValueError('Identity review only')
            path = '/apis/authentication.k8s.io/v1/selfsubjectreviews'
        elif resource == 'nodes':
            if method != 'GET' or name != NODE: raise ValueError('Exact Node read only')
            path = '/api/v1/nodes/' + NODE
        else:
            allowed = PODS if resource == 'pods' else MAPS if resource == 'configmaps' else ()
            if name not in allowed or subresource not in ('', 'binding'): raise ValueError('Unreviewed endpoint')
            path = '/api/v1/namespaces/' + NAMESPACE + '/' + resource
            if method != 'POST' or subresource: path += '/' + name
            if subresource: path += '/' + subresource
        headers = {'Authorization': 'Bearer ' + self.token.read_text().strip(), 'Accept': 'application/json'}
        if data is not None: headers['Content-Type'] = 'application/json-patch+json' if patch else 'application/json'
        request = Request(self.root + path, method=method, headers=headers,
                          data=None if data is None else fence.canonical(data))
        try:
            with urlopen(request, context=self.context, timeout=min(2, end - time.monotonic())) as response:
                status, raw = response.status, response.read(fence.MAX_BYTES + 1)
        except HTTPError as error:
            status, raw = error.code, error.read(fence.MAX_BYTES + 1)
        if len(raw) > fence.MAX_BYTES or time.monotonic() >= end: raise TimeoutError('Bounded API response exceeded')
        return status, json.loads(raw)
    def get(self, resource, namespace, name, *, deadline):
        if namespace != NAMESPACE: raise ValueError('QA scope only')
        status, obj = self.request('GET', resource, name, deadline=deadline)
        if status == 404: return None
        if status != 200: raise OSError('GET failed: ' + str(status))
        return obj
    def delete(self, resource, namespace, name, options, *, deadline):
        if namespace != NAMESPACE: raise ValueError('QA scope only')
        status, obj = self.request('DELETE', resource, name, options, deadline=deadline)
        if status not in (200, 202): raise OSError('DELETE failed: ' + str(status))
        return obj


def seal_patch(obj):
    return [{'op': 'test', 'path': '/metadata/' + key, 'value': obj['metadata'][key]}
            for key in ('uid', 'resourceVersion')] + [{'op': 'add', 'path': '/immutable', 'value': True}]


def binding(pod, *, uid=None, rv=None):
    return {'apiVersion': 'v1', 'kind': 'Binding', 'metadata': {'namespace': NAMESPACE,
        'name': pod['metadata']['name'], 'uid': uid or pod['metadata']['uid'],
        'resourceVersion': rv or pod['metadata']['resourceVersion']},
        'target': {'apiVersion': 'v1', 'kind': 'Node', 'name': NODE}}


def run(api):
    receipts = []
    def must(label, result, statuses):
        status, obj = result
        receipt = {'case': label, 'status': status,
                   'uid': obj.get('metadata', {}).get('uid'), 'resourceVersion': obj.get('metadata', {}).get('resourceVersion')}
        print(json.dumps({'event': 'native-api-receipt', **receipt}), flush=True)
        if status not in statuses: raise RuntimeError(label + ': unexpected status ' + str(status))
        receipts.append(receipt)
        return obj
    identity = must('actual-authenticated-identity', api.request('POST', 'selfsubjectreviews', data={
        'apiVersion': 'authentication.k8s.io/v1', 'kind': 'SelfSubjectReview'}), (201,))
    actor = identity['status']['userInfo']['username']
    if actor != 'system:serviceaccount:' + NAMESPACE + ':native-probe': raise RuntimeError('Actual SA identity required')
    node_before = must('node-before', api.request('GET', 'nodes', NODE), (200,))
    # Actual unscheduled CPU Pod, native UID and RV Preconditions; no invented GPU objects.
    pod = must('native-pod-create', api.request('POST', 'pods', 'native-bind', cpu_pod('native-bind')), (201,))
    must('native-binding-wrong-uid', api.request('POST', 'pods', 'native-bind',
        binding(pod, uid='11111111-1111-4111-8111-111111111111'), subresource='binding'), (409,))
    fresh = must('native-pod-rv-change', api.request('PATCH', 'pods', 'native-bind',
        [{'op': 'test', 'path': '/metadata/uid', 'value': pod['metadata']['uid']},
         {'op': 'add', 'path': '/metadata/annotations', 'value': {'qa': 'rv-change'}}], patch=True), (200,))
    must('native-binding-stale-rv', api.request('POST', 'pods', 'native-bind', binding(pod), subresource='binding'), (409,))
    must('native-binding-exact-generation', api.request('POST', 'pods', 'native-bind', binding(fresh), subresource='binding'), (201,))
    stale = must('replacement-old-create', api.request('POST', 'pods', 'native-stale', cpu_pod('native-stale')), (201,))
    api.delete('pods', NAMESPACE, 'native-stale', {'apiVersion': 'v1', 'kind': 'DeleteOptions',
        'preconditions': {k: stale['metadata'][k] for k in ('uid', 'resourceVersion')}}, deadline=api.deadline)
    if api.get('pods', NAMESPACE, 'native-stale', deadline=api.deadline) is not None: raise RuntimeError('Confirm deletion before recreate')
    replacement = must('replacement-new-create', api.request('POST', 'pods', 'native-stale', cpu_pod('native-stale')), (201,))
    must('replacement-old-uid-binding-denied', api.request('POST', 'pods', 'native-stale', binding(stale), subresource='binding'), (409,))
    if replacement['metadata']['uid'] == stale['metadata']['uid']: raise RuntimeError('Replacement UID required')
    owner = must('cancel-pod-create', api.request('POST', 'pods', 'native-cancel', cpu_pod('native-cancel', finalizer=True)), (201,))
    maps = []
    for name in MAPS[:2]:
        maps.append(must(name + '-create', api.request('POST', 'configmaps', name, {'apiVersion': 'v1', 'kind': 'ConfigMap',
            'metadata': {'name': name, 'namespace': NAMESPACE, 'ownerReferences': [{'apiVersion': 'v1', 'kind': 'Pod',
            'name': 'native-cancel', 'uid': owner['metadata']['uid']}]}, 'data': {'receipt': 'cpu-native-only'}}), (201,)))
    cap = must('first-map-native-seal', api.request('PATCH', 'configmaps', 'native-cap', seal_patch(maps[0]), patch=True), (200,))
    changed = must('second-map-concurrent-change', api.request('PATCH', 'configmaps', 'native-evar',
        [{'op': 'add', 'path': '/data/receipt', 'value': 'review-again'}], patch=True), (200,))
    must('second-map-stale-seal-denied', api.request('PATCH', 'configmaps', 'native-evar', seal_patch(maps[1]), patch=True), (422, 409))
    cap = api.get('configmaps', NAMESPACE, 'native-cap', deadline=api.deadline)
    evar = api.get('configmaps', NAMESPACE, 'native-evar', deadline=api.deadline)
    if cap.get('immutable') is not True or evar.get('immutable') is True: raise RuntimeError('Partial seal must remain explicit')
    receipts.append({'case': 'partial-seal-receipt', 'firstImmutable': True, 'secondImmutable': False,
                     'bindingAttempted': False, 'atomicRollback': False})
    evar = must('second-map-reviewed-retry-seal', api.request('PATCH', 'configmaps', 'native-evar', seal_patch(evar), patch=True), (200,))
    must('native-immutable-data-rewrite-denied', api.request('PATCH', 'configmaps', 'native-cap',
        [{'op': 'add', 'path': '/data/receipt', 'value': 'forged'}], patch=True), (422,))
    try:
        lifecycle.cancel(NAMESPACE, owner, [cap, evar], api, timeout_seconds=0.4)
    except lifecycle.CancellationAborted as error:
        if len(error.receipts) != 1 or error.receipts[0]['resource'] != 'pods': raise
        terminating = api.get('pods', NAMESPACE, 'native-cancel', deadline=api.deadline)
        if terminating['metadata']['uid'] != owner['metadata']['uid'] or not terminating['metadata'].get('deletionTimestamp'): raise
        if any(api.get('configmaps', NAMESPACE, cm['metadata']['name'], deadline=api.deadline) is None for cm in (cap, evar)): raise
        receipts.append({'case': 'termination-blocks-cleanup', 'podUid': owner['metadata']['uid'], 'mapsPreserved': True})
    else: raise RuntimeError('Terminating original UID must not allow cleanup')
    must('reviewed-finalizer-release', api.request('PATCH', 'pods', 'native-cancel',
        [{'op': 'test', 'path': '/metadata/uid', 'value': owner['metadata']['uid']},
         {'op': 'test', 'path': '/metadata/resourceVersion', 'value': terminating['metadata']['resourceVersion']},
         {'op': 'remove', 'path': '/metadata/finalizers'}], patch=True), (200,))
    for _ in range(40):
        if api.get('pods', NAMESPACE, 'native-cancel', deadline=api.deadline) is None: break
        time.sleep(0.025)
    else: raise RuntimeError('Original UID absence not established')
    new_pod = must('cancel-name-replacement-create', api.request('POST', 'pods', 'native-cancel', cpu_pod('native-cancel')), (201,))
    cleanup = lifecycle.cancel(NAMESPACE, owner, [cap, evar], api)
    kept = api.get('pods', NAMESPACE, 'native-cancel', deadline=api.deadline)
    if kept['metadata']['uid'] != new_pod['metadata']['uid']: raise RuntimeError('Named replacement must remain')
    receipts.append({'case': 'exact-original-uid-absence-cleanup', 'result': cleanup, 'replacementPreserved': True})
    must('apiserver-webhook-unregistered-map-denial', api.request('POST', 'configmaps', 'unregistered-map',
        {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'unregistered-map', 'namespace': NAMESPACE}}), (403,))
    node_after = must('node-after', api.request('GET', 'nodes', NODE), (200,))
    return {'status': 'cpu-native-protocol-passed', 'actor': actor, 'receipts': receipts,
        'node': {'name': NODE, 'uid': node_before['metadata']['uid'],
                 'beforeResourceVersion': node_before['metadata']['resourceVersion'],
                 'afterResourceVersion': node_after['metadata']['resourceVersion'],
                 'sameResourceVersion': node_before['metadata']['resourceVersion'] == node_after['metadata']['resourceVersion']},
        'qualification': {'gpuPreBind': False, 'fullGenerationFence': False, 'atomicRollback': False,
                          'gpuIsolation': False, 'mixedPacking': False, 'production': False}}


if __name__ == '__main__':
    if os.environ.get('POD_NAMESPACE') != NAMESPACE: raise SystemExit('Exact QA runner namespace required')
    print(json.dumps(run(API()), sort_keys=True), flush=True)

"""Bounded QA cancellation, never rollback immutable data or delete a replacement.

This is a sequential protocol, not an atomic multi-object transaction. Callers
must retain the generation fence and explicitly review any partial receipt.
"""
import time
import re

import fence


class CancellationAborted(RuntimeError):
    def __init__(self, reason, receipts):
        super().__init__(reason)
        self.receipts = list(receipts)


def cancel(namespace, pod, maps, api, *, timeout_seconds=2, clock=time.monotonic, pause=time.sleep):
    """DELETE with UID/RV CAS; wait for exact UID absence; then clean pinned maps.

    api.get returns None only for confirmed 404; api.delete accepts DeleteOptions
    and an absolute deadline. A named Pod replacement proves old UID absence,
    but is never deleted. Unknown delete outcomes require fresh explicit review.
    """
    fence.require(re.fullmatch(fence.quota_policy.NAMESPACE_PATTERN, namespace), 'QA namespace required')
    fence.identity(pod, 'Pod', namespace)
    fence.require(0 < timeout_seconds <= 3 and 1 <= len(maps) <= 2, 'Bounded cancellation required')
    for cm in maps:
        fence.identity(cm, 'ConfigMap', namespace)
        fence.require(cm['metadata'].get('ownerReferences') == [{'apiVersion': 'v1', 'kind': 'Pod',
            'name': pod['metadata']['name'], 'uid': pod['metadata']['uid']}], 'Only original Pod-owned maps may be cleaned')
    fence.require(len({cm['metadata']['name'] for cm in maps}) == len(maps), 'Distinct pinned maps required')
    deadline, receipts = clock() + timeout_seconds, []
    def read(resource, expected):
        if clock() >= deadline: raise TimeoutError('Cancellation deadline exceeded')
        return api.get(resource, namespace, expected['metadata']['name'], deadline=deadline)
    def deleting(resource, expected):
        options = {'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions':
                   {k: expected['metadata'][k] for k in ('uid', 'resourceVersion')}}
        api.delete(resource, namespace, expected['metadata']['name'], options, deadline=deadline)
        receipts.append({'resource': resource, 'name': expected['metadata']['name'],
                         'uid': expected['metadata']['uid'], 'deleteAccepted': True})
    def old_pod_absent():
        current = read('pods', pod)
        if current is None: return True
        fence.identity(current, 'Pod', namespace)
        fence.require(current['metadata']['name'] == pod['metadata']['name'], 'Unexpected Pod read')
        return current['metadata']['uid'] != pod['metadata']['uid']
    try:
        current = read('pods', pod)
        if current is not None:
            fence.identity(current, 'Pod', namespace)
            fence.require(current['metadata']['name'] == pod['metadata']['name'], 'Unexpected Pod read')
            if current['metadata']['uid'] == pod['metadata']['uid']:
                fence.require(current['metadata']['resourceVersion'] == pod['metadata']['resourceVersion'], 'Review current Pod RV before cancel')
                deleting('pods', pod)
        while not old_pod_absent():
            pause(min(0.025, max(0, deadline - clock())))
        for expected in maps:
            fence.require(old_pod_absent(), 'Original Pod UID must stay absent before cleanup')
            current = read('configmaps', expected)
            if current is None: continue
            fence.identity(current, 'ConfigMap', namespace)
            fence.require(current == expected, 'Review changed/recreated map before cleanup')
            deleting('configmaps', expected)
        return {'originalPodUidAbsent': True, 'receipts': receipts, 'atomicRollback': False}
    except Exception as error:
        raise CancellationAborted('Cancellation failed closed: ' + str(error), receipts) from error

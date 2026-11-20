"""Bounded QA hook for a trusted coordinator; never invoked by admission.

Two ConfigMaps cannot be sealed atomically. Return explicit partial receipts on
failure; publish no binding registry until both receipts are independently read.
"""
import copy
import time

import fence


class SealAborted(fence.Denied):
    def __init__(self, reason, partial_record):
        super().__init__(reason)
        self.partial_record = copy.deepcopy(partial_record)


def seal(record, namespace, api, *, timeout_seconds=2.0, clock=time.monotonic):
    """At most two UID/RV-tested PATCHes; api.get/patch must honor the deadline.

    An already-sealed exact receipt is a no-op retry. Changed generations/RVs
    require explicit review; there is no fresh-GET-and-overwrite retry loop.
    """
    if not 0 < timeout_seconds <= 3:
        raise ValueError('A bounded seal deadline in (0,3] seconds is required')
    deadline = clock() + timeout_seconds
    partial = copy.deepcopy(record)

    def bounded_get(resource, scope, name):
        fence.require(clock() < deadline, 'Sealer deadline exceeded')
        result = api.get(resource, scope, name, deadline=deadline)
        fence.require(clock() < deadline, 'Sealer API lookup exceeded deadline')
        return result

    try:
        fence.require(isinstance(namespace, str) and len(namespace) <= 63 and fence.re.fullmatch(fence.quota_policy.NAMESPACE_PATTERN, namespace), 'Sealer is restricted to a separate QA namespace')
        fence.validate_record(record, namespace)
        fence.check_live_record(record, namespace, bounded_get, sealed=False)
        for index, expected in enumerate(record['configMaps']):
            actual = bounded_get('configmaps', namespace, expected['metadata']['name'])
            fence.check_map(actual, expected, namespace, sealed=expected.get('immutable', False))
            if actual.get('immutable') is not True:
                fence.require(clock() < deadline, 'Sealer deadline exceeded')
                patch = [{'op': 'test', 'path': '/metadata/uid', 'value': expected['metadata']['uid']},
                         {'op': 'test', 'path': '/metadata/resourceVersion', 'value': expected['metadata']['resourceVersion']},
                         {'op': 'add', 'path': '/immutable', 'value': True}]
                result = api.patch('configmaps', namespace, expected['metadata']['name'], patch, deadline=deadline)
                fence.require(clock() < deadline, 'Sealer PATCH exceeded deadline')
                receipt = copy.deepcopy(expected)
                receipt['immutable'] = True
                receipt['metadata']['resourceVersion'] = result['metadata']['resourceVersion']
                fence.require(receipt['metadata']['resourceVersion'] != expected['metadata']['resourceVersion'], 'Seal must return a new persisted version')
                fence.check_map(result, receipt, namespace, sealed=True)
                partial['configMaps'][index] = result
        # Confirm both persisted generations, complete data and original live
        # Pod/parent/Node again. Admission still needs manual protected enrollment.
        fence.check_live_record(partial, namespace, bounded_get, sealed=True)
        return partial
    except Exception as error:
        raise SealAborted('Sealing aborted; no binding approval published: ' + str(error), partial) from error

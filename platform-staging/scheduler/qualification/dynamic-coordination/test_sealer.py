import copy
import time
import unittest

import fence
import sealer
from test_fence import ACTOR, CAP, COORDINATOR, NS, fixture, review


class FakeAPI:
    def __init__(self, registry, objects):
        self.registry, self.objects = registry, objects
        self.patches = []
        self.fail_second = False
        self.recreate_before_patch = False

    def get(self, resource, namespace, name, *, deadline):
        return copy.deepcopy(self.objects.get((resource, namespace, name)))

    def patch(self, resource, namespace, name, patch, *, deadline):
        self.patches.append(patch)
        if self.fail_second and len(self.patches) == 2:
            raise RuntimeError('second map conflict')
        old = self.objects[resource, namespace, name]
        if self.recreate_before_patch:
            old['metadata']['uid'] = '00000000-0000-4000-8000-000000000009'
        for test in patch[:2]:
            field = test['path'].split('/')[-1]
            if old['metadata'][field] != test['value']: raise RuntimeError('JSON Patch precondition failed')
        new = copy.deepcopy(old)
        new['immutable'] = True
        response = fence.authorize(review('configmaps', 'UPDATE', '', obj=new, old=copy.deepcopy(old), actor=COORDINATOR),
                                   self.registry, lambda r, ns, n: self.get(r, ns, n, deadline=deadline))
        if not response['response']['allowed']: raise RuntimeError(response['response']['status']['message'])
        new['metadata']['resourceVersion'] = str(int(old['metadata']['resourceVersion']) + 1)
        self.objects[resource, namespace, name] = new
        return copy.deepcopy(new)


class SealerTests(unittest.TestCase):
    def setUp(self):
        self.registry, self.objects = fixture(False)
        self.record = self.registry['records'][0]
        self.api = FakeAPI(self.registry, self.objects)

    def test_both_seals_use_uid_and_rv_tests_then_binding_needs_updated_registry(self):
        receipt = sealer.seal(self.record, NS, self.api)
        self.assertEqual(len(self.api.patches), 2)
        self.assertTrue(all(p[0]['path'] == '/metadata/uid' and p[1]['path'] == '/metadata/resourceVersion' for p in self.api.patches))
        read = lambda r, ns, n: self.api.get(r, ns, n, deadline=time.monotonic() + 1)
        self.assertFalse(fence.authorize(review(), self.registry, read)['response']['allowed'])
        self.registry['records'] = [receipt]
        self.assertTrue(fence.authorize(review(), self.registry, read)['response']['allowed'])
        self.assertEqual(sealer.seal(receipt, NS, self.api), receipt)
        self.assertEqual(len(self.api.patches), 2)

    def test_partial_failure_is_explicit_and_retry_requires_partial_receipts(self):
        self.api.fail_second = True
        with self.assertRaises(sealer.SealAborted) as failure:
            sealer.seal(self.record, NS, self.api)
        partial = failure.exception.partial_record
        self.assertTrue(partial['configMaps'][0]['immutable'])
        self.assertNotIn('immutable', partial['configMaps'][1])
        self.api.fail_second = False
        with self.assertRaises(sealer.SealAborted): sealer.seal(self.record, NS, self.api)
        receipt = sealer.seal(partial, NS, self.api)
        self.assertTrue(all(cm['immutable'] for cm in receipt['configMaps']))

    def test_recreation_between_get_and_patch_aborts_uid_precondition(self):
        self.api.recreate_before_patch = True
        with self.assertRaises(sealer.SealAborted): sealer.seal(self.record, NS, self.api)

    def test_missing_partial_or_changed_maps_never_start_patching(self):
        for change in ('missing', 'partial', 'changed'):
            self.setUp()
            if change == 'missing': del self.objects['configmaps', NS, CAP]
            elif change == 'partial': del self.objects['configmaps', NS, CAP]['data']['GPU_PORTION']
            else: self.objects['configmaps', NS, CAP]['metadata']['resourceVersion'] = '90'
            with self.subTest(change=change), self.assertRaises(sealer.SealAborted): sealer.seal(self.record, NS, self.api)
            self.assertEqual(self.api.patches, [])

    def test_deadline_and_api_error_abort_without_approval(self):
        ticks = iter([0, 4])
        with self.assertRaises(sealer.SealAborted): sealer.seal(self.record, NS, self.api, clock=lambda: next(ticks))
        self.assertEqual(self.api.patches, [])

    def test_noncoordinator_cannot_use_the_transition(self):
        old = self.objects['configmaps', NS, CAP]
        new = copy.deepcopy(old); new['immutable'] = True
        response = fence.authorize(review('configmaps', 'UPDATE', '', obj=new, old=old, actor=ACTOR),
                                   self.registry, lambda r, ns, n: copy.deepcopy(self.objects.get((r, ns, n))))
        self.assertFalse(response['response']['allowed'])

    def test_production_namespace_is_rejected_before_any_write(self):
        with self.assertRaises(sealer.SealAborted): sealer.seal(self.record, 'production', self.api)
        self.assertEqual(self.api.patches, [])

    def test_timeout_after_successful_patch_has_uncertain_receipt_and_never_approves(self):
        original_patch = self.api.patch
        def uncertain(*args, **kwargs):
            original_patch(*args, **kwargs)
            raise TimeoutError('Response lost after persisted seal')
        self.api.patch = uncertain
        with self.assertRaises(sealer.SealAborted) as error: sealer.seal(self.record, NS, self.api)
        self.assertTrue(self.objects['configmaps', NS, CAP]['immutable'])
        self.assertNotIn('immutable', error.exception.partial_record['configMaps'][0])
        read = lambda r, ns, n: copy.deepcopy(self.objects.get((r, ns, n)))
        self.assertFalse(fence.authorize(review(), self.registry, read)['response']['allowed'])


if __name__ == '__main__': unittest.main()

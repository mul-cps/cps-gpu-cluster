import copy
import unittest

import lifecycle
from test_fence import fixture


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        registry, self.objects = fixture()
        self.ns = registry['namespace']
        self.record = registry['records'][0]
        self.pod, self.maps = self.record['pod'], self.record['configMaps']
        self.now, self.calls, self.terminating, self.failure = 0, [], False, None
        outer = self
        class API:
            def get(self, resource, namespace, name, *, deadline):
                if outer.failure == 'read': raise OSError('API failed')
                return copy.deepcopy(outer.objects.get((resource, namespace, name)))
            def delete(self, resource, namespace, name, options, *, deadline):
                outer.calls.append((resource, name, options))
                if outer.failure == name: raise OSError('Unknown DELETE outcome')
                current = outer.objects[(resource, namespace, name)]
                assert options['preconditions'] == {k: current['metadata'][k] for k in ('uid', 'resourceVersion')}
                if resource == 'pods' and outer.terminating:
                    current['metadata']['deletionTimestamp'] = '2026-10-08T12:00:00Z'
                else: del outer.objects[(resource, namespace, name)]
        self.api = API()
    def pause(self, duration): self.now += duration
    def cancel(self, **kwargs):
        return lifecycle.cancel(self.ns, self.pod, self.maps, self.api,
            clock=lambda: self.now, pause=self.pause, timeout_seconds=0.1, **kwargs)
    def test_exact_uid_rv_delete_then_absence_then_maps(self):
        result = self.cancel()
        self.assertEqual([c[0] for c in self.calls], ['pods', 'configmaps', 'configmaps'])
        self.assertFalse(result['atomicRollback'])
        self.assertTrue(result['originalPodUidAbsent'])
    def test_terminating_original_uid_times_out_without_map_delete(self):
        self.terminating = True
        with self.assertRaises(lifecycle.CancellationAborted) as error: self.cancel()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(error.exception.receipts), 1)
    def test_recreated_pod_is_kept_while_old_maps_cleaned(self):
        replacement = self.objects[('pods', self.ns, self.pod['metadata']['name'])]
        replacement['metadata']['uid'] = '11111111-1111-4111-8111-111111111111'
        self.cancel()
        self.assertTrue(all(c[0] == 'configmaps' for c in self.calls))
        self.assertIn(('pods', self.ns, self.pod['metadata']['name']), self.objects)
    def test_stale_pod_rv_or_read_error_never_deletes(self):
        self.objects[('pods', self.ns, self.pod['metadata']['name'])]['metadata']['resourceVersion'] = '999'
        with self.assertRaises(lifecycle.CancellationAborted): self.cancel()
        self.assertEqual(self.calls, [])
        self.failure = 'read'
        with self.assertRaises(lifecycle.CancellationAborted): self.cancel()
        self.assertEqual(self.calls, [])
    def test_recreated_map_refuses_delete_and_partial_receipt_is_retained(self):
        self.objects[('configmaps', self.ns, self.maps[1]['metadata']['name'])]['metadata']['uid'] = '11111111-1111-4111-8111-111111111111'
        with self.assertRaises(lifecycle.CancellationAborted) as error: self.cancel()
        self.assertEqual([c[0] for c in self.calls], ['pods', 'configmaps'])
        self.assertEqual(len(error.exception.receipts), 2)
    def test_retry_after_partial_cleanup_requires_original_absence(self):
        self.failure = self.maps[1]['metadata']['name']
        with self.assertRaises(lifecycle.CancellationAborted): self.cancel()
        self.failure = None
        result = self.cancel()
        self.assertEqual(len(result['receipts']), 1)
    def test_foreign_owner_or_production_namespace_rejected_before_api(self):
        foreign = copy.deepcopy(self.maps)
        foreign[0]['metadata']['ownerReferences'][0]['uid'] = '11111111-1111-4111-8111-111111111111'
        for ns, maps in ((self.ns, foreign), ('cps-workflows', self.maps)):
            with self.assertRaises(ValueError): lifecycle.cancel(ns, self.pod, maps, self.api)
        self.assertEqual(self.calls, [])


if __name__ == '__main__': unittest.main()

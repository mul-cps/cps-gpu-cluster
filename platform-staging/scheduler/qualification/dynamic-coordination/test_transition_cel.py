"""Execute only NEW transition cases with the documented cached CEL engine."""
import copy
import unittest

import fence
import quota_transition
from test_fence import ACTOR, COORDINATOR, NS, fixture

cel_evaluate = fence._adjacent('cel_evaluate')


class TransitionCelTests(unittest.TestCase):
    def setUp(self):
        self.registry, _ = fixture(False)
        bundle = quota_transition.build(self.registry, quota_writers=[ACTOR])
        self.params, self.policy = bundle['items'][1], bundle['items'][2]

    def evaluate(self, old, new, actor=COORDINATOR, operation='UPDATE'):
        report = cel_evaluate.evaluate_policy(self.policy, {'params': self.params, 'object': new, 'oldObject': old,
            'request': {'namespace': NS, 'operation': operation, 'userInfo': {'username': actor}}})
        self.assertTrue(report['compiled'], report)
        return report['allExpressionsTrue'], [r for r in report['expressions'] if 'failure' in r]

    def test_complete_capabilities_and_evar_seal_for_exact_coordinator(self):
        for old in self.registry['records'][0]['configMaps']:
            for explicit_false in (False, True):
                old = copy.deepcopy(old)
                if explicit_false: old['immutable'] = False
                new = copy.deepcopy(old); new['immutable'] = True
                allowed, failures = self.evaluate(old, new)
                self.assertTrue(allowed, failures)

    def test_foreign_writer_data_owner_uid_and_stale_rv_never_seal(self):
        original = self.registry['records'][0]['configMaps'][0]
        for change in ('actor', 'data', 'owner', 'uid', 'rv', 'partial'):
            old = copy.deepcopy(original); new = copy.deepcopy(old); new['immutable'] = True
            actor = ACTOR if change == 'actor' else COORDINATOR
            if change == 'data': new['data']['GPU_PORTION'] = '1'
            if change == 'owner': new['metadata']['ownerReferences'][0]['uid'] = '00000000-0000-4000-8000-000000000099'
            if change == 'uid': new['metadata']['uid'] = '00000000-0000-4000-8000-000000000099'
            if change == 'rv': old['metadata']['resourceVersion'] = new['metadata']['resourceVersion'] = '29'
            if change == 'partial': old['data'].pop('GPU_PORTION'); new['data'].pop('GPU_PORTION')
            with self.subTest(change=change): self.assertFalse(self.evaluate(old, new, actor)[0])

    def test_sealed_data_reset_and_owner_change_deny(self):
        old = copy.deepcopy(self.registry['records'][0]['configMaps'][0]); old['immutable'] = True
        for change in ('reset', 'owner', 'unseal'):
            new = copy.deepcopy(old)
            if change == 'reset': new['data'] = {}
            if change == 'owner': new['metadata']['ownerReferences'] = []
            if change == 'unseal': new['immutable'] = False
            with self.subTest(change=change): self.assertFalse(self.evaluate(old, new, ACTOR)[0])

    def test_existing_mutable_writer_retry_and_absent_evar_data_remain_valid(self):
        cap, evar = self.registry['records'][0]['configMaps']
        self.assertTrue(self.evaluate(copy.deepcopy(cap), copy.deepcopy(cap), ACTOR)[0])
        old = copy.deepcopy(evar); old.pop('data')
        new = copy.deepcopy(old); new['immutable'] = True
        allowed, failures = self.evaluate(old, new)
        self.assertTrue(allowed, failures)


if __name__ == '__main__': unittest.main()

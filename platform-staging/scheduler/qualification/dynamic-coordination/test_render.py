import copy
import unittest

import fence
import quota_transition
import render
from test_fence import NS, fixture


class RenderTests(unittest.TestCase):
    def test_inactive_empty_default_has_no_node_or_sealer_write_permissions(self):
        manifest = render.build(image='qa.invalid/fence@sha256:' + 'a' * 64, ca_bundle=b'reviewed-test-ca')
        kinds = [item['kind'] for item in manifest['items']]
        self.assertNotIn('ClusterRole', kinds)
        self.assertNotIn('ClusterRoleBinding', kinds)
        deployment = next(i for i in manifest['items'] if i['kind'] == 'Deployment')
        self.assertEqual(deployment['spec']['replicas'], 0)
        for item in manifest['items']:
            for rule in item.get('rules', []): self.assertEqual(rule['verbs'], ['get'])
        webhook = next(i for i in manifest['items'] if i['kind'] == 'ValidatingWebhookConfiguration')['webhooks'][0]
        self.assertEqual(webhook['failurePolicy'], 'Fail')
        self.assertEqual(webhook['sideEffects'], 'None')
        self.assertEqual(webhook['timeoutSeconds'], 5)
        self.assertEqual(len(next(i for i in manifest['items'] if i['kind'] == 'DynamicGpuQuotaPolicy')['records']), 0)

    def test_node_get_and_window_protection_require_exact_opt_in(self):
        registry, _ = fixture()
        manifest = render.build(image='qa.invalid/fence@sha256:' + 'a' * 64, ca_bundle=b'qa-ca', registry=registry, namespace=NS, node_names=['qa-node'])
        role = next(i for i in manifest['items'] if i['kind'] == 'ClusterRole')
        self.assertEqual(role['rules'], [{'apiGroups': [''], 'resources': ['nodes'], 'resourceNames': ['qa-node'], 'verbs': ['get']}])
        webhooks = next(i for i in manifest['items'] if i['kind'] == 'ValidatingWebhookConfiguration')['webhooks']
        self.assertIn('qa-node', webhooks[1]['matchConditions'][0]['expression'])
        with self.assertRaises(ValueError): render.build(image='qa.invalid/fence@sha256:' + 'a' * 64, ca_bundle=b'qa-ca', registry=registry, namespace=NS, node_names=['unreviewed'])

    def test_sealer_patch_permission_names_only_current_reviewed_maps(self):
        registry, _ = fixture(False)
        registry['sealWriter'] = 'system:serviceaccount:cps-dynamic-coordination-review:trusted-sealer'
        manifest = render.build(image='qa.invalid/fence@sha256:' + 'a' * 64, ca_bundle=b'qa-ca', registry=registry, namespace=NS, node_names=['qa-node'], sealer_rbac=True)
        role = next(i for i in manifest['items'] if i['kind'] == 'Role' and i['metadata']['name'] == 'trusted-sealer')
        rules = [r for r in role['rules'] if 'patch' in r['verbs']]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]['resources'], ['configmaps'])
        self.assertEqual(set(rules[0]['resourceNames']), {cm['metadata']['name'] for cm in registry['records'][0]['configMaps']})
        self.assertTrue(all('delete' not in r['verbs'] and 'update' not in r['verbs'] for r in role['rules']))

    def test_transition_is_new_candidate_and_keeps_existing_population_rules(self):
        registry, _ = fixture(False)
        bundle = quota_transition.build(registry)
        policy = bundle['items'][2]
        self.assertTrue(policy['metadata']['name'].endswith('-seal-transition'))
        messages = [v['message'] for v in policy['spec']['validations']]
        self.assertIn('Same-stage retries or one forward population step are allowed; reset, removal and skipped stages are denied', messages)
        self.assertTrue(any('coordinator' in message for message in messages))
        for row in bundle['items'][1]['records']:
            self.assertEqual(row['sealResourceVersion'], '30')

    def test_latest_image_and_foreign_namespace_are_rejected(self):
        with self.assertRaises(ValueError): render.build(image='qa.invalid/fence:latest', ca_bundle=b'qa-ca')
        registry, _ = fixture()
        with self.assertRaises(ValueError): render.build(image='qa.invalid/fence@sha256:' + 'a' * 64, ca_bundle=b'qa-ca', registry=registry, namespace='cps-dynamic-admission-foreign')

    def test_registry_generations_use_distinct_immutable_configmaps_for_manual_rollout(self):
        registry, _ = fixture(False)
        first = render.build(image='qa.invalid/fence@sha256:' + 'a' * 64, ca_bundle=b'qa-ca', registry=registry, namespace=NS)
        registry['records'][0]['configMaps'][0]['immutable'] = True
        second = render.build(image='qa.invalid/fence@sha256:' + 'a' * 64, ca_bundle=b'qa-ca', registry=registry, namespace=NS)
        first_cm = next(i for i in first['items'] if i['kind'] == 'ConfigMap')
        second_cm = next(i for i in second['items'] if i['kind'] == 'ConfigMap')
        self.assertNotEqual(first_cm['metadata']['name'], second_cm['metadata']['name'])
        self.assertTrue(first_cm['immutable'] and second_cm['immutable'])


if __name__ == '__main__': unittest.main()

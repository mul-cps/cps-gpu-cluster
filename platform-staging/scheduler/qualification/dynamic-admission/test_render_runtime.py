"""Correspondence between three inactive admission boundaries, without apply."""
import copy
import unittest

import compiled_fixtures
import render_runtime

EXECUTOR = 'registry.invalid/executor@sha256:' + '2' * 64
ACTOR = 'system:serviceaccount:offline:declared-argo-controller'
BINDER = 'system:serviceaccount:offline:declared-binder'


class RuntimeComposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = compiled_fixtures.generate()['fixtures']['batch-shared-5']
        cls.workflow = value['compiledWorkflow']
        cls.pod = value['declaredControllerPod']['object']

    def registry(self, binding=False):
        owner = self.pod['metadata']['ownerReferences'][0]
        pod_name = self.pod['metadata']['name']
        prefix = owner['name'] + '-bcdfgh2-shared-gpu'
        pod_uid = '11111111-1111-1111-1111-111111111111'
        gpu = 'GPU-22222222-2222-2222-2222-222222222222'
        data = {'namespace': compiled_fixtures.NAMESPACE, 'podName': pod_name, 'podUid': pod_uid,
                'gpuUuid': gpu, 'visibleDevices': 'k8s.device-plugin.nvidia.com/gpu=1',
                'physicalGpuMemoryMiB': '40960', 'gpuPortion': '0.13', 'runaiNumOfGpus': '0.13', 'cudaDeviceMemoryLimit': '5324m'}
        maps = [{**data, 'name': prefix + '-1', 'type': 'capabilities'},
                {**data, 'name': prefix + '-1-evar', 'type': 'evar'}]
        registry = {'createCreators': [ACTOR], 'updateCreators': [BINDER],
                    'owners': [{'name': owner['name'], 'uid': owner['uid']}],
                    'reviewedPods': [{'name': pod_name, 'ownerUid': owner['uid'], 'configMapPrefix': prefix,
                                      'mainIndex': 1, 'gpuMemory': '5120'}],
                    'quotaWriters': [BINDER], 'quotaRecords': maps,
                    'bindingWriters': [BINDER], 'bindingRecords': []}
        if binding:
            maps[0]['cmUid'] = '33333333-3333-3333-3333-333333333333'
            maps[1]['cmUid'] = '44444444-4444-4444-4444-444444444444'
            registry['bindingRecords'] = [{'podName': pod_name, 'podUid': pod_uid, 'nodeName': 'offline-node',
                'capabilitiesName': maps[0]['name'], 'capabilitiesUid': maps[0]['cmUid'], 'capabilitiesResourceVersion': '10',
                'evarName': maps[1]['name'], 'evarUid': maps[1]['cmUid'], 'evarResourceVersion': '11',
                'compiledWorkflowSha256': compiled_fixtures.digest(self.workflow), 'registryReviewSha256': '5' * 64}]
        return registry

    def build(self, registry=None):
        return render_runtime.build(registry=registry, executor_image=EXECUTOR)

    def test_default_bundle_has_three_boundaries_and_empty_protected_tables(self):
        bundle = self.build()
        self.assertEqual(len(bundle['items']), 12)
        for kind in ('CustomResourceDefinition', 'ValidatingAdmissionPolicy', 'ValidatingAdmissionPolicyBinding'):
            self.assertEqual(sum(item['kind'] == kind for item in bundle['items']), 3)
        self.assertFalse(any(item['kind'] in ('Namespace', 'Role', 'RoleBinding', 'Deployment', 'Pod') for item in bundle['items']))
        for index in (1, 5, 9):
            item = bundle['items'][index]
            self.assertFalse(item.get('records', item.get('reviewedPods')))

    def test_consistent_staged_and_completed_attestations_are_accepted(self):
        for complete in (False, True):
            with self.subTest(binding=complete):
                self.assertEqual(len(self.build(self.registry(complete))['items']), 12)

    def test_cross_pod_map_wrong_profile_and_partial_pair_are_rejected(self):
        for name, change in (
            ('other-pod', lambda r: r['quotaRecords'][0].update(podName='other-pod')),
            ('other-map', lambda r: r['quotaRecords'][0].update(name='other-map')),
            ('wrong-limit', lambda r: r['quotaRecords'][0].update(cudaDeviceMemoryLimit='10240m')),
            ('missing-pair', lambda r: r['quotaRecords'].pop()),
            ('wrong-role', lambda r: r['quotaRecords'][0].update(type='evar')),
            ('different-pod-uid', lambda r: r['quotaRecords'][1].update(podUid='99999999-9999-9999-9999-999999999999')),
            ('different-device', lambda r: r['quotaRecords'][1].update(visibleDevices='k8s.device-plugin.nvidia.com/gpu=0')),
        ):
            with self.subTest(name=name):
                registry = self.registry(); change(registry)
                with self.assertRaises(ValueError): self.build(registry)

    def test_binding_generations_cannot_mix_pods_or_maps(self):
        for field, value in [('podName', 'other-pod'), ('podUid', '99999999-9999-9999-9999-999999999999'),
                             ('capabilitiesName', 'other-map'), ('evarName', 'other-evar'),
                             ('capabilitiesUid', '99999999-9999-9999-9999-999999999999'),
                             ('evarUid', '99999999-9999-9999-9999-999999999999')]:
            with self.subTest(field=field):
                registry = self.registry(True); registry['bindingRecords'][0][field] = value
                with self.assertRaises(ValueError): self.build(registry)
        registry = self.registry(True); del registry['quotaRecords'][0]['cmUid']
        with self.assertRaises(ValueError): self.build(registry)

    def test_unknown_registry_keys_and_production_namespaces_are_rejected(self):
        with self.assertRaises(ValueError): self.build({'trustAllUsers': True})
        for namespace in ('cps-workflows', 'jupyterhub', 'cit-jhub', 'cps-dynamic-admission-'):
            with self.subTest(namespace=namespace), self.assertRaises(ValueError):
                render_runtime.build(namespace=namespace, executor_image=EXECUTOR)

    def test_no_input_registry_is_mutated(self):
        registry = self.registry(True); original = copy.deepcopy(registry)
        self.build(registry)
        self.assertEqual(registry, original)


if __name__ == '__main__':
    unittest.main()

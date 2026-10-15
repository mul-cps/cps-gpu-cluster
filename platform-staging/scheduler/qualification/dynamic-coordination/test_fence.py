import copy
import unittest

import fence

NS = 'cps-dynamic-admission-coordination'
ACTOR = 'system:serviceaccount:' + NS + ':reviewed-binder'
COORDINATOR = 'system:serviceaccount:' + NS + ':reviewed-sealer'
POD_UID = '00000000-0000-4000-8000-000000000001'
OWNER_UID = '00000000-0000-4000-8000-000000000002'
NODE_UID = '00000000-0000-4000-8000-000000000003'
CAP_UID = '00000000-0000-4000-8000-000000000004'
EVAR_UID = '00000000-0000-4000-8000-000000000005'
PREFIX = 'reviewed-workflow-bcdfgh2-shared-gpu'
CAP = PREFIX + '-0'


def fixture(sealed=True):
    pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {
        'namespace': NS, 'name': 'reviewed-pod', 'uid': POD_UID, 'resourceVersion': '10',
        'ownerReferences': [{'apiVersion': 'argoproj.io/v1alpha1', 'kind': 'Workflow',
                             'name': 'reviewed-workflow', 'uid': OWNER_UID}],
        'annotations': {'gpu-memory': '5120', 'runai/shared-gpu-configmap': PREFIX}, 'labels': {}},
        'spec': {'containers': [{'name': 'main', 'image': 'qa.invalid/image@sha256:' + 'a' * 64,
          'env': [{'name': key, 'valueFrom': {'configMapKeyRef': dict(name=CAP, key=key,
                **({'optional': True} if key == 'CUDA_DEVICE_MEMORY_LIMIT' else {}))}}
                  for key in ('NVIDIA_VISIBLE_DEVICES', 'RUNAI_NUM_OF_GPUS', 'GPU_PORTION', 'CUDA_DEVICE_MEMORY_LIMIT')],
          'envFrom': [{'configMapRef': {'name': CAP + '-evar', 'optional': False}}]}],
          'volumes': [{'name': CAP + '-vol', 'configMap': {'name': CAP}}]}}
    workflow = {'apiVersion': 'argoproj.io/v1alpha1', 'kind': 'Workflow',
                'metadata': {'namespace': NS, 'name': 'reviewed-workflow', 'uid': OWNER_UID, 'resourceVersion': '3'},
                'spec': {'entrypoint': 'reviewed'}}
    node = {'apiVersion': 'v1', 'kind': 'Node', 'metadata': {'name': 'qa-node', 'uid': NODE_UID,
            'resourceVersion': '20', 'labels': {'nvidia.com/gpu.memory': '81920'}},
            'spec': {}, 'status': {'allocatable': {'nvidia.com/gpu': '8'}}}
    device = dict(gpuUuid='GPU-00000000-0000-4000-8000-000000000006',
                  visibleDevices='k8s.device-plugin.nvidia.com/gpu=0', physicalGpuMemoryMiB='81920',
                  gpuPortion='0.1', runaiNumOfGpus='0.1', cudaDeviceMemoryLimit='8192m')
    data = dict(NVIDIA_VISIBLE_DEVICES=device['visibleDevices'], GPU_PORTION='0.1',
                RUNAI_NUM_OF_GPUS='0.1', CUDA_DEVICE_MEMORY_LIMIT='8192m')
    maps = []
    for name, uid, payload in ((CAP, CAP_UID, data), (CAP + '-evar', EVAR_UID, {})):
        maps.append({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {
            'namespace': NS, 'name': name, 'uid': uid, 'resourceVersion': '30',
            'ownerReferences': [{'apiVersion': 'v1', 'kind': 'Pod', 'name': 'reviewed-pod', 'uid': POD_UID}]},
            'data': payload, **({'immutable': True} if sealed else {})})
    inventory = dict(nodeName='qa-node', nodeUid=NODE_UID, nodeResourceVersion='20', evidenceSha256='b' * 64,
        devices=[dict(index=i, gpuUuid='GPU-00000000-0000-4000-8000-' + str(i + 6).zfill(12), physicalGpuMemoryMiB='81920') for i in range(8)])
    record = dict(pod=pod, workflow=workflow, node=node, nodeInventory=inventory, device=device, configMaps=maps)
    registry = dict(schemaVersion=1, namespace=NS, bindingWriters=[ACTOR], cleanupWriters=[COORDINATOR],
                    sealWriter=COORDINATOR, records=[record])
    objects = {('pods', NS, pod['metadata']['name']): pod,
               ('workflows', NS, workflow['metadata']['name']): workflow,
               ('nodes', '', node['metadata']['name']): node,
               **{('configmaps', NS, cm['metadata']['name']): cm for cm in maps}}
    return copy.deepcopy(registry), objects


def review(resource='pods', operation='CREATE', subresource='binding', obj=None, old=None, actor=ACTOR):
    if obj is None and resource == 'pods':
        obj = {'apiVersion': 'v1', 'kind': 'Binding', 'metadata': {
            'namespace': NS, 'name': 'reviewed-pod', 'uid': POD_UID, 'resourceVersion': '10'},
            'target': {'apiVersion': 'v1', 'kind': 'Node', 'name': 'qa-node'}}
    name = (obj or old)['metadata']['name']
    request = dict(uid='admission-review-id', namespace=NS, name=name, operation=operation,
                   resource=dict(group='', version='v1', resource=resource), subResource=subresource,
                   userInfo={'username': actor}, object=obj, oldObject=old)
    if operation == 'DELETE':
        request['options'] = {'preconditions': {k: old['metadata'][k] for k in ('uid', 'resourceVersion')}}
    return dict(apiVersion='admission.k8s.io/v1', kind='AdmissionReview', request=request)


class FenceTests(unittest.TestCase):
    def setUp(self):
        self.registry, self.objects = fixture()
        self.reads = []

    def read(self, resource, namespace, name):
        self.reads.append((resource, namespace, name))
        return copy.deepcopy(self.objects.get((resource, namespace, name)))

    def allowed(self, request):
        return fence.authorize(request, self.registry, self.read)['response']['allowed']

    def test_exact_final_pod_complete_immutable_generations_allow_binding(self):
        self.assertTrue(self.allowed(review()))
        self.assertGreaterEqual(self.reads.count(('pods', NS, 'reviewed-pod')), 2)

    def test_termination_blocks_binding_and_cleanup_until_absence(self):
        self.objects['pods', NS, 'reviewed-pod']['metadata']['deletionTimestamp'] = '2026-10-08T12:00:00Z'
        self.assertFalse(self.allowed(review()))
        cm = self.objects['configmaps', NS, CAP]
        deletion = review('configmaps', 'DELETE', '', obj=None, old=cm, actor=COORDINATOR)
        self.assertFalse(self.allowed(deletion))
        del self.objects['pods', NS, 'reviewed-pod']
        self.assertTrue(self.allowed(deletion))

    def test_recreated_named_pod_cannot_bind_original_generation(self):
        self.objects['pods', NS, 'reviewed-pod']['metadata']['uid'] = OWNER_UID
        self.assertFalse(self.allowed(review()))

    def test_missing_binding_uid_precondition_denies(self):
        request = review()
        del request['request']['object']['metadata']['uid']
        self.assertFalse(self.allowed(request))

    def test_binding_metadata_merge_and_stale_pod_rv_are_denied(self):
        for field, value in [('annotations', {'gpu-memory': '20480'}), ('labels', {'forged': 'true'}), ('resourceVersion', '9')]:
            request = review()
            request['request']['object']['metadata'][field] = value
            with self.subTest(field=field): self.assertFalse(self.allowed(request))

    def test_full_actual_final_executable_contract_is_pinned(self):
        self.objects['pods', NS, 'reviewed-pod']['spec']['containers'][0]['command'] = ['unauthorized-command']
        self.assertFalse(self.allowed(review()))

    def test_old_generation_cleanup_can_follow_name_recreation_but_api_errors_deny(self):
        self.objects['pods', NS, 'reviewed-pod']['metadata']['uid'] = OWNER_UID
        request = review('configmaps', 'DELETE', '', obj=None, old=self.objects['configmaps', NS, CAP], actor=COORDINATOR)
        self.assertTrue(self.allowed(request))
        def read(resource, namespace, name):
            if resource == 'pods': raise OSError('Cannot confirm absence')
            return self.read(resource, namespace, name)
        self.assertFalse(fence.authorize(request, self.registry, read)['response']['allowed'])

    def test_missing_partial_recreated_and_mutable_maps_deny(self):
        for change in ('missing', 'partial', 'recreated', 'mutable', 'version', 'owner'):
            self.registry, self.objects = fixture()
            cm = self.objects['configmaps', NS, CAP]
            if change == 'missing': del self.objects['configmaps', NS, CAP]
            elif change == 'partial': del cm['data']['GPU_PORTION']
            elif change == 'recreated': cm['metadata']['uid'] = OWNER_UID
            elif change == 'mutable': cm.pop('immutable')
            elif change == 'version': cm['metadata']['resourceVersion'] = '31'
            else: cm['metadata']['ownerReferences'][0]['uid'] = OWNER_UID
            with self.subTest(change=change): self.assertFalse(self.allowed(review()))

    def test_wrong_parent_and_stale_node_generation_deny(self):
        for key in (('workflows', NS, 'reviewed-workflow'), ('nodes', '', 'qa-node')):
            self.registry, self.objects = fixture()
            self.objects[key]['metadata']['uid'] = CAP_UID
            with self.subTest(key=key): self.assertFalse(self.allowed(review()))
        self.registry, self.objects = fixture()
        self.objects['nodes', '', 'qa-node']['metadata']['resourceVersion'] = '21'
        self.assertFalse(self.allowed(review()))

    def test_actual_prefix_is_derived_from_injected_references_not_annotation(self):
        self.objects['pods', NS, 'reviewed-pod']['spec']['containers'][0]['env'][0]['valueFrom']['configMapKeyRef']['name'] = 'forged-prefix-0'
        self.assertFalse(self.allowed(review()))

    def test_wrong_device_or_quota_approval_is_invalid(self):
        for field, value in [('gpuUuid', 'GPU-not-a-uuid'), ('gpuUuid', 'GPU-00000000-0000-4000-8000-000000000007'), ('gpuPortion', '0.9'), ('physicalGpuMemoryMiB', '90000')]:
            self.registry, self.objects = fixture()
            self.registry['records'][0]['device'][field] = value
            with self.subTest(field=field): self.assertFalse(self.allowed(review()))

    def test_partial_inventory_and_stale_inventory_receipts_deny(self):
        for change in ('partial', 'stale'):
            self.registry, self.objects = fixture()
            inventory = self.registry['records'][0]['nodeInventory']
            if change == 'partial': inventory['devices'].pop()
            else: inventory['nodeResourceVersion'] = '19'
            with self.subTest(change=change): self.assertFalse(self.allowed(review()))

    def test_malformed_review_fails_closed(self):
        for value in ({'request': None}, {'request': []}, []):
            with self.subTest(value=value):
                self.assertFalse(fence.authorize(value, self.registry, self.read)['response']['allowed'])

    def test_pod_disappearing_during_binding_lookups_denies(self):
        calls = 0
        def read(resource, namespace, name):
            nonlocal calls
            if resource == 'pods':
                calls += 1
                if calls == 2: return None
            return self.read(resource, namespace, name)
        self.assertFalse(fence.authorize(review(), self.registry, read)['response']['allowed'])

    def test_cleanup_requires_uid_and_resource_version_preconditions(self):
        del self.objects['pods', NS, 'reviewed-pod']
        request = review('configmaps', 'DELETE', '', obj=None, old=self.objects['configmaps', NS, CAP], actor=COORDINATOR)
        for field in ('uid', 'resourceVersion'):
            changed = copy.deepcopy(request)
            del changed['request']['options']['preconditions'][field]
            with self.subTest(field=field): self.assertFalse(self.allowed(changed))
        self.assertTrue(self.allowed(request))

    def test_live_pod_freezes_delete_data_and_owner_even_for_trusted_actor(self):
        cm = self.objects['configmaps', NS, CAP]
        self.assertFalse(self.allowed(review('configmaps', 'DELETE', '', obj=None, old=cm, actor=COORDINATOR)))
        for field in ('data', 'owner'):
            changed = copy.deepcopy(cm)
            if field == 'data': changed['data']['GPU_PORTION'] = '1'
            else: changed['metadata']['ownerReferences'][0]['uid'] = OWNER_UID
            with self.subTest(field=field):
                self.assertFalse(self.allowed(review('configmaps', 'UPDATE', '', obj=changed, old=cm, actor=COORDINATOR)))

    def test_missing_registry_unauthorized_actor_and_api_errors_fail_closed(self):
        self.assertFalse(self.allowed(review(actor='unreviewed')))
        self.registry['records'] = []
        self.assertFalse(self.allowed(review()))
        self.registry, self.objects = fixture()
        def failure(*args): raise TimeoutError('API timeout')
        response = fence.authorize(review(), self.registry, failure)
        self.assertFalse(response['response']['allowed'])
        self.assertEqual(response['response']['uid'], 'admission-review-id')

    def test_node_window_blocks_deletion_and_relevant_mutation(self):
        node = self.objects['nodes', '', 'qa-node']
        request = review('nodes', 'DELETE', '', obj=None, old=node, actor=COORDINATOR)
        request['request']['namespace'] = ''
        self.assertFalse(self.allowed(request))
        changed = copy.deepcopy(node)
        changed['metadata']['labels']['nvidia.com/gpu.memory'] = '90000'
        request = review('nodes', 'UPDATE', '', obj=changed, old=node, actor=COORDINATOR)
        request['request']['namespace'] = ''
        self.assertFalse(self.allowed(request))


if __name__ == '__main__': unittest.main()

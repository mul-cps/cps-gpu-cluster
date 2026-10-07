"""Adversarial execution of literal quota-policy CEL with synthetic requests."""
import copy
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cel_evaluate
import quota_policy as quota

NAMESPACE = 'cps-dynamic-admission-review'
WRITER = 'system:serviceaccount:kai-scheduler:kai-binder'
POD_UID = '11111111-2222-3333-4444-555555555555'
CM_UID = '66666666-7777-8888-9999-aaaaaaaaaaaa'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
BASE = {'namespace': NAMESPACE, 'name': 'reviewed-abcdefg-shared-gpu-0', 'type': 'capabilities',
    'podName': 'reviewed-pod', 'podUid': POD_UID, 'gpuUuid': GPU, 'visibleDevices': GPU,
    'physicalGpuMemoryMiB': '40960',
    'gpuPortion': '0.13', 'runaiNumOfGpus': '0.13', 'cudaDeviceMemoryLimit': '5324m'}
EVAR = {**BASE, 'name': BASE['name'] + '-evar', 'type': 'evar'}
STAGES = [{}, {'NVIDIA_VISIBLE_DEVICES': GPU},
    {'NVIDIA_VISIBLE_DEVICES': GPU, 'GPU_PORTION': '0.13', 'RUNAI_NUM_OF_GPUS': '0.13'},
    {'NVIDIA_VISIBLE_DEVICES': GPU, 'GPU_PORTION': '0.13', 'RUNAI_NUM_OF_GPUS': '0.13',
     'CUDA_DEVICE_MEMORY_LIMIT': '5324m'}]


def configmap(stage=0, *, evar=False, absent_data=False):
    result = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {
        'name': EVAR['name'] if evar else BASE['name'], 'namespace': NAMESPACE, 'uid': CM_UID,
        'ownerReferences': [{'apiVersion': 'v1', 'kind': 'Pod', 'name': BASE['podName'], 'uid': POD_UID}]}}
    if not absent_data:
        result['data'] = {} if evar else copy.deepcopy(STAGES[stage])
    return result


def inputs(operation, value, old=None, *, writer=WRITER, params=None):
    return {'request': {'operation': operation, 'namespace': NAMESPACE,
        'userInfo': {'username': writer}}, 'object': value, 'oldObject': old,
        'params': params or quota.build(writers=[WRITER], records=[BASE, EVAR])['items'][1]}


class QuotaPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec('celpy') is None:
            raise RuntimeError('Use the actual cached CEL venv; no policy-mirror fallback')
        cls.policy = quota.build(writers=[WRITER], records=[BASE, EVAR])['items'][2]

    def evaluate(self, request, *, policy=None):
        return cel_evaluate.evaluate_policy(policy or self.policy, request)

    def assert_accepted(self, request):
        report = self.evaluate(request)
        self.assertTrue(report['allExpressionsTrue'], json.dumps([record for record in
            report['expressions'] if 'failure' in record], indent=2))
        self.assertTrue(report['compiled'])
        self.assertTrue(report['evaluated'])

    def assert_denied(self, request):
        report = self.evaluate(request)
        self.assertFalse(report['allExpressionsTrue'])
        self.assertTrue(report['compiled'])

    def test_manifest_is_separate_bounded_and_defaults_deny(self):
        manifest = quota.build()
        self.assertEqual([item['kind'] for item in manifest['items']], [
            'CustomResourceDefinition', 'DynamicGpuQuotaPolicy', 'ValidatingAdmissionPolicy',
            'ValidatingAdmissionPolicyBinding'])
        crd, params, policy, binding = manifest['items']
        self.assertEqual(params['writers'], [])
        self.assertEqual(params['records'], [])
        self.assertEqual(policy['spec']['failurePolicy'], 'Fail')
        self.assertNotIn('matchConditions', policy['spec'])
        self.assertEqual(policy['spec']['matchConstraints']['resourceRules'][0]['resources'], ['configmaps'])
        self.assertEqual(policy['spec']['matchConstraints']['resourceRules'][0]['operations'], ['CREATE', 'UPDATE', 'DELETE'])
        self.assertNotIn('objectSelector', policy['spec']['matchConstraints'])
        self.assertEqual(binding['spec']['validationActions'], ['Deny'])
        self.assertEqual(binding['spec']['paramRef']['parameterNotFoundAction'], 'Deny')
        self.assertTrue(all(item['metadata']['annotations']['compute.cps.unileoben.ac.at/qualification-state'] ==
                            'disabled-offline-candidate' for item in manifest['items']))
        self.assertEqual(crd['spec']['scope'], 'Namespaced')
        for operation in ('CREATE', 'UPDATE', 'DELETE'):
            value = configmap()
            request = inputs(operation, None if operation == 'DELETE' else value,
                             None if operation == 'CREATE' else configmap(), params=params)
            self.assertFalse(self.evaluate(request, policy=policy)['allExpressionsTrue'])

    def test_empty_create_absent_or_empty_data_for_both_reviewed_maps(self):
        for evar in (False, True):
            for absent in (False, True):
                with self.subTest(evar=evar, absent=absent):
                    self.assert_accepted(inputs('CREATE', configmap(evar=evar, absent_data=absent)))
        for stage in (1, 2, 3):
            self.assert_denied(inputs('CREATE', configmap(stage)))

    def test_every_observed_stage_transition_and_same_stage_retry(self):
        for old_stage in range(4):
            for new_stage in range(4):
                with self.subTest(old=old_stage, new=new_stage):
                    request = inputs('UPDATE', configmap(new_stage), configmap(old_stage))
                    if old_stage <= new_stage <= old_stage + 1:
                        self.assert_accepted(request)
                    else:
                        self.assert_denied(request)
        self.assert_accepted(inputs('UPDATE', configmap(1), configmap(absent_data=True)))
        self.assert_accepted(inputs('UPDATE', configmap(absent_data=True), configmap()))

    def test_source_empty_same_owner_upsert_preserves_populated_data(self):
        # The reviewed Go branch loops over the empty desired map, then patches
        # existingCm.DeepCopy(): the admission request remains the SAME stage.
        for stage in (1, 2, 3):
            self.assert_accepted(inputs('UPDATE', configmap(stage), configmap(stage)))
            self.assert_denied(inputs('UPDATE', configmap(), configmap(stage)))

    def test_evar_never_acquires_environment_values(self):
        self.assert_accepted(inputs('UPDATE', configmap(evar=True), configmap(evar=True)))
        self.assert_accepted(inputs('UPDATE', configmap(evar=True, absent_data=True), configmap(evar=True)))
        for data in ({'NVIDIA_VISIBLE_DEVICES': GPU}, {'LD_PRELOAD': '/unsafe.so'}, {'GPU_PORTION': '0.13'}):
            value = configmap(evar=True);value['data'] = data
            self.assert_denied(inputs('UPDATE', value, configmap(evar=True)))

    def test_unknown_actor_record_namespace_and_labels_do_not_authorize(self):
        for writer in ('system:serviceaccount:cps-workflows:cps-workflow', 'bjoern', 'system:anonymous',
                       'system:serviceaccount:kai-scheduler:lookalike-binder'):
            for operation in ('CREATE', 'UPDATE', 'DELETE'):
                with self.subTest(writer=writer, operation=operation):
                    value = configmap()
                    self.assert_denied(inputs(operation, None if operation == 'DELETE' else value,
                        None if operation == 'CREATE' else configmap(), writer=writer))
        value = configmap();value['metadata']['name'] = 'unregistered-quota'
        value['metadata']['labels'] = {'compute.cps.unileoben.ac.at/qualification': 'trusted-operator'}
        self.assert_denied(inputs('CREATE', value))
        request = inputs('CREATE', configmap());request['request']['namespace'] = 'cps-workflows'
        self.assert_denied(request)
        value = configmap();value['metadata']['namespace'] = 'cps-workflows'
        self.assert_denied(inputs('CREATE', value))
        request = inputs('CREATE', configmap());request['request']['userInfo'] = {}
        self.assert_denied(request)

    def test_owner_identity_flags_and_count_are_exact(self):
        changes = [lambda value: value['metadata'].pop('ownerReferences'),
            lambda value: value['metadata'].update(ownerReferences=[]),
            lambda value: value['metadata']['ownerReferences'].append(copy.deepcopy(value['metadata']['ownerReferences'][0])),
            lambda value: value['metadata']['ownerReferences'][0].update(uid=CM_UID),
            lambda value: value['metadata']['ownerReferences'][0].update(name='other-pod'),
            lambda value: value['metadata']['ownerReferences'][0].update(kind='Job'),
            lambda value: value['metadata']['ownerReferences'][0].update(apiVersion='apps/v1'),
            lambda value: value['metadata']['ownerReferences'][0].update(controller=True),
            lambda value: value['metadata']['ownerReferences'][0].update(blockOwnerDeletion=True)]
        for change in changes:
            with self.subTest(change=change):
                value = configmap();change(value)
                self.assert_denied(inputs('CREATE', value))
                self.assert_denied(inputs('DELETE', None, value))
        value = configmap();value['metadata']['ownerReferences'][0].update(controller=False, blockOwnerDeletion=False)
        self.assert_accepted(inputs('CREATE', value))

    def test_wrong_device_portions_quota_keys_binary_and_immutable_denied(self):
        changes = [lambda value: value['data'].update(NVIDIA_VISIBLE_DEVICES='GPU-' + CM_UID),
            lambda value: value['data'].update(GPU_PORTION='1'),
            lambda value: value['data'].update(RUNAI_NUM_OF_GPUS='1'),
            lambda value: value['data'].update(CUDA_DEVICE_MEMORY_LIMIT='40960m'),
            lambda value: value['data'].update(LD_PRELOAD='/unsafe.so'),
            lambda value: value['data'].update(**{'CUDA_DEVICE_MEMORY_LIMIT_0': '40960m'}),
            lambda value: value['data'].update(**{'RUNAI-VISIBLE-DEVICES': GPU}),
            lambda value: value.update(binaryData={'hidden': 'YQ=='}),
            lambda value: value.update(binaryData={}),
            lambda value: value.update(immutable=True), lambda value: value.update(immutable=False),
            lambda value: value['data'].pop('GPU_PORTION')]
        for change in changes:
            with self.subTest(change=change):
                value = configmap(3);change(value)
                self.assert_denied(inputs('UPDATE', value, configmap(2)))

    def test_update_pins_configmap_uid_name_namespace_and_owner_refs(self):
        changes = [lambda value: value['metadata'].pop('uid'),
            lambda value: value['metadata'].update(uid='bbbbbbbb-cccc-dddd-eeee-ffffffffffff'),
            lambda value: value['metadata'].update(name=EVAR['name']),
            lambda value: value['metadata'].update(namespace='other'),
            lambda value: value['metadata']['ownerReferences'][0].update(controller=False)]
        for change in changes:
            with self.subTest(change=change):
                value = configmap(1);change(value)
                self.assert_denied(inputs('UPDATE', value, configmap()))
        for uid in ('not-a-uid', '', None):
            old = configmap();old['metadata']['uid'] = uid
            value = configmap(1);value['metadata']['uid'] = uid
            self.assert_denied(inputs('UPDATE', value, old))
        self.assert_denied(inputs('UPDATE', configmap(1), None))
        old = configmap();old['data'] = {'unreviewed': 'value'}
        self.assert_denied(inputs('UPDATE', configmap(1), old))

    def test_registered_binder_rollback_delete_uses_old_object(self):
        for stage in range(4):
            self.assert_accepted(inputs('DELETE', None, configmap(stage)))
        self.assert_accepted(inputs('DELETE', None, configmap(evar=True)))
        for mutate in (lambda value: value['metadata'].pop('uid'),
                       lambda value: value['metadata'].update(uid='bad'),
                       lambda value: value['metadata'].update(name='unknown'),
                       lambda value: value['metadata'].update(namespace='other')):
            value = configmap(3);mutate(value)
            self.assert_denied(inputs('DELETE', None, value))
        self.assert_denied(inputs('DELETE', configmap(), None))
        self.assert_denied(inputs('DELETE', None, configmap(), writer='system:serviceaccount:kube-system:generic-garbage-collector'))

    def test_optional_independent_configmap_uid_pin(self):
        manifest = quota.build(writers=[WRITER], records=[{**BASE, 'cmUid': CM_UID}, EVAR])
        params = manifest['items'][1]
        self.assert_accepted(inputs('UPDATE', configmap(1), configmap(), params=params))
        self.assert_accepted(inputs('DELETE', None, configmap(3), params=params))
        self.assert_denied(inputs('CREATE', configmap(), params=params))
        other = copy.deepcopy(params);other['records'][0]['cmUid'] = POD_UID
        self.assert_denied(inputs('UPDATE', configmap(1), configmap(), params=other))
        self.assert_denied(inputs('DELETE', None, configmap(), params=other))

    def test_source_uuid_and_cdi_selections_are_exact(self):
        prefix = 'k8s.device-plugin.nvidia.com/gpu='
        for visible in (GPU, prefix + GPU, prefix + '0', prefix + '31'):
            with self.subTest(visible=visible):
                record = {**BASE, 'visibleDevices': visible}
                manifest = quota.build(writers=[WRITER], records=[record, {**EVAR, 'visibleDevices': visible}])
                params, policy = manifest['items'][1:3]
                old = configmap()
                for stage in (1, 2, 3):
                    value = configmap(stage)
                    value['data']['NVIDIA_VISIBLE_DEVICES'] = visible
                    self.assertTrue(self.evaluate(inputs('UPDATE', value, old, params=params),
                                                  policy=policy)['allExpressionsTrue'])
                    old = value
                other = configmap(1)
                other['data']['NVIDIA_VISIBLE_DEVICES'] = prefix + ('1' if visible != prefix + '1' else '2')
                self.assertFalse(self.evaluate(inputs('UPDATE', other, configmap(), params=params),
                                               policy=policy)['allExpressionsTrue'])
                for forbidden in ('all', 'void', prefix + '0,' + prefix + '1', '/dev/nvidia0',
                                  prefix + '01', prefix + '32', prefix + '-1'):
                    value = configmap(1);value['data']['NVIDIA_VISIBLE_DEVICES'] = forbidden
                    self.assertFalse(self.evaluate(inputs('UPDATE', value, configmap(), params=params),
                                                   policy=policy)['allExpressionsTrue'])

    def test_renderer_requires_single_canonical_visible_selection(self):
        prefix = 'k8s.device-plugin.nvidia.com/gpu='
        invalid = ('all', 'void', '', GPU + ',' + GPU, prefix + '0,' + prefix + '1',
            '/dev/nvidia0', 'k8s.device-plugin.nvidia.com/gpu/0', prefix + '01', prefix + '32',
            prefix + '-1', prefix + ' 0', prefix + GPU + '/unsafe',
            'GPU-' + CM_UID, prefix + 'GPU-' + CM_UID)
        for visible in invalid:
            with self.subTest(visible=visible):
                with self.assertRaises(ValueError):
                    quota.build(records=[{**BASE, 'visibleDevices': visible}])
        without_selection = {key: value for key, value in BASE.items() if key != 'visibleDevices'}
        with self.assertRaises(ValueError):
            quota.build(records=[without_selection])
        crd = quota.build()['items'][0]
        fields = crd['spec']['versions'][0]['schema']['openAPIV3Schema']['properties']['records']['items']
        self.assertIn('visibleDevices', fields['required'])
        self.assertTrue(any('independent review' in value for value in quota.LIMITATIONS))

    def test_renderer_rejects_unbounded_or_ambiguous_registry(self):
        for namespace in ('cps-workflows', 'jupyterhub', 'cps-dynamic-admission-', 'x' * 64):
            with self.assertRaises(ValueError):quota.build(namespace=namespace)
        for writers in ([WRITER, WRITER], ['admin'], [WRITER] * 9):
            with self.assertRaises(ValueError):quota.build(writers=writers)
        changes = [lambda value: value.update(type='other'), lambda value: value.update(namespace='other'),
            lambda value: value.update(podUid='unknown'), lambda value: value.update(gpuUuid='MIG-' + POD_UID),
            lambda value: value.update(gpuPortion='0', runaiNumOfGpus='0'),
            lambda value: value.update(gpuPortion='1.1', runaiNumOfGpus='1.1'),
            lambda value: value.update(runaiNumOfGpus='0.25'), lambda value: value.update(cudaDeviceMemoryLimit='40961m'),
            lambda value: value.update(cudaDeviceMemoryLimit='0m'), lambda value: value.update(cmUid='bad'),
            lambda value: value.update(unreviewed='anything')]
        for change in changes:
            value = copy.deepcopy(BASE);change(value)
            with self.subTest(record=value):
                with self.assertRaises(ValueError):quota.build(writers=[WRITER], records=[value])
        with self.assertRaises(ValueError):quota.build(records=[BASE, BASE])
        with self.assertRaises(ValueError):quota.build(records=[BASE] * 65)

    def test_crd_quota_pattern_is_bounded_without_extra_cel_extensions(self):
        crd = quota.build()['items'][0]
        record = crd['spec']['versions'][0]['schema']['openAPIV3Schema']['properties']['records']['items']
        pattern = record['properties']['cudaDeviceMemoryLimit']['pattern']
        for value in ('1m', '9999m', '10000m', '39999m', '40000m', '40899m', '40959m', '40960m'):
            self.assertIsNotNone(re.fullmatch(pattern, value))
        for value in ('0m', '01m', '40961m', '50000m', '40960', '-1m'):
            self.assertIsNone(re.fullmatch(pattern, value))
        self.assertNotIn('substring', json.dumps(record))

    def test_source_float64_quota_for_each_received_portion(self):
        for portion, limit in (('0.13', '5324m'), ('0.25', '10240m'), ('0.5', '20480m')):
            with self.subTest(portion=portion, limit=limit):
                fields = {'gpuPortion': portion, 'runaiNumOfGpus': portion, 'cudaDeviceMemoryLimit': limit}
                manifest = quota.build(writers=[WRITER], records=[{**BASE, **fields}, {**EVAR, **fields}])
                params, policy = manifest['items'][1:3]
                old = configmap(2)
                old['data'].update(GPU_PORTION=portion, RUNAI_NUM_OF_GPUS=portion)
                value = copy.deepcopy(old);value['data']['CUDA_DEVICE_MEMORY_LIMIT'] = limit
                report = self.evaluate(inputs('UPDATE', value, old, params=params), policy=policy)
                self.assertTrue(report['compiled'])
                self.assertTrue(report['allExpressionsTrue'], json.dumps(report))
                for wrong in ('5120m', str(int(limit[:-1]) + 1) + 'm'):
                    if wrong == limit:
                        continue
                    with self.assertRaises(ValueError):
                        quota.build(records=[{**BASE, **fields, 'cudaDeviceMemoryLimit': wrong}])
                    unsafe = copy.deepcopy(params)
                    unsafe['records'][0]['cudaDeviceMemoryLimit'] = wrong
                    value['data']['CUDA_DEVICE_MEMORY_LIMIT'] = wrong
                    self.assertFalse(self.evaluate(inputs('UPDATE', value, old, params=unsafe),
                                                   policy=policy)['allExpressionsTrue'])

    def test_advertised_memory_is_mandatory_canonical_and_bounded(self):
        crd = quota.build()['items'][0]
        schema = crd['spec']['versions'][0]['schema']['openAPIV3Schema']['properties']['records']['items']
        self.assertIn('physicalGpuMemoryMiB', schema['required'])
        pattern = schema['properties']['physicalGpuMemoryMiB']['pattern']
        for memory in ('1', '40960', '99999', '100000', '129999', '130000', '130999', '131000', '131069', '131070', '131072'):
            self.assertIsNotNone(re.fullmatch(pattern, memory))
        for memory in ('0', '01', '-1', '+40960', '40960.0', '4e4', ' 40960', '131073', '140000', '999999', '', None, 40960):
            with self.subTest(memory=memory):
                with self.assertRaises(ValueError):
                    quota.build(records=[{**BASE, 'physicalGpuMemoryMiB': memory}])
                if isinstance(memory, str):
                    self.assertIsNone(re.fullmatch(pattern, memory))
        missing = {key: value for key, value in BASE.items() if key != 'physicalGpuMemoryMiB'}
        with self.assertRaises(ValueError):
            quota.build(records=[missing])
        # The same quota is incompatible with a changed advertised memory label.
        with self.assertRaises(ValueError):
            quota.build(records=[{**BASE, 'physicalGpuMemoryMiB': '40000'}])
        bad_params = inputs('CREATE', configmap())['params']
        bad_params['records'][0].pop('physicalGpuMemoryMiB')
        self.assert_denied(inputs('CREATE', configmap(), params=bad_params))

    def test_crd_crosscheck_executes_literal_cel_not_a_python_mirror(self):
        from celpy import Environment, celtypes
        from celpy.adapter import json_to_cel
        crd = quota.build()['items'][0]
        schema = crd['spec']['versions'][0]['schema']['openAPIV3Schema']['properties']['records']['items']
        expressions = [value['rule'] for value in schema['x-kubernetes-validations']]
        expression = next(value for value in expressions if 'physicalGpuMemoryMiB' in value)
        env = Environment()
        program = env.program(env.compile(expression))
        # Record the engine discrepancy explicitly rather than adapting its
        # conversion function or pretending this is Kubernetes conformance.
        rounded = env.program(env.compile('int(5324.8)')).evaluate({})
        self.assertEqual(rounded, 5325)
        self.assertTrue(any('rounds int(double)' in text for text in quota.LIMITATIONS))
        for portion, limit in (('0.13', '5324m'), ('0.25', '10240m'), ('0.5', '20480m')):
            record = {**BASE, 'gpuPortion': portion, 'runaiNumOfGpus': portion, 'cudaDeviceMemoryLimit': limit}
            self.assertIsInstance(program.evaluate(json_to_cel({'self': record})), celtypes.BoolType)
            self.assertTrue(program.evaluate(json_to_cel({'self': record})))
            record['cudaDeviceMemoryLimit'] = str(int(limit[:-1]) + 1) + 'm'
            self.assertFalse(program.evaluate(json_to_cel({'self': record})))


if __name__ == '__main__':
    unittest.main()

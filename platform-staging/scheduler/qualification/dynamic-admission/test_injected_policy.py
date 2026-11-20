"""Literal CEL tests on declared source-inferred KAI shapes, not live Pods."""
import copy
import unittest

import cel_evaluate
import compiled_fixtures
import injected_policy

ACTOR = 'system:serviceaccount:offline:declared-argo-controller'
BINDER = 'system:serviceaccount:offline:declared-binder'
EXECUTOR = 'registry.invalid/executor@sha256:' + '2' * 64


def declared_injection(pod, record):
    """Synthetic JSON declaration; neither upstream Go mutator is executed."""
    pod = copy.deepcopy(pod)
    metadata, spec = pod['metadata'], pod['spec']
    metadata['annotations'][injected_policy.PREFIX_ANNOTATION] = record['configMapPrefix']
    metadata['annotations']['nvidia.com/container.main.gpu-memory.request'] = str(int(record['gpuMemory']) // 1024) + 'Gi'
    metadata['uid'] = '11111111-1111-1111-1111-111111111111'
    spec['runtimeClassName'] = 'nvidia'
    if record['mainIndex'] == 1:
        security = copy.deepcopy(spec['containers'][0]['securityContext'])
        security.update(runAsUser=10001, runAsGroup=10001, readOnlyRootFilesystem=True)
        spec['containers'].insert(0, {'name': 'wait', 'image': EXECUTOR,
            'command': ['argoexec','wait','--loglevel','info','--log-format','text','--gloglevel','0'],
            'securityContext': security,
            'resources': {'requests': {'cpu': '100m', 'memory': '64Mi'}, 'limits': {'cpu': '1', 'memory': '256Mi'}}})
    main = spec['containers'][record['mainIndex']]
    for key in injected_policy.CAPABILITY_ENV:
        source = {'name': record['capabilitiesName'], 'key': key}
        if key == 'CUDA_DEVICE_MEMORY_LIMIT':
            source['optional'] = True
        main['env'].append({'name': key, 'valueFrom': {'configMapKeyRef': source}})
    main['env'] += [{'name': 'POD_UID', 'valueFrom': {'fieldRef': {'apiVersion': 'v1', 'fieldPath': 'metadata.uid'}}},
                    {'name': 'CONTAINER_NAME', 'value': 'main'},
                    {'name': 'CONTAINER_VGPU_MOUNT', 'value': '/usr/local/vgpu'}]
    main['envFrom'] = [{'configMapRef': {'name': record['evarName'], 'optional': False}}]
    main['volumeMounts'] += copy.deepcopy(injected_policy.ISOLATOR_MOUNTS)
    spec['volumes'] += [{'name': record['capabilitiesVolume'], 'configMap': {'name': record['capabilitiesName']}}]
    spec['volumes'] += [{'name': name, 'hostPath': {'path': path, 'type': 'DirectoryOrCreate'}}
                        for name, path in injected_policy.ISOLATOR_HOSTS.items()]
    return pod


class InjectedAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = compiled_fixtures.generate()
        cls.owners = [{'name': item['compiledWorkflow']['metadata']['name'],
                       'uid': item['declaredControllerPod']['object']['metadata']['ownerReferences'][0]['uid']}
                      for item in cls.fixtures['fixtures'].values()]
        cls.bundles = {}
        for index in (0, 1):
            records = [{'name': value['declaredControllerPod']['object']['metadata']['name'],
                        'ownerUid': owner['uid'],
                        'configMapPrefix': owner['name'][:33].rstrip('.-') + '-bcdfgh2-shared-gpu',
                        'mainIndex': index, 'gpuMemory': str(value['profileGiB'] * 1024)}
                       for owner, value in zip(cls.owners, cls.fixtures['fixtures'].values())]
            cls.bundles[index] = injected_policy.build(executor_image=EXECUTOR, owners=cls.owners,
                create_creators=[ACTOR], update_creators=[BINDER], reviewed_pods=records)

    def inputs(self, profile='batch-shared-5', index=0, operation='CREATE'):
        bundle = self.bundles[index]
        item = self.fixtures['fixtures'][profile]
        record = next(record for record in bundle['items'][1]['reviewedPods']
                      if record['name'] == item['declaredControllerPod']['object']['metadata']['name'])
        pod = declared_injection(item['declaredControllerPod']['object'], record)
        return {'object': pod, 'params': copy.deepcopy(bundle['items'][1]),
            'request': {'namespace': compiled_fixtures.NAMESPACE, 'operation': operation,
                        'userInfo': {'username': ACTOR if operation == 'CREATE' else BINDER}},
            'oldObject': copy.deepcopy(pod) if operation == 'UPDATE' else None}

    def check(self, value, expected, index=0):
        result = cel_evaluate.evaluate_policy(self.bundles[index]['items'][2], value)
        errors = [(entry['stage'], entry['index'], entry.get('failure'), entry.get('errorType'))
                  for entry in result['expressions'] if entry.get('failure')]
        self.assertTrue(result['compiled'], errors)
        self.assertEqual(result['allExpressionsTrue'], expected, errors)
        return result

    def test_three_compiler_profiles_with_both_real_container_index_shapes(self):
        for index in (0, 1):
            for profile in self.fixtures['fixtures']:
                with self.subTest(index=index, profile=profile):
                    self.check(self.inputs(profile, index), True, index)

    def test_original_create_actor_is_required_not_the_injector_or_binder(self):
        for actor in (BINDER, 'system:serviceaccount:offline:resource-isolator', 'student'):
            value = self.inputs(); value['request']['userInfo']['username'] = actor
            result = self.check(value, False)
            self.assertTrue(next(entry for entry in result['expressions']
                                 if entry['stage'] == 'matchCondition')['resultBool'])
        for field in ('createCreators', 'owners', 'reviewedPods'):
            value = self.inputs(); value['params'][field] = []
            self.check(value, False)

    def test_api_omitempty_writable_mounts_accept_absent_or_false_only(self):
        value = self.inputs()
        mounts = value['object']['spec']['containers'][0]['volumeMounts']
        for mount in mounts:
            if mount.get('readOnly') is False:
                del mount['readOnly']
        self.check(value, True)
        value['object']['spec']['containers'][0]['volumeMounts'][-1]['readOnly'] = True
        self.check(value, False)

    def test_quota_name_index_optional_selector_and_duplicates_are_fenced(self):
        for name, change in (
            ('other-map', lambda c: c['env'][3]['valueFrom']['configMapKeyRef'].update(name='other-pod-shared-gpu-0')),
            ('optional-device', lambda c: c['env'][3]['valueFrom']['configMapKeyRef'].update(optional=True)),
            ('wrong-key', lambda c: c['env'][3]['valueFrom']['configMapKeyRef'].update(key='GPU_PORTION')),
            ('device-literal', lambda c: c['env'][3].update(value='all')),
            ('duplicate-env', lambda c: c['env'].append(copy.deepcopy(c['env'][3]))),
            ('loader', lambda c: c['env'].append({'name': 'ld_preload', 'value': '/evil.so'})),
            ('other-index-quota', lambda c: c['env'].append({'name': 'CUDA_DEVICE_MEMORY_LIMIT_1', 'value': '80G'})),
            ('other-envfrom', lambda c: c['envFrom'][0]['configMapRef'].update(name='other-evar')),
            ('envfrom-optional', lambda c: c['envFrom'][0]['configMapRef'].update(optional=True)),
            ('envfrom-prefix', lambda c: c['envFrom'][0].update(prefix='LD_')),
            ('metric-source', lambda c: c['env'][-3].update(valueFrom={'fieldRef': {'apiVersion': 'v1', 'fieldPath': 'metadata.name'}})),
            ('metric-root', lambda c: c['env'][-1].update(value='/tmp/evil')),
        ):
            with self.subTest(name=name):
                value = self.inputs(); change(value['object']['spec']['containers'][0]); self.check(value, False)
        for field, changed in [('name', 'other-pod'), ('namespace', 'cps-workflows')]:
            value = self.inputs(); value['object']['metadata'][field] = changed; self.check(value, False)
        value = self.inputs(); value['object']['metadata']['annotations'][injected_policy.PREFIX_ANNOTATION] = 'copied-shared-gpu'
        self.check(value, False)
        value = self.inputs(index=1); value['object']['spec']['containers'].reverse(); self.check(value, False, 1)

    def test_every_hostpath_and_mount_is_exact_and_executor_does_not_get_gpu(self):
        for name, change in (
            ('host-root', lambda p: p['volumes'][-1]['hostPath'].update(path='/')),
            ('host-type', lambda p: p['volumes'][-1]['hostPath'].update(type='Directory')),
            ('missing-host', lambda p: p['volumes'].pop()),
            ('other-quota-volume', lambda p: p['volumes'][-4]['configMap'].update(name='other-quota')),
            ('duplicate-volume', lambda p: p['volumes'].append(copy.deepcopy(p['volumes'][-1]))),
            ('preload-writable', lambda p: p['containers'][0]['volumeMounts'][-3].update(readOnly=False)),
            ('preload-file', lambda p: p['containers'][0]['volumeMounts'][-3].update(subPath='evil.so')),
            ('mount-shadow', lambda p: p['containers'][0]['volumeMounts'][-4].update(mountPath='/usr/local/bin')),
            ('mount-propagation', lambda p: p['containers'][0]['volumeMounts'][-1].update(mountPropagation='Bidirectional')),
            ('duplicate-mount', lambda p: p['containers'][0]['volumeMounts'].append(copy.deepcopy(p['containers'][0]['volumeMounts'][-1]))),
        ):
            with self.subTest(name=name):
                value = self.inputs(); change(value['object']['spec']); self.check(value, False)
        value = self.inputs(index=1)
        value['object']['spec']['containers'][0]['volumeMounts'] = [copy.deepcopy(injected_policy.ISOLATOR_MOUNTS[0])]
        self.check(value, False, 1)
        value = self.inputs(); value['object']['spec']['initContainers'][0]['volumeMounts'].append(copy.deepcopy(injected_policy.ISOLATOR_MOUNTS[0]))
        self.check(value, False)

    def test_nvfraction_normalization_injector_optout_and_wrong_targets_deny(self):
        for key, value in [('nvidia.com/container.main.gpu-memory.request', '80Gi'),
                           ('nvidia.com/container.wait.gpu-memory.request', '5Gi'),
                           ('kai-resource-isolator.io/inject', 'false')]:
            case = self.inputs(); case['object']['metadata']['annotations'][key] = value; self.check(case, False)
        value = self.inputs(); value['object']['spec']['runtimeClassName'] = 'other'; self.check(value, False)

    def test_source_binding_updates_work_but_executable_or_reference_replacement_deny(self):
        value = self.inputs(operation='UPDATE')
        value['object']['metadata'].setdefault('labels', {})['runai-gpu-group'] = 'source-reservation-group'
        value['object']['metadata']['annotations']['received-resource-type'] = 'Fraction'
        value['object']['spec']['nodeName'] = 'offline-qualified-node'
        self.check(value, True)
        for name, change in (
            ('command', lambda p: p['spec']['containers'][0].update(command=['sh'])),
            ('reference', lambda p: p['metadata']['annotations'].update({injected_policy.PREFIX_ANNOTATION: 'other'})),
            ('volume', lambda p: p['spec']['volumes'][0]['emptyDir'].update(sizeLimit='64Gi')),
            ('unknown-writer', lambda p: None),
        ):
            value = self.inputs(operation='UPDATE'); change(value['object'])
            if name == 'unknown-writer': value['request']['userInfo']['username'] = ACTOR
            self.check(value, False)

    def test_registration_names_prefixes_owner_and_container_index_are_not_guessed(self):
        original = {key: value for key, value in self.bundles[0]['items'][1]['reviewedPods'][0].items()
                    if key in ('name', 'ownerUid', 'configMapPrefix', 'mainIndex', 'gpuMemory')}
        for field, value in [('ownerUid', 'unregistered'), ('mainIndex', True), ('mainIndex', 2),
                             ('configMapPrefix', 'guessed-shared-gpu'), ('gpuMemory', '81920')]:
            record = {**original, field: value}
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                injected_policy.reviewed_records([record], self.owners)
        with self.assertRaises(ValueError):
            injected_policy.reviewed_records([original, original], self.owners)
        long_owner = {'name': 'a' * 32 + '.suffix', 'uid': original['ownerUid']}
        record = {**original, 'configMapPrefix': 'a' * 32 + '-bcdfgh2-shared-gpu'}
        self.assertTrue(injected_policy.reviewed_records([record], [long_owner]))


if __name__ == '__main__':
    unittest.main()

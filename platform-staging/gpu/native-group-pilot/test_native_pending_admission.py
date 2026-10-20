"""Actual SDK v2 pending publications through rendered CEL (CPU only).

The inline objects were captured from the real prepare/bind SDK test below,
removing only server-assigned UID/resourceVersion from ConfigMap metadata.
The Go evaluator is built from ./cel-evaluator with official CEL extensions;
this does not establish K3s typing, RBAC, propagation or live qualification.
"""
import copy
import hashlib
import json
import os
import subprocess
import unittest

import render
from test_node_agent import fixtures

GATEWAY = 'system:serviceaccount:cps-compute:cps-compute-controller'
POLICY = 'cps-native-gateway-pending-current-groups'
# Source test: test_current_group_actual_prepare_bind_and_accept_keeps_v1_wire.
SDK_CAPTURE = {'objects': {'allocation.json': {'apiVersion': 'v1',
                                 'data': {'allocation.json': (
                                     '{"approval_ref":{"data_sha256":"sha256:0a8ec528e62d8f528d74d625e7f901363bbd8d3a735a99f99e5eaf1ba9f'
                                     'e929a","name":"actual-node-approval","namespace":"cps-compute","policy_hash":"sha256:4215ee4774f78'
                                     '4b59b5f65104879d88c7ba42ce27e8074767dcf8697da837a8d","revision":"sha256:567a0ad9b3c878a428318c2055'
                                     '2059ac93fc603080a6aa0fd889943f043d67eb","uid":"44444444-4444-4444-8444-444444444444"},"attempt":"2'
                                     '2222222-2222-4222-8222-222222222222","bind_request":{"generation":1,"name":"request","namespace":"'
                                     'cit-jhub","resourceVersion":"20","spec_sha256":"656ec20fef8c1e9211cb66f8bf87ae53e232624422c48e1d87'
                                     '53a176a366e49e","uid":"f427475b-c169-4b13-907d-14106607656f"},"capacity":[{"cap_mib":10240,"pod_ui'
                                     'd":"11111111-1111-4111-8111-111111111111"}],"enrollment":{"document_sha256":"ca5049aa99515d2965bde'
                                     'f84a194fcb124c773ce2e3a640c669ae31105e8eac3","name":"cps-native-enrollment-3275305d78349c5bc9d1382'
                                     'bd99138d740603ef8","namespace":"cps-compute","resourceVersion":"10","uid":"5767094d-da2d-4ee8-b02d'
                                     '-87c03c52c2d5"},"epoch":{"boot_id":"209f8bc9-a478-48e4-925a-6e07ffa56f7a","driver_generation":"b10'
                                     '498fc-9153-4394-875a-ea7cfb498625","gpu_uuid":"GPU-16128952-b438-556a-00bb-93039ee24e56","node_uid'
                                     '":"3336cdd5-d245-436e-b57c-2f66c6dcaa41"},"intent":{"cap_mib":10240,"gpu_uuid":"GPU-16128952-b438-'
                                     '556a-00bb-93039ee24e56","name":"jupyter-group-10","namespace":"cit-jhub","node":"k3s-wk-gpu2","nod'
                                     'e_uid":"3336cdd5-d245-436e-b57c-2f66c6dcaa41","pod_uid":"11111111-1111-4111-8111-111111111111","po'
                                     'licy_hash":"sha256:4215ee4774f784b59b5f65104879d88c7ba42ce27e8074767dcf8697da837a8d","spec_sha256"'
                                     ':"23f7b6ee5b337cd9c19d9c863def4c307ec66d0f4bd64f9d7f8c06f14e33dc6c"},"kai_commit":"bdf434e5e9201cc'
                                     'cf4e05fad04d814363653f692","maps":[{"data_sha256":"664d18238ec45d224ca952d38511b1f9dc5f757995a3227'
                                     '5782faf0b6ee1299a","name":"cps-native-12f7587d57defce0d124e3b24c319be5-shared-gpu-0","namespace":"'
                                     'cit-jhub","owner":{"apiVersion":"v1","kind":"Pod","name":"jupyter-group-10","uid":"11111111-1111-4'
                                     '111-8111-111111111111"},"resourceVersion":"8","uid":"26b93d66-68ba-43e4-a744-d58d71fd9a3b"},{"data'
                                     '_sha256":"44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a","name":"cps-native-12f'
                                     '7587d57defce0d124e3b24c319be5-shared-gpu-0-evar","namespace":"cit-jhub","owner":{"apiVersion":"v1"'
                                     ',"kind":"Pod","name":"jupyter-group-10","uid":"11111111-1111-4111-8111-111111111111"},"resourceVer'
                                     'sion":"8","uid":"271d622a-201c-410a-96c9-f0aba98a38f3"}],"max_workspaces":2,"memory_budget_mib":15'
                                     '360,"node":{"name":"k3s-wk-gpu2","resourceVersion":"30","uid":"3336cdd5-d245-436e-b57c-2f66c6dcaa4'
                                     '1"},"node_configuration_ref":{"data_sha256":"sha256:04783ac5279527f948d7227ef564a7517fdcf5327ee6f6'
                                     'ed3f023b90abfc5efd","key":"config.json","name":"current-kai-config","namespace":"cps-compute","res'
                                     'ourceVersion":"31","uid":"1114d6c9-285f-45c3-bc3c-ba31b1eaba13"},"pending_spec_sha256":"7fb802d3f9'
                                     '2b711fa72ec10865ddf256c4ec9c2ff194d0ce74906afca3832d64","pod":{"metadata_sha256":"49aa6306e3dcc27b'
                                     'e25327be76c5ea7d86f581e9c6b64e5af9edf34931037cfc","name":"jupyter-group-10","namespace":"cit-jhub"'
                                     ',"resourceVersion":"102","uid":"11111111-1111-4111-8111-111111111111"},"profile":"interactive-shar'
                                     'ed-10","protocol":"cps-native-pending-allocation/v2","registry":{"document_sha256":"7db33d740c17e8'
                                     '6affa34375e9f1393d34fa25f64a3a808f6fceb4d22955829a","name":"cps-pending-registry-11111111-1111-411'
                                     '1-8111-111111111111","namespace":"cps-compute","resourceVersion":"10","uid":"1d4ee6a5-538e-493d-85'
                                     'c5-308ce4dd6126"},"state":"allocation-enrolled-before-bind"}'
                                 )},
                                 'immutable': True,
                                 'kind': 'ConfigMap',
                                 'metadata': {'name': 'cps-pending-allocation-11111111-1111-4111-8111-111111111111',
                                              'namespace': 'cps-compute'}},
             'registry.json': {'apiVersion': 'v1',
                               'data': {'registry.json': (
                                     '{"approval_ref":{"data_sha256":"sha256:0a8ec528e62d8f528d74d625e7f901363bbd8d3a735a99f99e5eaf1ba9f'
                                     'e929a","name":"actual-node-approval","namespace":"cps-compute","policy_hash":"sha256:4215ee4774f78'
                                     '4b59b5f65104879d88c7ba42ce27e8074767dcf8697da837a8d","revision":"sha256:567a0ad9b3c878a428318c2055'
                                     '2059ac93fc603080a6aa0fd889943f043d67eb","uid":"44444444-4444-4444-8444-444444444444"},"attempt":"2'
                                     '2222222-2222-4222-8222-222222222222","binding_id":"3275305d78349c5bc9d1382bd99138d740603ef874ef3fe'
                                     'fe6d3f338c31e","bound_spec_sha256":"23f7b6ee5b337cd9c19d9c863def4c307ec66d0f4bd64f9d7f8c06f14e33dc'
                                     '6c","capabilities_configmap":"cps-native-12f7587d57defce0d124e3b24c319be5-shared-gpu-0","container'
                                     '_index":0,"container_name":"notebook","env_configmap":"cps-native-12f7587d57defce0d124e3b24c319be5'
                                     '-shared-gpu-0-evar","epoch":{"boot_id":"209f8bc9-a478-48e4-925a-6e07ffa56f7a","driver_generation":'
                                     '"b10498fc-9153-4394-875a-ea7cfb498625","gpu_uuid":"GPU-16128952-b438-556a-00bb-93039ee24e56","node'
                                     '_uid":"3336cdd5-d245-436e-b57c-2f66c6dcaa41"},"gpu_uuid":"GPU-16128952-b438-556a-00bb-93039ee24e56'
                                     '","kai_commit":"bdf434e5e9201cccf4e05fad04d814363653f692","kind":"protected-pending-registry","nam'
                                     'e":"jupyter-group-10","namespace":"cit-jhub","node":"k3s-wk-gpu2","node_configuration_ref":{"data_'
                                     'sha256":"sha256:04783ac5279527f948d7227ef564a7517fdcf5327ee6f6ed3f023b90abfc5efd","key":"config.js'
                                     'on","name":"current-kai-config","namespace":"cps-compute","resourceVersion":"31","uid":"1114d6c9-2'
                                     '85f-45c3-bc3c-ba31b1eaba13"},"node_uid":"3336cdd5-d245-436e-b57c-2f66c6dcaa41","pending_spec_sha25'
                                     '6":"7fb802d3f92b711fa72ec10865ddf256c4ec9c2ff194d0ce74906afca3832d64","pod_uid":"11111111-1111-411'
                                     '1-8111-111111111111","policy_hash":"sha256:4215ee4774f784b59b5f65104879d88c7ba42ce27e8074767dcf869'
                                     '7da837a8d","profile":"interactive-shared-10","protocol":"cps-native-pending-allocation/v2"}'
                                 )},
                               'immutable': True,
                               'kind': 'ConfigMap',
                               'metadata': {'name': 'cps-pending-registry-11111111-1111-4111-8111-111111111111',
                                            'namespace': 'cps-compute'}}},
 'source_commit': '36b91d33da4508e54de74a900ee039cd01d14cb4',
 'source_sha256': {'src/cps_compute/native_scheduler_allocation.py': '34feb18690bbd263e64aa96327657d5a29eb2b29f091358eccf3e88a94b19dce',
                   'src/cps_compute/native_scheduler_coordinator.py': 'cc187397df88d03d65a34bec74d5e5cc3ec950828f63f18b1b1bb608cfaf54d2',
                   'src/cps_compute/native_scheduler_group_contract.py': 'c052735a84c730cd8c171f4013816574bf190e68ef0b4edb40a62479894eb1b8'}}

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


class PendingAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.config, _, _ = fixtures()
        self.config['authority_namespace'] = 'cps-compute'

    def bundle(self, enabled=True):
        return render.render(self.config, allow_pending_current_groups=enabled)

    def policies(self, enabled=True):
        return [p for p in self.bundle(enabled)['items'] if p['kind'] == 'ValidatingAdmissionPolicy']

    def evaluate(self, policy, obj, *, username=GATEWAY, namespace=None):
        executable = os.environ.get('CPS_NATIVE_PENDING_CEL_EVALUATOR')
        self.assertTrue(executable, 'Build cel-evaluator and set CPS_NATIVE_PENDING_CEL_EVALUATOR')
        payload = {'policy': policy, 'inputs': {'object': obj, 'oldObject': None, 'params': None,
            'request': {'namespace': namespace or obj['metadata']['namespace'],
                        'userInfo': {'username': username}}}}
        completed = subprocess.run([executable], input=json.dumps(payload), text=True,
                                   capture_output=True, timeout=15, check=True)
        result = json.loads(completed.stdout)
        self.assertTrue(result['compiled'], result)
        self.assertTrue(result['evaluated'], result)
        self.assertIn(result['decision'], ('pass', 'deny', 'not-matched'), result)
        return result

    def admitted(self, obj, **kwargs):
        # A skipped policy is not a denial. At least one matching policy is
        # required for these tests to assert protection of a pending prefix.
        results = [self.evaluate(p, obj, **kwargs) for p in self.policies()]
        self.assertTrue(any(r['matched'] for r in results), results)
        return not any(r['decision'] == 'deny' for r in results)

    def test_opt_in_changes_only_gateway_allowance_and_adds_pending_policy(self):
        default = render.render(self.config)
        self.assertEqual(canonical(default), canonical(self.bundle(False)))
        old = {p['metadata']['name']: p for p in default['items']}
        enabled = self.bundle()
        new = {p['metadata']['name']: p for p in enabled['items']}
        self.assertEqual(set(new) - set(old), {POLICY})  # VAP + binding share a name.
        changed = [p for p in enabled['items'] if p in default['items']]
        self.assertEqual(len(changed), len(default['items']) - 1)
        gateway = 'cps-native-gateway-authority-create-only'
        legacy = next(p for p in default['items'] if p['kind'] == 'ValidatingAdmissionPolicy'
                      and p['metadata']['name'] == gateway)
        current = next(p for p in enabled['items'] if p['kind'] == 'ValidatingAdmissionPolicy'
                       and p['metadata']['name'] == gateway)
        self.assertEqual(legacy['spec']['matchConditions'], current['spec']['matchConditions'])
        self.assertEqual(legacy['spec']['validations'][1:], current['spec']['validations'][1:])
        policy = next(p for p in enabled['items'] if p['kind'] == 'ValidatingAdmissionPolicy'
                      and p['metadata']['name'] == POLICY)
        self.assertEqual(policy['spec']['matchConstraints'], legacy['spec']['matchConstraints'])
        self.assertEqual(policy['spec']['failurePolicy'], 'Fail')
        binding = next(p for p in enabled['items'] if p['kind'] == 'ValidatingAdmissionPolicyBinding'
                       and p['metadata']['name'] == POLICY)
        self.assertEqual(binding['spec'], {'policyName': POLICY, 'validationActions': ['Deny']})

    def test_pending_opt_in_rejects_implicit_truthy_values(self):
        for value in (None, 0, 1, 'true', [], {}):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    render.render(self.config, allow_pending_current_groups=value)

    def test_default_authority_bytes_change_only_workload_map_reads(self):
        parts = copy.deepcopy([p for p in render.render()['items'] if p['kind'].startswith('Validating')
                 or p['kind'] in ('Role', 'RoleBinding', 'ClusterRole', 'ClusterRoleBinding')])
        roles = [p for p in parts if p['kind'] == 'Role'
                 and p['metadata']['name'] == 'cps-native-node-agent-pods']
        self.assertEqual({p['metadata']['namespace'] for p in roles}, {'jupyterhub', 'cit-jhub'})
        self.assertEqual(len(roles), 2)
        added = {'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get']}
        for role in roles:
            self.assertEqual(role['rules'].count(added), 1)
            role['rules'].remove(added)
        # Every prior Role, binding and admission byte stays pinned; only the
        # two explicitly reviewed workload ConfigMap read rules are removed.
        self.assertEqual(hashlib.sha256(canonical(parts).encode()).hexdigest(),
                         '6ac08b32608544a371e7628b475649d86c1c97df1e5efcc1358cb66203330292')

    def test_real_sdk_registry_and_allocation_require_explicit_opt_in(self):
        self.assertEqual(SDK_CAPTURE['source_commit'], '36b91d33da4508e54de74a900ee039cd01d14cb4')
        for key, obj in SDK_CAPTURE['objects'].items():
            with self.subTest(key=key):
                self.assertTrue(self.admitted(obj))
                gateway = next(p for p in self.policies(False)
                    if p['metadata']['name'] == 'cps-native-gateway-authority-create-only')
                self.assertEqual(self.evaluate(gateway, obj)['decision'], 'deny')

    def test_wrong_actor_and_namespace_are_denied_by_matching_pending_policy(self):
        for obj in SDK_CAPTURE['objects'].values():
            for actor in ('system:serviceaccount:foreign:foreign',
                          'system:serviceaccount:cps-compute:cps-native-node-agent',
                          'system:serviceaccount:cit-jhub:cps-compute-controller'):
                with self.subTest(name=obj['metadata']['name'], actor=actor):
                    result = self.evaluate(next(p for p in self.policies()
                        if p['metadata']['name'] == POLICY), obj, username=actor)
                    self.assertTrue(result['matched'])
                    self.assertEqual(result['decision'], 'deny')
            for namespace in ('foreign', 'cps-native-authority'):
                value = copy.deepcopy(obj); value['metadata']['namespace'] = namespace
                self.assertFalse(self.admitted(value, namespace=namespace))
            self.assertFalse(self.admitted(obj, namespace='foreign'))

    def test_unrelated_configmap_is_skipped_by_pending_policy(self):
        obj = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {
            'name': 'ordinary-config', 'namespace': 'foreign'}, 'data': {'ordinary': 'value'}}
        policy = next(p for p in self.policies() if p['metadata']['name'] == POLICY)
        self.assertEqual(self.evaluate(policy, obj, username='ordinary')['decision'], 'not-matched')

    def test_envelope_mutations_are_denied(self):
        mutations = {
            'mutable': lambda x: x.update(immutable=False),
            'missing-immutable': lambda x: x.pop('immutable'),
            'binary': lambda x: x.update(binaryData={}),
            'wrong-key': lambda x: x.update(data={'wrong.json': next(iter(x['data'].values()))}),
            'extra-key': lambda x: x['data'].update(extra='{}'),
            'labels': lambda x: x['metadata'].update(labels={'foreign': 'value'}),
            'annotations': lambda x: x['metadata'].update(annotations={'foreign': 'value'}),
            'owners': lambda x: x['metadata'].update(ownerReferences=[{'uid': 'foreign'}]),
            'finalizers': lambda x: x['metadata'].update(finalizers=['foreign']),
            'generated': lambda x: x['metadata'].update(generateName='foreign-'),
            'deleting': lambda x: x['metadata'].update(deletionTimestamp='2026-10-17T00:00:00Z'),
            'delete-grace': lambda x: x['metadata'].update(deletionGracePeriodSeconds=0),
            'cross-key': lambda x: x.update(data={('allocation.json' if 'registry.json' in x['data'] else 'registry.json'): next(iter(x['data'].values()))}),
            'wrong-uuid': lambda x: x['metadata'].update(name=x['metadata']['name'][:-1] + '2'),
            'short-uuid': lambda x: x['metadata'].update(name=x['metadata']['name'][:-1]),
            'long-uuid': lambda x: x['metadata'].update(name=x['metadata']['name'] + '0'),
            'uppercase-uuid': lambda x: x['metadata'].update(name=x['metadata']['name'][:-1] + 'A'),
        }
        for key, original in SDK_CAPTURE['objects'].items():
            for label, mutate in mutations.items():
                with self.subTest(key=key, mutation=label):
                    obj = copy.deepcopy(original); mutate(obj)
                    self.assertFalse(self.admitted(obj))

    def test_closed_canonical_v2_wire_mutations_are_denied(self):
        for key, original in SDK_CAPTURE['objects'].items():
            for label, value in (('protocol', 'cps-native-pending-allocation/v1'),
                ('kai_commit', '0' * 40), ('profile', 'foreign profile'),
                ('attempt', 'not-a-uuid'), ('epoch', {}), ('approval_ref', {}),
                ('node_configuration_ref', {}), ('extra', 'foreign'),
                ('profile', 'x' * 65536)):
                with self.subTest(key=key, field=label):
                    obj = copy.deepcopy(original); body = json.loads(obj['data'][key])
                    body[label] = value; obj['data'][key] = canonical(body)
                    self.assertFalse(self.admitted(obj))
            for mutation in ('whitespace', 'duplicate-field', 'trailing', 'missing-pin', 'wrong-discriminator'):
                with self.subTest(key=key, mutation=mutation):
                    obj = copy.deepcopy(original); body = json.loads(obj['data'][key])
                    if mutation == 'whitespace': obj['data'][key] = json.dumps(body, sort_keys=True)
                    elif mutation == 'duplicate-field': obj['data'][key] = '{"attempt":"foreign",' + obj['data'][key][1:]
                    elif mutation == 'trailing': obj['data'][key] += 'garbage'
                    elif mutation == 'missing-pin':
                        del body['node_configuration_ref']['uid']; obj['data'][key] = canonical(body)
                    else:
                        body['kind' if key == 'registry.json' else 'state'] = 'foreign'
                        obj['data'][key] = canonical(body)
                    self.assertFalse(self.admitted(obj))

    def test_all_allocation_pod_uid_and_registry_name_occurrences_are_bound(self):
        key = 'allocation.json'; original = SDK_CAPTURE['objects'][key]
        paths = [('intent', 'pod_uid'), ('pod', 'uid'), ('registry', 'name'),
                 ('maps', 0, 'owner', 'uid'), ('maps', 1, 'owner', 'uid')]
        for path in paths:
            with self.subTest(path=path):
                obj = copy.deepcopy(original); body = json.loads(obj['data'][key]); target = body
                for part in path[:-1]: target = target[part]
                target[path[-1]] = target[path[-1]][:-1] + '2'
                obj['data'][key] = canonical(body)
                self.assertFalse(self.admitted(obj))

    def test_allocation_slot_and_budget_bounds_remain_closed(self):
        key = 'allocation.json'; original = SDK_CAPTURE['objects'][key]
        for field, value in (('max_workspaces', 3), ('memory_budget_mib', 20480),
                             ('max_workspaces', True), ('memory_budget_mib', '15360')):
            with self.subTest(field=field, value=value):
                obj = copy.deepcopy(original); body = json.loads(obj['data'][key]); body[field] = value
                obj['data'][key] = canonical(body); self.assertFalse(self.admitted(obj))
        for capacity in ([], [{'cap_mib': 20480, 'pod_uid': '11111111-1111-4111-8111-111111111111'}],
            [{'cap_mib': 10240, 'pod_uid': '11111111-1111-4111-8111-111111111111'},
             {'cap_mib': 10240, 'pod_uid': '22222222-2222-4222-8222-222222222222'}],
            [{'cap_mib': 5120, 'pod_uid': '22222222-2222-4222-8222-222222222222'}],
            [{'cap_mib': 5120, 'pod_uid': '11111111-1111-4111-8111-111111111111'}] * 3):
            with self.subTest(capacity=capacity):
                obj = copy.deepcopy(original); body = json.loads(obj['data'][key]); body['capacity'] = capacity
                obj['data'][key] = canonical(body); self.assertFalse(self.admitted(obj))

    def test_syntactic_pins_are_not_claimed_as_live_authority_validation(self):
        # This is intentionally a wire boundary, not a JSON-decoded API read or
        # grant gate. Only the typed SDK/Node may authenticate an otherwise
        # well-shaped reference, profile, policy, epoch or hash against live state.
        for key, original in SDK_CAPTURE['objects'].items():
            obj = copy.deepcopy(original); body = json.loads(obj['data'][key])
            body['approval_ref']['uid'] = '55555555-5555-4555-8555-555555555555'
            obj['data'][key] = canonical(body)
            self.assertTrue(self.admitted(obj))

    def test_legacy_enrollment_ledger_and_node_policy_are_not_extended(self):
        from test_native_authority_create_admission import AuthorityAdmissionTests
        AuthorityAdmissionTests.setUpClass()
        legacy = AuthorityAdmissionTests()
        objects = [legacy.barrier(), legacy.cm('cps-native-enrollment-', 'enrollment.json', legacy.enrollment),
                   {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {
                       'namespace': 'cps-native-system', 'name': 'cps-native-gpu-allocations'},
                    'data': {'state.json': '{"allocations":{},"version":1}'}}]
        config = copy.deepcopy(self.config); config['authority_namespace'] = 'cps-native-system'
        policies = [p for p in render.render(config, allow_pending_current_groups=True)['items']
                    if p['kind'] == 'ValidatingAdmissionPolicy']
        for obj in objects:
            for suffix in ('', '-tampered'):
                value = copy.deepcopy(obj); value['metadata']['name'] += suffix
                results = [self.evaluate(p, value) for p in policies]
                self.assertEqual(not any(r['decision'] == 'deny' for r in results), not suffix)
        original_node = next(p for p in render.render(config)['items'] if p['kind'] == 'ValidatingAdmissionPolicy'
                             and p['metadata']['name'] == 'cps-native-node-agent-cleanup-only')
        self.assertIn(original_node, policies)


    def compiler_seed(self, source='cps'):
        binding = 'a' * 60
        pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': 'test', 'namespace': 'jupyterhub'},
               'spec': {'containers': [{'name': 'notebook', 'image': 'example@sha256:' + 'b' * 64}]}}
        seed = {'actor': source, 'source': source, 'binding_id': binding,
                'attempt': '22222222-2222-4222-8222-222222222222', 'source_pod': pod, 'admitted': pod}
        return {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
                'metadata': {'name': 'cps-pending-compiler-' + binding[:40], 'namespace': 'cps-compute'},
                'data': {'seed.json': canonical(seed)}}

    def test_compiler_seed_envelope_requires_explicit_opt_in(self):
        for source in ('cps', 'cit'):
            obj = self.compiler_seed(source)
            self.assertTrue(self.admitted(obj))
            gateway = next(p for p in self.policies(False)
                           if p['metadata']['name'] == 'cps-native-gateway-authority-create-only')
            self.assertEqual(self.evaluate(gateway, obj)['decision'], 'deny')

    def test_compiler_seed_denies_foreign_writer_and_namespace(self):
        obj = self.compiler_seed()
        self.assertFalse(self.admitted(obj, username='system:serviceaccount:foreign:foreign'))
        obj['metadata']['namespace'] = 'foreign'
        self.assertFalse(self.admitted(obj))

    def test_compiler_seed_rejects_malformed_envelopes(self):
        original = self.compiler_seed()
        mutations = []
        for field, value in [('binding_id', 'b' * 60), ('actor', 'cit'), ('source', 'foreign'),
                             ('attempt', 'not-a-uuid'), ('extra', True)]:
            obj = copy.deepcopy(original); seed = json.loads(obj['data']['seed.json']); seed[field] = value
            obj['data']['seed.json'] = canonical(seed); mutations.append(obj)
        for field, value in [('immutable', False), ('binaryData', {'payload': 'eA=='})]:
            obj = copy.deepcopy(original); obj[field] = value; mutations.append(obj)
        for field, value in [('labels', {'unexpected': 'label'}), ('annotations', {'x': 'y'}),
                             ('finalizers', ['foreign']), ('ownerReferences', [{'apiVersion': 'v1', 'kind': 'Pod', 'name': 'x', 'uid': '22222222-2222-4222-8222-222222222222'}])]:
            obj = copy.deepcopy(original); obj['metadata'][field] = value; mutations.append(obj)
        obj = copy.deepcopy(original); obj['data']['seed.json'] += ' '; mutations.append(obj)
        obj = copy.deepcopy(original); obj['data']['seed.json'] = 'x' * 1048577; mutations.append(obj)
        obj = copy.deepcopy(original); obj['data']['extra'] = '{}'; mutations.append(obj)
        obj = copy.deepcopy(original); obj['metadata']['name'] += '-extra'; mutations.append(obj)
        for obj in mutations:
            with self.subTest(obj=obj):
                self.assertFalse(self.admitted(obj))


if __name__ == '__main__':
    unittest.main()

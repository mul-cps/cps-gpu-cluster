import copy
from dataclasses import asdict, replace
import hashlib
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
POD = '11111111-1111-4111-8111-111111111111'
NODE = '3336cdd5-d245-436e-b57c-2f66c6dcaa41'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
BINDING = 'a' * 60


def fixtures():
    config = {'version': 1, 'enabled': True, 'authority_namespace': 'cps-native-authority',
              'policy_hash': 'sha256:' + 'b' * 64,
              'pool': {'node': 'k3s-wk-gpu2', 'node_uid': NODE, 'gpu_uuid': GPU, 'max_workspaces': 2},
              'workspaces': {'cps:pilot': {'profile': 'group-native-5g'}}}
    intent = {'namespace': 'jupyterhub', 'name': 'jupyter-pilot', 'pod_uid': POD,
              'node': 'k3s-wk-gpu2', 'node_uid': NODE, 'gpu_uuid': GPU,
              'spec_sha256': 'c' * 64, 'cap_mib': 5120, 'policy_hash': config['policy_hash']}
    enrollment = dict(version=1, binding_id=BINDING, source='cps', actor='service:cps-hub',
        workspace='pilot', principal='workspace:cps:pilot', members=['person:one', 'person:two'],
        attempt='22222222-2222-4222-8222-222222222222', profile='group-native-5g',
        policy_hash=config['policy_hash'], namespace='jupyterhub', name=intent['name'],
        node=intent['node'], node_uid=NODE, gpu_uuid=GPU, cap_mib=5120, intent=intent)
    cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
        'metadata': {'name': 'cps-native-enrollment-' + BINDING[:40],
            'namespace': 'cps-native-authority', 'uid': '44444444-4444-4444-8444-444444444444',
            'resourceVersion': '1', 'labels': {'cps.compute/native-binding': BINDING}},
        'data': {'enrollment.json': json.dumps(enrollment)}}
    return config, enrollment, cm


class EnrollmentTest(unittest.TestCase):
    def setUp(self):
        if not (HERE / 'node_agent.py').exists(): self.fail('Node authority implementation is missing')
        self.agent = importlib.import_module('node_agent')
        self.models = self.agent.load_models_from_snapshot()
        self.config, self.enrollment, self.cm = fixtures()

    def check(self, cm=None, config=None):
        return self.agent.validate_enrollment(cm or self.cm, config or self.config, self.models)

    def test_exact_immutable_selected_pool_enrollment(self):
        self.assertEqual(self.check()['enrollment'], self.enrollment)

    def core_configmap_list(self):
        enrollment = copy.deepcopy(self.cm)
        backend, record = self.agent_cleanup_fixture('cleaned', False, False, 'unlimited')
        cleanup = self.agent.cleanup_receipt(self.check(), record, backend, None, self.models)
        cleanup['metadata'].update(uid='66666666-6666-4666-8666-666666666666', resourceVersion='2')
        for item in (enrollment, cleanup):
            item.pop('apiVersion'); item.pop('kind')
        return {'apiVersion':'v1','kind':'ConfigMapList','metadata':{'resourceVersion':'17'},
                'items':[enrollment,cleanup]}

    def list_enrollments(self, response):
        from types import SimpleNamespace
        # Fake only HTTP transport. The actual list adapter must establish the
        # typed API context before the unchanged public validator sees an item.
        api = self.agent.api_class(SimpleNamespace(Kubernetes=object))()
        def read(method, path, value=None):
            self.assertEqual(method, 'GET')
            self.assertEqual(path, '/api/v1/namespaces/cps-native-authority/configmaps?limit=200&labelSelector=cps.compute%2Fnative-binding')
            self.assertIsNone(value)
            return response
        api.call = read
        return api.enrollments(self.config['authority_namespace'])

    def test_real_core_list_items_without_type_metadata_validate_and_cleanup_is_ignored(self):
        response = self.core_configmap_list(); original = copy.deepcopy(response)
        self.assertEqual(response['items'][0]['metadata']['labels'], response['items'][1]['metadata']['labels'])
        selected = self.list_enrollments(response)
        self.assertEqual(len(selected), 1)
        self.assertEqual(self.check(selected[0])['enrollment'], self.enrollment)
        self.assertEqual(response, original)

    def test_binding_selector_is_retained_on_continuation_pages(self):
        from types import SimpleNamespace
        from urllib.parse import parse_qs, urlparse
        api = self.agent.api_class(SimpleNamespace(Kubernetes=object))()
        paths = []
        def read(method, path, value=None):
            query = parse_qs(urlparse(path).query)
            self.assertEqual(query['labelSelector'], ['cps.compute/native-binding'])
            self.assertEqual(query['limit'], ['200'])
            paths.append(path)
            response = self.core_configmap_list()
            if len(paths) == 1:
                response['items'] = []
                response['metadata']['continue'] = 'reviewed/page+token'
            else:
                self.assertEqual(query['continue'], ['reviewed/page+token'])
            return response
        api.call = read
        self.assertEqual(len(api.enrollments(self.config['authority_namespace'])), 1)
        self.assertEqual(len(paths), 2)

    def test_direct_enrollment_without_typed_list_context_remains_rejected(self):
        item = self.core_configmap_list()['items'][0]
        with self.assertRaises(ValueError): self.check(item)

    def test_malformed_or_wrong_configmap_list_envelope_is_rejected(self):
        changes = [lambda r:r.pop('apiVersion'), lambda r:r.pop('kind'),
            lambda r:r.update(apiVersion='apps/v1'), lambda r:r.update(kind='SecretList'),
            lambda r:r.update(metadata=[]), lambda r:r.pop('metadata'),
            lambda r:r.update(items={}), lambda r:r.update(items=None)]
        for index, change in enumerate(changes):
            response = self.core_configmap_list(); change(response)
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.list_enrollments(response)

    def test_explicit_wrong_item_type_or_namespace_is_rejected_before_name_filtering(self):
        changes = [lambda item:item.update(apiVersion='apps/v1'),
            lambda item:item.update(kind='Secret'),
            lambda item:item['metadata'].update(namespace='other-authority')]
        for index in (0,1):
            for change_index, change in enumerate(changes):
                response = self.core_configmap_list(); change(response['items'][index])
                with self.subTest(item=index, change=change_index), self.assertRaises(ValueError):
                    self.list_enrollments(response)
        response = self.core_configmap_list(); response['items'][0] = 'not-a-configmap'
        with self.assertRaises(ValueError): self.list_enrollments(response)

    def test_mutable_or_tampered_list_enrollment_still_fails_public_validation(self):
        for mutable in (True,False):
            response = self.core_configmap_list()
            if mutable: response['items'][0]['immutable'] = False
            else:
                payload = copy.deepcopy(self.enrollment); payload['intent']['cap_mib'] = 10240
                response['items'][0]['data']['enrollment.json'] = json.dumps(payload)
            selected = self.list_enrollments(response)
            self.assertEqual(len(selected), 1)
            with self.assertRaises(ValueError): self.check(selected[0])

    def test_tampered_cap_intent_or_pool_blocks(self):
        for change in ('cap_mib', 'namespace', 'node_uid', 'gpu_uuid', 'policy_hash'):
            cm = copy.deepcopy(self.cm)
            value = copy.deepcopy(self.enrollment)
            value['intent'][change] = 10240 if change == 'cap_mib' else 'forged'
            cm['data']['enrollment.json'] = json.dumps(value)
            with self.subTest(change=change), self.assertRaises(ValueError): self.check(cm)

    def test_untrusted_mutable_wrong_namespace_or_label_blocks(self):
        changes = [lambda c: c.update(immutable=False),
            lambda c: c['metadata'].update(namespace='jupyterhub'),
            lambda c: c['metadata'].update(labels={'cps.compute/native-binding': 'd' * 60}),
            lambda c: c['metadata'].update(deletionTimestamp='now'),
            lambda c: c['metadata'].update(name='cps-native-enrollment-fake')]
        for change in changes:
            cm = copy.deepcopy(self.cm); change(cm)
            with self.assertRaises(ValueError): self.check(cm)

    def test_closed_schema_duplicate_json_unknown_profile_or_workspace_blocks(self):
        for field, replacement in [('extra', True), ('profile', 'unreviewed'), ('workspace', 'outsider'),
                ('principal', 'person:one'), ('members', ['person:two', 'person:one']), ('attempt', '')]:
            value = dict(self.enrollment, **{field: replacement}); cm = copy.deepcopy(self.cm)
            cm['data']['enrollment.json'] = json.dumps(value)
            with self.assertRaises(ValueError): self.check(cm)
        cm = copy.deepcopy(self.cm)
        cm['data']['enrollment.json'] = cm['data']['enrollment.json'][:-1] + ',"version":1}'
        with self.assertRaises(ValueError): self.check(cm)

    def test_root_private_mirror_rejects_replacement_missing_and_uid_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); os.chmod(state, 0o700)
            store = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
            accepted = store.synchronize([self.check()])
            self.assertEqual(accepted[POD]['enrollment'], self.enrollment)
            self.assertEqual((state / 'intents' / (POD + '.json')).stat().st_mode & 0o777, 0o600)
            changed = self.check(); changed['configmap_uid'] = '55555555-5555-4555-8555-555555555555'
            with self.assertRaises(ValueError): store.synchronize([changed])
            with self.assertRaises(ValueError): store.synchronize([])
            changed = self.check(); changed['enrollment']['binding_id'] = 'e' * 60
            with self.assertRaises(ValueError): store.synchronize([self.check(), changed])

    def test_world_writable_or_symlink_mirror_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); os.chmod(state, 0o700)
            store = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
            store.synchronize([self.check()])
            path = state / 'intents' / (POD + '.json'); path.chmod(0o644)
            with self.assertRaises(ValueError): store.synchronize([self.check()])

    def test_cleanup_requires_actual_absence_cleaned_journal_zero_tasks_clients_and_readback(self):
        for state, pod, tasks, clients, readback in [
                ('sealed', None, False, False, 'unlimited'),
                ('cleaned', {'metadata': {'uid': POD}}, False, False, 'unlimited'),
                ('cleaned', None, True, False, 'unlimited'),
                ('cleaned', None, False, True, 'unlimited'),
                ('cleaned', None, False, False, 'capped'),
                ('cleaned', None, False, False, 'ambiguous')]:
            backend, record = self.agent_cleanup_fixture(state, tasks, clients, readback)
            with self.assertRaises(ValueError):
                self.agent.cleanup_receipt(self.check(), record, backend, pod, self.models)
        backend, record = self.agent_cleanup_fixture('cleaned', False, False, 'unlimited')
        receipt = self.agent.cleanup_receipt(self.check(), record, backend, None, self.models)
        self.assertTrue(json.loads(receipt['data']['receipt.json'])['cleanup_confirmed'])

    def agent_cleanup_fixture(self, state, tasks, clients, readback):
        from types import SimpleNamespace
        intent = self.models.CapIntent(**self.enrollment['intent'])
        relative = '/kubepods.slice/kubepods-burstable-pod' + intent.pod_uid.replace('-', '_') + '.slice'
        identity = self.models.CapIdentity(intent.pod_uid, intent.spec_sha256, intent.node_uid,
            intent.gpu_uuid, 'c' * 64, 211, 345, '209f8bc9-a478-48e4-925a-6e07ffa56f7a',
            relative, '/sys/fs/cgroup' + relative, 29, 71, 'e148263b-805d-4ccd-857c-84a03d4f4229')
        record = self.models.CapRecord(intent, identity, state, 'e148263b-805d-4ccd-857c-84a03d4f4229',
            self.models.CapLimit(intent.cap_bytes, intent.cap_bytes))
        class Backend:
            def check_cleanup(inner, identity):
                return self.models.CleanupObservation(identity.epoch, None, False, identity.cgroup_path,
                    identity.cgroup_device, identity.cgroup_inode, True, tasks, clients, True)
            def read_gate(inner, identity): return None
            def _raw(inner, identity):
                if readback == 'ambiguous': return {'nvml_result': 3, 'state': 'unset-or-unsupported'}
                return {'soft': 0, 'hard': self.models.MAX_LIMIT, 'used': 0} if readback == 'unlimited' else {'soft': 1, 'hard': 1, 'used': 0}
        return Backend(), record

    def test_cleanup_create_conflict_requires_identical_existing_immutable_receipt(self):
        backend, record = self.agent_cleanup_fixture('cleaned', False, False, 'unlimited')
        receipt = self.agent.cleanup_receipt(self.check(), record, backend, None, self.models)
        receipt['metadata']['uid'] = '66666666-6666-4666-8666-666666666666'
        class API:
            def __init__(inner, existing): inner.existing = existing
            def create_configmap(inner, namespace, value): raise self.agent.Conflict()
            def configmap(inner, namespace, name): return inner.existing
        self.agent.publish_cleanup(API(receipt), receipt)
        changed = copy.deepcopy(receipt); changed['immutable'] = False
        with self.assertRaises(ValueError): self.agent.publish_cleanup(API(changed), receipt)
        changed = copy.deepcopy(receipt); changed['data']['receipt.json'] = '{}'
        with self.assertRaises(ValueError): self.agent.publish_cleanup(API(changed), receipt)

    def retired_cleanup_fixture(self):
        backend, record = self.agent_cleanup_fixture('cleaned', False, True, 'capped')
        inode = record.identity.cgroup_inode
        document = {'version': 1, 'backend': 'misc-fallback', 'gpu_uuid': GPU, 'gpu_id': 1,
            'entries': [{'cgroup_id': inode, 'kernfs_id': inode, 'inode': inode, 'offline': True,
                'pinned': True, 'default_hierarchy': True, 'soft': record.limit.soft,
                'hard': record.limit.hard, 'used': 0}]}
        proof = self.models.validate_retired_inventory(document, record.identity, record.limit)
        record = replace(record, state='retired-inert-cap', retirement=proof)
        backend.check_cleanup = lambda identity: self.models.CleanupObservation(identity.epoch, None, False,
            identity.cgroup_path, None, None, False, False, True, True)
        backend.retired_inert_cap = lambda identity, limit: self.models.validate_retired_inventory(document, identity, limit)
        def unavailable_nvml(identity): raise RuntimeError('NVML_ERROR_INVALID_ARGUMENT 17')
        backend._raw = unavailable_nvml
        return backend, record, document

    def test_retired_receipt_preserves_finite_cap_and_requires_fresh_entry_with_busy_peer(self):
        backend, record, document = self.retired_cleanup_fixture()
        envelope = self.check()
        cm = self.agent.cleanup_receipt(envelope, record, backend, None, self.models)
        payload = json.loads(cm['data']['receipt.json'])
        self.assertEqual(set(payload), {'version', 'binding_id', 'attempt', 'intent', 'cleanup_confirmed', 'retirement'})
        retirement = payload['retirement']
        self.assertEqual(retirement['proof']['state'], 'retired-inert-cap')
        self.assertEqual(retirement['proof']['entry']['hard'], record.limit.hard)
        self.assertEqual(retirement['enrollment_uid'], envelope['configmap_uid'])
        self.assertEqual(retirement['enrollment_sha256'], self.agent.canonical_sha256(self.enrollment))
        self.assertEqual(retirement['journal_sha256'], self.agent.canonical_sha256(record.to_dict()))
        for change in ({'used': 1}, {'offline': False}, {'pinned': False}):
            original = copy.deepcopy(document['entries'][0]); document['entries'][0].update(change)
            with self.assertRaises(ValueError): self.agent.cleanup_receipt(envelope, record, backend, None, self.models)
            document['entries'][0] = original

    def test_retired_cleanup_tombstone_pins_journal_and_actual_immutable_uid(self):
        backend, record, _ = self.retired_cleanup_fixture(); envelope = self.check()
        cm = self.agent.cleanup_receipt(envelope, record, backend, None, self.models)
        cm['metadata']['uid'] = '66666666-6666-4666-8666-666666666666'
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); state.chmod(0o700)
            store = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
            store.mark_cleanup_published(POD, envelope, cm, record)
            self.assertTrue(store.cleanup_published(POD, envelope, record, cm))
            changed = copy.deepcopy(cm); changed['metadata']['uid'] = NODE
            with self.assertRaises(ValueError): store.cleanup_published(POD, envelope, record, changed)
            changed = replace(record, state='cleaned', retirement=None)
            with self.assertRaises(ValueError): store.cleanup_published(POD, envelope, changed, cm)

    def test_published_cleanup_tombstone_survives_new_pod_and_busy_peer(self):
        backend, record = self.agent_cleanup_fixture('cleaned', False, False, 'unlimited')
        envelope = self.check()
        receipt = self.agent.cleanup_receipt(envelope, record, backend, None, self.models)
        receipt['metadata']['uid'] = '66666666-6666-4666-8666-666666666666'
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); os.chmod(state, 0o700)
            store = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
            self.assertFalse(store.cleanup_published(POD, envelope, record, receipt))
            store.mark_cleanup_published(POD, envelope, receipt)
            self.assertTrue(store.cleanup_published(POD, envelope, record, receipt))
            replaced = copy.deepcopy(receipt)
            replaced['metadata']['uid'] = '77777777-7777-4777-8777-777777777777'
            with self.assertRaises(ValueError): store.cleanup_published(POD, envelope, record, replaced)
            with self.assertRaises(ValueError): store.cleanup_published(POD, envelope, record, None)

    def test_loaded_config_requires_protected_exact0400_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'config.json'; path.write_text(json.dumps(self.config)); path.chmod(0o400)
            self.assertEqual(self.agent.read_config(path, trusted_uid=os.getuid()), self.config)
            path.chmod(0o600)
            with self.assertRaises(ValueError): self.agent.read_config(path, trusted_uid=os.getuid())
            path.chmod(0o400); link = path.with_suffix('.link'); link.symlink_to(path)
            with self.assertRaises(OSError): self.agent.read_config(link, trusted_uid=os.getuid())

    def test_default_cli_makes_no_source_api_or_gpu_calls(self):
        from unittest.mock import patch
        with patch.object(self.agent, 'load_bundle', side_effect=AssertionError('source read')):
            self.agent.main([])


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def canonical_digest(value):
    return 'sha256:' + hashlib.sha256(canonical_json(value).encode()).hexdigest()


class AbortTest(unittest.TestCase):
    setUp = EnrollmentTest.setUp
    check = EnrollmentTest.check

    def abort_fixture(self, envelope=None):
        envelope = envelope or self.check()
        enrollment = envelope['enrollment']; binding = enrollment['binding_id']
        epoch = self.models.DriverEpoch(NODE, '88888888-8888-4888-8888-888888888888',
            'dddddddd-dddd-4ddd-8ddd-dddddddddddd', GPU)
        payload = {'version': 1, 'outcome': 'pre-gate-aborted', 'binding_id': binding,
            'attempt': enrollment['attempt'], 'intent': copy.deepcopy(enrollment['intent']),
            'enrollment_sha256': canonical_digest(enrollment), 'audit_sha256': 'sha256:' + 'd' * 64,
            'node_epoch': asdict(epoch)}
        cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
            'metadata': {'name': 'cps-native-abort-' + binding[:40],
                'namespace': envelope['authority_namespace'],
                'uid': '99999999-9999-4999-8999-999999999999', 'resourceVersion': '3',
                'labels': {'cps.compute/native-binding': binding}},
            'data': {'abort.json': canonical_json(payload)}}
        record = dict(copy.deepcopy(enrollment), ceiling={'cpu': '4', 'memory': '16Gi', 'gpu_memory_gib': 5},
            group_id='native-pilot-group-a', state='released',
            pre_gate_abort={'configmap': cm['metadata']['name'], 'configmap_uid': cm['metadata']['uid'],
                'sha256': canonical_digest(payload)})
        ledger = {'apiVersion': 'v1', 'kind': 'ConfigMap',
            'metadata': {'name': 'cps-native-gpu-allocations', 'namespace': envelope['authority_namespace'],
                'uid': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'resourceVersion': '4'},
            'data': {'state.json': canonical_json({'version': 1, 'allocations': {binding: record}})}}
        return cm, envelope, ledger, epoch

    def validate(self, values):
        return self.agent.validate_abort(*values, self.models)

    def alter_payload(self, values, change, *, update_proof=True):
        cm, envelope, ledger, epoch = copy.deepcopy(values)
        payload = json.loads(cm['data']['abort.json']); change(payload)
        cm['data']['abort.json'] = canonical_json(payload)
        if update_proof:
            state = json.loads(ledger['data']['state.json'])
            state['allocations'][envelope['enrollment']['binding_id']]['pre_gate_abort']['sha256'] = canonical_digest(payload)
            ledger['data']['state.json'] = canonical_json(state)
        return cm, envelope, ledger, epoch

    def alter_ledger(self, values, change):
        cm, envelope, ledger, epoch = copy.deepcopy(values)
        state = json.loads(ledger['data']['state.json']); change(state)
        ledger['data']['state.json'] = canonical_json(state)
        return cm, envelope, ledger, epoch

    def test_abort_requires_exact_canonical_full_enrollment_and_ledger_proof(self):
        cm, envelope, ledger, epoch = self.abort_fixture()
        proof = self.validate((cm, envelope, ledger, epoch))
        self.assertEqual(proof, {'enrollment_uid': envelope['configmap_uid'],
            'abort_uid': cm['metadata']['uid'], 'abort_sha256': canonical_digest(json.loads(cm['data']['abort.json'])),
            'ledger_uid': ledger['metadata']['uid'], 'payload': json.loads(cm['data']['abort.json'])})
        self.assertEqual(self.agent.canonical_sha256(envelope['enrollment']), canonical_digest(envelope['enrollment']))

    def test_abort_rejects_mutable_wrong_authority_type_identity_or_extra_data(self):
        changes = [lambda cm: cm.update(immutable=False), lambda cm: cm.update(apiVersion='apps/v1'),
            lambda cm: cm.update(kind='Secret'), lambda cm: cm.update(binaryData={'extra': 'AA=='}),
            lambda cm: cm['metadata'].update(namespace='jupyterhub'),
            lambda cm: cm['metadata'].update(uid=''), lambda cm: cm['metadata'].pop('uid'),
            lambda cm: cm['metadata'].update(deletionTimestamp='now'),
            lambda cm: cm['metadata'].update(name='cps-native-abort-forged'),
            lambda cm: cm['metadata'].update(labels={'cps.compute/native-binding': 'e' * 60}),
            lambda cm: cm['data'].update(extra='untrusted')]
        for index, change in enumerate(changes):
            values = self.abort_fixture(); change(values[0])
            with self.subTest(change=index), self.assertRaises(ValueError): self.validate(values)

    def test_abort_rejects_noncanonical_duplicate_or_nonfinite_payload(self):
        for raw in (json.dumps(json.loads(self.abort_fixture()[0]['data']['abort.json'])),
                self.abort_fixture()[0]['data']['abort.json'][:-1] + ',"version":1}',
                '{"version":NaN}'):
            values = self.abort_fixture(); values[0]['data']['abort.json'] = raw
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError): self.validate(values)

    def test_abort_rejects_tampered_binding_attempt_intent_hash_schema_and_epoch(self):
        changes = [lambda p: p.update(version=True), lambda p: p.update(outcome='cleaned'),
            lambda p: p.update(binding_id='e' * 60), lambda p: p.update(attempt='another-attempt'),
            lambda p: p['intent'].update(pod_uid='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'),
            lambda p: p['intent'].update(cap_mib=10240), lambda p: p['intent'].update(extra=True),
            lambda p: p.update(enrollment_sha256='sha256:' + 'e' * 64),
            lambda p: p.update(enrollment_sha256='e' * 64), lambda p: p.update(extra=True),
            lambda p: p.update(audit_sha256='d' * 64), lambda p: p.update(audit_sha256='sha256:' + 'D' * 64),
            lambda p: p.update(audit_sha256='sha256:' + 'd' * 63),
            lambda p: p['node_epoch'].update(node_uid='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'),
            lambda p: p['node_epoch'].update(boot_id='cccccccc-cccc-4ccc-8ccc-cccccccccccc'),
            lambda p: p['node_epoch'].update(driver_generation='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'),
            lambda p: p['node_epoch'].update(gpu_uuid='GPU-ffffffff-ffff-4fff-8fff-ffffffffffff'),
            lambda p: p['node_epoch'].update(extra=True)]
        for index, change in enumerate(changes):
            values = self.alter_payload(self.abort_fixture(), change)
            with self.subTest(change=index), self.assertRaises(ValueError): self.validate(values)

    def test_abort_rejects_nonreleased_or_orphan_ledger_and_wrong_proof(self):
        changes = [lambda state: state.update(version=True), lambda state: state['allocations'].clear(),
            lambda state: state['allocations'][BINDING].update(state='sealed'),
            lambda state: state['allocations'][BINDING].update(attempt='another-attempt'),
            lambda state: state['allocations'][BINDING].update(members=['person:outsider']),
            lambda state: state['allocations'][BINDING].pop('intent'),
            lambda state: state['allocations'][BINDING].pop('pre_gate_abort'),
            lambda state: state['allocations'][BINDING]['pre_gate_abort'].update(configmap='cps-native-abort-forged'),
            lambda state: state['allocations'][BINDING]['pre_gate_abort'].update(configmap_uid='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'),
            lambda state: state['allocations'][BINDING]['pre_gate_abort'].update(sha256='sha256:' + 'e' * 64),
            lambda state: state['allocations'][BINDING]['pre_gate_abort'].update(extra=True)]
        for index, change in enumerate(changes):
            with self.subTest(change=index), self.assertRaises(ValueError):
                self.validate(self.alter_ledger(self.abort_fixture(), change))
        for change in (lambda cm: cm.update(kind='Secret'),
                lambda cm: cm['metadata'].update(namespace='jupyterhub'),
                lambda cm: cm['metadata'].update(name='another-ledger'),
                lambda cm: cm['metadata'].pop('uid'), lambda cm: cm['data'].update(extra='untrusted')):
            values = self.abort_fixture(); change(values[2])
            with self.assertRaises(ValueError): self.validate(values)

    def test_abort_tombstone_is_separate_durable_and_rejects_replacement_or_missing_proof(self):
        values = self.abort_fixture(); cm, envelope, ledger, epoch = values
        proof = self.validate(values)
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); state.chmod(0o700)
            store = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
            store.synchronize([envelope])
            self.assertFalse(store.abort_published(POD, envelope, proof))
            store.mark_abort(POD, envelope, proof)
            tombstone = state / 'pre-gate-aborts' / (POD + '.json')
            self.assertEqual(tombstone.stat().st_mode & 0o777, 0o600)
            self.assertFalse((state / 'journal').exists())
            restarted = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
            self.assertTrue(restarted.abort_published(POD, envelope, proof))
            for field in ('abort_uid', 'enrollment_uid', 'ledger_uid', 'abort_sha256'):
                changed = copy.deepcopy(proof); changed[field] = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
                with self.subTest(field=field), self.assertRaises(ValueError):
                    restarted.abort_published(POD, envelope, changed)
            with self.assertRaises(ValueError): restarted.abort_published(POD, envelope, None)

    def fake_authority(self, values, *, pod=None, abort=True, record=True):
        from types import SimpleNamespace
        cm, envelope, ledger, epoch = values
        if not record:
            ledger = self.alter_ledger(values,
                lambda state: state['allocations'][BINDING].pop('pre_gate_abort'))[2]
        pods = []
        def configmap(namespace, name):
            self.assertEqual(namespace, envelope['authority_namespace'])
            if name == 'cps-native-gpu-allocations': return ledger
            self.assertEqual(name, cm['metadata']['name'])
            return cm if abort else None
        def get_pod(intent):
            self.assertEqual(intent.to_dict(), envelope['enrollment']['intent'])
            pods.append(intent.pod_uid)
            return pod
        return SimpleNamespace(configmap=configmap, pod=get_pod, pod_reads=pods)

    def recognize(self, store, journal, values, kube):
        cm, envelope, ledger, epoch = values
        return self.agent.recognize_aborts(store, journal, {POD: envelope}, kube, epoch, self.models)

    def test_first_abort_requires_absence_and_no_native_journal(self):
        from types import SimpleNamespace
        values = self.abort_fixture()
        for journal_record, pod in ((object(), None), (None, {'metadata': {'uid': POD}}),
                (None, {'metadata': {'uid': 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'}})):
            with self.subTest(journal=journal_record is not None, pod=pod), tempfile.TemporaryDirectory() as temporary:
                state = Path(temporary); state.chmod(0o700)
                store = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
                store.synchronize([values[1]])
                journal = SimpleNamespace(read=lambda uid: journal_record)
                with self.assertRaises(ValueError):
                    self.recognize(store, journal, values, self.fake_authority(values, pod=pod))
                self.assertEqual(list((state / 'pre-gate-aborts').iterdir()), [])

    def test_recognized_abort_survives_restart_and_does_not_inspect_replacement_pod(self):
        from types import SimpleNamespace
        values = self.abort_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); state.chmod(0o700)
            store = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
            store.synchronize([values[1]])
            journal = SimpleNamespace(read=lambda uid: None)
            kube = self.fake_authority(values)
            self.assertEqual(self.recognize(store, journal, values, kube), {POD})
            self.assertEqual(kube.pod_reads, [POD])
            restarted = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
            replacement = self.fake_authority(values, pod={'metadata': {'uid': 'new-peer'}})
            self.assertEqual(self.recognize(restarted, journal, values, replacement), {POD})
            self.assertEqual(replacement.pod_reads, [])
            self.assertFalse((state / 'journal').exists())

    def test_consumed_abort_survives_actual_driver_generation_change_without_new_observation(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        values = self.abort_fixture(); old_epoch = values[3]
        new_epoch = replace(old_epoch, driver_generation='ffffffff-ffff-4fff-8fff-ffffffffffff')
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); state.chmod(0o700)
            store = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
            store.synchronize([values[1]]); journal = SimpleNamespace(read=lambda uid: None)
            generation = state / 'authority/driver-generation'
            generation.write_text(old_epoch.driver_generation+'\n'); generation.chmod(0o600)
            def first_epoch():
                return replace(old_epoch, driver_generation=store.backend.private_read(generation, os.getuid(), raw=True))
            self.assertEqual(self.agent.recognize_aborts(store, journal, {POD: values[1]},
                self.fake_authority(values), None, self.models, epoch_reader=first_epoch), {POD})
            generation.write_text(new_epoch.driver_generation+'\n')
            restarted = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
            kube = self.fake_authority(values, pod={'metadata': {'uid': 'new-peer'}})
            reader = Mock(side_effect=AssertionError('Completed abort must not reread live epoch'))
            self.assertEqual(self.agent.recognize_aborts(restarted, journal, {POD: values[1]}, kube,
                new_epoch, self.models, epoch_reader=reader), {POD})
            self.assertEqual(self.agent.recognize_aborts(restarted, journal, {POD: values[1]}, kube,
                None, self.models, epoch_reader=reader), {POD})
            reader.assert_not_called(); self.assertEqual(kube.pod_reads, [])
            self.assertEqual(restarted.abort_record(POD)['payload']['node_epoch']['driver_generation'],
                             old_epoch.driver_generation)
            self.assertEqual(restarted.backend.private_read(generation, os.getuid(), raw=True), new_epoch.driver_generation)

    def test_completed_abort_maintenance_rejects_changed_authority_or_native_journal(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        for change in ('abort-uid', 'payload', 'released-state', 'ledger-proof', 'enrollment', 'journal',
                       'late-journal', 'current-node', 'current-gpu'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                state = Path(temporary); state.chmod(0o700)
                values = self.abort_fixture(); store = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
                store.synchronize([values[1]]); journal = SimpleNamespace(read=lambda uid: None)
                self.recognize(store, journal, values, self.fake_authority(values))
                current = replace(values[3], driver_generation='ffffffff-ffff-4fff-8fff-ffffffffffff')
                if change == 'abort-uid': values[0]['metadata']['uid'] = POD
                if change == 'payload':
                    values = self.alter_payload(values, lambda p: p.update(audit_sha256='sha256:'+'f'*64))
                if change == 'released-state':
                    values = self.alter_ledger(values, lambda s: s['allocations'][BINDING].update(state='enrolled'))
                if change == 'ledger-proof':
                    values = self.alter_ledger(values, lambda s: s['allocations'][BINDING]['pre_gate_abort'].update(sha256='sha256:'+'f'*64))
                if change == 'enrollment': values[1]['configmap_uid'] = POD
                if change == 'journal': journal.read = lambda uid: object()
                if change == 'late-journal': journal.read = Mock(side_effect=[None, object()])
                if change == 'current-node': current = replace(current, node_uid=POD)
                if change == 'current-gpu': current = replace(current, gpu_uuid='GPU-'+POD)
                kube = self.fake_authority(values, pod={'metadata': {'uid': 'new-peer'}})
                reader = Mock(side_effect=AssertionError('Completed abort must not reread live epoch'))
                with self.assertRaises(ValueError):
                    self.agent.recognize_aborts(store, journal, {POD: values[1]}, kube, current,
                        self.models, epoch_reader=reader)
                reader.assert_not_called(); self.assertEqual(kube.pod_reads, [])

    def test_unconsumed_abort_still_requires_its_original_fresh_epoch_after_maintenance(self):
        from types import SimpleNamespace
        values = self.abort_fixture()
        current = replace(values[3], driver_generation='ffffffff-ffff-4fff-8fff-ffffffffffff')
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); state.chmod(0o700)
            store = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
            store.synchronize([values[1]]); journal = SimpleNamespace(read=lambda uid: None)
            with self.assertRaisesRegex(ValueError, 'Unchanged healthy typed abort epoch'):
                self.agent.recognize_aborts(store, journal, {POD: values[1]}, self.fake_authority(values),
                    current, self.models)
            self.assertIsNone(store.abort_record(POD))

    def test_absent_without_proof_is_not_abort_and_orphan_proof_blocks(self):
        from types import SimpleNamespace
        values = self.abort_fixture(); journal = SimpleNamespace(read=lambda uid: None)
        for orphan in (False, True):
            with self.subTest(orphan=orphan), tempfile.TemporaryDirectory() as temporary:
                state = Path(temporary); state.chmod(0o700)
                store = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
                store.synchronize([values[1]])
                kube = self.fake_authority(values, abort=False, record=orphan)
                if orphan:
                    with self.assertRaises(ValueError): self.recognize(store, journal, values, kube)
                else: self.assertEqual(self.recognize(store, journal, values, kube), set())
                self.assertEqual(kube.pod_reads, [])
                self.assertEqual(list((state / 'pre-gate-aborts').iterdir()), [])

    def test_recognized_abort_requires_original_proof_and_private_tombstone(self):
        from types import SimpleNamespace
        for change in ('missing-abort', 'replaced-abort', 'missing-ledger-proof', 'missing-tombstone'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                state = Path(temporary); state.chmod(0o700)
                values = self.abort_fixture(); store = self.agent.EnrollmentStore(state, self.models, trusted_uid=os.getuid())
                store.synchronize([values[1]]); journal = SimpleNamespace(read=lambda uid: None)
                self.assertEqual(self.recognize(store, journal, values, self.fake_authority(values)), {POD})
                if change == 'replaced-abort':
                    values[0]['metadata']['uid'] = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
                if change == 'missing-tombstone': (state / 'pre-gate-aborts' / (POD + '.json')).unlink()
                kube = self.fake_authority(values, pod={'metadata': {'uid': 'new-peer'}},
                    abort=change != 'missing-abort', record=change != 'missing-ledger-proof')
                with self.assertRaises(ValueError): self.recognize(store, journal, values, kube)

    def new_enrollment(self, digit, pod_uid, *, actual_spec=None):
        cm = copy.deepcopy(self.cm); value = copy.deepcopy(self.enrollment)
        value.update(binding_id=digit * 60, attempt=pod_uid)
        value['intent']['pod_uid'] = pod_uid
        if actual_spec is not None:
            value['intent']['spec_sha256'] = hashlib.sha256(canonical_json(actual_spec).encode()).hexdigest()
        cm['metadata'].update(name='cps-native-enrollment-' + value['binding_id'][:40], uid=pod_uid,
            labels={'cps.compute/native-binding': value['binding_id']})
        cm['data']['enrollment.json'] = json.dumps(value)
        return cm, self.check(cm)

    def run_cpu_fixture(self, *, changed_epoch=False):
        from contextlib import nullcontext, redirect_stdout
        from io import StringIO
        from types import SimpleNamespace
        from unittest.mock import patch
        old_two_cm, old_two = self.new_enrollment('b', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb')
        spec = {'nodeName': 'k3s-wk-gpu2',
            'initContainers': [{'name': 'cps-native-cap-gate', 'image': 'example.test/gate@sha256:' + 'a' * 64}],
            'containers': [{'name': 'notebook', 'image': 'example.test/notebook@sha256:' + 'b' * 64}]}
        new_uid = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
        new_cm, new = self.new_enrollment('c', new_uid, actual_spec=spec)
        one, two = self.abort_fixture(), self.abort_fixture(old_two)
        # Keep distinct actual ConfigMap UIDs, not only distinct payloads.
        two[0]['metadata']['uid'] = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'
        two_record = json.loads(two[2]['data']['state.json'])['allocations']['b' * 60]
        two_record['pre_gate_abort']['configmap_uid'] = two[0]['metadata']['uid']
        state = json.loads(one[2]['data']['state.json']); state['allocations']['b' * 60] = two_record
        state['allocations']['c' * 60] = dict(copy.deepcopy(new['enrollment']), state='enrolled')
        one[2]['data']['state.json'] = canonical_json(state)
        maps = {one[0]['metadata']['name']: one[0], two[0]['metadata']['name']: two[0],
            'cps-native-gpu-allocations': one[2]}
        pod = {'metadata': {'uid': new_uid, 'name': new['enrollment']['name'], 'namespace': 'jupyterhub'},
            'spec': spec, 'status': {'phase': 'Running'}}
        pod_reads, reconciled, cleanup_calls, created, records = [], [], [], [], {}
        def get_pod(intent):
            pod_reads.append(intent.pod_uid)
            return pod if intent.pod_uid == new_uid else None
        def configmap(namespace, name):
            self.assertEqual(namespace, self.config['authority_namespace'])
            return maps.get(name)
        kube = SimpleNamespace(node=lambda name: {'metadata': {'name': name, 'uid': NODE}},
            enrollments=lambda ns: [self.cm, old_two_cm, new_cm], configmap=configmap, pod=get_pod,
            delete=lambda *args: self.fail('Abort must not delete Pods'),
            create_configmap=lambda *args: created.append(args))
        journal = SimpleNamespace(locked=lambda: nullcontext(), records=lambda: list(records.values()),
            read=lambda uid: records.get(uid), write=lambda record: self.fail('Abort cannot invent native journal'))
        class Controller:
            def __init__(inner, backend, actual_journal, enabled):
                self.assertIs(actual_journal, journal); self.assertTrue(enabled)
            def reconcile(inner, intent):
                reconciled.append(intent.pod_uid)
                self.assertEqual(intent.pod_uid, new_uid)
                return SimpleNamespace(state='sealed')
            def cleanup(inner, intent):
                cleanup_calls.append(intent.pod_uid); self.fail('No native cleanup for never-gated attempts')
        qualification = SimpleNamespace(cri_reader=lambda *args: None, gpu_clients=lambda *args: (),
            health=lambda *args, **kwargs: self.fail('No driver probe in CPU fixture'),
            awaiting_first_gate=lambda pod, intent: False)
        bundle = (SimpleNamespace(QualificationNodeBackend=lambda *args, **kwargs: object()), qualification,
            {'models': self.models, 'manual': object(), 'health': object()})
        epoch = one[3]
        second_epoch = self.models.DriverEpoch(NODE, epoch.boot_id, 'ffffffff-ffff-4fff-8fff-ffffffffffff', GPU)
        store_class = self.agent.EnrollmentStore
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary); state_root.chmod(0o700); output = StringIO()
            config = copy.deepcopy(self.config); config['pool']['max_workspaces'] = 1
            with patch.object(self.agent, 'EnrollmentStore', side_effect=lambda path, models:
                    store_class(path, models, trusted_uid=os.getuid())), \
                    patch.object(self.models, 'PrivateJournal', return_value=journal), \
                    patch.object(self.models, 'NativeCapController', Controller), \
                    patch.object(self.models, 'CapIdentity', side_effect=AssertionError('No native identity for abort')), \
                    patch.object(self.agent, 'abort_current_epoch', return_value=epoch,
                        side_effect=[epoch, second_epoch] if changed_epoch else None), \
                    redirect_stdout(output):
                if changed_epoch:
                    with self.assertRaisesRegex(ValueError, 'epoch changed'):
                        self.agent.run(config, bundle, state_root, kube, object(), iterations=1,
                            interval=0, crictl='unused', cri_socket='unused')
                else:
                    self.agent.run(config, bundle, state_root, kube, object(), iterations=1,
                        interval=0, crictl='unused', cri_socket='unused')
            self.assertFalse((state_root / 'journal').exists())
            self.assertEqual(len(list((state_root / 'pre-gate-aborts').glob('*.json'))), 0 if changed_epoch else 2)
            self.assertEqual(cleanup_calls, []); self.assertEqual(created, [])
            events = [json.loads(line) for line in output.getvalue().splitlines()]
        return events, reconciled, pod_reads, new_uid

    def test_two_old_aborts_do_not_consume_capacity_or_reconcile_while_new_enrollment_runs(self):
        events, reconciled, pod_reads, new_uid = self.run_cpu_fixture()
        self.assertEqual(reconciled, [new_uid])
        self.assertEqual({event['pod_uid']: event['state'] for event in events},
            {POD: 'pre-gate-aborted', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb': 'pre-gate-aborted', new_uid: 'sealed'})
        self.assertEqual(pod_reads.count(POD), 1)
        self.assertTrue(all(event['production_qualified'] is False for event in events))

    def test_epoch_change_fences_run_before_any_native_reconciliation(self):
        events, reconciled, pod_reads, new_uid = self.run_cpu_fixture(changed_epoch=True)
        self.assertEqual(events, []); self.assertEqual(reconciled, [])

if __name__ == '__main__': unittest.main()

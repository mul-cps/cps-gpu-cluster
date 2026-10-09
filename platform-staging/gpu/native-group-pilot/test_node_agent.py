import copy
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
        record = SimpleNamespace(state=state, intent=intent, identity=object())
        class Backend:
            def check_cleanup(inner, identity):
                return SimpleNamespace(pod_uid=None, live_tasks=tasks, gpu_clients=clients,
                                       cgroup_exists=True, descendants_supported=True)
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

if __name__ == '__main__': unittest.main()

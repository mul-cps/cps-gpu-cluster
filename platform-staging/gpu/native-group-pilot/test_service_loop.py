"""CPU integration through the real source-pinned controller and host adapter."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import node_agent as agent
from test_node_agent import fixtures

HERE = Path(__file__).resolve().parent
QUALIFICATION = HERE.parent / 'qualification' / 'native-cap-controller'


class ServiceLoopTest(unittest.TestCase):
    def setUp(self):
        source = agent.snapshot_sources()
        self.models = agent.load_models_from_snapshot()
        adapter = agent.load_source('node_backend', source['node_backend.py'].encode(),
                                    agent.SOURCE_PINS['node_backend.py'], 'node_backend.py')
        qualification = agent.load_source('poll', source['poll.py'].encode(),
                                          agent.SOURCE_PINS['poll.py'], 'poll.py')
        manual = agent.load_source('_service_test_manual', source['pod_cap.py'].encode(),
                                   agent.SOURCE_PINS['pod_cap.py'], 'pod_cap.py')
        spec = importlib.util.spec_from_file_location('_existing_node_fixture', QUALIFICATION / 'test_node_backend.py')
        test_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(test_module)
        test_module.NodeBackendTests.m = self.models
        test_module.NodeBackendTests.manual = manual
        fixture = test_module.NodeBackendTests('test_inert_cli_needs_no_modules_credentials_or_driver')
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        config, enrollment, cm = fixtures()
        config['pool'].update(node_uid=fixture.intent.node_uid, gpu_uuid=fixture.intent.gpu_uuid)
        fixture.pod['metadata']['namespace'] = 'jupyterhub'
        fixture.cri['status']['labels']['io.kubernetes.pod.namespace'] = 'jupyterhub'
        for container in fixture.pod['spec']['initContainers'] + fixture.pod['spec']['containers']:
            container['image'] = 'ghcr.io/cps/runtime@sha256:' + 'f' * 64
        from cps_compute.native_gpu_runtime import GPU_IDENTITY_SOURCE
        fixture.pod['spec']['initContainers'].insert(1, {
            'name':'cps-native-device-identity', 'image':fixture.pod['spec']['containers'][0]['image'],
            'command':['python','-I','-S','-c',GPU_IDENTITY_SOURCE], 'args':[fixture.intent.gpu_uuid],
            'env':[{'name':'NVIDIA_VISIBLE_DEVICES','value':fixture.intent.gpu_uuid},
                   {'name':'CUDA_VISIBLE_DEVICES','value':'0'}]})
        spec_sha = hashlib.sha256(json.dumps(fixture.pod['spec'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        intent = dict(fixture.intent.to_dict(), namespace='jupyterhub', spec_sha256=spec_sha,
                      policy_hash=config['policy_hash'])
        enrollment.update({key: intent[key] for key in ('namespace','name','node','node_uid','gpu_uuid','cap_mib','policy_hash')})
        enrollment['intent'] = intent
        cm['data']['enrollment.json'] = json.dumps(enrollment)
        self.intent = self.models.CapIntent(**intent)
        self.config, self.enrollment, self.cm = config, enrollment, cm
        class API:
            def __init__(inner): inner.cleanup = None; inner.created = 0
            def node(inner, name): return fixture.node
            def pod(inner, intent): return fixture.pod
            def enrollments(inner, namespace): return [cm]
            def delete(inner, intent): fixture.deleted.append(intent.pod_uid)
            def configmap(inner, namespace, name):
                return inner.cleanup if inner.cleanup is not None and inner.cleanup['metadata']['name'] == name else None
            def create_configmap(inner, namespace, value):
                if inner.cleanup is not None: raise agent.Conflict()
                inner.created += 1; inner.cleanup = copy.deepcopy(value)
                inner.cleanup['metadata']['uid'] = '66666666-6666-4666-8666-666666666666'
                return inner.cleanup
        self.api = API()
        def backend(models, manual, **kwargs):
            return adapter.QualificationNodeBackend(models, manual, proc_root=fixture.proc,
                cgroup_root=fixture.cg, trusted_uid=os.getuid(), **kwargs)
        self.bundle = (SimpleNamespace(QualificationNodeBackend=backend),
            SimpleNamespace(awaiting_first_gate=qualification.awaiting_first_gate,
                cri_reader=lambda *a: lambda intent: fixture.cri, gpu_clients=lambda _: fixture.clients,
                health=lambda *a, **kw: True), {'models': self.models, 'manual': manual, 'health': None, 'cdi': SimpleNamespace(observe_current_cdi=lambda gpu: {'mapping':gpu})})
        self.real_store = agent.EnrollmentStore
        self.output = io.StringIO()

    def run_loop(self, iterations=1, between=None):
        with patch.object(agent, 'EnrollmentStore', side_effect=lambda *a: self.real_store(*a, trusted_uid=os.getuid())), \
                patch.object(agent.time, 'sleep', side_effect=between), \
                patch.object(agent, 'abort_current_epoch', return_value=self.models.DriverEpoch(
                    self.intent.node_uid,
                    (self.fixture.proc/'sys/kernel/random/boot_id').read_text().strip(),
                    (self.fixture.state/'authority/driver-generation').read_text().strip(),self.intent.gpu_uuid)), \
                patch('sys.stdout', self.output):
            agent.run(self.config, self.bundle, self.fixture.state, self.api, self.fixture.driver,
                      iterations=iterations, interval=0.1, crictl='cpu-injected', cri_socket='cpu-injected')

    def test_pending_sealed_restart_terminal_absent_then_busy_peer_tombstone(self):
        def gate_started(_):
            self.assertIsNone(self.fixture.journal.read(self.intent.pod_uid))
            self.assertEqual(self.fixture.driver.writes, [])
            self.fixture.pod['status']['initContainerStatuses'] = [{'name': 'cps-native-cap-gate',
                'restartCount': 0, 'state': {'running': {'startedAt': '2026-10-09T16:00:00Z'}}}]
        self.run_loop(iterations=2, between=gate_started)
        self.assertEqual(self.fixture.journal.read(self.intent.pod_uid).state, 'sealed')
        writes = list(self.fixture.driver.writes)
        self.run_loop()  # Restart retains the exact already-sealed transaction.
        self.assertEqual(self.fixture.driver.writes, writes)
        self.fixture.stop(); self.run_loop()
        self.assertEqual(self.fixture.journal.read(self.intent.pod_uid).state, 'cleaned')
        self.assertIsNone(self.api.cleanup)  # Terminal still visible is insufficient.
        self.fixture.pod = None; self.run_loop()
        self.assertEqual(self.api.created, 1)
        self.assertEqual(json.loads(self.api.cleanup['data']['receipt.json'])['intent'], self.enrollment['intent'])
        self.fixture.pod = {'metadata': {'uid': '77777777-7777-4777-8777-777777777777'}, 'spec': {}}
        self.fixture.clients = {901}  # New workload may now use the old name/GPU.
        self.run_loop()
        self.assertEqual(self.api.created, 1)
        self.assertEqual(self.fixture.deleted, [])

    def test_no_journal_and_absent_pod_retains_allocation_without_cleanup(self):
        self.fixture.pod = None; self.run_loop()
        self.assertIsNone(self.fixture.journal.read(self.intent.pod_uid))
        self.assertIsNone(self.api.cleanup)
        self.assertIn('blocked-absent-without-native-journal', self.output.getvalue())

    def test_actual_spec_image_or_node_drift_blocks_before_cap(self):
        self.fixture.pod['spec']['containers'][0]['image'] = 'runtime:latest'
        with self.assertRaises(ValueError): self.run_loop()
        self.assertEqual(self.fixture.driver.writes, [])
        self.assertIsNone(self.api.cleanup)

    def test_wrong_cdi_mapping_prevents_any_cap_write_or_gate_release(self):
        self.fixture.pod['status']['initContainerStatuses'] = [{'name':'cps-native-cap-gate',
            'restartCount':0,'state':{'running':{'startedAt':'2026-10-09T16:00:00Z'}}}]
        self.bundle[2]['cdi'].observe_current_cdi = lambda gpu: (_ for _ in ()).throw(ValueError('Stale CDI'))
        with self.assertRaises(ValueError): self.run_loop()
        self.assertEqual(self.fixture.driver.writes, [])
        self.assertIsNone(self.fixture.journal.read(self.intent.pod_uid))
        self.assertIsNone(self.api.cleanup)

    def test_cdi_change_after_apply_keeps_cap_but_never_publishes_gate(self):
        self.fixture.pod['status']['initContainerStatuses'] = [{'name':'cps-native-cap-gate',
            'restartCount':0,'state':{'running':{'startedAt':'2026-10-09T16:00:00Z'}}}]
        reads = []
        def observation(gpu):
            reads.append(gpu)
            if len(reads)>2: raise ValueError('Stale CDI before seal')
            return {'mapping':gpu}
        self.bundle[2]['cdi'].observe_current_cdi = observation
        with self.assertRaises(ValueError): self.run_loop()
        record=self.fixture.journal.read(self.intent.pod_uid)
        self.assertEqual(record.state,'sealed')  # Journal precedes actual gate-file publication.
        self.assertEqual(len(self.fixture.driver.writes),2)
        self.assertEqual(list((self.fixture.state/'receipts').iterdir()), [])
        self.assertIsNone(self.api.cleanup)


if __name__ == '__main__': unittest.main()

"""Offline safety and observation contracts; no Kubernetes requests."""
import asyncio
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

PATH = Path(__file__).resolve().parents[2] / 'platform-staging/jobset/cpu-controller/qualify.py'
spec = importlib.util.spec_from_file_location('cpu_controller_qualify', PATH)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def packet(tmp):
    namespace = 'cps-jobset-qa-' + 'a' * 16
    image = 'fixture.invalid/python@sha256:' + 'a' * 64
    catalog = {'version': 'fixture', 'trusted': {'schedulerName': 'kai-scheduler', 'namespace': namespace, 'jobsets': {
        'namespace': namespace, 'command': ['python'], 'maxWorkers': 2, 'maxRetries': 2,
        'ttlSecondsAfterFinished': 600, 'checkpointClaims': {}}},
        'workloadScheduling': {'batch': {'queue': 'cps-batch', 'priorityClassName': 'cps-batch'}},
        'profiles': {'cpu': {'kind': 'batch', 'enabled': True, 'gpu': '0', 'cpu': '250m',
                            'memory': '128Mi', 'images': [image]}},
        'distributedQualification': {'qualified': True, 'policyVersion': 'fixture',
                                    'evidence': ['synthetic-cpu-controller-fixture-only']}}
    path = Path(tmp) / 'policy.json'; path.write_text(json.dumps(catalog))
    return {'version': 1, 'enabled': True, 'namespace': namespace, 'image': image, 'profile': 'cpu',
            'timeoutSeconds': 30, 'cleanupIntervalSeconds': 1, 'context': 'reviewed-fixture-context',
            'policyPath': str(path), 'policySha256': hashlib.sha256(path.read_bytes()).hexdigest()}, catalog


class Preflight(unittest.TestCase):
    def test_inert_has_no_sdk_or_cluster_imports(self):
        import subprocess, sys
        result = subprocess.run([sys.executable, '-I', str(PATH)], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), {'enabled': False, 'api_calls': False})

    def test_scope_and_hash_fail_before_execution(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p, c = packet(tmp)
            self.assertEqual(m.validate(p), c)
            for key, value in [('namespace', 'cps-workflows'), ('namespace', 'default'), ('image', 'python:latest'),
                               ('timeoutSeconds', 301), ('cleanupIntervalSeconds', True),
                               ('policySha256', '0' * 64), ('enabled', False)]:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    m.validate({**p, key: value})
            for field, value in [('gpu', {'mode': 'exclusive', 'count': 1}), ('cpu', '2'), ('memory', '4Gi')]:
                bad = copy.deepcopy(c); bad['profiles']['cpu'][field] = value
                path = Path(p['policyPath']); path.write_text(json.dumps(bad))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    m.validate({**p, 'policySha256': hashlib.sha256(path.read_bytes()).hexdigest()})

    def test_real_sdk_manifest_matches_failsafe_contract(self):
        from cps_compute.gateway import Identity
        from cps_compute.jobsets import JobSetLauncher
        from cps_compute.policy import Policy
        root = PATH.parents[3]
        catalog = json.loads((root / 'compute-policy/generated/policy.json').read_text())
        namespace = 'cps-jobset-qa-' + 'a' * 16
        catalog['trusted']['namespace'] = namespace
        catalog['trusted']['jobsets'].update(namespace=namespace, maxWorkers=2, maxRetries=2)
        catalog['distributedQualification'] = {'qualified': True, 'policyVersion': catalog['version'],
                                              'evidence': ['synthetic-cpu-controller-fixture-only']}
        profile = catalog['profiles']['batch-cpu']
        profile.update(enabled=True, cpu='250m', memory='128Mi', images=['fixture.invalid/python@sha256:' + 'a' * 64])
        catalog.pop('policyHash', None)
        catalog['approvedImages'] = profile['images']
        p = {'namespace': namespace, 'image': profile['images'][0]}
        launcher = JobSetLauncher(None, Policy(catalog))
        manifest = launcher.generate({'profile': 'batch-cpu', 'project': 'synthetic-cpu-fixture',
            'workers': 2, 'args': ['-c', m.CODE], 'walltime': 60},
            Identity('synthetic-cpu-fixture', {'batch-cpu'}, {'synthetic-cpu-fixture'}, [], {}, []),
            idempotency_key=namespace)
        m.validate_manifest(manifest, p)

    def test_fixed_worker_refuses_device_exposure_without_opening_devices(self):
        import subprocess, sys
        # Replace only sleep so this exact checked-in code can run offline.
        code = m.CODE.replace('time.sleep(10)', 'time.sleep(0)')
        for devices in [[], ['/dev/nvidia0'], ['/dev/kfd'], ['/dev/dri/renderD128']]:
            setup = 'import glob; glob.glob=lambda pattern: ' + repr(devices) + '; '
            result = subprocess.run([sys.executable, '-I', '-O', '-c', setup + code], capture_output=True, text=True)
            self.assertEqual(result.returncode == 0, not devices)
            self.assertEqual('cps-jobset-cpu-fixture' in result.stdout, not devices)
        self.assertIn('glob.glob(pattern)', m.CODE)
        for pattern in ('/dev/nvidia*', '/dev/kfd', '/dev/dri/renderD*'):
            self.assertIn(pattern, m.CODE)
        self.assertNotIn('open(', m.CODE)

    def test_manifest_forbids_devices_mounts_and_node_placement(self):
        p = {'namespace': 'cps-jobset-qa-' + 'a' * 16, 'image': 'fixture@sha256:' + 'a' * 64}
        container = {'image': p['image'], 'command': ['python'], 'args': ['-c', m.CODE],
                     'resources': {'requests': {'cpu': '250m', 'memory': '128Mi'},
                                   'limits': {'cpu': '250m', 'memory': '128Mi'}}}
        manifest = {'metadata': {'namespace': p['namespace']}, 'spec': {'failurePolicy': {'maxRestarts': 2},
            'replicatedJobs': [{'replicas': 2, 'template': {'spec': {'template': {'spec': {
                'automountServiceAccountToken': False, 'containers': [container]}}}}}]}}
        m.validate_manifest(manifest, p)
        for field in ['volumes', 'initContainers', 'nodeName', 'nodeSelector', 'runtimeClassName', 'hostIPC']:
            bad = copy.deepcopy(manifest); bad['spec']['replicatedJobs'][0]['template']['spec']['template']['spec'][field] = []
            with self.subTest(field=field), self.assertRaises(ValueError):
                m.validate_manifest(bad, p)
        bad = copy.deepcopy(manifest)
        bad['spec']['replicatedJobs'][0]['template']['spec']['template']['spec']['containers'][0]['resources']['limits']['nvidia.com/gpu'] = '1'
        with self.assertRaises(ValueError): m.validate_manifest(bad, p)


class Observation(unittest.IsolatedAsyncioTestCase):
    async def test_only_periodic_timer_cleans_and_retains_tombstone(self):
        from cps_compute.jobsets import TERMINATED
        class Fixture:
            cleaned = False
            async def cleanup(self, **kw): self.cleaned = True
            async def inspect(self, name, uid):
                return {'metadata': {'annotations': {TERMINATED: 'fixture'} if self.cleaned else {}},
                        'spec': {'suspend': self.cleaned}, 'status': {'conditions': [
                            {'type': 'Completed', 'status': 'True'}]}}, 0 if self.cleaned else 2
        fixture = Fixture()
        result = await m.observe(fixture, fixture, 'own', 'uid', .01, 1)
        self.assertTrue(result['tombstone_retained']); self.assertTrue(result['periodic_sweeps'])
        self.assertGreater(result['observed_terminal_to_clean_seconds'], 0)

    async def test_timeout_cancels_timer_and_does_not_report_pass(self):
        class Fixture:
            calls = 0
            async def cleanup(self, **kw): self.calls += 1
            async def inspect(self, name, uid): return {'metadata': {}, 'status': {}}, 2
        fixture = Fixture()
        with self.assertRaises(TimeoutError): await m.observe(fixture, fixture, 'own', 'uid', .01, .05)
        count = fixture.calls; await asyncio.sleep(.03)
        self.assertEqual(fixture.calls, count)

    async def test_periodic_failure_is_not_a_passing_receipt(self):
        class Fixture:
            async def cleanup(self, **kw): raise RuntimeError('fixture cleanup failed')
            async def inspect(self, name, uid): return {'metadata': {}, 'status': {}}, 2
        with self.assertRaises(RuntimeError): await m.observe(Fixture(), Fixture(), 'own', 'uid', .01, .5)

    async def test_retry_injection_requires_current_attempt_running_pod_and_exact_job_uid(self):
        ref = NS(kind='Job', name='own-job', uid='job-uid')
        pod = NS(metadata=NS(annotations={m.ATTEMPT: '1'}, labels={}, deletion_timestamp=None,
                             owner_references=[ref]), status=NS(phase='Running'))
        class Batch:
            patched = []
            uid = 'job-uid'
            def read_namespaced_job(self, *a, **kw): return NS(metadata=NS(uid=self.uid,
                owner_references=[NS(uid='parent')], resource_version='42', deletion_timestamp=None))
            def patch_namespaced_job(self, *a, **kw): self.patched.append((a, kw))
        batch = Batch(); cluster = m.Cluster(None, None, batch, None, 'fixture')
        cluster.observed_pods = [pod]
        self.assertIsNone(await cluster.inject({'status': {'restarts': 0}}, 'parent', 3, set()))
        self.assertIsNone(await cluster.inject({'status': {'restarts': 1}}, 'parent', 3, {1}))
        batch.uid = 'replacement'
        with self.assertRaises(ValueError): await cluster.inject({'status': {'restarts': 1}}, 'parent', 3, set())
        self.assertEqual(batch.patched, [])
        batch.uid = 'job-uid'
        self.assertEqual(await cluster.inject({'status': {'restarts': 1}}, 'parent', 3, set()),
                         {'attempt': 1, 'job_uid': 'job-uid'})
        self.assertEqual(batch.patched[0][0][2], {'metadata': {'uid': 'job-uid', 'resourceVersion': '42'},
                                                'spec': {'activeDeadlineSeconds': 1}})

    async def test_retry_matrix_terminal_and_injection_counts_are_required(self):
        from cps_compute.jobsets import TERMINATED
        for case, failures, expected, restarts in m.SCENARIOS:
            class Fixture:
                injected = 0
                cleaned = False
                async def cleanup(self, **kw):
                    if self.injected == failures: self.cleaned = True
                async def inject(self, obj, uid, maximum, previous):
                    row = {'attempt': self.injected, 'job_uid': 'own-' + str(self.injected)}
                    self.injected += 1
                    return row
                async def inspect(self, name, uid):
                    status = {'restarts': min(self.injected, 2)}
                    if self.injected == failures: status['terminalState'] = expected
                    return {'metadata': {'annotations': {TERMINATED: 'fixture'} if self.cleaned else {}},
                            'spec': {'suspend': self.cleaned}, 'status': status}, 0 if self.cleaned else 2
            fixture = Fixture()
            result = await m.observe(fixture, fixture, 'own', 'uid', .01, 2,
                                     failures=failures, expected=expected, restarts=restarts)
            self.assertEqual(len(result['injected_failures']), failures)
            self.assertEqual(result['terminal_state'], expected)
        class Wrong:
            async def cleanup(self, **kw): pass
            async def inspect(self, *a): return {'status': {'terminalState': 'Failed', 'restarts': 0}}, 0
        with self.assertRaises(ValueError): await m.observe(Wrong(), Wrong(), 'own', 'uid', .01, .5)

    async def test_uid_replacement_and_foreign_children_are_rejected(self):
        class Custom:
            async_dummy = None
            def get_namespaced_custom_object(self, *a, **kw): return {
                'metadata': {'uid': 'owned-parent', 'annotations': {}}}
            def list_namespaced_custom_object(self, *a, **kw): return {'items': []}
        class Jobs:
            def list_namespaced_job(self, *a, **kw): return NS(metadata=NS(_continue=None), items=[
                NS(metadata=NS(uid='foreign', owner_references=[NS(uid='another-parent')]))])
        class Core:
            def list_namespaced_pod(self, *a, **kw): return NS(metadata=NS(_continue=None), items=[])
        cluster = m.Cluster(Custom(), Core(), Jobs(), None, 'fixture')
        with self.assertRaisesRegex(ValueError, 'UID replaced'): await cluster.inspect('name', 'wrong')
        with self.assertRaisesRegex(ValueError, 'Foreign Job'): await cluster.inspect('name', 'owned-parent')

    async def test_observed_ephemeral_container_and_runtime_class_are_rejected(self):
        class Custom:
            def get_namespaced_custom_object(self, *a, **kw):
                return {'metadata': {'uid': 'parent', 'annotations': {}}}
            def list_namespaced_custom_object(self, *a, **kw): return {'items': []}
        class Jobs:
            def list_namespaced_job(self, *a, **kw):
                return NS(metadata=NS(_continue=None), items=[NS(metadata=NS(uid='job', owner_references=[NS(uid='parent')]))])
        class Core:
            spec = None
            def list_namespaced_pod(self, *a, **kw):
                return NS(metadata=NS(_continue=None), items=[NS(spec=self.spec,
                    metadata=NS(owner_references=[NS(uid='job')]))])
        worker = NS(image='pinned', volume_mounts=None, volume_devices=None, env=None, env_from=None,
                    resources=NS(requests={'cpu': '250m', 'memory': '128Mi'}, limits={'cpu': '250m', 'memory': '128Mi'}))
        fields = dict(volumes=None, init_containers=None, ephemeral_containers=None, runtime_class_name=None,
                      node_selector=None, host_ipc=False, host_pid=False, host_network=False,
                      containers=[worker], automount_service_account_token=False)
        core = Core(); core.spec = NS(**fields)
        cluster = m.Cluster(Custom(), core, Jobs(), None, 'fixture', image='pinned')
        await cluster.inspect('own', 'parent')
        for field, value in [('ephemeral_containers', [NS(name='debug')]), ('runtime_class_name', 'nvidia')]:
            core.spec = NS(**{**fields, field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                await cluster.inspect('own', 'parent')

    async def test_namespace_deletion_has_uid_precondition_and_refuses_replacement(self):
        from kubernetes.client.exceptions import ApiException
        class Core:
            uid = 'own'; deleted = None
            def read_namespace(self, *a, **kw):
                if self.deleted: raise ApiException(status=404)
                return NS(metadata=NS(uid=self.uid, labels={m.OWNER: 'true'}))
            def delete_namespace(self, *a, **kw): self.deleted = kw['body']
        core = Core(); cluster = m.Cluster(None, core, None, None, 'fixture'); cluster.uid = 'own'
        core.uid = 'replacement'
        with self.assertRaises(ValueError): await cluster.remove(1)
        self.assertIsNone(core.deleted)
        core.uid = 'own'; await cluster.remove(1)
        self.assertEqual(core.deleted, {'preconditions': {'uid': 'own'}})


if __name__ == '__main__': unittest.main()

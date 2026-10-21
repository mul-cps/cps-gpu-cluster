#!/usr/bin/env python3
"""Bounded disposable CPU controller fixture. No imports with cluster effects by default."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import time

SCENARIOS = (('success', 0, 'Completed', 0), ('recover', 1, 'Completed', 1), ('exhaust', 3, 'Failed', 2))
ATTEMPT = 'jobset.sigs.k8s.io/restart-attempt'
PREFIX = 'cps-jobset-qa-'
OWNER = 'compute.cps.unileoben.ac.at/cpu-controller-fixture'
CODE = ('import glob,time\n'
        'if any(glob.glob(pattern) for pattern in '
        '("/dev/nvidia*","/dev/kfd","/dev/dri/renderD*")):\n'
        '    raise RuntimeError("GPU device exposed to CPU fixture")\n'
        'print("cps-jobset-cpu-fixture", flush=True)\n'
        'time.sleep(10)')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate(packet):
    require(packet.get('enabled') is True and packet.get('version') == 1, 'Explicit version 1 enabled packet required')
    namespace = packet.get('namespace', '')
    require(re.fullmatch(PREFIX + r'[a-f0-9]{16}', namespace), 'Unique disposable fixture namespace required')
    require(re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}', packet.get('image', '')), 'Pinned image required')
    for key, low, high in [('timeoutSeconds', 30, 300), ('cleanupIntervalSeconds', 1, 60)]:
        value = packet.get(key)
        require(type(value) is int and low <= value <= high, 'Bounded ' + key + ' required')
    require(packet['timeoutSeconds'] >= 3 * packet['cleanupIntervalSeconds'], 'Observe at least three cleanup intervals')
    require(isinstance(packet.get('context'), str) and bool(packet['context'].strip()), 'Explicit reviewed Kubernetes context required')
    raw = Path(packet['policyPath']).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == packet.get('policySha256'), 'Exact reviewed fixture policy hash required')
    catalog = json.loads(raw)
    trusted = catalog['trusted']; settings = trusted['jobsets']
    require(trusted['schedulerName'] == 'kai-scheduler' and catalog['workloadScheduling']['batch'] ==
            {'queue': 'cps-batch', 'priorityClassName': 'cps-batch'}, 'Reviewed KAI batch scheduling required')
    require(trusted['namespace'] == settings['namespace'] == namespace, 'Fixture policy namespace differs')
    require(settings['command'] == ['python'] and settings['maxWorkers'] == 2 and settings['maxRetries'] == 2
            and settings['ttlSecondsAfterFinished'] >= packet['timeoutSeconds'] and not settings.get('checkpointClaims'),
            'Two workers, two retries, retained tombstone and no claims required')
    profile = catalog['profiles'][packet['profile']]
    require(profile.get('kind') == 'batch' and profile.get('enabled') is True and profile.get('gpu') in ('0', {'mode': 'none'})
            and profile['cpu'] == '250m' and profile['memory'] == '128Mi' and profile['images'] == [packet['image']] and profile.get('maxAgeSeconds', 3600) >= packet['timeoutSeconds'],
            'Pinned tiny CPU-only batch profile required')
    require(catalog['distributedQualification'].get('qualified') is True
            and catalog['distributedQualification'].get('policyVersion') == catalog['version']
            and catalog['distributedQualification'].get('evidence') == ['synthetic-cpu-controller-fixture-only'],
            'Synthetic fixture qualification evidence required')
    return catalog


def validate_manifest(manifest, packet):
    require(manifest['metadata']['namespace'] == packet['namespace'], 'Generated namespace differs')
    jobs = manifest['spec']['replicatedJobs']
    require(len(jobs) == 1 and jobs[0]['replicas'] == 2 and manifest['spec']['failurePolicy']['maxRestarts'] == 2,
            'Exactly two workers and two retries required')
    pod = jobs[0]['template']['spec']['template']['spec']
    require(not any(key in pod for key in ('volumes', 'initContainers', 'nodeName', 'nodeSelector', 'affinity',
                                         'tolerations', 'hostPID', 'hostIPC', 'hostNetwork', 'runtimeClassName')),
            'No mounts, device runtime, host or node selection allowed')
    require(pod.get('automountServiceAccountToken') is False and len(pod['containers']) == 1,
            'One worker without API token required')
    container = pod['containers'][0]
    require(not any(key in container for key in ('volumeMounts', 'volumeDevices', 'env', 'envFrom')),
            'No device, mount or environment injection allowed')
    require(container['image'] == packet['image'] and container['command'] == ['python']
            and container['args'] == ['-c', CODE]
            and container['resources'] == {'requests': {'cpu': '250m', 'memory': '128Mi'},
                                           'limits': {'cpu': '250m', 'memory': '128Mi'}},
            'Exact bounded CPU worker required')


async def periodic(launcher, interval, samples, stop):
    """A running timer owns sweeps; observation never invokes cleanup."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), interval)
        except asyncio.TimeoutError:
            start = time.monotonic()
            await launcher.cleanup(max_items=100)
            samples.append({'start': start, 'end': time.monotonic()})


async def observe(launcher, cluster, name, uid, interval, timeout, *, failures=0, expected='Completed', restarts=0):
    """Require real completion followed by timer-driven cleanup and a retained tombstone."""
    from cps_compute.jobsets import TERMINATED
    start = time.monotonic(); terminal_at = None; ticks = []; injections = []; stop = asyncio.Event()
    timer = asyncio.create_task(periodic(launcher, interval, ticks, stop))
    try:
        async with asyncio.timeout(timeout):
            while True:
                if timer.done():
                    timer.result()
                    raise RuntimeError('Periodic cleanup unexpectedly stopped')
                obj, children = await cluster.inspect(name, uid)
                conditions = obj.get('status', {}).get('conditions', [])
                terminal = obj.get('status', {}).get('terminalState') or next((c['type'] for c in conditions
                    if c.get('status') == 'True' and c.get('type') in ('Completed', 'Failed')), None)
                if terminal:
                    require(terminal == expected and obj.get('status', {}).get('restarts', 0) == restarts,
                            'Unexpected terminal state or retry count')
                    require(len(injections) == failures, 'Failure injection matrix incomplete')
                    if terminal_at is None:
                        terminal_at = time.monotonic()
                elif failures:
                    injected = await cluster.inject(obj, uid, failures, {row['attempt'] for row in injections})
                    if injected is not None:
                        injections.append(injected)
                if terminal_at is not None and obj.get('spec', {}).get('suspend') is True and TERMINATED in obj['metadata'].get('annotations', {}) and children == 0:
                    require(bool(ticks), 'Timer cleanup receipt required')
                    return {'terminal_state': expected, 'restarts': restarts, 'injected_failures': injections, 'tombstone_retained': True, 'uid_owned_children_remaining': 0,
                            'observed_terminal_to_clean_seconds': time.monotonic() - terminal_at,
                            'elapsed_seconds': time.monotonic() - start, 'periodic_sweeps': ticks}
                await asyncio.sleep(.25)
    finally:
        stop.set()
        await timer


class Cluster:
    def __init__(self, custom, core, batch, network, namespace, account=None, image=None):
        self.custom = custom; self.core = core; self.batch = batch; self.network = network
        self.namespace = namespace; self.uid = None; self.saw_gang = False
        self.account = account; self.image = image; self.observed_child_uids = set(); self.observed_pods = []

    async def create(self):
        # A collision is fatal; never adopt an existing namespace.
        obj = await asyncio.to_thread(self.core.create_namespace, {'metadata': {'name': self.namespace,
            'labels': {OWNER: 'true', 'pod-security.kubernetes.io/enforce': 'restricted'}}}, _request_timeout=10)
        self.uid = obj.metadata.uid
        require(bool(self.uid), 'Observed namespace UID required')
        await asyncio.to_thread(self.network.create_namespaced_network_policy, self.namespace,
            {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': {'name': 'deny-all'},
             'spec': {'podSelector': {}, 'policyTypes': ['Ingress', 'Egress'], 'ingress': [], 'egress': []}}, _request_timeout=10)

        if self.account:
            await asyncio.to_thread(self.core.create_namespaced_service_account, self.namespace,
                {'metadata': {'name': self.account}, 'automountServiceAccountToken': False}, _request_timeout=10)

    async def inject(self, obj, uid, failures, injected):
        attempt = obj.get('status', {}).get('restarts', 0)
        require(type(attempt) is int and 0 <= attempt <= 2, 'Unknown controller restart count')
        if attempt >= failures or attempt in injected:
            return None
        for pod in self.observed_pods:
            metadata = pod.metadata
            seen = (metadata.annotations or {}).get(ATTEMPT, (metadata.labels or {}).get(ATTEMPT))
            if pod.status.phase != 'Running' or metadata.deletion_timestamp or seen != str(attempt):
                continue
            refs = [r for r in (metadata.owner_references or []) if r.kind == 'Job']
            require(len(refs) == 1, 'Running worker lacks unique Job owner')
            ref = refs[0]
            job = await asyncio.to_thread(self.batch.read_namespaced_job, ref.name, self.namespace, _request_timeout=10)
            require(job.metadata.uid == ref.uid and any(r.uid == uid for r in (job.metadata.owner_references or []))
                    and job.metadata.resource_version and not job.metadata.deletion_timestamp,
                    'Observed failure target UID/parent/version changed')
            await asyncio.to_thread(self.batch.patch_namespaced_job, ref.name, self.namespace,
                {'metadata': {'uid': ref.uid, 'resourceVersion': job.metadata.resource_version},
                 'spec': {'activeDeadlineSeconds': 1}}, _request_timeout=10)
            return {'attempt': attempt, 'job_uid': ref.uid}
        return None

    async def inspect(self, name, uid):
        obj = await asyncio.to_thread(self.custom.get_namespaced_custom_object,
            'jobset.x-k8s.io', 'v1alpha2', self.namespace, 'jobsets', name, _request_timeout=10)
        require(obj['metadata']['uid'] == uid, 'JobSet UID replaced')
        jobs = await asyncio.to_thread(self.batch.list_namespaced_job, self.namespace, limit=100, _request_timeout=10)
        pods = await asyncio.to_thread(self.core.list_namespaced_pod, self.namespace, limit=100, _request_timeout=10)
        groups = await asyncio.to_thread(self.custom.list_namespaced_custom_object,
            'scheduling.run.ai', 'v2alpha2', self.namespace, 'podgroups', limit=100, _request_timeout=10)
        require(not getattr(jobs.metadata, '_continue', None) and not getattr(pods.metadata, '_continue', None)
                and not groups.get('metadata', {}).get('continue'), 'Fixture inventory exceeds bound')
        child_uids = self.observed_child_uids | set(json.loads(obj['metadata'].get('annotations', {}).get('compute.cps.unileoben.ac.at/child-uids', '[]')))
        for job in jobs.items:
            require(any(r.uid == uid for r in (job.metadata.owner_references or [])), 'Foreign Job in fixture namespace')
            child_uids.add(job.metadata.uid)
        self.observed_child_uids.update(child_uids)
        self.observed_pods = pods.items
        for pod in pods.items:
            spec = pod.spec
            require(not spec.volumes and not spec.init_containers and not spec.ephemeral_containers
                    and not spec.runtime_class_name and not spec.node_selector
                    and not spec.host_ipc and not spec.host_pid and not spec.host_network
                    and len(spec.containers) == 1 and spec.automount_service_account_token is False,
                    'Observed worker gained mounts, host access or extra containers')
            worker = spec.containers[0]
            require(worker.image == self.image and not worker.volume_mounts and not worker.volume_devices
                    and not worker.env and not worker.env_from and worker.resources.requests == {'cpu': '250m', 'memory': '128Mi'}
                    and worker.resources.limits == {'cpu': '250m', 'memory': '128Mi'}, 'Observed worker resource/image/environment drift')
            require(any(r.uid in child_uids for r in (pod.metadata.owner_references or [])), 'Foreign Pod in fixture namespace')
        for group in groups.get('items', []):
            require(any(r.get('uid') in child_uids | {uid} for r in group['metadata'].get('ownerReferences', [])), 'Foreign PodGroup in fixture namespace')
        self.saw_gang = self.saw_gang or bool(groups.get('items'))
        return obj, len(jobs.items) + len(pods.items) + len(groups.get('items', []))

    async def remove(self, timeout):
        if not self.uid:
            return
        observed = await asyncio.to_thread(self.core.read_namespace, self.namespace, _request_timeout=10)
        require(observed.metadata.uid == self.uid and observed.metadata.labels.get(OWNER) == 'true', 'Namespace ownership changed; cleanup refused')
        await asyncio.to_thread(self.core.delete_namespace, self.namespace,
            body={'preconditions': {'uid': self.uid}}, _request_timeout=10)
        from kubernetes.client.exceptions import ApiException
        async with asyncio.timeout(timeout):
            while True:
                try:
                    await asyncio.to_thread(self.core.read_namespace, self.namespace, _request_timeout=10)
                except ApiException as exc:
                    if exc.status == 404:
                        return
                    raise
                await asyncio.sleep(.5)


async def execute(packet, catalog):
    from kubernetes import client, config
    from cps_compute.gateway import Identity
    from cps_compute.jobsets import JobSetLauncher
    from cps_compute.policy import Policy
    import inspect
    sdk_hash = hashlib.sha256(Path(inspect.getfile(JobSetLauncher)).read_bytes()).hexdigest()
    policy = Policy(catalog)
    launcher = JobSetLauncher(None, policy)
    identity = Identity('synthetic-cpu-fixture', {packet['profile']}, {'synthetic-cpu-fixture'}, [], {}, [])
    body = {'profile': packet['profile'], 'project': 'synthetic-cpu-fixture', 'workers': 2,
            'args': ['-c', CODE], 'walltime': packet['timeoutSeconds']}
    manifest = launcher.generate(body, identity, idempotency_key=packet['namespace'])
    validate_manifest(manifest, packet)
    # No client requests, not even discovery, precede complete offline preflight.
    config.load_kube_config(context=packet['context'])
    # Recreate clients after configuration, which Kubernetes copies at construction.
    custom = client.CustomObjectsApi(); core = client.CoreV1Api(); batch = client.BatchV1Api()
    cluster = Cluster(custom, core, batch, client.NetworkingV1Api(), packet['namespace'], launcher.settings['serviceAccountName'], packet['image'])
    launcher = JobSetLauncher(custom, policy, batch_api=batch, core_api=core)
    cases = []
    try:
        await cluster.create()
        for case, failures, expected, restarts in SCENARIOS:
            key = packet['namespace'] + '-' + case
            cluster.saw_gang = False
            cluster.observed_child_uids.clear()
            created = await launcher(body, identity, idempotency_key=key)
            name = created['metadata']['name']; uid = created['metadata']['uid']
            require(bool(uid), 'Observed JobSet UID required')
            foreign = Identity('other-synthetic-cpu-fixture', {packet['profile']}, {'synthetic-cpu-fixture'}, [], {}, [])
            for operation in (launcher.get, launcher.logs, launcher.terminate):
                try:
                    await operation(name, foreign)
                except PermissionError:
                    pass
                else:
                    raise ValueError('Cross-owner operation was not denied')
            require(not (await launcher.list(foreign))['jobsets'], 'Foreign listing exposed fixture')
            result = await observe(launcher, cluster, name, uid, packet['cleanupIntervalSeconds'],
                                   packet['timeoutSeconds'], failures=failures, expected=expected, restarts=restarts)
            require(cluster.saw_gang, 'No UID-owned KAI gang observed; controller integration unqualified')
            replay = await launcher(body, identity, idempotency_key=key)
            require(replay['metadata']['uid'] == uid and replay['spec'].get('suspend') is True, 'Idempotent tombstone replay differs')
            cases.append({'case': case, 'jobset_uid': uid, 'idempotent_tombstone_replay': True,
                          'uid_owned_kai_gang_observed': True, 'cross_owner_operations_denied': True, **result})
    finally:
        await cluster.remove(packet['timeoutSeconds'])
    return {'state': 'synthetic-cpu-controller-passed', 'production_oauth_qualified': False,
            'production_cleanup_latency_qualified': False, 'gpu_qualified': False,
            'synthetic_retry_matrix_qualified': True, 'production_hub_authentication_qualified': False,
            'sdk_jobsets_source_sha256': sdk_hash, 'namespace_deleted': True, 'policy_sha256': packet['policySha256'], 'image': packet['image'], 'cases': cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='REVIEWED_PACKET')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'enabled': False, 'api_calls': False})); return 0
    try:
        packet = json.loads(Path(args.execute).read_bytes()); catalog = validate(packet)
        print(json.dumps(asyncio.run(execute(packet, catalog)), sort_keys=True)); return 0
    except Exception as exc:
        # Do not print API bodies, credentials or private policy contents.
        print(json.dumps({'state': 'failed-or-cleanup-pending', 'error_type': type(exc).__name__})); return 1


if __name__ == '__main__':
    raise SystemExit(main())

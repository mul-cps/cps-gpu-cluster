"""Report declared notebook and compute resources from scoped Kubernetes Pods."""
from collections import Counter
from functools import partial

from storage_exporter import api_list, sample

HUBS = {"cit-jhub": "cit-jhub", "jupyterhub": "cps-jhub"}
COMPUTE = ("cps-workflows", "cps-compute")
SCOPES = (*HUBS.values(), "compute-jobs")
MIB = 1024**2
METRIC = partial(sample, prefix="cps_workload_")


def scope_for(namespace, pod, batch_jobs):
    metadata = pod["metadata"]
    labels = metadata.get("labels", {})
    if namespace in HUBS:
        if labels.get("component") == "singleuser-server" or "hub.jupyter.org/username" in labels:
            return HUBS[namespace]
        return None
    if namespace not in COMPUTE:
        return None
    if labels.get("workflows.argoproj.io/workflow"):
        return "compute-jobs"
    if any(owner["kind"] == "Workflow" or owner["uid"] in batch_jobs
           for owner in metadata.get("ownerReferences", [])):
        return "compute-jobs"
    return None


def gpu_claim(container):
    resources = container.get("resources", {})
    limits = resources.get("limits", {})
    requests = resources.get("requests", {})
    env = {item["name"]: item.get("value", "") for item in container.get("env", [])}
    devices = int(requests.get("nvidia.com/gpu", limits.get("nvidia.com/gpu", "0")))

    def gpu_mib(name):
        value = env.get(name, "0")
        return int(value) * MIB if value.isascii() and value.isdecimal() else 0

    return devices, gpu_mib("NVIDIA_GPU_MEMORY_REQUEST"), gpu_mib("NVIDIA_GPU_MEMORY_LIMIT")


def batch_job_phase(job):
    for condition in job.get("status", {}).get("conditions", []):
        if condition["status"] == "True" and condition["type"] in {"Complete", "Failed", "Suspended"}:
            return condition["type"].lower()
    return "active" if job.get("status", {}).get("active", 0) else "waiting"


def collect():
    totals = {scope: Counter() for scope in SCOPES}
    jobs_by_phase = Counter()
    claims = set()
    for namespace in (*HUBS, *COMPUTE):
        batch_jobs = set()
        if namespace in COMPUTE:
            for job in api_list(f"/apis/batch/v1/namespaces/{namespace}/jobs"):
                meta = job["metadata"]
                if any(owner["kind"] == "CronJob" for owner in meta.get("ownerReferences", [])):
                    continue
                batch_jobs.add(meta["uid"])
                jobs_by_phase[batch_job_phase(job)] += 1
        for pod in api_list(f"/api/v1/namespaces/{namespace}/pods"):
            scope = scope_for(namespace, pod, batch_jobs)
            phase = pod.get("status", {}).get("phase")
            if not scope or phase not in {"Running", "Pending", "Unknown"}:
                continue
            spec, meta = pod["spec"], pod["metadata"]
            binding = "bound" if spec.get("nodeName") else "unbound"
            count = totals[scope]
            count["pods_" + binding] += 1
            count["pods_running"] += int(phase == "Running")
            for container in spec.get("containers", []):
                devices, request, limit = gpu_claim(container)
                count[f"gpu_device_slots_{binding}"] += devices
                count[f"gpu_nonfractional_slots_{binding}"] += devices if not (request or limit) else 0
                count[f"fractional_vram_request_bytes_{binding}"] += request
                count[f"fractional_vram_limit_bytes_{binding}"] += limit
                count[f"fractional_containers_{binding}"] += int(bool(request or limit))
            for volume in spec.get("volumes", []):
                pvc = volume.get("persistentVolumeClaim")
                if pvc and binding == "bound":
                    claims.add((scope, namespace, pvc["claimName"]))
            yield METRIC("pod", 1, scope=scope, namespace=namespace, pod=meta["name"], placement=binding)
    for scope, count in totals.items():
        for name in ("pods_running", "pods_bound", "pods_unbound"):
            yield METRIC(name, count[name], scope=scope)
        for state in ("bound", "unbound"):
            for kind in ("gpu_device_slots", "gpu_nonfractional_slots", "fractional_vram_request_bytes",
                         "fractional_vram_limit_bytes", "fractional_containers"):
                yield METRIC(kind, count[f"{kind}_{state}"], scope=scope, placement=state)
    for phase in ("active", "waiting", "complete", "failed", "suspended"):
        yield METRIC("batch_jobs", jobs_by_phase[phase], phase=phase)
    for scope, namespace, name in sorted(claims):
        yield METRIC("bound_claim", 1, scope=scope, namespace=namespace, persistentvolumeclaim=name)

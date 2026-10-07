#!/usr/bin/env python3
"""Offline renderer: reviewed inputs produce suspended Jobs, never execution."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import uuid

HERE = Path(__file__).resolve().parent
NODE = "k3s-wk-gpu2"
NAMESPACE = "cps-gpu-qualification"
IMAGE = ("ghcr.io/mul-cps/cps-compute:qualification-a7abe7d13465a8ea@sha256:"
         "f107b407f3e6c9218a4a9b5ec4df9f0ea013f4abd0a177e474013ff6b682c893")
HAMI_REVISION = "5496322f2fb3e71bf1eca014fba3c9bc59ab8ffd"
HAMI_PATH = "/usr/local/vgpu/libvgpu.so"
CACHE_KEY = "CUDA_DEVICE_MEMORY_SHARED_CACHE"
CACHE_PATH = "/tmp/cps-workspace-usage.cache"
INITIALIZE = '''import json,os,stat
path='/cache-root/usage.cache'
assert os.getuid()==10001
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
try:
 s=os.fstat(fd)
 assert stat.S_ISREG(s.st_mode) and s.st_uid==10001 and s.st_size==0
 print(json.dumps({'event':'workspace-cache-created','device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid}),flush=True)
finally:os.close(fd)
'''
OPERATOR_GATE = '''import json,os,pathlib,sys,time
assert os.getuid()==10001
proof=json.loads(pathlib.Path('/probe/preflight.json').read_text())
expected={'runtimeReviewed':True,'role':sys.argv[1],'podUid':os.environ['FIXTURE_POD_UID'],
 'runId':proof['runId'],'nodeUid':proof['nodeUid'],
 'gpuUuid':proof['gpuUuid'],'hamiSha256':proof['hami']['sha256'],'probeSha256':sys.argv[2]}
marker=pathlib.Path('/cache-root/operator-approved.json')
deadline=time.monotonic()+60
while time.monotonic()<deadline:
 if marker.exists():
  assert marker.stat().st_uid==10001 and marker.stat().st_size<=4096
  assert json.loads(marker.read_text())==expected, 'Operator review marker mismatch'
  print(json.dumps({'event':'operator-runtime-review-released','role':sys.argv[1]}),flush=True)
  sys.exit(0)
 time.sleep(0.2)
raise SystemExit('Final injected Pod runtime review was not released within 60 seconds')
'''


def validate_preflight(value, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    observed = dt.datetime.fromisoformat(value["observedAt"].replace("Z", "+00:00"))
    if observed.tzinfo is None or not 0 <= (now - observed).total_seconds() <= 900:
        raise ValueError("Fresh timezone-aware inventory within 15 minutes is required")
    node = value["node"]
    if node["name"] != NODE:
        raise ValueError("Only the explicitly reviewed GPU2 node may be targeted")
    if str(uuid.UUID(node["uid"])) != node["uid"]:
        raise ValueError("Canonical observed node UID is required")
    if value["image"] != IMAGE:
        raise ValueError("Only the existing trusted immutable qualification image is allowed")
    hami = value["hami"]
    if (hami["referenceSourceRevision"] != HAMI_REVISION or hami["libraryPath"] != HAMI_PATH
            or hami["sourceRevisionVerified"] is not False
            or not re.fullmatch(r"[a-f0-9]{64}", hami["sha256"])):
        raise ValueError("Observed binary SHA256 and explicitly unverified reference source revision required")
    target = value["targetGpuUuid"]
    if not re.fullmatch(r"GPU-[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}", target):
        raise ValueError("Explicit physical GPU UUID required; MIG is excluded")
    entries = [gpu for gpu in value["gpus"] if gpu["uuid"] == target]
    if len(entries) != 1 or type(entries[0]["index"]) is not int or entries[0]["index"] < 0:
        raise ValueError("Target UUID must be observed exactly once on GPU2 with an index")
    if value["activeGpuPods"] != []:
        raise ValueError("Target node has active GPU workloads or reservations")
    servers = [server for server in value["mpsServers"]
               if server.get("gpuUuid") == target and server.get("ready") is True
               and type(server.get("pid")) is int and server["pid"] > 0]
    if not servers:
        raise ValueError("An existing Ready MPS server on this exact GPU is required")
    return {"node": NODE, "nodeUid": node["uid"], "gpuUuid": target,
            "gpuIndex": entries[0]["index"], "observedAt": value["observedAt"],
            "image": IMAGE, "existingMpsPids": [s["pid"] for s in servers], "hami": hami}


def render(preflight, run_id, now=None):
    proof = validate_preflight(preflight, now)
    if not re.fullmatch(r"[a-z0-9]{8,16}", run_id):
        raise ValueError("Run ID must be 8-16 lowercase letters or digits")
    name = f"dynamic-cache-{run_id}"
    proof["runId"] = run_id
    source = (HERE / "probe.py").read_text()
    digest = hashlib.sha256(source.encode()).hexdigest()
    base_labels = {"compute.cps.unileoben.ac.at/qualification": "trusted-operator",
                   "compute.cps.unileoben.ac.at/fixture": name,
                   "kai.scheduler/queue": "cps-batch"}
    annotations = {"compute.cps.unileoben.ac.at/qualification-state": "disabled-manual-fixture",
                   "compute.cps.unileoben.ac.at/expected-node-uid": proof["nodeUid"],
                   "compute.cps.unileoben.ac.at/expected-gpu-uuid": proof["gpuUuid"],
                   "compute.cps.unileoben.ac.at/preflight-at": proof["observedAt"],
                   "compute.cps.unileoben.ac.at/fixture-run-id": run_id,
                   "compute.cps.unileoben.ac.at/probe-sha256": digest,
                   "compute.cps.unileoben.ac.at/hami-reference-revision": HAMI_REVISION}
    security = {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                "capabilities": {"drop": ["ALL"]}}
    items = [{"apiVersion": "v1", "kind": "ConfigMap",
              "metadata": {"name": name, "namespace": NAMESPACE,
                           "labels": base_labels, "annotations": annotations},
              "immutable": True,
              "data": {"probe.py": source, "initialize.py": INITIALIZE,
                       "operator-gate.py": OPERATOR_GATE,
                       "preflight.json": json.dumps(proof, sort_keys=True)}}]
    for role in ("peer", "workspace"):
        job_name = f"{name}-{role}"
        pod_annotations = {**annotations, "gpu-fraction-container-name": "main", "gpu-memory": "5120"}
        spec = {"schedulerName": "kai-scheduler", "priorityClassName": "cps-batch",
                "restartPolicy": "Never", "activeDeadlineSeconds": 180,
                "automountServiceAccountToken": False,
                "nodeSelector": {"kubernetes.io/hostname": NODE},
                "securityContext": {"runAsNonRoot": True, "runAsUser": 10001,
                    "runAsGroup": 10001, "fsGroup": 10001,
                    "seccompProfile": {"type": "RuntimeDefault"}},
                "initContainers": [{"name": "initialize-workspace-cache", "image": IMAGE,
                    "command": ["python", "-u", "/probe/initialize.py"],
                    "securityContext": security,
                    "resources": {"requests": {"cpu": "10m", "memory": "32Mi"},
                                  "limits": {"cpu": "100m", "memory": "64Mi"}},
                    "volumeMounts": [{"name": "probe", "mountPath": "/probe", "readOnly": True},
                                     {"name": "workspace-cache", "mountPath": "/cache-root"}]},
                    {"name": "await-operator-runtime-review", "image": IMAGE,
                     "command": ["python", "-u", "/probe/operator-gate.py", role, digest],
                     "securityContext": security,
                     "env": [{"name": "FIXTURE_POD_UID", "valueFrom": {
                         "fieldRef": {"fieldPath": "metadata.uid"}}}],
                     "resources": {"requests": {"cpu": "10m", "memory": "32Mi"},
                                   "limits": {"cpu": "100m", "memory": "64Mi"}},
                     "volumeMounts": [{"name": "probe", "mountPath": "/probe", "readOnly": True},
                                      {"name": "workspace-cache", "mountPath": "/cache-root"}]}],
                "containers": [{"name": "main", "image": IMAGE,
                    "command": ["python", "-u", "/probe/probe.py", role],
                    "securityContext": security,
                    "env": [{"name": CACHE_KEY, "value": CACHE_PATH},
                            {"name": "FIXTURE_POD_UID", "valueFrom": {
                                "fieldRef": {"fieldPath": "metadata.uid"}}},
                            {"name": "FIXTURE_RUN_ID", "value": run_id},
                            {"name": "CUDA_DEVICE_MEMORY_LIMIT", "value": "5120m"},
                            {"name": "EXPECTED_HAMI_SHA256", "value": proof["hami"]["sha256"]},
                            {"name": "EXPECTED_HAMI_REVISION", "value": HAMI_REVISION},
                            {"name": "EXPECTED_GPU_UUID", "value": proof["gpuUuid"]},
                            {"name": "CUDA_MPS_PIPE_DIRECTORY", "value": "/mps/pipe"},
                            {"name": "NVIDIA_DRIVER_CAPABILITIES", "value": "compute,utility"}],
                    "resources": {"requests": {"cpu": "100m", "memory": "128Mi"},
                                  "limits": {"cpu": "1", "memory": "256Mi"}},
                    "volumeMounts": [{"name": "probe", "mountPath": "/probe", "readOnly": True},
                            {"name": "scratch", "mountPath": "/tmp"},
                            {"name": "workspace-cache", "mountPath": CACHE_PATH, "subPath": "usage.cache"},
                            {"name": "mps-pipe", "mountPath": "/mps/pipe"},
                            {"name": "mps-shm", "mountPath": "/dev/shm"}]}],
                "volumes": [{"name": "probe", "configMap": {"name": name, "defaultMode": 292}},
                            {"name": "workspace-cache", "emptyDir": {"sizeLimit": "16Mi"}},
                            {"name": "scratch", "emptyDir": {"sizeLimit": "64Mi"}},
                            {"name": "mps-pipe", "hostPath": {"path": "/run/nvidia/mps/nvidia.com/gpu/pipe", "type": "Directory"}},
                            {"name": "mps-shm", "hostPath": {"path": "/run/nvidia/mps/shm", "type": "Directory"}}]}
        items.append({"apiVersion": "batch/v1", "kind": "Job",
                      "metadata": {"name": job_name, "namespace": NAMESPACE,
                                   "labels": base_labels, "annotations": annotations},
                      "spec": {"suspend": True, "backoffLimit": 0,
                               "activeDeadlineSeconds": 180,
                               "template": {"metadata": {"labels": base_labels,
                                                         "annotations": pod_annotations}, "spec": spec}}})
    return {"apiVersion": "v1", "kind": "List", "items": items}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(HERE.parents[3]):
        raise SystemExit("Store rendered runtime fixtures outside Git")
    result = render(json.loads(args.preflight.read_text()), args.run_id)
    # Exclusive creation keeps an already reviewed artifact from being replaced.
    with args.output.open("x") as destination:
        json.dump(result, destination, indent=2)
        destination.write("\n")
    print(json.dumps({"rendered": True, "suspendedJobs": 2,
                      "executed": False, "productionQualified": False}))

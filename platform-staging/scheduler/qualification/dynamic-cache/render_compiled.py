#!/usr/bin/env python3
"""Offline, suspended 5 GiB fixture using the exact packaged runtime compiler."""
import argparse
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import sys
import types
import zipfile

import render as baseline

HERE = Path(__file__).resolve().parent
NODE, NAMESPACE = baseline.NODE, baseline.NAMESPACE
HAMI_REVISION, HAMI_PATH = baseline.HAMI_REVISION, baseline.HAMI_PATH
CACHE_KEY, CACHE_PATH = baseline.CACHE_KEY, baseline.CACHE_PATH
REVIEWED_GPU_ANNOTATION = baseline.REVIEWED_GPU_ANNOTATION
GPU_UUID_FIELD_PATH = baseline.GPU_UUID_FIELD_PATH
SOURCE_COMMIT = "2f43f59aa319f8a114bae41ff89226018e3e5089"
IMAGE = ("ghcr.io/mul-cps/cps-compute:qualification-2f43f59aa319@sha256:"
         "38dad2077eb1552683cdb54c1ee50ffdf42d63e4a7dcd322f95f9f0236261c04")
WHEEL_SHA256 = "06939b3e4cefc882f419635129e982f46d40f376e9f6b3122e51ab4bed96febe"
MODULE_SHA256 = "93f4e01c3682e52192d43c130073b3daf50c59ea7bd06342971f5f4add0a2b68"
REVIEWED_IDENTITIES = {(10001, 10001), (1000, 1000), (1000, 100)}
PROFILE = {"gpu": {"mode": "shared", "nominalMemoryGiB": 5,
    "qualification": {"mechanism": "kai-hami", "annotations": {"gpu-memory": "5120"}, "resources": {}}}}

OPERATOR_GATE = '''import json,os,pathlib,stat,sys,time
proof=json.loads(pathlib.Path('/probe/preflight.json').read_text())
uid,gid=proof['runtimeIdentity']['uid'],proof['runtimeIdentity']['gid']
assert (uid,gid) in ((10001,10001),(1000,1000),(1000,100))
assert (os.getuid(),os.getgid())==(uid,gid)
cache=pathlib.Path('/cache-root/private/usage.cache').stat(follow_symlinks=False)
assert stat.S_ISREG(cache.st_mode) and (cache.st_uid,cache.st_gid)==(uid,gid)
assert stat.S_IMODE(cache.st_mode)==0o600 and cache.st_nlink==1
expected={'runtimeReviewed':True,'role':sys.argv[1],'podUid':os.environ['FIXTURE_POD_UID'],
 'runId':proof['runId'],'nodeUid':proof['nodeUid'],'uid':uid,'gid':gid,
 'hamiSha256':proof['hami']['sha256'],'probeSha256':sys.argv[2],
 'compilerWheelSha256':proof['compiler']['wheelSha256']}
marker=pathlib.Path('/cache-root/operator-approved.json')
deadline=time.monotonic()+60
while time.monotonic()<deadline:
 if marker.exists():
  info=marker.stat(follow_symlinks=False)
  assert stat.S_ISREG(info.st_mode) and (info.st_uid,info.st_gid)==(uid,gid) and info.st_size<=4096
  assert stat.S_IMODE(info.st_mode)==0o600 and info.st_nlink==1
  actual=json.loads(marker.read_text())
  assert actual.get('gpuUuid') in proof['gpuUuidAllowlist'], 'GPU is outside observed GPU allowlist'
  assert actual==dict(expected,gpuUuid=actual['gpuUuid']), 'Operator review marker mismatch'
  print(json.dumps({'event':'operator-runtime-review-released','role':sys.argv[1],
   'podUid':expected['podUid'],'runId':expected['runId'],'uid':uid,'gid':gid,
   'gpuUuid':actual['gpuUuid'],'probeSha256':sys.argv[2]}),flush=True)
  sys.exit(0)
 time.sleep(0.2)
raise SystemExit('Final injected Pod runtime review was not released within 60 seconds')
'''


def load_compiler(wheel):
    """Load only verified wheel module bytes, without importing editable sources."""
    wheel = Path(wheel)
    content = wheel.read_bytes()
    if hashlib.sha256(content).hexdigest() != WHEEL_SHA256:
        raise ValueError("Only the exact verified compiler wheel is allowed")
    with zipfile.ZipFile(wheel) as archive:
        source = archive.read("cps_compute/gpu_runtime.py")
    if hashlib.sha256(source).hexdigest() != MODULE_SHA256:
        raise ValueError("Runtime module bytes differ from the reviewed package")
    # This exact module is stdlib-only. Avoid executing package __init__ or an
    # editable site-packages copy, and give dataclasses a real module identity.
    name = "_cps_qualification_packaged_gpu_runtime"
    module = types.ModuleType(name)
    module.__file__ = str(wheel.resolve()) + "/cps_compute/gpu_runtime.py"
    sys.modules[name] = module
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def compile_plan(wheel, uid=10001, gid=10001):
    if (uid, gid) not in REVIEWED_IDENTITIES or type(uid) is not int or type(gid) is not int:
        raise ValueError("Only explicitly reviewed workload identities are permitted")
    module = load_compiler(wheel)
    catalog = {"trusted": {"sharedGpuRuntime": {"initializerImage": IMAGE,
        "approvedInitializerImages": [IMAGE], "uid": 10001, "gid": 10001}}}
    settings = module.SharedGpuRuntimeSettings.from_catalog(catalog, uid=uid, gid=gid)
    plan = module.compile_gpu_runtime(copy.deepcopy(PROFILE), settings=settings, container_name="main")
    return asdict(plan)


def validate_preflight(value, now=None):
    if value.get("image") != IMAGE:
        raise ValueError("Only the verified 2f43f59 immutable runtime image is permitted")
    # Reuse unchanged safety checks, substituting only the already-validated
    # image while validating the old fixture's fixed inventory contract.
    proof = baseline.validate_preflight({**value, "image": baseline.IMAGE}, now)
    proof["image"] = IMAGE
    return proof


def render(preflight, run_id, wheel, *, uid=10001, gid=10001, now=None):
    proof = validate_preflight(preflight, now)
    if not re.fullmatch(r"[a-z0-9]{8,16}", run_id):
        raise ValueError("Run ID must be 8-16 lowercase letters or digits")
    plan = compile_plan(wheel, uid, gid)
    proof.update(runId=run_id, runtimeIdentity={"uid": uid, "gid": gid},
        compiler={"sourceCommit": SOURCE_COMMIT, "wheelSha256": WHEEL_SHA256,
                  "moduleSha256": MODULE_SHA256, "image": IMAGE}, runtimePlan=plan)
    source = (HERE / "probe_compiled.py").read_text()
    digest = hashlib.sha256(source.encode()).hexdigest()
    proof["probeSha256"] = digest
    name = f"dynamic-compiled-{run_id}"
    labels = {"compute.cps.unileoben.ac.at/qualification": "trusted-operator",
              "compute.cps.unileoben.ac.at/fixture": name, "kai.scheduler/queue": "cps-batch"}
    annotations = {"compute.cps.unileoben.ac.at/qualification-state": "disabled-manual-fixture",
        "compute.cps.unileoben.ac.at/expected-node-uid": proof["nodeUid"],
        "compute.cps.unileoben.ac.at/initial-preflight-gpu-choice": proof["gpuUuid"],
        "compute.cps.unileoben.ac.at/preflight-at": proof["observedAt"],
        "compute.cps.unileoben.ac.at/fixture-run-id": run_id,
        "compute.cps.unileoben.ac.at/probe-sha256": digest,
        "compute.cps.unileoben.ac.at/compiler-source": SOURCE_COMMIT,
        "compute.cps.unileoben.ac.at/compiler-wheel-sha256": WHEEL_SHA256,
        "compute.cps.unileoben.ac.at/hami-reference-revision": HAMI_REVISION}
    items = [{"apiVersion": "v1", "kind": "ConfigMap", "immutable": True,
        "metadata": {"name": name, "namespace": NAMESPACE, "labels": labels, "annotations": annotations},
        "data": {"probe_compiled.py": source, "operator-gate.py": OPERATOR_GATE,
                 "preflight.json": json.dumps(proof, sort_keys=True)}}]
    security = {**plan["container_security_context"], "readOnlyRootFilesystem": True}
    for role in ("peer", "workspace"):
        env = [{"name": k, "value": v} for k, v in plan["environment"].items()]
        env.extend([{"name": "FIXTURE_POD_UID", "valueFrom": {"fieldRef": {"apiVersion": "v1", "fieldPath": "metadata.uid"}}},
            {"name": "FIXTURE_RUN_ID", "value": run_id}, {"name": "FIXTURE_UID", "value": str(uid)},
            {"name": "FIXTURE_GID", "value": str(gid)}, {"name": "EXPECTED_HAMI_LIMIT_MIB", "value": "5120"},
            {"name": "EXPECTED_HAMI_SHA256", "value": proof["hami"]["sha256"]},
            {"name": "EXPECTED_HAMI_REVISION", "value": HAMI_REVISION},
            {"name": "EXPECTED_GPU_UUID", "valueFrom": {"fieldRef": {"apiVersion": "v1", "fieldPath": GPU_UUID_FIELD_PATH}}}])
        gate = {"name": "await-operator-runtime-review", "image": IMAGE,
            "command": ["python", "-u", "/probe/operator-gate.py", role, digest],
            "securityContext": security,
            "env": [{"name": "FIXTURE_POD_UID", "valueFrom": {"fieldRef": {"apiVersion": "v1", "fieldPath": "metadata.uid"}}}],
            "resources": {"requests": {"cpu": "10m", "memory": "32Mi"}, "limits": {"cpu": "100m", "memory": "64Mi"}},
            "volumeMounts": [{"name": "probe", "mountPath": "/probe", "readOnly": True},
                             {"name": "cps-gpu-cache", "mountPath": "/cache-root"}]}
        spec = {"schedulerName": "kai-scheduler", "priorityClassName": "cps-batch", "restartPolicy": "Never",
            "activeDeadlineSeconds": 180, "automountServiceAccountToken": False,
            "nodeSelector": {"kubernetes.io/hostname": NODE}, "securityContext": copy.deepcopy(plan["pod_security_context"]),
            "initContainers": [*copy.deepcopy(plan["init_containers"]), gate],
            "containers": [{"name": "main", "image": IMAGE, "command": ["python", "-u", "/probe/probe_compiled.py", role],
                "securityContext": security, "env": env,
                "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "1", "memory": "256Mi"}},
                "volumeMounts": [{"name": "probe", "mountPath": "/probe", "readOnly": True},
                    {"name": "scratch", "mountPath": "/tmp"}, *copy.deepcopy(plan["volume_mounts"])]}],
            "volumes": [{"name": "probe", "configMap": {"name": name, "defaultMode": 292}},
                        {"name": "scratch", "emptyDir": {"sizeLimit": "64Mi"}}, *copy.deepcopy(plan["volumes"])]}
        items.append({"apiVersion": "batch/v1", "kind": "Job", "metadata": {
            "name": f"{name}-{role}", "namespace": NAMESPACE, "labels": labels, "annotations": annotations},
            "spec": {"suspend": True, "backoffLimit": 0, "activeDeadlineSeconds": 180,
                "template": {"metadata": {"labels": labels, "annotations": {**annotations, **plan["annotations"]}}, "spec": spec}}})
    return {"apiVersion": "v1", "kind": "List", "items": items}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--compiler-wheel", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--uid", type=int, default=10001)
    parser.add_argument("--gid", type=int, default=10001)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(HERE.parents[3]):
        raise SystemExit("Store rendered runtime fixtures outside Git")
    result = render(json.loads(args.preflight.read_text()), args.run_id, args.compiler_wheel, uid=args.uid, gid=args.gid)
    with args.output.open("x") as destination:
        json.dump(result, destination, indent=2)
        destination.write("\n")
    print(json.dumps({"rendered": True, "suspendedJobs": 2, "executed": False,
                      "compilerSource": SOURCE_COMMIT, "productionQualified": False}))

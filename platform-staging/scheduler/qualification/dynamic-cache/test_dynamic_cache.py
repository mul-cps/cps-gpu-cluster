import ast
import contextlib
import copy
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import evaluate
import probe
import render

NOW = dt.datetime(2026, 10, 7, 14, tzinfo=dt.timezone.utc)
GPU = "GPU-12345678-1234-1234-1234-123456789abc"
OTHER_GPU = "GPU-12345678-1234-1234-1234-123456789abd"
UID = "12345678-1234-1234-1234-123456789abc"


def preflight():
    return {"observedAt": NOW.isoformat(), "node": {"name": render.NODE, "uid": UID},
            "image": render.IMAGE, "targetGpuUuid": GPU,
            "hami": {"referenceSourceRevision": render.HAMI_REVISION, "sourceRevisionVerified": False,
                     "libraryPath": render.HAMI_PATH, "sha256": "a" * 64},
            "schedulerQuota": {"kaiVersion": "0.18.1", "requestedMiB": 5120,
                               "schedulerInjectedMiB": 5324, "cudaDeviceMemoryLimit": "5324m", "gpuPortion": "0.13",
                               "canonicalLimitMiB": 5120, "cudaDeviceMemoryLimit0": "5120m"},
            "gpus": [{"uuid": GPU, "index": 0}, {"uuid": OTHER_GPU, "index": 1}], "activeGpuPods": [],
            "mpsServers": [{"gpuUuid": GPU, "pid": 100, "ready": True},
                           {"gpuUuid": OTHER_GPU, "pid": 200, "ready": True}]}


def value(code=0, start=100, end=None, pid=101):
    return {"cudaResult": code, "startMonotonicNs": start,
            "endMonotonicNs": start + 100 if end is None else end, "allocationMiB": 3072,
            "pid": pid,
            "cache": {"device": 20, "inode": 21, "mappingVerified": True, "noTmpFallback": True},
            "hami": {"referenceSourceRevision": render.HAMI_REVISION, "sourceRevisionVerified": False,
                     "libraryPath": render.HAMI_PATH,
                     "sha256": "a" * 64, "loaded": True, "preloadVerified": True, "effectiveLimitBytes": 5120*1024**2,
                     "schedulerInjectedLimitBytes": 5324*1024**2, "canonicalLimitBytes": 5120*1024**2,
                     "perDeviceLimitVerified": True, "singleVisibleDeviceVerified": True},
            "gpu": probe.normalized_uuid(GPU)}


def valid_evidence():
    fixture = render.render(preflight(), "abcd1234", NOW)
    pods = []
    configmaps = []
    for number, item in enumerate(fixture["items"][1:]):
        pods.append({"metadata": {**item["spec"]["template"]["metadata"],
                     "uid": f"pod-{number}", "name": f"pod-name-{number}", "namespace": render.NAMESPACE},
                     "spec": {**item["spec"]["template"]["spec"], "nodeName": render.NODE},
                     "status": {"phase": "Succeeded"}})
        pod = pods[-1]
        pod["metadata"]["annotations"]["compute.cps.unileoben.ac.at/reviewed-gpu-uuid"] = GPU
        cm_name = pod["metadata"]["name"] + "-shared-gpu-0"
        pod["spec"]["containers"][0]["env"].append({"name": "NVIDIA_VISIBLE_DEVICES", "valueFrom": {
            "configMapKeyRef": {"name": cm_name, "key": "NVIDIA_VISIBLE_DEVICES"}}})
        configmaps.append({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {
            "name": cm_name, "namespace": render.NAMESPACE, "uid": cm_name+"-uid", "resourceVersion": "123",
            "ownerReferences": [{"apiVersion": "v1", "kind": "Pod", "name": pod["metadata"]["name"], "uid": pod["metadata"]["uid"]}]},
            "data": {"CUDA_DEVICE_MEMORY_LIMIT": "5324m", "GPU_PORTION": "0.13",
                     "NVIDIA_VISIBLE_DEVICES": f"k8s.device-plugin.nvidia.com/gpu={GPU}"}})
    ordinary = {key: value(2 if key == "bDenied" else 0) for key in
                ("aHold", "bDenied", "aContinued", "aFree", "bAfterFree", "bContinued")}
    report = {"event": "workspace-result", "status": "bounded-standard-cases-passed",
              "startedNs": 1_000_000_000, "finishedNs": 2_000_000_000,
              "requestedMiB": 5120, "schedulerInjectedMiB": 5324, "canonicalLimitMiB": 5120,
              "effectiveHamiLimitMiB": 5120, "schedulerQuotaDrift": True, "canonicalQuotaDrift": False,
              "exactProfileQuotaQualified": False,
              "ordinary": ordinary, "gpu": probe.normalized_uuid(GPU), "cache": value()["cache"],
              "hami": value()["hami"], "concurrency": []}
    workspace = [{"event": "child-evidence", "child": name,
                  "value": {**value(pid=pid), "event": "ready"}} for name, pid in (("a", 101), ("b", 102))]
    for number in range(probe.ROUNDS):
        ident = f"concurrent-{number}"
        results = [{**value(code, start, pid=pid), "event": "response", "id": ident,
                    "label": ident, "action": "allocate"}
                   for code, start, pid in ((0, 100, 101), (2, 110, 102))]
        tick = {**value(pid=101), "event": "response", "id": f"{ident}-tick",
                "label": ident, "action": "tick"}
        report["concurrency"].append({"round": number, "results": results, "successfulTicks": [tick]})
        workspace.extend({"event": "child-evidence", "child": name, "value": receipt}
                         for name, receipt in (("a", results[0]), ("b", results[1]), ("a", tick)))
    workspace.append(report)
    peer_cache = {**value()["cache"], "inode": 22}
    peer = [{"event": "peer-ready", "gpu": probe.normalized_uuid(GPU), "cache": peer_cache, "hami": value()["hami"]}]
    peer.extend({"event": "peer-alive", "gpu": probe.normalized_uuid(GPU),
                 "cache": peer_cache, "hami": value()["hami"], "cudaResult": 0, "observedNs": t}
                for t in (900_000_000, 1_200_000_000, 1_600_000_000, 2_100_000_000))
    peer.append({"event": "peer-completed", "gpu": probe.normalized_uuid(GPU), "cudaResult": 0})
    for events, uid in ((workspace, "pod-1"), (peer, "pod-0")):
        for event in events:
            event.update(podUid=uid, runId="abcd1234")
    return (workspace, peer, pods[1], pods[0], {"metadata": {"name": render.NODE, "uid": UID}}, preflight(),
            {"before": {"items": configmaps}, "after": {"items": copy.deepcopy(configmaps)}})


class RendererTests(unittest.TestCase):
    def test_mps_server_must_already_be_ready_for_each_allowed_gpu(self):
        for index in (0, 1):
            for change in ("missing", "not-ready"):
                data = preflight()
                if change == "missing":
                    data["mpsServers"].pop(index)
                else:
                    data["mpsServers"][index]["ready"] = False
                with self.subTest(index=index, change=change), self.assertRaises(ValueError):
                    render.render(data, "abcd1234", NOW)

    def test_manifest_is_disabled_and_cache_is_a_private_nonroot_file_mount(self):
        result = render.render(preflight(), "abcd1234", NOW)
        self.assertEqual([x["kind"] for x in result["items"]], ["ConfigMap", "Job", "Job"])
        for job in result["items"][1:]:
            self.assertTrue(job["spec"]["suspend"])
            self.assertEqual(job["spec"]["backoffLimit"], 0)
            pod = job["spec"]["template"]["spec"]
            self.assertEqual(pod["nodeSelector"], {"kubernetes.io/hostname": "k3s-wk-gpu2"})
            self.assertFalse(pod["automountServiceAccountToken"])
            self.assertEqual([c["name"] for c in pod["initContainers"]],
                             ["initialize-workspace-cache", "await-operator-runtime-review"])
            self.assertIn("operator-gate.py", pod["initContainers"][1]["command"][2])
            self.assertEqual(pod["securityContext"]["runAsUser"], 10001)
            volumes = {v["name"]: v for v in pod["volumes"]}
            self.assertIn("emptyDir", volumes["workspace-cache"])
            mounts = [m for m in pod["containers"][0]["volumeMounts"] if m["name"] == "workspace-cache"]
            self.assertEqual(mounts, [{"name": "workspace-cache", "mountPath": probe.CACHE_PATH, "subPath": "usage.cache"}])
            hosts = {v["hostPath"]["path"] for v in pod["volumes"] if "hostPath" in v}
            self.assertEqual(hosts, {"/run/nvidia/mps/nvidia.com/gpu/pipe", "/run/nvidia/mps/shm"})
            for container in [*pod["initContainers"], *pod["containers"]]:
                self.assertEqual(container["image"], render.IMAGE)
                self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
                self.assertNotIn("nvidia.com/gpu", container["resources"]["limits"])
            env = {e["name"]: e.get("value") for e in pod["containers"][0]["env"]}
            self.assertEqual(env["CUDA_DEVICE_MEMORY_SHARED_CACHE"], probe.CACHE_PATH)
            self.assertEqual(env["EXPECTED_HAMI_LIMIT_MIB"], "5120")
            self.assertEqual(env["CUDA_DEVICE_MEMORY_LIMIT_0"], "5120m")
            self.assertEqual(env["CUDA_DEVICE_MEMORY_LIMIT"], "5324m")
            self.assertEqual(env["GPU_PORTION"], "0.13")
            expected = next(e for e in pod["containers"][0]["env"] if e["name"] == "EXPECTED_GPU_UUID")
            self.assertEqual(expected["valueFrom"]["fieldRef"]["fieldPath"],
                             "metadata.annotations['compute.cps.unileoben.ac.at/reviewed-gpu-uuid']")
            self.assertNotIn("NVIDIA_VISIBLE_DEVICES", env)

    def test_preflight_rejects_unsafe_or_unbound_targets(self):
        changes = [lambda d: d["node"].update(name="k3s-wk-gpu1"),
                   lambda d: d["node"].pop("uid"),
                   lambda d: d.update(image="untrusted:latest"),
                   lambda d: d.update(targetGpuUuid="MIG-123"),
                   lambda d: d.update(activeGpuPods=[{"name": "existing-user"}]),
                   lambda d: d.update(mpsServers=[]),
                   lambda d: d["hami"].update(sha256="not-a-binary-hash"),
                   lambda d: d["hami"].update(referenceSourceRevision="different"),
                   lambda d: d["hami"].update(sourceRevisionVerified=True),
                   lambda d: d["schedulerQuota"].update(schedulerInjectedMiB=6144),
                   lambda d: d["schedulerQuota"].update(cudaDeviceMemoryLimit="5120m"),
                   lambda d: d["schedulerQuota"].update(gpuPortion="0.125"),
                   lambda d: d.update(gpus=[]),
                   lambda d: d.update(observedAt=(NOW-dt.timedelta(minutes=16)).isoformat()),
                   lambda d: d.update(observedAt=(NOW+dt.timedelta(seconds=1)).isoformat()),
                   lambda d: d.update(observedAt="2026-10-07T14:00:00")]
        for change in changes:
            data = preflight()
            change(data)
            with self.subTest(data=data), self.assertRaises((ValueError, KeyError)):
                render.render(data, "abcd1234", NOW)

    def test_cache_initializer_never_replaces_an_existing_file_or_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "usage.cache"
            target.write_bytes(b"existing cache must survive")
            source = render.INITIALIZE.replace("/cache-root/usage.cache", str(target))
            with patch("os.getuid", return_value=10001), self.assertRaises(FileExistsError):
                exec(compile(source, "initializer", "exec"), {})
            self.assertEqual(target.read_bytes(), b"existing cache must survive")
            target.unlink()
            victim = Path(directory) / "victim"
            victim.write_bytes(b"preserve")
            target.symlink_to(victim)
            with patch("os.getuid", return_value=10001), self.assertRaises(FileExistsError):
                exec(compile(source, "initializer", "exec"), {})
            self.assertEqual(victim.read_bytes(), b"preserve")

    def test_runtime_has_no_cache_replacement_or_environment_override(self):
        source = (render.HERE / "probe.py").read_text()
        tree = ast.parse(source)
        calls = {node.func.attr for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(calls & {"unlink", "remove", "chmod", "fchmod", "truncate", "ftruncate", "putenv", "setenv"})
        popen = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and node.func.attr == "Popen")
        self.assertNotIn("env", {keyword.arg for keyword in popen.keywords})
        self.assertNotIn("CUDA_DISABLE_CONTROL", source)
        self.assertNotIn("CUDA_MPS_PIPE_DIRECTORY", source)

    def test_final_runtime_gate_does_not_touch_gpu_or_call_external_commands(self):
        source = render.OPERATOR_GATE
        self.assertIn("Operator review marker mismatch", source)
        self.assertIn("time.monotonic()+60", source)
        self.assertIn("'nodeUid':proof['nodeUid']", source)
        self.assertIn("'podUid':os.environ['FIXTURE_POD_UID']", source)
        self.assertIn("'runId':proof['runId']", source)
        tree = ast.parse(source)
        imports = {name.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                   for name in node.names}
        self.assertFalse(imports & {"ctypes", "subprocess", "requests", "kubernetes"})
        calls = {node.func.attr for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(calls & {"unlink", "chmod", "write_text", "write_bytes"})

    def test_operator_gate_accepts_only_the_exact_actual_pod_and_rendered_proof(self):
        proof = {"nodeUid": UID, "gpuUuid": GPU, "gpuUuidAllowlist": [GPU, OTHER_GPU],
                 "runId": "abcd1234", "hami": {"sha256": "a"*64}}
        marker = {"runtimeReviewed": True, "role": "peer", "podUid": "actual-pod",
                  "runId": "abcd1234", "nodeUid": UID, "gpuUuid": GPU,
                  "hamiSha256": "a"*64, "probeSha256": "b"*64}
        class FakePath:
            def __init__(self, value):
                self.path = value
            def exists(self):
                return True
            def stat(self):
                return SimpleNamespace(st_uid=10001, st_size=1024)
            def read_text(self):
                return json.dumps(proof if self.path == '/probe/preflight.json' else marker)
        with patch("pathlib.Path", FakePath), patch("os.getuid", return_value=10001), \
             patch.dict("os.environ", {"FIXTURE_POD_UID": "actual-pod"}), \
             patch("sys.argv", ["gate", "peer", "b"*64]), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as complete:
                exec(compile(render.OPERATOR_GATE, "operator-gate", "exec"), {})
            self.assertEqual(complete.exception.code, 0)
            marker["gpuUuid"] = OTHER_GPU
            with self.assertRaises(SystemExit) as other_complete:
                exec(compile(render.OPERATOR_GATE, "operator-gate", "exec"), {})
            self.assertEqual(other_complete.exception.code, 0)
            marker["gpuUuid"] = "GPU-00000000-0000-0000-0000-000000000000"
            with self.assertRaisesRegex(AssertionError, "observed GPU allowlist"):
                exec(compile(render.OPERATOR_GATE, "operator-gate", "exec"), {})
            marker["gpuUuid"] = GPU
            for key in ("podUid", "runId", "hamiSha256", "probeSha256", "nodeUid", "role"):
                original = marker[key]
                marker[key] = "mismatched"
                with self.subTest(key=key), self.assertRaisesRegex(AssertionError, "Operator review marker mismatch"):
                    exec(compile(render.OPERATOR_GATE, "operator-gate", "exec"), {})
                marker[key] = original

    def test_runtime_requires_preloaded_binary_hash_and_actual_quota(self):
        library = b"offline reviewed fixture bytes"
        info = SimpleNamespace(st_dev=1, st_ino=2, st_size=len(library), st_mtime_ns=3, st_ctime_ns=4)
        env = {"EXPECTED_HAMI_REVISION": render.HAMI_REVISION,
               "EXPECTED_HAMI_SHA256": probe.hashlib.sha256(library).hexdigest(),
               "CUDA_DEVICE_MEMORY_LIMIT": "5324m", "CUDA_DEVICE_MEMORY_LIMIT_0": "5120m",
               "EXPECTED_HAMI_LIMIT_MIB": "5120", "GPU_PORTION": "0.13"}
        maps = f"1000-2000 r-xp 00000000 00:01 2 {render.HAMI_PATH}\n"
        def text(path):
            return maps if str(path) == "/proc/self/maps" else render.HAMI_PATH + "\n"
        class Limit:
            argtypes = None
            restype = None
            size = 5120 * 1024**2
            def __call__(self, device):
                return self.size
        core = SimpleNamespace(get_current_device_memory_limit=Limit())
        with patch.dict("os.environ", env, clear=True), patch.object(probe.Path, "stat", return_value=info), \
             patch.object(probe.Path, "read_bytes", return_value=library), \
             patch.object(probe.Path, "read_text", text), patch.object(probe.Path, "exists", return_value=True), \
             patch.object(probe.ctypes, "CDLL", return_value=core) as load:
            _, proof = probe.hami_provenance()
            self.assertTrue(proof["preloadVerified"])
            self.assertEqual(load.call_args.kwargs["mode"], probe.os.RTLD_NOLOAD | probe.os.RTLD_NOW)
            for observed_limit in (5324 * 1024**2, 40 * 1024**3):
                core.get_current_device_memory_limit.size = observed_limit
                with self.assertRaisesRegex(RuntimeError, "Effective HAMi quota"):
                    probe.hami_provenance()
            core.get_current_device_memory_limit.size = 5120 * 1024**2
            with patch.dict("os.environ", {"EXPECTED_HAMI_SHA256": "f" * 64}):
                with self.assertRaisesRegex(RuntimeError, "binary does not match"):
                    probe.hami_provenance()
            with patch.object(probe.Path, "read_text", return_value=""):
                with self.assertRaisesRegex(RuntimeError, "not loaded"):
                    probe.hami_provenance()


class VerdictTests(unittest.TestCase):
    def test_rounded_observation_never_claims_exact_requested_profile_quota(self):
        result = evaluate.evaluate(*valid_evidence())
        self.assertEqual(result["status"], "bounded-standard-cases-passed")
        self.assertEqual(result["requestedMiB"], 5120)
        self.assertEqual(result["schedulerInjectedMiB"], 5324)
        self.assertEqual(result["effectiveHamiLimitMiB"], 5120)
        self.assertTrue(result["schedulerQuotaDrift"])
        self.assertFalse(result["canonicalQuotaDrift"])
        self.assertFalse(result["exactProfileQuotaQualified"])
        evidence = list(valid_evidence())
        evidence[0][-1]["exactProfileQuotaQualified"] = True
        self.assertEqual(evaluate.evaluate(*evidence)["status"], "failed-or-inconclusive")

    def test_failed_hook_initialization_does_not_report_an_observed_canonical_quota(self):
        evidence = list(valid_evidence())
        report = evidence[0][-1]
        report.pop("hami")
        report.update(status="incomplete", effectiveHamiLimitMiB=None, canonicalQuotaDrift=None)
        result = evaluate.evaluate(*evidence)
        self.assertEqual(result["status"], "failed-or-inconclusive")
        self.assertIsNone(result["effectiveHamiLimitMiB"])
        self.assertIsNone(result["canonicalQuotaDrift"])

    def test_mutated_quota_env_requires_stable_owned_configmap_receipts(self):
        evidence = list(valid_evidence())
        items = []
        for pod in (evidence[2], evidence[3]):
            name = pod["metadata"]["name"] + "-shared-gpu-0"
            for entry in pod["spec"]["containers"][0]["env"]:
                if entry["name"] in ("CUDA_DEVICE_MEMORY_LIMIT", "GPU_PORTION"):
                    entry.pop("value")
                    entry["valueFrom"] = {"configMapKeyRef": {"name": name, "key": entry["name"]}}
            items.append({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {
                "name": name, "namespace": render.NAMESPACE, "uid": name+"-uid", "resourceVersion": "123",
                "ownerReferences": [{"apiVersion": "v1", "kind": "Pod", "name": pod["metadata"]["name"], "uid": pod["metadata"]["uid"]}]},
                "data": {"CUDA_DEVICE_MEMORY_LIMIT": "5324m", "GPU_PORTION": "0.13",
                         "NVIDIA_VISIBLE_DEVICES": f"k8s.device-plugin.nvidia.com/gpu={GPU}"}})
        snapshots = {"before": {"items": items}, "after": {"items": copy.deepcopy(items)}}
        self.assertEqual(evaluate.evaluate(*evidence[:6], configmaps=snapshots)["status"], "bounded-standard-cases-passed")
        for kind in ("missing", "uid", "rv", "owner", "quota", "portion"):
            changed = copy.deepcopy(snapshots)
            if kind == "missing":
                changed["after"]["items"] = []
            elif kind == "uid":
                changed["after"]["items"][0]["metadata"]["uid"] = "replaced"
            elif kind == "rv":
                changed["after"]["items"][0]["metadata"]["resourceVersion"] = "124"
            elif kind == "owner":
                for stage in ("before", "after"):
                    changed[stage]["items"][0]["metadata"]["ownerReferences"][0]["uid"] = "another-pod"
            else:
                key = "CUDA_DEVICE_MEMORY_LIMIT" if kind == "quota" else "GPU_PORTION"
                for stage in ("before", "after"):
                    changed[stage]["items"][0]["data"][key] = "unexpected"
            with self.subTest(kind=kind):
                self.assertEqual(evaluate.evaluate(*evidence[:6], configmaps=changed)["status"], "failed-or-inconclusive")

    def test_reviewed_selection_must_be_observed_same_card_and_owned_by_each_pod(self):
        for kind in ("missing-review", "unobserved", "different-card", "cm-selection", "cm-missing"):
            evidence = list(valid_evidence())
            key = "compute.cps.unileoben.ac.at/reviewed-gpu-uuid"
            if kind == "missing-review":
                evidence[2]["metadata"]["annotations"].pop(key)
            elif kind == "unobserved":
                evidence[2]["metadata"]["annotations"][key] = "GPU-00000000-0000-0000-0000-000000000000"
            elif kind == "different-card":
                evidence[3]["metadata"]["annotations"][key] = OTHER_GPU
            elif kind == "cm-selection":
                for stage in ("before", "after"):
                    evidence[6][stage]["items"][0]["data"]["NVIDIA_VISIBLE_DEVICES"] = f"k8s.device-plugin.nvidia.com/gpu={OTHER_GPU}"
            else:
                evidence[6] = None
            with self.subTest(kind=kind):
                self.assertEqual(evaluate.evaluate(*evidence)["status"], "failed-or-inconclusive")

    def test_actual_second_observed_card_can_pass_without_changing_initial_choice(self):
        evidence = list(valid_evidence())
        def update_gpu(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "gpu":
                        value[key] = probe.normalized_uuid(OTHER_GPU)
                    elif key == "compute.cps.unileoben.ac.at/reviewed-gpu-uuid":
                        value[key] = OTHER_GPU
                    elif key == "NVIDIA_VISIBLE_DEVICES":
                        value[key] = f"k8s.device-plugin.nvidia.com/gpu={OTHER_GPU}"
                    else:
                        update_gpu(item)
            elif isinstance(value, list):
                for item in value:
                    update_gpu(item)
        for value in (evidence[0], evidence[1], evidence[2], evidence[3], evidence[6]):
            update_gpu(value)
        self.assertEqual(evidence[5]["targetGpuUuid"], GPU)
        result = evaluate.evaluate(*evidence)
        self.assertEqual(result["status"], "bounded-standard-cases-passed", result)
        self.assertEqual(result["gpu"], probe.normalized_uuid(OTHER_GPU))

    def test_sequential_or_touching_intervals_are_not_concurrency_evidence(self):
        for starts_ends in ((100, 105, 110, 115), (100, 110, 110, 120)):
            a_start, a_end, b_start, b_end = starts_ends
            results = [value(0, a_start, a_end), value(2, b_start, b_end)]
            with self.subTest(intervals=starts_ends):
                self.assertEqual(probe.concurrent_verdict(results), "inconclusive-nonoverlapping-intervals")

    def test_backwards_missing_or_noninteger_intervals_are_inconclusive(self):
        for bad in (value(0, 100, 99), {k: v for k, v in value().items() if k != "endMonotonicNs"},
                    {**value(), "endMonotonicNs": "200"}):
            with self.subTest(bad=bad):
                self.assertEqual(probe.concurrent_verdict([bad, value(2, 110)]), "inconclusive-invalid-intervals")

    def test_evaluator_requires_exact_tick_for_each_successful_allocation(self):
        for kind in ("missing", "failed", "wrong-pid", "wrong-label", "wrong-id", "wrong-gpu", "not-in-log"):
            evidence = list(valid_evidence())
            current_round = evidence[0][-1]["concurrency"][0]
            tick = current_round["successfulTicks"][0]
            if kind == "missing":
                current_round["successfulTicks"] = []
            elif kind == "failed":
                tick["cudaResult"] = 700
            elif kind == "wrong-pid":
                tick["pid"] = 102
            elif kind == "wrong-label":
                tick["label"] = "unrelated-allocation"
            elif kind == "wrong-id":
                tick["id"] = "unrelated-response"
            elif kind == "wrong-gpu":
                tick["gpu"] = "0"*32
            else:
                evidence[0] = [e for e in evidence[0] if e.get("value", {}).get("id") != "concurrent-0-tick"]
            with self.subTest(kind=kind):
                self.assertEqual(evaluate.evaluate(*evidence)["status"], "failed-or-inconclusive")

    def test_peer_coverage_cannot_use_far_outside_boundary_heartbeats(self):
        evidence = list(valid_evidence())
        evidence[0][-1].update(startedNs=10_000_000_000, finishedNs=20_000_000_000)
        alive = [e for e in evidence[1] if e["event"] == "peer-alive"]
        template = alive[0]
        evidence[1] = [e for e in evidence[1] if e["event"] != "peer-alive"]
        evidence[1].extend({**template, "observedNs": t} for t in (0, 15_000_000_000, 30_000_000_000))
        self.assertEqual(evaluate.evaluate(*evidence)["status"], "failed-or-inconclusive")

    def test_non_oom_cuda_failure_is_not_accepted_as_quota_denial(self):
        evidence = valid_evidence()[0][-1]["ordinary"]
        self.assertTrue(probe.ordinary_verdict(evidence))
        for code in (0, 1, 3, 100, 999):
            bad = copy.deepcopy(evidence)
            bad["bDenied"]["cudaResult"] = code
            self.assertFalse(probe.ordinary_verdict(bad))

    def test_race_and_nonoverlapping_or_invalid_results_cannot_pass(self):
        self.assertEqual(probe.concurrent_verdict([value(0), value(0)]), "aggregate-limit-exceeded")
        self.assertEqual(probe.concurrent_verdict([value(2), value(2)]), "inconclusive-cuda-results")
        self.assertEqual(probe.concurrent_verdict([value(0), value(999)]), "inconclusive-cuda-results")
        self.assertEqual(probe.concurrent_verdict([value(0, 100), value(2, 100+probe.MAX_SKEW_NS+1)]), "inconclusive-launch-skew")

    def test_valid_standard_evidence_keeps_hostile_and_production_gates_false(self):
        result = evaluate.evaluate(*valid_evidence())
        self.assertEqual(result["status"], "bounded-standard-cases-passed", result)
        self.assertFalse(result["productionQualified"])
        self.assertFalse(result["hostileIsolationQualified"])
        self.assertEqual(result["tamper"]["status"], "not-run")

    def test_independent_same_gpu_peer_and_live_progress_are_required(self):
        for kind in ("wrong-gpu", "same-pod", "same-cache", "stale", "failed", "missing"):
            evidence = list(valid_evidence())
            if kind == "wrong-gpu":
                evidence[1][1]["gpu"] = "0" * 32
            elif kind == "same-pod":
                evidence[3]["metadata"]["uid"] = evidence[2]["metadata"]["uid"]
            elif kind == "same-cache":
                for event in evidence[1]:
                    if "cache" in event:
                        event["cache"]["inode"] = 21
            elif kind == "stale":
                evidence[1] = [e for e in evidence[1] if e.get("observedNs") != 2_100_000_000]
            elif kind == "failed":
                evidence[1][1]["cudaResult"] = 700
            else:
                evidence[1] = []
            with self.subTest(kind=kind):
                result = evaluate.evaluate(*evidence)
                self.assertEqual(result["status"], "failed-or-inconclusive", result)

    def test_changed_node_cache_image_or_insufficient_rounds_cannot_pass(self):
        for kind in ("node", "cache", "fallback", "image", "rounds", "race", "library", "quota", "size", "pod-log", "run-log"):
            evidence = list(valid_evidence())
            if kind == "node":
                evidence[4]["metadata"]["uid"] = "different"
            elif kind == "cache":
                evidence[0][0]["value"]["cache"]["inode"] += 1
            elif kind == "fallback":
                evidence[0][0]["value"]["cache"]["noTmpFallback"] = False
            elif kind == "image":
                evidence[2]["spec"]["containers"][0]["image"] = "bad:latest"
            elif kind == "rounds":
                evidence[0][-1]["concurrency"].pop()
            elif kind == "race":
                evidence[0][-1]["concurrency"][0]["results"][1]["cudaResult"] = 0
            elif kind == "library":
                evidence[0][0]["value"]["hami"]["sha256"] = "f" * 64
            elif kind == "quota":
                evidence[0][-1]["hami"]["effectiveLimitBytes"] = 40 * 1024**3
            elif kind == "size":
                evidence[0][-1]["ordinary"]["aHold"]["allocationMiB"] = 1
            elif kind == "pod-log":
                evidence[0][-1]["podUid"] = "different-pod"
            else:
                evidence[1][1]["runId"] = "different-run"
            with self.subTest(kind=kind):
                result = evaluate.evaluate(*evidence)
                self.assertEqual(result["status"], "failed-or-inconclusive", result)


if __name__ == "__main__":
    unittest.main()

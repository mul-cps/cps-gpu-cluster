import ast
import copy
import datetime as dt
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mps_dynamic_plan", HERE / "plan.py")
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)
NOW = dt.datetime(2026, 10, 7, 16, 0, tzinfo=dt.timezone.utc)


def fixture(threads=False, cordoned=False, field_present=True):
    statuses = [{"name": name, "imageId": plan.DAEMON_IMAGE, "containerId": "containerd://" + letter * 64,
                 "restarts": 0} for name, letter in (("config-manager", "a"), ("mps-control-daemon-ctr", "b"))]
    identity = {"observedAt": NOW.isoformat(), "nodeUid": plan.NODE_UID, "daemonPod": plan.DAEMON,
        "daemonUid": plan.DAEMON_UID, "daemonStatuses": statuses, "readOnlyCommands": plan.REFERENCE_COMMANDS,
        "controlOutput": "3166883\nACTIVE\n5G\n5G\n5G\n5G\n12.0\n12.0\n", "settingsChanged": False,
        # /proc stat fields 3..21 precede field22 (process start ticks); comm may contain spaces.
        "processIdentityOutput": "3166883 (nvidia cuda mps) " + " ".join(["S"] + ["0"] * 18 + ["792169718"])}
    details = {"observedAt": NOW.isoformat(), "settingsChanged": False, "processes": {
        "3166883": {"status": {"Uid": "10001\t10001\t10001\t10001", "PPid": "1260846"},
                     "command": ["nvidia-cuda-mps-server", ""]},
        "1260846": {"status": {"Uid": "0\t0\t0\t0"}, "command": ["nvidia-cuda-mps-control", "-d"]}}}
    request = {"runId": "matrix0716a", "maxWindowSeconds": 180, "raiseActiveThreads": threads}
    observation = {"observedAt": NOW.isoformat(),
        "node": {"name": plan.NODE, "uid": plan.NODE_UID, "resourceVersion": "100",
                 "ready": True, "unschedulable": cordoned, "unschedulablePresent": field_present},
        "daemon": {"namespace": "gpu-operator", "name": plan.DAEMON, "uid": plan.DAEMON_UID,
            "resourceVersion": "200", "nodeName": plan.NODE, "phase": "Running", "containerStatuses": statuses},
        "protected": {"namespace": "jupyterhub", "name": "jupyter-bjoern", "uid": plan.PROTECTED_UID,
            "resourceVersion": "300", "nodeName": "k3s-wk-gpu1", "phase": "Running", "restarts": 0},
        "server": {"pid": 3166883, "startTimeTicks": 792169718, "uid": 10001, "status": "ACTIVE", "clients": [],
            "deviceMemoryLimits": {gpu: "5G" for gpu in plan.GPUS}, "activeThreadPercentage": "12.0"},
        "control": {"pid": 1260846, "uid": 0, "command": ["nvidia-cuda-mps-control", "-d"]},
        "defaults": {"deviceMemoryLimits": {"0": "5G", "1": "5G"}, "activeThreadPercentage": "12.0"},
        "gpus": [{"index": index, "uuid": gpu, "totalMiB": 40960, "usedMiB": 45,
                  "migCurrent": "Disabled", "migPending": "Disabled", "computeMode": "Default"}
                 for index, gpu in enumerate(plan.GPUS)],
        "gpuProcesses": [{"gpuUuid": gpu, "pid": 3166883, "uid": 10001} for gpu in plan.GPUS],
        "unexpectedGpuPods": [], "stagedPods": [{"namespace": "cps-gpu-qualification", "name": f"matrix-{memory}",
            "uid": f"pod-{memory}", "jobUid": f"job-{memory}", "resourceVersion": f"400-{memory}",
            "nodeName": plan.NODE, "runId": request["runId"], "gpuUuid": plan.GPUS[0], "memoryMiB": memory,
            "processUid": 10001, "image": "registry.example/probe@sha256:" + "c" * 64,
            "probeSha256": "d" * 64, "gateRunning": True, "mainStarted": False, "processesExited": False,
            "phase": "Pending"} for memory in (5120, 10240, 20480)]}
    return identity, details, observation, request


def prepared(**kwargs):
    identity, details, observation, request = fixture(**kwargs)
    candidate = plan.prepare(identity, details, observation, request, now=NOW)
    review = {"schemaVersion": 1, "candidateSha256": candidate["candidateSha256"], "actor": "reviewed-operator",
              "reviewedAt": NOW.isoformat(), "steps": candidate["steps"], "statefulStepsReviewed": True}
    return candidate, review, observation


def apply_result(operation, observation, journal):
    """Offline state transition only: no subprocess, cluster, driver or CUDA calls."""
    step = operation["step"]
    entry = {"step": step, "candidateSha256": operation["candidateSha256"]}
    if step == "cordon":
        observation["node"].update(unschedulable=True, unschedulablePresent=True, resourceVersion="101")
        entry["resultNodeResourceVersion"] = "101"
    elif "memory" in step:
        observation["server"]["deviceMemoryLimits"][plan.GPUS[int(step[-1])]] = "5120M" if step.startswith("restore-") else "40960M"
    elif "threads" in step:
        observation["server"]["activeThreadPercentage"] = "12.0" if step.startswith("restore-") else "100.0"
    elif step == "run-qualification":
        for pod in observation["stagedPods"]:
            pod.update(mainStarted=True, gateRunning=False, processesExited=True, phase="Succeeded")
    journal.append(entry)


class PlanTests(unittest.TestCase):
    def test_full_roundtrip_memory_only_and_optional_threads(self):
        for threads in (False, True):
            with self.subTest(threads=threads):
                candidate, review, observation = prepared(threads=threads)
                initial = copy.deepcopy(observation)
                journal = []
                for step in candidate["steps"]:
                    operation = plan.unlock_step(candidate, review, observation, journal, step, authorize=True, now=NOW)
                    self.assertFalse(operation["executionImplemented"])
                    if operation["kind"] == "active-server-control":
                        self.assertNotIn("default", operation["stdin"])
                        self.assertNotIn("quit", operation["stdin"])
                        self.assertEqual(operation["podUid"], plan.DAEMON_UID)
                        self.assertEqual(operation["serverProcessFence"]["startTimeTicks"], 792169718)
                    apply_result(operation, observation, journal)
                self.assertEqual(observation["defaults"], initial["defaults"])
                self.assertEqual(observation["protected"], initial["protected"])
                self.assertEqual(observation["daemon"], initial["daemon"])
                self.assertEqual({plan.memory_mib(v) for v in observation["server"]["deviceMemoryLimits"].values()}, {5120})
                self.assertEqual(observation["server"]["activeThreadPercentage"], "12.0")

    def test_flag_and_exact_review_are_both_required(self):
        candidate, review, observation = prepared()
        with self.assertRaisesRegex(ValueError, "Explicit"):
            plan.unlock_step(candidate, review, observation, [], "cordon", now=NOW)
        for update in ({"candidateSha256": "other"}, {"statefulStepsReviewed": False}, {"steps": []}, {"actor": " "}):
            bad = {**review, **update}
            with self.assertRaisesRegex(ValueError, "reviewed candidate"):
                plan.unlock_step(candidate, bad, observation, [], "cordon", authorize=True, now=NOW)

    def test_candidate_and_command_tampering_rejected(self):
        candidate, review, observation = prepared()
        candidate["limits"]["temporaryMemoryMiB"] = 99999
        with self.assertRaisesRegex(ValueError, "hash changed"):
            plan.unlock_step(candidate, review, observation, [], "cordon", authorize=True, now=NOW)

    def test_fresh_uid_rv_pidstarttime_clients_and_images_are_required(self):
        candidate, review, observation = prepared()
        mutations = [
            lambda o: o["node"].update(uid="replacement"), lambda o: o["node"].update(resourceVersion=""),
            lambda o: o["daemon"].update(uid="replacement"), lambda o: o["daemon"].update(resourceVersion="changed"),
            lambda o: o["daemon"]["containerStatuses"][0].update(imageId="other"),
            lambda o: o["daemon"]["containerStatuses"][0].update(restarts=1),
            lambda o: o["protected"].update(uid="replacement"), lambda o: o["protected"].update(resourceVersion="changed"),
            lambda o: o["protected"].update(restarts=1), lambda o: o["server"].update(pid=3166884),
            lambda o: o["server"].update(startTimeTicks=792169719), lambda o: o["server"].update(uid=1000),
            lambda o: o["server"].update(clients=[123]), lambda o: o["server"].update(status="FAULT"),
            lambda o: o["control"].update(command=["nvidia-cuda-mps-control", "-d", "-multiuser-server"]),
            lambda o: o["gpus"][0].update(uuid=plan.GPUS[1]), lambda o: o["gpus"][1].update(index=-1),
            lambda o: o["gpus"][0].update(usedMiB=4096), lambda o: o.update(unexpectedGpuPods=["unreviewed"]),
            lambda o: o["gpuProcesses"].append({"pid": 1, "uid": 1000, "gpuUuid": plan.GPUS[0]}),
            lambda o: o["stagedPods"][0].update(mainStarted=True), lambda o: o["stagedPods"][0].update(uid="replaced"),
            lambda o: o.update(observedAt=(NOW - dt.timedelta(seconds=16)).isoformat()),
            lambda o: o.update(observedAt=(NOW + dt.timedelta(seconds=1)).isoformat()),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                bad = copy.deepcopy(observation); mutate(bad)
                with self.assertRaises(ValueError):
                    plan.unlock_step(candidate, review, bad, [], "cordon", authorize=True, now=NOW)

    def test_actual_ready_true_is_required_at_prepare_and_every_step(self):
        for value in (False, None, "True", "Unknown", 1):
            with self.subTest(ready=value):
                identity, details, observation, request = fixture()
                observation["node"]["ready"] = value
                with self.assertRaisesRegex(ValueError, "Ready"):
                    plan.prepare(identity, details, observation, request, now=NOW)
                candidate, review, observation = prepared()
                observation["node"]["ready"] = value
                with self.assertRaisesRegex(ValueError, "Ready"):
                    plan.unlock_step(candidate, review, observation, [], "cordon", authorize=True, now=NOW)
        identity, details, observation, request = fixture()
        del observation["node"]["ready"]
        with self.assertRaisesRegex(ValueError, "Ready"):
            plan.prepare(identity, details, observation, request, now=NOW)

    def test_node_status_rv_drift_uses_fresh_cas_and_allows_guarded_rollback(self):
        for field_present in (False, True):
            with self.subTest(field_present=field_present):
                candidate, review, observation = prepared(field_present=field_present)
                journal = []
                observation["node"]["resourceVersion"] = "status-before-cordon"
                cordon = plan.unlock_step(candidate, review, observation, journal, "cordon", authorize=True, now=NOW)
                self.assertEqual(cordon["patch"][1], {"op": "test", "path": "/metadata/resourceVersion",
                                                      "value": "status-before-cordon"})
                apply_result(cordon, observation, journal)
                observation["node"]["resourceVersion"] = "status-after-cordon"
                raised = plan.unlock_step(candidate, review, observation, journal, "raise-memory-0", authorize=True, now=NOW)
                apply_result(raised, observation, journal)
                later = NOW + dt.timedelta(seconds=181)
                observation["observedAt"] = later.isoformat()
                observation["node"]["resourceVersion"] = "status-after-raising"
                restored = plan.unlock_step(candidate, review, observation, journal, "restore-memory-0", authorize=True, now=later)
                self.assertEqual(restored["stdin"], f"set_device_pinned_mem_limit 3166883 {plan.GPUS[0]} 5120M\n")
                apply_result(restored, observation, journal)
                observation["node"]["resourceVersion"] = "status-before-restoring-node"
                restored_node = plan.unlock_step(candidate, review, observation, journal, "restore-node", authorize=True, now=later)
                self.assertEqual(restored_node["patch"][1], {"op": "test", "path": "/metadata/resourceVersion",
                                                             "value": "status-before-restoring-node"})
                self.assertEqual(restored_node["patch"][-1],
                                 {"op": "replace", "path": "/spec/unschedulable", "value": False}
                                 if field_present else {"op": "remove", "path": "/spec/unschedulable"})
                self.assertEqual(candidate["original"]["node"]["unschedulablePresent"], field_present)
                self.assertFalse(restored_node["executionImplemented"])

    def test_node_status_drift_does_not_relax_identity_cordon_or_server_fences(self):
        candidate, review, observation = prepared(field_present=False)
        for update in ({"uid": "replacement"}, {"unschedulable": True, "unschedulablePresent": True},
                       {"unschedulablePresent": True}):
            bad = copy.deepcopy(observation)
            bad["node"].update(resourceVersion="benign-status-rv", **update)
            with self.subTest(before_cordon=update), self.assertRaises(ValueError):
                plan.unlock_step(candidate, review, bad, [], "cordon", authorize=True, now=NOW)
        journal = []
        for step in ("cordon", "raise-memory-0"):
            operation = plan.unlock_step(candidate, review, observation, journal, step, authorize=True, now=NOW)
            apply_result(operation, observation, journal)
        mutations = [lambda o: o["node"].update(uid="replacement"),
                     lambda o: o["node"].update(unschedulable=False),
                     lambda o: o["node"].update(unschedulablePresent=False),
                     lambda o: o["node"].update(ready=False),
                     lambda o: o["server"].update(pid=3166884),
                     lambda o: o["server"].update(startTimeTicks=792169719),
                     lambda o: o["server"].update(uid=1000),
                     lambda o: o["server"].update(clients=[123]),
                     lambda o: o["defaults"]["deviceMemoryLimits"].update({"0": "40G"}),
                     lambda o: o.update(unexpectedGpuPods=["unrelated"])]
        for mutate in mutations:
            bad = copy.deepcopy(observation)
            bad["node"]["resourceVersion"] = "benign-status-rv"
            mutate(bad)
            with self.subTest(rollback_fence=mutate), self.assertRaises(ValueError):
                plan.unlock_step(candidate, review, bad, journal, "restore-memory-0", authorize=True, now=NOW)

    def test_prepare_rejects_unsafe_reference_and_stage(self):
        for field, value in (("maxWindowSeconds", 181), ("maxWindowSeconds", True), ("raiseActiveThreads", "yes")):
            identity, details, observation, request = fixture(); request[field] = value
            with self.assertRaises(ValueError): plan.prepare(identity, details, observation, request, now=NOW)
        for mutate in (lambda o: o["stagedPods"][0].update(processUid=1000),
                       lambda o: o["stagedPods"][0].update(gpuUuid=plan.GPUS[1]),
                       lambda o: o["defaults"]["deviceMemoryLimits"].update({"0": "40G"})):
            identity, details, observation, request = fixture(); mutate(observation)
            with self.assertRaises(ValueError): plan.prepare(identity, details, observation, request, now=NOW)
        identity, details, observation, request = fixture()
        details["processes"]["1260846"]["command"].append("-multiuser-server")
        with self.assertRaisesRegex(ValueError, "without multiuser"):
            plan.prepare(identity, details, observation, request, now=NOW)

    def test_deadline_blocks_forward_but_allows_fresh_guarded_rollback(self):
        candidate, review, observation = prepared()
        journal = []
        for step in ("cordon", "raise-memory-0"):
            operation = plan.unlock_step(candidate, review, observation, journal, step, authorize=True, now=NOW)
            apply_result(operation, observation, journal)
        later = NOW + dt.timedelta(seconds=181)
        observation["observedAt"] = later.isoformat()
        with self.assertRaisesRegex(ValueError, "window elapsed"):
            plan.unlock_step(candidate, review, observation, journal, "raise-memory-1", authorize=True, now=later)
        rollback = plan.unlock_step(candidate, review, observation, journal, "restore-memory-0", authorize=True, now=later)
        self.assertTrue(rollback["stdin"].endswith("5120M\n"))
        apply_result(rollback, observation, journal)
        restored = plan.unlock_step(candidate, review, observation, journal, "restore-node", authorize=True, now=later)
        self.assertEqual(restored["patch"][-1]["value"], False)
        with self.assertRaisesRegex(ValueError, "rollback forbids"):
            plan.unlock_step(candidate, review, observation, journal, "raise-memory-1", authorize=True, now=later)

    def test_restore_node_requires_all_ceilings_restored_and_clients_exited(self):
        candidate, review, observation = prepared()
        journal = []
        for step in ("cordon", "raise-memory-0"):
            operation = plan.unlock_step(candidate, review, observation, journal, step, authorize=True, now=NOW)
            apply_result(operation, observation, journal)
        with self.assertRaisesRegex(ValueError, "Restore all"):
            plan.unlock_step(candidate, review, observation, journal, "restore-node", authorize=True, now=NOW)
        observation["stagedPods"][0].update(mainStarted=True, gateRunning=False, phase="Running")
        with self.assertRaisesRegex(ValueError, "must exit"):
            plan.unlock_step(candidate, review, observation, journal, "restore-memory-0", authorize=True, now=NOW)

    def test_original_cordon_is_preserved_and_absent_field_restored_as_absent(self):
        candidate, _, _ = prepared(cordoned=True)
        self.assertNotIn("cordon", candidate["steps"]); self.assertNotIn("restore-node", candidate["steps"])
        candidate, review, observation = prepared(field_present=False)
        journal = []
        operation = plan.unlock_step(candidate, review, observation, journal, "cordon", authorize=True, now=NOW)
        self.assertEqual(operation["patch"][-1], {"op": "add", "path": "/spec/unschedulable", "value": True})
        apply_result(operation, observation, journal)
        operation = plan.unlock_step(candidate, review, observation, journal, "restore-node", authorize=True, now=NOW)
        self.assertEqual(operation["patch"][-1], {"op": "remove", "path": "/spec/unschedulable"})

    def test_input_mutation_isolation_and_serialized_step_survives_roundtrip(self):
        identity, details, observation, request = fixture()
        original = copy.deepcopy((identity, details, observation, request))
        candidate = plan.prepare(identity, details, observation, request, now=NOW)
        self.assertEqual((identity, details, observation, request), original)
        observation["node"]["uid"] = "changed"
        self.assertEqual(candidate["original"]["node"]["uid"], plan.NODE_UID)
        json.loads(json.dumps(candidate))

    def test_offline_module_has_no_process_network_or_cuda_execution(self):
        tree = ast.parse((HERE / "plan.py").read_text())
        imports = {name.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for name in node.names}
        self.assertTrue(imports <= {"argparse", "copy", "datetime", "hashlib", "json", "re"})
        from_imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(from_imports, {"decimal", "pathlib"})
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
                            node.func.id in ("eval", "exec", "__import__") for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()

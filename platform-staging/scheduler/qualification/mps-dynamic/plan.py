#!/usr/bin/env python3
"""Offline, receipt-gated MPS maintenance steps. This program never executes them."""
import argparse
import copy
import datetime as dt
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

NODE = "k3s-wk-gpu2"
NODE_UID = "3336cdd5-d245-436e-b57c-2f66c6dcaa41"
DAEMON = "mps-control-daemon-standalone-m2587"
DAEMON_UID = "4cb8c92b-95a7-4a30-9d62-bc17bb542941"
DAEMON_IMAGE = "nvcr.io/nvidia/k8s-device-plugin@sha256:2d16df5f3f12081b4bd6b317cf697e5c7a195c53cec7e0bab756db02a06b985c"
PROTECTED_UID = "a663ab6b-e927-418f-9671-fc0b36a27b3a"
GPUS = ("GPU-16128952-b438-556a-00bb-93039ee24e56", "GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6")
PIPE = "/mps/nvidia.com/gpu/pipe"
REFERENCE_COMMANDS = ["get_server_list", "get_server_status 3166883", "get_client_list 3166883",
    *[f"get_device_pinned_mem_limit 3166883 {gpu}" for gpu in GPUS],
    "get_default_device_pinned_mem_limit 0", "get_default_device_pinned_mem_limit 1",
    "get_active_thread_percentage 3166883", "get_default_active_thread_percentage"]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                   allow_nan=False).encode()).hexdigest()


def instant(value):
    require(isinstance(value, str), "Receipt timestamp text required")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "Timezone-aware receipt timestamp required")
    return parsed.astimezone(dt.timezone.utc)


def fresh(value, now, seconds):
    age = (now - instant(value)).total_seconds()
    require(0 <= age <= seconds, "Receipt is stale or in the future")


def memory_mib(value):
    require(isinstance(value, str), "MPS memory limit text required")
    match = re.fullmatch(r"([1-9][0-9]*)([GM])", value)
    require(match is not None, "MPS memory limit must use reviewed integer G/M units")
    return int(match[1]) * (1024 if match[2] == "G" else 1)


def percentage(value):
    require(isinstance(value, str), "MPS percentage receipt text required")
    require(re.fullmatch(r"[0-9]+(?:\.0+)?", value) is not None, "Integral MPS percentage required")
    result = int(Decimal(value))
    require(1 <= result <= 100, "MPS percentage outside 1..100")
    return result


def reference(identity, details):
    """Pin the root's observed controller/server rather than predicting a PID."""
    require(identity.get("settingsChanged") is False and details.get("settingsChanged") is False,
            "Read-only reference receipts required")
    require((identity.get("nodeUid"), identity.get("daemonPod"), identity.get("daemonUid")) ==
            (NODE_UID, DAEMON, DAEMON_UID), "Reference node/daemon differs from reviewed GPU2")
    require(identity.get("readOnlyCommands") == REFERENCE_COMMANDS, "Reference command sequence changed")
    require(identity.get("controlOutput", "").split() ==
            ["3166883", "ACTIVE", "5G", "5G", "5G", "5G", "12.0", "12.0"],
            "Reference MPS limits or clients changed")
    stat = identity["processIdentityOutput"]
    require(stat.startswith("3166883 (") and ")" in stat, "Reference process stat malformed")
    fields = stat[stat.rfind(")") + 1:].split()
    require(len(fields) >= 20 and fields[19].isdigit(), "Reference process start time missing")
    processes = details["processes"]
    server, control = processes["3166883"], processes["1260846"]
    require(server["status"]["Uid"].split() == ["10001"] * 4,
            "Reviewed server process UID changed")
    require(server["status"]["PPid"] == "1260846" and
            [v for v in server["command"] if v] == ["nvidia-cuda-mps-server"],
            "Reviewed server parent/command changed")
    require(control["status"]["Uid"].split() == ["0"] * 4 and
            control["command"] == ["nvidia-cuda-mps-control", "-d"],
            "Root legacy controller without multiuser mode required")
    statuses = identity["daemonStatuses"]
    require({s["name"] for s in statuses} == {"config-manager", "mps-control-daemon-ctr"},
            "Both reviewed daemon containers required")
    require(all(s["imageId"] == DAEMON_IMAGE and s["restarts"] == 0 and
                re.fullmatch(r"containerd://[a-f0-9]{64}", s["containerId"]) for s in statuses),
            "Reference daemon image/container identity changed")
    return {"pid": 3166883, "startTimeTicks": int(fields[19]), "uid": 10001,
            "controlPid": 1260846, "containerStatuses": copy.deepcopy(statuses)}


def common(observation, pinned, *, now, max_age):
    fresh(observation["observedAt"], now, max_age)
    node, daemon, protected = (observation[k] for k in ("node", "daemon", "protected"))
    require(node["name"] == NODE and node["uid"] == NODE_UID, "GPU2 node UID changed")
    require(node.get("ready") is True, "Fresh GPU2 Ready condition must be True")
    require(type(node["unschedulable"]) is bool, "Original node scheduling state required")
    require(type(node["unschedulablePresent"]) is bool, "Original scheduling-field presence required")
    require(node["unschedulablePresent"] or node["unschedulable"] is False,
            "Absent unschedulable field cannot represent a cordoned node")
    require(all(isinstance(v["resourceVersion"], str) and v["resourceVersion"]
                for v in (node, daemon, protected)), "Node/daemon/protected resource versions required")
    require((daemon["namespace"], daemon["name"], daemon["uid"], daemon["nodeName"], daemon["phase"]) ==
            ("gpu-operator", DAEMON, DAEMON_UID, NODE, "Running"), "Daemon Pod identity changed")
    require(sorted(daemon["containerStatuses"], key=lambda v: v["name"]) ==
            sorted(pinned["containerStatuses"], key=lambda v: v["name"]), "Daemon restarted or image changed")
    require((protected["namespace"], protected["name"], protected["uid"], protected["nodeName"],
             protected["phase"], protected["restarts"]) ==
            ("jupyterhub", "jupyter-bjoern", PROTECTED_UID, "k3s-wk-gpu1", "Running", 0),
            "Protected GPU1 notebook changed")
    server, control = observation["server"], observation["control"]
    require(all(server[k] == pinned[k] for k in ("pid", "startTimeTicks", "uid")),
            "Server replaced or process identity changed; never automatically reapply")
    require(server["status"] == "ACTIVE" and server["clients"] == [], "Idle ACTIVE server required")
    require(control == {"pid": pinned["controlPid"], "uid": 0,
                        "command": ["nvidia-cuda-mps-control", "-d"]}, "Controller identity/flags changed")
    require(observation["unexpectedGpuPods"] == [], "Unexpected running or bound pending GPU Pod")
    gpus = observation["gpus"]
    require(len(gpus) == 2 and {g["uuid"] for g in gpus} == set(GPUS), "Physical GPU inventory changed")
    for gpu in gpus:
        require(type(gpu["index"]) is int and gpu["index"] in (0, 1) and GPUS[gpu["index"]] == gpu["uuid"] and
                gpu["totalMiB"] == 40960 and gpu["migCurrent"] == gpu["migPending"] == "Disabled" and
                gpu["computeMode"] == "Default", "GPU ordinal/memory/mode differs from reference")
        require(type(gpu["usedMiB"]) is int and 0 <= gpu["usedMiB"] <= 128, "GPU not idle")
    processes = observation["gpuProcesses"]
    require(len(processes) == 2 and {p["gpuUuid"] for p in processes} == set(GPUS) and
            all(p["pid"] == pinned["pid"] and p["uid"] == pinned["uid"] for p in processes),
            "Unexpected GPU process or missing server/device association")


def staged(observation, *, run_id, started=False, expected=None):
    pods = observation["stagedPods"]
    require(len(pods) == 3 and len({p["uid"] for p in pods}) == 3,
            "Exactly three distinct reviewed CPU-gated profile Pods required")
    require({p["memoryMiB"] for p in pods} == {5120, 10240, 20480}, "5/10/20 GiB staged matrix required")
    require(len({p["gpuUuid"] for p in pods}) == 1, "Mixed matrix must actually occupy the same GPU")
    for pod in pods:
        require(pod["namespace"] == "cps-gpu-qualification" and pod["nodeName"] == NODE and
                pod["runId"] == run_id and pod["gpuUuid"] in GPUS and pod["uid"] and pod["jobUid"] and
                pod["resourceVersion"] and re.fullmatch(r"\S+@sha256:[a-f0-9]{64}", pod["image"]) and
                re.fullmatch(r"[a-f0-9]{64}", pod["probeSha256"]), "Staged Pod provenance incomplete")
        require(pod["processUid"] == 10001, "Current-server candidate permits only matching UID 10001")
        if not started:
            require(pod["gateRunning"] is True and pod["mainStarted"] is False,
                    "Every main container must remain behind a running CPU-only gate")
        else:
            require((pod["mainStarted"] is False and pod["gateRunning"] is True) or
                    (pod["phase"] in ("Succeeded", "Failed") and pod["processesExited"] is True),
                    "All qualification processes must exit before rollback")
    fingerprints = [{k: p[k] for k in ("namespace", "name", "uid", "jobUid", "image", "probeSha256",
                    "nodeName", "runId", "gpuUuid", "memoryMiB", "processUid")} for p in pods]
    fingerprints.sort(key=lambda p: p["uid"])
    if expected is not None:
        require(fingerprints == expected, "Qualification Pod generation/provenance changed")
    return fingerprints


def prepare(identity, details, observation, request, *, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    require(set(request) == {"runId", "maxWindowSeconds", "raiseActiveThreads"}, "Closed request schema required")
    require(isinstance(request["runId"], str) and re.fullmatch(r"[a-z0-9]{8,32}", request["runId"]) is not None,
            "Bounded run identifier required")
    require(type(request["maxWindowSeconds"]) is int and 1 <= request["maxWindowSeconds"] <= 180,
            "Maintenance window must be at most 180 seconds")
    require(type(request["raiseActiveThreads"]) is bool, "Explicit optional thread-ceiling choice required")
    pinned = reference(identity, details)
    common(observation, pinned, now=now, max_age=900)
    fingerprints = staged(observation, run_id=request["runId"])
    original = copy.deepcopy(observation)
    memory = observation["server"]["deviceMemoryLimits"]
    require(set(memory) == set(GPUS) and all(memory_mib(memory[g]) == 5120 for g in GPUS),
            "Original active memory ceilings must match the reviewed 5GiB reference")
    require(observation["defaults"] == {"deviceMemoryLimits": {"0": "5G", "1": "5G"},
                                      "activeThreadPercentage": "12.0"}, "Daemon defaults changed")
    old_threads = percentage(observation["server"]["activeThreadPercentage"])
    require(old_threads == 12, "Original active thread ceiling differs from reference")
    steps = []
    if not original["node"]["unschedulable"]:
        steps.append("cordon")
    steps += ["raise-memory-0", "raise-memory-1"]
    if request["raiseActiveThreads"]:
        steps.append("raise-threads")
    steps.append("run-qualification")
    if request["raiseActiveThreads"]:
        steps.append("restore-threads")
    steps += ["restore-memory-0", "restore-memory-1"]
    if not original["node"]["unschedulable"]:
        steps.append("restore-node")
    candidate = {"schemaVersion": 1, "status": "locked-offline-candidate", "executionImplemented": False,
        "productionQualified": False, "request": copy.deepcopy(request), "pinned": pinned,
        "sourceReceiptHashes": {"identity": digest(identity), "processDetails": digest(details)},
        "original": original, "stagedFingerprints": fingerprints, "steps": steps,
        "limits": {"temporaryMemoryMiB": 40960, "temporaryThreadPercentage": 100,
                   "stepObservationMaxAgeSeconds": 15}}
    candidate["candidateSha256"] = digest(candidate)
    return candidate


def unlock_step(candidate, review, observation, journal, step, *, authorize=False, now=None):
    """Return ONE guarded operation, never perform it. Root supplies fresh results."""
    now = now or dt.datetime.now(dt.timezone.utc)
    require(authorize is True, "Explicit --authorize-stateful-step flag required")
    unhashed = {k: v for k, v in candidate.items() if k != "candidateSha256"}
    require(candidate["candidateSha256"] == digest(unhashed), "Candidate hash changed")
    require(review.get("schemaVersion") == 1 and review.get("candidateSha256") == candidate["candidateSha256"] and
            review.get("statefulStepsReviewed") is True and isinstance(review.get("actor"), str) and
            review["actor"].strip() and review.get("steps") == candidate["steps"], "Exact reviewed candidate receipt required")
    require(isinstance(journal, list), "Completed-step journal required")
    completed = [entry.get("step") for entry in journal]
    require(all(name in candidate["steps"] for name in completed) and len(set(completed)) == len(completed),
            "Unknown or repeated completed step")
    split = next((i for i, name in enumerate(completed) if name.startswith("restore-")), len(completed))
    require(completed[:split] == candidate["steps"][:split] and
            all(name.startswith("restore-") for name in completed[split:]), "Ordered completed-step journal required")
    rollback = step.startswith("restore-")
    require(step in candidate["steps"] and step not in completed, "Unknown or repeated requested step")
    if not rollback:
        require(split == len(completed) and step == candidate["steps"][len(completed)],
                "Only next forward step allowed; rollback forbids further raising/release")
    require(all(entry.get("candidateSha256") == candidate["candidateSha256"] for entry in journal),
            "Journal belongs to another candidate")
    age = (now - instant(review["reviewedAt"])).total_seconds()
    require(age >= 0 and (rollback or age <= candidate["request"]["maxWindowSeconds"]),
            "180-second window elapsed; only guarded rollback remains permitted")
    common(observation, candidate["pinned"], now=now, max_age=15)
    original = candidate["original"]
    require(observation["defaults"] == original["defaults"], "Default settings changed during window")
    for name in ("daemon", "protected"):
        require(observation[name]["resourceVersion"] == original[name]["resourceVersion"],
                f"{name} resource version changed; fresh review required")
    expected_cordon = original["node"]["unschedulable"] if step == "cordon" else True
    expected_presence = original["node"]["unschedulablePresent"] if step == "cordon" else True
    require(observation["node"]["unschedulable"] is expected_cordon and
            observation["node"]["unschedulablePresent"] is expected_presence,
            "GPU2 scheduling state or field presence changed")
    # Node status updates may advance RV without changing the scheduling fence.
    # Cordon/restore patches compare-and-swap the freshly observed API version.
    node_rv = observation["node"]["resourceVersion"]
    for entry in journal:
        if entry["step"] == "cordon":
            require(isinstance(entry.get("resultNodeResourceVersion"), str) and entry["resultNodeResourceVersion"],
                    "Observed cordon result resource version required")
    staged(observation, run_id=candidate["request"]["runId"], started=rollback,
           expected=candidate["stagedFingerprints"])
    expected_memory = copy.deepcopy(original["server"]["deviceMemoryLimits"])
    expected_thread = percentage(original["server"]["activeThreadPercentage"])
    for entry in journal:
        previous = entry["step"]
        if previous.startswith("raise-memory-"):
            expected_memory[GPUS[int(previous[-1])]] = "40960M"
        elif previous.startswith("restore-memory-"):
            expected_memory[GPUS[int(previous[-1])]] = original["server"]["deviceMemoryLimits"][GPUS[int(previous[-1])]]
        elif previous == "raise-threads":
            expected_thread = 100
        elif previous == "restore-threads":
            expected_thread = percentage(original["server"]["activeThreadPercentage"])
    actual_memory = observation["server"]["deviceMemoryLimits"]
    require(set(actual_memory) == set(GPUS) and all(memory_mib(actual_memory[g]) == memory_mib(expected_memory[g]) for g in GPUS),
            "Active memory readback differs from completed steps")
    require(percentage(observation["server"]["activeThreadPercentage"]) == expected_thread,
            "Active thread readback differs from completed steps")
    result = {"step": step, "candidateSha256": candidate["candidateSha256"], "executionImplemented": False,
              "authorizedOperationOnly": True, "mustRecordReadbackBeforeNextStep": True}
    if step in ("cordon", "restore-node"):
        patch = [
            {"op": "test", "path": "/metadata/uid", "value": NODE_UID},
            {"op": "test", "path": "/metadata/resourceVersion", "value": node_rv}]
        if step == "cordon":
            if original["node"]["unschedulablePresent"]:
                patch += [{"op": "test", "path": "/spec/unschedulable", "value": False},
                          {"op": "replace", "path": "/spec/unschedulable", "value": True}]
            else:
                patch.append({"op": "add", "path": "/spec/unschedulable", "value": True})
        else:
            require(all(memory_mib(actual_memory[g]) == memory_mib(original["server"]["deviceMemoryLimits"][g]) for g in GPUS)
                    and expected_thread == percentage(original["server"]["activeThreadPercentage"]),
                    "Restore all active ceilings before restoring node scheduling")
            patch += [{"op": "test", "path": "/spec/unschedulable", "value": True},
                      {"op": "replace", "path": "/spec/unschedulable", "value": False}
                      if original["node"]["unschedulablePresent"] else {"op": "remove", "path": "/spec/unschedulable"}]
        result.update(kind="node-json-patch", name=NODE, patch=patch)
    elif "memory" in step or "threads" in step:
        pid = candidate["pinned"]["pid"]
        if "memory" in step:
            gpu = GPUS[int(step[-1])]
            limit = memory_mib(original["server"]["deviceMemoryLimits"][gpu]) if rollback else 40960
            command = f"set_device_pinned_mem_limit {pid} {gpu} {limit}M"
            readback = f"get_device_pinned_mem_limit {pid} {gpu}"
        else:
            value = percentage(original["server"]["activeThreadPercentage"]) if rollback else 100
            command, readback = f"set_active_thread_percentage {pid} {value}", f"get_active_thread_percentage {pid}"
        result.update(kind="active-server-control", namespace="gpu-operator", pod=DAEMON,
            podUid=DAEMON_UID, podResourceVersion=observation["daemon"]["resourceVersion"],
            container="mps-control-daemon-ctr", pipeDirectory=PIPE, stdin=command + "\n", readback=readback,
            serverProcessFence={k: candidate["pinned"][k] for k in ("pid", "startTimeTicks", "uid")})
    else:
        result.update(kind="root-owned-qualification-gates", remainingWindowSeconds=
            max(0, int(candidate["request"]["maxWindowSeconds"] - age)),
            pods=[{**p, "resourceVersion": next(v["resourceVersion"] for v in observation["stagedPods"]
                    if v["uid"] == p["uid"])} for p in candidate["stagedFingerprints"]],
            requirements=["Approved jobs have their own bounded deadlines", "Capture every actual MPS client PID",
                "New clients inherit temporary ceilings; existing clients are unaffected",
                "Synchronize CUDA work and confirm all clients exit before recording completion"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("prepare")
    for name in ("identity", "process-details", "observation", "request"):
        build.add_argument("--" + name, type=Path, required=True)
    step = sub.add_parser("step")
    for name in ("candidate", "review", "observation", "journal"):
        step.add_argument("--" + name, type=Path, required=True)
    step.add_argument("--step", required=True)
    step.add_argument("--authorize-stateful-step", action="store_true")
    args = parser.parse_args()
    read = lambda name: json.loads(getattr(args, name).read_text())
    try:
        value = prepare(read("identity"), read("process_details"), read("observation"), read("request")) \
            if args.command == "prepare" else unlock_step(read("candidate"), read("review"),
                read("observation"), read("journal"), args.step, authorize=args.authorize_stateful_step)
    except (ValueError, KeyError, TypeError, IndexError, OSError) as exc:
        parser.exit(2, f"Refused: {exc}\n")
    print(json.dumps(value, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

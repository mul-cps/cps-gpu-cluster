#!/usr/bin/env python3
"""Offline evidence evaluation; no synthetic report can activate production."""
import argparse
import json
import hashlib
from pathlib import Path

from probe_compiled import CACHE_PATH, ROUNDS, concurrent_verdict, normalized_uuid, ordinary_verdict
from render_compiled import (GPU_UUID_FIELD_PATH, HAMI_PATH, HAMI_REVISION, IMAGE, NODE,
    REVIEWED_GPU_ANNOTATION, SOURCE_COMMIT, WHEEL_SHA256, MODULE_SHA256,
    REVIEWED_IDENTITIES, OPERATOR_GATE, compile_plan)
from probe_compiled import HOLD_SECONDS, HOLD_TICKS


def valid_hami(value, preflight):
    return (value["referenceSourceRevision"] == HAMI_REVISION and value["sourceRevisionVerified"] is False
            and value["libraryPath"] == HAMI_PATH
            and value["sha256"] == preflight["hami"]["sha256"]
            and value["loaded"] is True and value["preloadVerified"] is True
            and value["effectiveLimitBytes"] == 5120 * 1024**2
            and value["schedulerInjectedLimitBytes"] == 5324 * 1024**2
            and value["canonicalLimitBytes"] == 5120 * 1024**2
            and value["perDeviceLimitVerified"] is True and value["singleVisibleDeviceVerified"] is True)


def resolve_configmap_env(entry, pod, receipts):
    """Resolve only a stable, currently observed ConfigMap owned by this Pod."""
    if "value" in entry and "valueFrom" not in entry:
        return entry["value"], None
    reference = entry["valueFrom"]["configMapKeyRef"]
    metadata = pod["metadata"]
    matches = []
    for stage in ("before", "after"):
        items = [cm for cm in receipts[stage]["items"]
                 if cm.get("metadata", {}).get("name") == reference["name"] and
                 cm.get("metadata", {}).get("namespace") == metadata["namespace"]]
        if len(items) != 1:
            raise ValueError("Referenced ConfigMap snapshot missing or ambiguous")
        cm = items[0]
        own = cm["metadata"]
        if (cm.get("apiVersion") != "v1" or cm.get("kind") != "ConfigMap" or
                not own.get("uid") or not own.get("resourceVersion") or
                not any(owner.get("kind") == "Pod" and owner.get("apiVersion") == "v1" and
                    owner.get("uid") == metadata["uid"] and owner.get("name") == metadata["name"]
                    for owner in own.get("ownerReferences", []))):
            raise ValueError("Referenced ConfigMap identity/Pod ownership unproven")
        matches.append(cm)
    before, after = matches
    if (before["metadata"]["uid"] != after["metadata"]["uid"] or
            before["metadata"]["resourceVersion"] != after["metadata"]["resourceVersion"] or
            before["metadata"].get("ownerReferences") != after["metadata"].get("ownerReferences") or
            before.get("data") != after.get("data")):
        raise ValueError("Referenced ConfigMap changed during collection")
    result = after["data"][reference["key"]]
    if not isinstance(result, str):
        raise ValueError("ConfigMap environment value must be a string")
    return result, {"name": reference["name"], "namespace": metadata["namespace"],
                    "uid": after["metadata"]["uid"], "resourceVersion": after["metadata"]["resourceVersion"],
                    "key": reference["key"], "ownerPodUid": metadata["uid"]}


def valid_round_ticks(record, child_values):
    """Bind each successful allocation to its exact same-process write receipt."""
    try:
        number = record["round"]
        if type(number) is not int or not 0 <= number < ROUNDS:
            return False
        ident = f"concurrent-{number}"
        results, ticks = record["results"], record["successfulTicks"]
        if len(results) != 2 or len({value["pid"] for value in results}) != 2:
            return False
        for value in results:
            if (type(value["pid"]) is not int or value["pid"] <= 0 or
                    value["event"] != "response" or value["id"] != ident or
                    value["label"] != ident or value["action"] != "allocate" or
                    sum(receipt == value for receipt in child_values) != 1):
                return False
        successes = {value["pid"]: value for value in results if value["cudaResult"] == 0}
        if len(ticks) != len(successes) or {tick["pid"] for tick in ticks} != set(successes):
            return False
        for tick in ticks:
            allocation = successes[tick["pid"]]
            if (tick["event"] != "response" or tick["action"] != "tick" or
                    tick["id"] != f"{ident}-tick" or tick["label"] != ident or
                    tick["cudaResult"] != 0 or tick["gpu"] != allocation["gpu"] or
                    tick["cache"] != allocation["cache"] or tick["hami"] != allocation["hami"] or
                    sum(receipt == tick for receipt in child_values) != 1):
                return False
        return True
    except (KeyError, TypeError):
        return False


def peer_covers_window(times, start, finish):
    """Include boundary heartbeats and every intervening gap in the proof."""
    if (type(start) is not int or type(finish) is not int or not 0 <= start < finish or
            not times or any(type(t) is not int or t < 0 for t in times)):
        return False
    ordered = sorted(times)
    preceding = [t for t in ordered if t <= start]
    following = [t for t in ordered if t >= finish]
    if not preceding or not following:
        return False
    before, after = preceding[-1], following[0]
    if start - before > 1_000_000_000 or after - finish > 1_000_000_000:
        return False
    covered = [t for t in ordered if before <= t <= after]
    return all(b - a <= 1_000_000_000 for a, b in zip(covered, covered[1:]))


def json_events(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.startswith("{")]



def contains_fragment(actual, required):
    if isinstance(required, dict):
        return isinstance(actual, dict) and all(k in actual and contains_fragment(actual[k], v)
                                               for k, v in required.items())
    return actual == required


def require_named_fragments(actual, required):
    if len({item["name"] for item in actual}) != len(actual):
        raise ValueError("Duplicate Pod runtime names")
    for fragment in required:
        matches = [item for item in actual if item.get("name") == fragment["name"]]
        if len(matches) != 1 or not contains_fragment(matches[0], fragment):
            raise ValueError("Compiled runtime fragment changed")


def valid_hold(hold, events, child_values, cache, gpu):
    """Actual child writes during a fixed hold are not an MPS daemon receipt."""
    try:
        start, finish = hold["startedNs"], hold["finishedNs"]
        if (type(start) is not int or type(finish) is not int or
                not HOLD_SECONDS * 10**9 <= finish-start <= (HOLD_SECONDS+15) * 10**9 or
                hold["durationSeconds"] != HOLD_SECONDS or hold["mpsThreeClientQualified"] is not False):
            return False
        pids = hold["childPids"]
        ready = [v for v in child_values if v.get("event") == "ready"]
        names = {e["value"]["pid"]: e["child"] for e in events
                 if e.get("event") == "child-evidence" and e["value"].get("event") == "ready"}
        if (len(pids) != 2 or len(set(pids)) != 2 or set(pids) != {v["pid"] for v in ready}
                or set(names) != set(pids) or set(names.values()) != {"a", "b"}):
            return False
        phases = [e for e in events if e.get("event") in ("mps-hold-start", "mps-hold-finished")]
        starts = [e for e in phases if e["event"] == "mps-hold-start"]
        ends = [e for e in phases if e["event"] == "mps-hold-finished"]
        if (len(starts) != 1 or len(ends) != 1 or starts[0]["startedNs"] != start or
                ends[0]["startedNs"] != start or ends[0]["finishedNs"] != finish or
                any(e["childPids"] != pids or e["mpsThreeClientQualified"] is not False for e in phases)):
            return False
        ticks = hold["ticks"]
        if len(ticks) != HOLD_TICKS or [t["tick"] for t in ticks] != list(range(HOLD_TICKS)):
            return False
        times = [t["observedNs"] for t in ticks]
        if (any(type(t) is not int for t in times) or times != sorted(times) or
                not start <= times[0] <= start+10**9 or not finish-10**9 <= times[-1] <= finish or
                any(b-a > 10**9 for a,b in zip(times,times[1:]))):
            return False
        progress = [e for e in events if e.get("event") == "mps-hold-progress"]
        if len(progress) != HOLD_TICKS:
            return False
        for tick, event in zip(ticks, progress):
            if any(event.get(k) != v for k,v in tick.items()) or event.get("mpsThreeClientQualified") is not False:
                return False
            values = tick["values"]
            if len(values) != 2 or {v["pid"] for v in values} != set(pids):
                return False
            for value in values:
                if (value["event"] != "response" or value["id"] != f"hold-{tick['tick']}-{names[value['pid']]}" or
                        value["action"] != "tick" or value["label"] != "mps-hold" or
                        value["cudaResult"] != 0 or value["gpu"] != gpu or value["cache"] != cache or
                        sum(v == value for v in child_values) != 1):
                    return False
        for action, key in (("allocate", "allocations"), ("free", "frees")):
            values = hold[key]
            if len(values) != 2 or {v["pid"] for v in values} != set(pids):
                return False
            if any(v["event"] != "response" or v["id"] != f"hold-{names[v['pid']]}-{action}" or
                   v["action"] != action or v["label"] != "mps-hold" or v["cudaResult"] != 0 or
                   v["gpu"] != gpu or v["cache"] != cache or sum(c == v for c in child_values) != 1
                   for v in values):
                return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def evaluate(workspace_events, peer_events, workspace_pod, peer_pod, node, preflight, configmaps=None, *, fixture=None, compiler_wheel=None):
    reasons = []
    fixture_proof, plan, identity = None, None, None
    try:
        fixture_cm = fixture["items"][0]
        if fixture_cm["kind"] != "ConfigMap" or fixture_cm["immutable"] is not True:
            raise ValueError("Immutable fixture ConfigMap required")
        fixture_proof = json.loads(fixture_cm["data"]["preflight.json"])
        identity = (fixture_proof["runtimeIdentity"]["uid"], fixture_proof["runtimeIdentity"]["gid"])
        if identity not in REVIEWED_IDENTITIES:
            raise ValueError("Unknown reviewed workload identity")
        compiler = {"sourceCommit": SOURCE_COMMIT, "wheelSha256": WHEEL_SHA256,
                    "moduleSha256": MODULE_SHA256, "image": IMAGE}
        if fixture_proof["compiler"] != compiler or fixture_proof["image"] != IMAGE or preflight["image"] != IMAGE:
            raise ValueError("Compiler/image provenance mismatch")
        plan = compile_plan(compiler_wheel, *identity)
        if fixture_proof["runtimePlan"] != plan or fixture_proof["nodeUid"] != preflight["node"]["uid"]:
            raise ValueError("Compiled plan/node receipt mismatch")
        source_sha = hashlib.sha256(fixture_cm["data"]["probe_compiled.py"].encode()).hexdigest()
        current_sha = hashlib.sha256((Path(__file__).parent / "probe_compiled.py").read_bytes()).hexdigest()
        if (source_sha != fixture_proof["probeSha256"] or source_sha != current_sha or
                fixture_cm["data"]["operator-gate.py"] != OPERATOR_GATE):
            raise ValueError("Fixture probe source hash mismatch")
    except (KeyError, TypeError, ValueError, OSError):
        reasons.append("Exact packaged compiler fixture provenance is missing or invalid")
    reports = [e for e in workspace_events if e.get("event") == "workspace-result"]
    if len(reports) != 1:
        return {"status": "inconclusive", "reasons": ["Exactly one workspace report required"],
                "productionQualified": False, "hostileIsolationQualified": False}
    report = reports[0]
    reviewed_gpu = workspace_pod.get("metadata", {}).get("annotations", {}).get(REVIEWED_GPU_ANNOTATION)
    whitelist = [gpu["uuid"] for gpu in preflight["gpus"]]
    expected = None
    try:
        if reviewed_gpu not in whitelist:
            raise ValueError("Selection is not in observed GPU2 inventory")
        expected = normalized_uuid(reviewed_gpu)
    except (TypeError, ValueError):
        reasons.append("Reviewed physical GPU selection is missing or outside observed GPU2 inventory")
    if node["metadata"].get("name") != NODE or node["metadata"].get("uid") != preflight["node"]["uid"]:
        reasons.append("Target node UID changed or does not match")
    uids = []
    run_ids = []
    quota_receipts = []
    selection_receipts = []
    for pod in (workspace_pod, peer_pod):
        metadata, spec = pod["metadata"], pod["spec"]
        uids.append(metadata["uid"])
        if metadata.get("namespace") != "cps-gpu-qualification" or spec.get("nodeName") != NODE:
            reasons.append("Fixture Pod is not in the reviewed namespace/node")
        main = [c for c in spec["containers"] if c["name"] == "main"]
        if len(main) != 1 or main[0]["image"] != IMAGE:
            reasons.append("Fixture image mismatch")
        env = {e["name"]: e.get("value") for e in main[0].get("env", [])}
        if metadata.get("annotations", {}).get(REVIEWED_GPU_ANNOTATION) != reviewed_gpu:
            reasons.append("Independent peer and workspace were not reviewed on the same physical GPU")
        expected_entries = [e for e in main[0].get("env", []) if e["name"] == "EXPECTED_GPU_UUID"]
        if (len(expected_entries) != 1 or expected_entries[0].get("valueFrom") != {
                "fieldRef": {"apiVersion": "v1", "fieldPath": GPU_UUID_FIELD_PATH}}):
            reasons.append("Expected GPU identity must come from the reviewed Pod annotation")
        try:
            selections = [e for e in main[0].get("env", []) if e["name"] == "NVIDIA_VISIBLE_DEVICES"]
            if (len(selections) != 1 or "value" in selections[0] or
                    selections[0]["valueFrom"]["configMapKeyRef"]["key"] != "NVIDIA_VISIBLE_DEVICES"):
                raise ValueError("Actual KAI-owned device selection reference required")
            selected, proof = resolve_configmap_env(selections[0], pod, configmaps)
            if proof is None or selected != f"k8s.device-plugin.nvidia.com/gpu={reviewed_gpu}":
                raise ValueError("Actual selected GPU differs from the reviewed annotation")
            selection_receipts.append(proof)
        except (KeyError, TypeError, ValueError):
            reasons.append("Actual KAI ConfigMap GPU selection could not be verified")
        for key in ("CUDA_DEVICE_MEMORY_LIMIT", "GPU_PORTION"):
            try:
                entries = [e for e in main[0].get("env", []) if e["name"] == key]
                if len(entries) != 1:
                    raise ValueError("Exactly one quota environment entry required")
                resolved, proof = resolve_configmap_env(entries[0], pod, configmaps)
                env[key] = resolved
                if proof:
                    quota_receipts.append(proof)
            except (KeyError, TypeError, ValueError):
                reasons.append("Scheduler quota ConfigMap identity/value could not be verified")
        run_ids.append(env.get("FIXTURE_RUN_ID"))
        if env.get("FIXTURE_RUN_ID") != metadata.get("annotations", {}).get("compute.cps.unileoben.ac.at/fixture-run-id"):
            reasons.append("Fixture run ID does not match the rendered annotation")
        if env.get("CUDA_DEVICE_MEMORY_SHARED_CACHE") != CACHE_PATH:
            reasons.append("Fixture cache configuration mismatch")
        if (env.get("CUDA_DEVICE_MEMORY_LIMIT") != "5324m" or env.get("GPU_PORTION") != "0.13" or
                env.get("CUDA_DEVICE_MEMORY_LIMIT_0") != "5120m" or env.get("EXPECTED_HAMI_LIMIT_MIB") != "5120" or
                env.get("EXPECTED_HAMI_SHA256") != preflight["hami"]["sha256"] or
                env.get("EXPECTED_HAMI_REVISION") != HAMI_REVISION):
            reasons.append("Fixture quota/HAMi provenance configuration mismatch")
        mount = [m for m in main[0].get("volumeMounts", []) if m["mountPath"] == CACHE_PATH]
        if len(mount) != 1 or mount[0].get("subPath") != "private/usage.cache":
            reasons.append("Fixed cache file mount absent")
        if plan and fixture_proof and identity:
            try:
                if len({e["name"] for e in main[0]["env"]}) != len(main[0]["env"]):
                    raise ValueError("Duplicate runtime environment names")
                if len(spec["containers"]) != 1 or [c["name"] for c in spec["initContainers"]] != [
                        "cps-gpu-cache-init", "await-operator-runtime-review"]:
                    raise ValueError("Unexpected executable container or init order")
                if (metadata["annotations"].get("compute.cps.unileoben.ac.at/probe-sha256") != fixture_proof["probeSha256"] or
                        env.get("FIXTURE_UID") != str(identity[0]) or env.get("FIXTURE_GID") != str(identity[1])):
                    raise ValueError("Identity/probe binding changed")
                if spec.get("automountServiceAccountToken") is not False:
                    raise ValueError("Fixture API credentials must be disabled")
                if spec.get("schedulerName") != "kai-scheduler" or spec.get("priorityClassName") != "cps-batch":
                    raise ValueError("Trusted scheduling changed")
                if not contains_fragment(spec.get("securityContext", {}), plan["pod_security_context"]):
                    raise ValueError("Pod identity/security mismatch")
                if not contains_fragment(main[0].get("securityContext", {}), plan["container_security_context"]):
                    raise ValueError("Main identity/security mismatch")
                if main[0].get("securityContext", {}).get("privileged", False) is not False:
                    raise ValueError("Privileged main container")
                for field, fragments in (("volumes", plan["volumes"]),):
                    require_named_fragments(spec[field], fragments)
                require_named_fragments(spec["initContainers"], plan["init_containers"])
                mounts = main[0]["volumeMounts"]
                for fragment in plan["volume_mounts"]:
                    matches = [item for item in mounts if item.get("mountPath") == fragment["mountPath"]]
                    if len(matches) != 1 or not contains_fragment(matches[0], fragment):
                        raise ValueError("Compiled mount changed")
                for key, expected_value in plan["environment"].items():
                    if env.get(key) != expected_value:
                        raise ValueError("Compiler-owned environment changed")
                gates = [c for c in spec["initContainers"] if c["name"] == "await-operator-runtime-review"]
                if len(gates) != 1 or gates[0]["command"] != ["python", "-u", "/probe/operator-gate.py",
                        "workspace" if pod is workspace_pod else "peer", fixture_proof["probeSha256"]]:
                    raise ValueError("Final CPU review gate absent or unbound")
                if (gates[0]["image"] != IMAGE or
                        not contains_fragment(gates[0].get("securityContext", {}), plan["container_security_context"]) or
                        gates[0].get("securityContext", {}).get("privileged", False) is not False or
                        gates[0].get("volumeMounts") != [
                            {"name": "probe", "mountPath": "/probe", "readOnly": True},
                            {"name": "cps-gpu-cache", "mountPath": "/cache-root"}]):
                    raise ValueError("CPU review gate runtime changed")
            except (KeyError, TypeError, ValueError):
                reasons.append("Actual Pod differs from trusted compiled runtime or CPU review gate")
        if pod.get("status", {}).get("phase") != "Succeeded":
            reasons.append("Fixture Pod did not finish successfully")
    if len(set(uids)) != 2:
        reasons.append("An independent peer workspace Pod is required")
    if len(set(run_ids)) != 1 or run_ids[0] is None:
        reasons.append("Both Pods must belong to the same controlled fixture run")
    for events, pod_uid in ((workspace_events, uids[0]), (peer_events, uids[1])):
        if any(event.get("podUid") != pod_uid or event.get("runId") != run_ids[0] for event in events):
            reasons.append("Log receipt does not belong to the observed fixture Pod/run")
    try:
        if not ordinary_verdict(report["ordinary"]):
            reasons.append("Ordinary CUDA denial/progress/recovery gate failed")
        rounds = report["concurrency"]
        if len(rounds) != ROUNDS or any(concurrent_verdict(r["results"]) != "bounded-round-passed" for r in rounds):
            reasons.append("Synchronized same-inode concurrency gate failed or was inconclusive")
        if report["gpu"] != expected:
            reasons.append("Workspace used a different GPU")
        if (report["requestedMiB"] != 5120 or report["schedulerInjectedMiB"] != 5324 or
                report["canonicalLimitMiB"] != 5120 or report["effectiveHamiLimitMiB"] != 5120 or
                report["schedulerQuotaDrift"] is not True or report["canonicalQuotaDrift"] is not False or
                report["exactProfileQuotaQualified"] is not False):
            reasons.append("Requested/scheduler/canonical quota observation contract changed")
        cache = report["cache"]
        if (not identity or (cache.get("uid"), cache.get("gid")) != identity or
                report.get("compiler") != {"sourceCommit": SOURCE_COMMIT, "moduleSha256": MODULE_SHA256, "version": "0.1.0"}):
            reasons.append("Observed cache owner or installed compiler package is unproven")
        if not valid_hami(report["hami"], preflight):
            reasons.append("Workspace preloaded HAMi binary or effective quota is unproven")
        if not cache["noTmpFallback"] or not cache["mappingVerified"]:
            reasons.append("Workspace cache inode mapping was not proven")
        child_values = [e["value"] for e in workspace_events if e.get("event") == "child-evidence"]
        if not valid_hold(report.get("hold"), workspace_events, child_values, cache, expected):
            reasons.append("Bounded two-client MPS observation hold is incomplete or unbound")
        if report.get("mpsThreeClientQualified") is not False:
            reasons.append("Hold phase cannot qualify three actual MPS clients")
        if ([r["round"] for r in rounds] != list(range(ROUNDS)) or
                any(not valid_round_ticks(r, child_values) for r in rounds)):
            reasons.append("Each concurrent success requires its exact successful child tick receipt")
        if {e.get("child") for e in workspace_events if e.get("event") == "child-evidence"} != {"a", "b"}:
            reasons.append("Both child processes require evidence")
        if not child_values or any(not valid_hami(v["hami"], preflight) or
            v["gpu"] != expected or not v["cache"]["noTmpFallback"] or
            (v["cache"]["device"], v["cache"]["inode"]) != (cache["device"], cache["inode"]) for v in child_values):
            reasons.append("A child changed cache inode, used fallback, or used another GPU")
        ready = [e for e in peer_events if e.get("event") == "peer-ready"]
        alive = [e for e in peer_events if e.get("event") == "peer-alive"]
        completed = [e for e in peer_events if e.get("event") == "peer-completed"]
        if len(ready) != 1 or len(completed) != 1 or not alive:
            reasons.append("Independent peer lifecycle evidence is incomplete")
        else:
            peer_cache = ready[0]["cache"]
            if (not identity or (peer_cache.get("uid"), peer_cache.get("gid")) != identity or
                    ready[0].get("compiler") != {"sourceCommit": SOURCE_COMMIT, "moduleSha256": MODULE_SHA256, "version": "0.1.0"}):
                reasons.append("Independent peer compiler/owner observation is unproven")
            if (peer_cache["device"], peer_cache["inode"]) == (cache["device"], cache["inode"]):
                reasons.append("Peer must have its own workspace cache inode")
            if any(e["gpu"] != expected or e.get("cudaResult", 0) != 0 for e in [ready[0], *alive, completed[0]]):
                reasons.append("Independent peer did not continue on the same physical GPU")
            if any(not valid_hami(e["hami"], preflight) or not e["cache"]["noTmpFallback"] or
                (e["cache"]["device"], e["cache"]["inode"]) != (peer_cache["device"], peer_cache["inode"]) for e in [ready[0], *alive]):
                reasons.append("Independent peer cache mapping changed")
            times = [e["observedNs"] for e in alive]
            start, finish = report["startedNs"], report["finishedNs"]
            if not peer_covers_window(times, start, finish):
                reasons.append("Peer progress has a missing, stale or interrupted boundary/window heartbeat")
    except (KeyError, TypeError, ValueError):
        reasons.append("Required CUDA/cache evidence is malformed or missing")
    if report.get("status") != "bounded-standard-cases-passed":
        reasons.append("Workspace reported failure or inconclusive evidence")
    return {"mpsThreeClientQualified": False, "compilerGeneratedRuntimeQualified": not reasons,
            "runtimeIdentity": {"uid": identity[0], "gid": identity[1]} if identity else None,
            "compilerSource": SOURCE_COMMIT,
            "status": "bounded-standard-cases-passed" if not reasons else "failed-or-inconclusive",
            "reasons": reasons, "productionQualified": False, "hostileIsolationQualified": False,
            "tamper": {"status": "not-run", "existingFailureRemains": True},
            "requestedMiB": 5120, "schedulerInjectedMiB": 5324, "canonicalLimitMiB": 5120,
            "effectiveHamiLimitMiB": report.get("effectiveHamiLimitMiB") if report.get("hami") else None,
            "schedulerQuotaDrift": True,
            "canonicalQuotaDrift": report.get("canonicalQuotaDrift") if report.get("hami") else None,
            "exactProfileQuotaQualified": False, "schedulerQuotaReceipts": quota_receipts,
            "schedulerSelectionReceipts": selection_receipts,
            "node": NODE, "nodeUid": preflight["node"]["uid"], "gpu": expected,
            "podUids": uids}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("workspace-log", "peer-log", "workspace-pod", "peer-pod", "node", "preflight"):
        parser.add_argument(f"--{argument}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--compiler-wheel", type=Path, required=True)
    parser.add_argument("--configmaps", type=Path, help="Root before/after snapshots of all referenced quota ConfigMaps")
    args = parser.parse_args()
    result = evaluate(json_events(args.workspace_log), json_events(args.peer_log),
        json.loads(args.workspace_pod.read_text()), json.loads(args.peer_pod.read_text()),
        json.loads(args.node.read_text()), json.loads(args.preflight.read_text()),
        configmaps=json.loads(args.configmaps.read_text()) if args.configmaps else None,
        fixture=json.loads(args.fixture.read_text()), compiler_wheel=args.compiler_wheel)
    with args.output.open("x") as destination:
        json.dump(result, destination, indent=2)
        destination.write("\n")
    print(json.dumps(result))
    raise SystemExit(0 if result["status"] == "bounded-standard-cases-passed" else 1)

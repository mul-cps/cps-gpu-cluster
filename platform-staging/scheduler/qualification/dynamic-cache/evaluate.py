#!/usr/bin/env python3
"""Offline evidence evaluation; no synthetic report can activate production."""
import argparse
import json
from pathlib import Path

from probe import CACHE_PATH, ROUNDS, concurrent_verdict, normalized_uuid, ordinary_verdict
from render import HAMI_PATH, HAMI_REVISION, IMAGE, NODE


def valid_hami(value, preflight):
    return (value["referenceSourceRevision"] == HAMI_REVISION and value["sourceRevisionVerified"] is False
            and value["libraryPath"] == HAMI_PATH
            and value["sha256"] == preflight["hami"]["sha256"]
            and value["loaded"] is True and value["preloadVerified"] is True
            and value["effectiveLimitBytes"] == 5120 * 1024**2)


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


def evaluate(workspace_events, peer_events, workspace_pod, peer_pod, node, preflight):
    reasons = []
    reports = [e for e in workspace_events if e.get("event") == "workspace-result"]
    if len(reports) != 1:
        return {"status": "inconclusive", "reasons": ["Exactly one workspace report required"],
                "productionQualified": False, "hostileIsolationQualified": False}
    report = reports[0]
    expected = normalized_uuid(preflight["targetGpuUuid"])
    if node["metadata"].get("name") != NODE or node["metadata"].get("uid") != preflight["node"]["uid"]:
        reasons.append("Target node UID changed or does not match")
    uids = []
    run_ids = []
    for pod in (workspace_pod, peer_pod):
        metadata, spec = pod["metadata"], pod["spec"]
        uids.append(metadata["uid"])
        if metadata.get("namespace") != "cps-gpu-qualification" or spec.get("nodeName") != NODE:
            reasons.append("Fixture Pod is not in the reviewed namespace/node")
        main = [c for c in spec["containers"] if c["name"] == "main"]
        if len(main) != 1 or main[0]["image"] != IMAGE:
            reasons.append("Fixture image mismatch")
        env = {e["name"]: e.get("value") for e in main[0].get("env", [])}
        run_ids.append(env.get("FIXTURE_RUN_ID"))
        if env.get("FIXTURE_RUN_ID") != metadata.get("annotations", {}).get("compute.cps.unileoben.ac.at/fixture-run-id"):
            reasons.append("Fixture run ID does not match the rendered annotation")
        if env.get("CUDA_DEVICE_MEMORY_SHARED_CACHE") != CACHE_PATH:
            reasons.append("Fixture cache configuration mismatch")
        if (env.get("CUDA_DEVICE_MEMORY_LIMIT") != "5120m" or
                env.get("EXPECTED_HAMI_SHA256") != preflight["hami"]["sha256"] or
                env.get("EXPECTED_HAMI_REVISION") != HAMI_REVISION):
            reasons.append("Fixture quota/HAMi provenance configuration mismatch")
        mount = [m for m in main[0].get("volumeMounts", []) if m["mountPath"] == CACHE_PATH]
        if len(mount) != 1 or mount[0].get("subPath") != "usage.cache":
            reasons.append("Fixed cache file mount absent")
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
        if report["nominalMiB"] != 5120:
            reasons.append("Workspace nominal quota changed")
        cache = report["cache"]
        if not valid_hami(report["hami"], preflight):
            reasons.append("Workspace preloaded HAMi binary or effective quota is unproven")
        if not cache["noTmpFallback"] or not cache["mappingVerified"]:
            reasons.append("Workspace cache inode mapping was not proven")
        child_values = [e["value"] for e in workspace_events if e.get("event") == "child-evidence"]
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
    return {"status": "bounded-standard-cases-passed" if not reasons else "failed-or-inconclusive",
            "reasons": reasons, "productionQualified": False, "hostileIsolationQualified": False,
            "tamper": {"status": "not-run", "existingFailureRemains": True},
            "node": NODE, "nodeUid": preflight["node"]["uid"], "gpu": expected,
            "podUids": uids}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("workspace-log", "peer-log", "workspace-pod", "peer-pod", "node", "preflight"):
        parser.add_argument(f"--{argument}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(json_events(args.workspace_log), json_events(args.peer_log),
        json.loads(args.workspace_pod.read_text()), json.loads(args.peer_pod.read_text()),
        json.loads(args.node.read_text()), json.loads(args.preflight.read_text()))
    with args.output.open("x") as destination:
        json.dump(result, destination, indent=2)
        destination.write("\n")
    print(json.dumps(result))
    raise SystemExit(0 if result["status"] == "bounded-standard-cases-passed" else 1)

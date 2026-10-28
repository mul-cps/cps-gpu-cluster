#!/usr/bin/env python3
"""Offline verifier for an MPS aggregate-cap hold within one Pod cgroup.

This binds a host MPS capture to separately reviewed Pod/container and
workload receipts. It is intentionally not a production qualification tool.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _parse_utc(value: object, label: str) -> dt.datetime:
    _require(isinstance(value, str) and bool(value), f"{label} timestamp is missing")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} timestamp is malformed") from exc
    _require(parsed.tzinfo is not None, f"{label} timestamp must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def verify(capture: dict, pod: dict, workload: dict, *, expected_cap_bytes: int) -> dict:
    """Check attribution and workload assertions; never returns qualified=True."""
    _require(expected_cap_bytes > 0, "expected memory cap must be positive")
    _require(capture.get("schema") == "native-shared-mps-host-attribution/v1",
             "unsupported host capture schema")
    run_id = capture.get("runId")
    _require(isinstance(run_id, str) and run_id == pod.get("runId") == workload.get("runId"),
             "run ID does not match across evidence")
    _require(isinstance(pod.get("podUid"), str) and pod["podUid"], "Pod UID receipt is missing")
    _require(isinstance(pod.get("containerId"), str) and pod["containerId"],
             "container ID receipt is missing")
    _require(isinstance(pod.get("cgroup"), str) and pod["cgroup"],
             "reviewed container cgroup is missing")
    normalized_uid = pod["podUid"].replace("-", "_")
    _require(pod["podUid"] in pod["cgroup"] or normalized_uid in pod["cgroup"],
             "Pod UID in reviewed receipt does not match the container cgroup")
    container_token = pod["containerId"].split("://")[-1]
    _require(container_token in pod["cgroup"],
             "container ID in reviewed receipt does not match the container cgroup")
    _require(pod.get("gpuMemoryCapBytes") == expected_cap_bytes and
             isinstance(pod.get("gpuMemoryCapEvidence"), str) and
             bool(pod["gpuMemoryCapEvidence"].strip()),
             "reviewed GPU memory cap and its readback evidence must match the expected cap")
    _require(workload.get("podUid") == pod["podUid"],
             "workload receipt Pod UID does not match the reviewed Pod")
    _require(workload.get("probeSucceeded") is True,
             "two-client CUDA workload did not report successful completion")
    _require(workload.get("capBytes") == expected_cap_bytes,
             "workload receipt cap does not match the reviewed cgroup memory cap")
    hold_start = _parse_utc(workload.get("holdStartedAt"), "workload hold start")
    hold_finish = _parse_utc(workload.get("holdFinishedAt"), "workload hold finish")
    capture_start = _parse_utc(capture.get("observedAtStart"), "host capture start")
    capture_finish = _parse_utc(capture.get("observedAtFinish"), "host capture finish")
    _require(hold_finish >= hold_start, "workload hold timestamps are reversed")
    _require(capture_finish >= capture_start, "host capture timestamps are reversed")
    _require(capture_start <= hold_finish and capture_finish >= hold_start,
             "host process capture did not overlap the two-client hold")

    servers = capture.get("servers")
    _require(isinstance(servers, list) and len(servers) == 1,
             "capture must contain exactly one MPS server")
    clients = servers[0].get("clients")
    _require(isinstance(clients, list) and len(clients) == 2 and len(set(clients)) == 2,
             "MPS server must report exactly two distinct clients")

    process_rows = capture.get("processes")
    _require(isinstance(process_rows, list), "host process records are missing")
    by_pid = {row.get("pid"): row for row in process_rows if isinstance(row, dict)}
    _require(len(by_pid) == len(process_rows), "host process records contain duplicate or invalid PIDs")
    _require(servers[0].get("pid") in by_pid, "MPS server process record is missing")
    _require(all(pid in by_pid for pid in clients), "an MPS client process record is missing")

    client_rows = [by_pid[pid] for pid in clients]
    _require(all(row.get("cgroup") == pod["cgroup"] for row in client_rows),
             "both MPS clients must be in the reviewed same container cgroup")
    _require(pod.get("gpuUuid") in by_pid[servers[0]["pid"]].get("gpuUuids", []),
             "MPS server GPU UUID does not match the reviewed Pod GPU")

    def map_namespace_pid(namespace_pid: object) -> int:
        matches = [row["pid"] for row in client_rows
                   if isinstance(namespace_pid, int) and row.get("namespacePids")
                   and row["namespacePids"][-1] == namespace_pid]
        _require(len(matches) == 1, "workload namespace PID does not uniquely map to a captured MPS client")
        return matches[0]

    survivor = workload.get("survivor", {})
    challenger = workload.get("challenger", {})
    survivor_pid = map_namespace_pid(survivor.get("namespacePid"))
    challenger_pid = map_namespace_pid(challenger.get("namespacePid"))
    _require(survivor_pid != challenger_pid, "survivor and challenger must be distinct MPS clients")
    _require(isinstance(survivor.get("heldBytes"), int) and
             0 < survivor["heldBytes"] < expected_cap_bytes,
             "survivor must hold a positive allocation below the aggregate cap")
    _require(isinstance(challenger.get("overCapRequestedBytes"), int) and
             0 < challenger["overCapRequestedBytes"] < expected_cap_bytes and
             survivor["heldBytes"] + challenger["overCapRequestedBytes"] > expected_cap_bytes,
             "survivor plus challenger must exceed the aggregate cap while each allocation fits alone")
    _require(isinstance(challenger.get("recoveryBytes"), int) and
             challenger["recoveryBytes"] > 0 and
             survivor["heldBytes"] + challenger["recoveryBytes"] < expected_cap_bytes,
             "challenger recovery allocation must fit alongside the surviving allocation")
    _require(challenger.get("overCapRejected") is True,
             "challenger over-cap rejection was not observed")
    _require(challenger.get("recoverySucceeded") is True,
             "challenger recovery after rejection was not observed")
    _require(isinstance(survivor.get("progressBefore"), int) and
             isinstance(survivor.get("progressAfter"), int) and
             survivor["progressAfter"] > survivor["progressBefore"],
             "survivor progress did not advance across the challenger test")

    return {
        "schema": "native-shared-mps-same-pod-verification/v1",
        "runId": run_id,
        "podUid": pod["podUid"],
        "containerId": pod["containerId"],
        "gpuUuid": pod["gpuUuid"],
        "gpuMemoryCapBytes": expected_cap_bytes,
        "captureOverlappedHold": True,
        "mpsClientPids": sorted(clients),
        "samePodCgroup": True,
        "overCapRejected": True,
        "challengerRecovered": True,
        "survivorProgressed": True,
        "productionQualified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--pod-receipt", required=True, type=Path)
    parser.add_argument("--workload-receipt", required=True, type=Path)
    parser.add_argument("--expected-cap-bytes", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        result = verify(*(json.loads(path.read_text()) for path in
                          (args.capture, args.pod_receipt, args.workload_receipt)),
                        expected_cap_bytes=args.expected_cap_bytes)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"same-Pod MPS verification failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

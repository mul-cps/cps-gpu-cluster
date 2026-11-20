#!/usr/bin/env python3
"""Read-only, sanitized collector for the bounded 2026-10-09 no-MIG pilot.

This validates supplied raw measurements, not their authenticity or production
qualification. It never runs probes, imports executed probe source, or calls a
cluster/GPU API. A valid partial capture exits zero; absent/invalid critical
evidence exits one. Private Pod objects are inputs only, never output objects.
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import stat
import sys
import uuid
from pathlib import Path
from typing import Any

CAP_BYTES = 5120 * 1048576
MPS_HELD_SOURCE_SHA256 = "80d43e3f9950f39a7b88f4b69505af118ff7d3ca40b71cbeb871d07d596c3b1b"
MAX_INPUT_BYTES = 8 * 1024 * 1024


class EvidenceError(Exception):
    """Only a fixed, sanitized diagnostic code is returned to the caller."""


def need(condition: bool, code: str) -> None:
    if not condition:
        raise EvidenceError(code)


def integer(value: Any, code: str, minimum: int = 0) -> int:
    need(type(value) is int and value >= minimum, code)
    return value


def canonical_uuid(value: Any) -> str:
    need(isinstance(value, str), "invalid-uuid")
    try:
        need(str(uuid.UUID(value)) == value, "invalid-uuid")
    except ValueError:
        raise EvidenceError("invalid-uuid") from None
    return value


def exact_result(value: Any, expected: int) -> None:
    need(type(value) is int and value == expected, "unexpected-cuda-result")


def memory(value: Any) -> None:
    need(isinstance(value, dict), "missing-cap-memory")
    exact_result(value.get("cuda_result"), 0)
    need(integer(value.get("total_bytes"), "invalid-cap") == CAP_BYTES, "cap-mismatch")
    need(integer(value.get("free_bytes"), "invalid-free-memory") <= CAP_BYTES, "invalid-free-memory")


def unique(rows: list[dict], key: str, value: Any) -> dict:
    hits = [r for r in rows if r.get(key) == value]
    need(len(hits) == 1, "missing-or-duplicate-phase")
    return hits[0]


def timestamps(rows: list[dict], key: str = "observed_ns") -> list[int]:
    values = [integer(r.get(key), "invalid-timestamp", 1) for r in rows]
    need(all(b > a for a, b in zip(values, values[1:])), "nonmonotonic-timestamps")
    return values


def no_error_rows(rows: list[dict]) -> None:
    need(not any(r.get("state") in {"error", "blocked", "failed"}
                 or r.get("kind") == "error" or r.get("error") for r in rows), "probe-error")


def _object(pairs: list[tuple[str, Any]]) -> dict:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        need(key not in obj, "duplicate-json-key")
        obj[key] = value
    return obj


class Inputs:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.provenance: dict[str, dict] = {}

    def raw(self, name: str) -> bytes:
        # All names are fixed in this module; refuse symlinks and special files.
        path = self.root / name
        fd = None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            info = os.fstat(fd)
            need(stat.S_ISREG(info.st_mode), "unsafe-input-file")
            need(info.st_size <= MAX_INPUT_BYTES, "input-too-large")
            data = bytearray()
            while True:
                chunk = os.read(fd, min(65536, MAX_INPUT_BYTES + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                need(len(data) <= MAX_INPUT_BYTES, "input-too-large")
            after = os.fstat(fd)
            need((info.st_size, info.st_mtime_ns, info.st_ctime_ns) ==
                 (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "input-changed-during-read")
        except OSError as exc:
            raise EvidenceError("unsafe-input-file" if exc.errno == errno.ELOOP else
                                "missing-or-unreadable-input") from None
        finally:
            if fd is not None:
                os.close(fd)
        data = bytes(data)
        self.provenance[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        return data

    def text(self, name: str) -> str:
        try:
            return self.raw(name).decode("utf-8")
        except UnicodeError:
            raise EvidenceError("invalid-utf8") from None

    def json(self, name: str) -> dict:
        try:
            result = json.loads(self.text(name), object_pairs_hook=_object)
        except (ValueError, TypeError):
            raise EvidenceError("invalid-json") from None
        need(isinstance(result, dict), "expected-json-object")
        return result

    def rows(self, name: str) -> list[dict]:
        lines = self.text(name).splitlines()
        need(bool(lines) and all(line.strip() for line in lines), "empty-jsonl-record")
        try:
            rows = [json.loads(line, object_pairs_hook=_object) for line in lines]
        except (ValueError, TypeError):
            raise EvidenceError("invalid-jsonl") from None
        need(all(isinstance(row, dict) for row in rows), "expected-jsonl-object")
        no_error_rows(rows)
        return rows


def identities(src: Inputs) -> dict:
    intents = []
    for role in ("main", "peer"):
        intent = src.json(f"native-cap-{role}-intent.json")
        pod = src.json(f"native-cap-{role}-actual.json")
        uid = canonical_uuid(intent.get("pod_uid"))
        canonical_uuid(intent.get("node_uid"))
        gpu = intent.get("gpu_uuid")
        need(isinstance(gpu, str) and gpu.startswith("GPU-"), "invalid-gpu-uuid")
        canonical_uuid(gpu[4:])
        need(type(intent.get("cap_mib")) is int and intent["cap_mib"] == 5120, "intent-cap-mismatch")
        need(isinstance(intent.get("policy_hash"), str)
             and re.fullmatch(r"sha256:[0-9a-f]{64}", intent["policy_hash"]) is not None,
             "invalid-policy-hash")
        need(isinstance(intent.get("spec_sha256"), str)
             and re.fullmatch(r"[0-9a-f]{64}", intent["spec_sha256"]) is not None,
             "invalid-spec-hash")
        need(pod.get("kind") == "Pod" and isinstance(pod.get("metadata"), dict)
             and isinstance(pod.get("spec"), dict), "invalid-actual-pod")
        meta = pod["metadata"]
        need(meta.get("uid") == uid and meta.get("name") == intent.get("name")
             and meta.get("namespace") == intent.get("namespace")
             and pod["spec"].get("nodeName") == intent.get("node"), "actual-pod-binding-mismatch")
        digest = hashlib.sha256(json.dumps(pod["spec"], sort_keys=True, separators=(",", ":"),
                                          ensure_ascii=False).encode()).hexdigest()
        need(digest == intent["spec_sha256"], "actual-spec-hash-mismatch")
        intents.append({"role": role, "pod_uid": uid, "gpu_uuid": gpu, "cap_bytes": CAP_BYTES,
                        "policy_hash": intent["policy_hash"], "spec_sha256": digest})
    need(intents[0]["pod_uid"] != intents[1]["pod_uid"], "duplicate-pod-uid")
    need(intents[0]["gpu_uuid"] == intents[1]["gpu_uuid"]
         and intents[0]["policy_hash"] == intents[1]["policy_hash"], "inconsistent-pair-authority")
    rows = src.rows("controller-restarted.jsonl")
    for intent in intents:
        hits = [r for r in rows if r.get("pod_uid") == intent["pod_uid"]]
        need(len(hits) >= 2 and all(r.get("state") == "sealed"
             and r.get("production_qualified") is False for r in hits), "restart-not-repeatedly-sealed")
        iterations = [integer(r.get("iteration"), "invalid-controller-iteration") for r in hits]
        need(len(set(iterations)) >= 2, "restart-not-repeatedly-sealed")
    need(all(r.get("pod_uid") in {i["pod_uid"] for i in intents}
             and r.get("state") == "sealed" for r in rows), "unexpected-controller-result")
    guard = src.json("guard-load-receipt.json")
    need(guard.get("state") == "guard-loaded-trusted-epoch-issued", "guard-not-loaded")
    generation = canonical_uuid(guard.get("driver_generation"))
    params = guard.get("params", {})
    need(isinstance(params, dict) and all(params.get(k) == v for k, v in {
        "uvm_deny_managed_mmap": "Y", "uvm_disable_hmm": "Y", "uvm_ats_mode": "0",
        "uvm_enable_builtin_tests": "0", "uvm_disable_sam_migration": "Y"}.items()), "guard-health-mismatch")
    return {"status": "passed", "pods": intents, "controller_reconcile_rows": len(rows),
            "driver_generation": generation,
            "scope": "raw sealed restart observations; complete private journal identity not re-derived"}


def session_case(src: Inputs, name: str, mode: str, managed: bool = False) -> dict:
    rows = src.rows(name)
    timestamps(rows)
    need([r.get("state") for r in rows] == ["context-ready", "managed-attempt" if managed else
         "over-cap-attempt", "measurement-passed"], "invalid-session-phase-order")
    context = unique(rows, "state", "context-ready")
    need(context.get("mode") == mode and context.get("attributes") == {"88": 0, "100": 0},
         "unexpected-context")
    memory(context.get("memory"))
    end = unique(rows, "state", "measurement-passed")
    need(end.get("mode") == mode and end.get("production_qualified") is False,
         "missing-bounded-completion")
    if managed:
        attempt = unique(rows, "state", "managed-attempt")["result"]
        need(isinstance(attempt, dict), "invalid-managed-attempt")
        exact_result(attempt.get("cuda_result"), 801)
        memory(attempt.get("memory"))
        need(attempt.get("touch_result") is None and attempt.get("prefetch_result") is None,
             "managed-attempt-touched")
    else:
        exact_result(unique(rows, "state", "over-cap-attempt").get("cuda_result"), 2)
    need(rows.index(context) < rows.index(end), "invalid-phase-order")
    return {"status": "passed", "cuda_result": 801 if managed else 2,
            "cap_bytes": CAP_BYTES,
            "recovery": "completion recorded; no separate raw recovery result" if not managed else None}


def native_rows(src: Inputs, name: str, gpu: str, oom_phase: str | None = None,
                final_status: str = "bounded-measurement-completed") -> list[dict]:
    rows = src.rows(name)
    identity = unique(rows, "kind", "identity")
    need(identity.get("gpu_uuid") == gpu and type(identity.get("uid")) is int
         and identity["uid"] == 1000 and type(identity.get("gid")) is int
         and identity["gid"] == 100 and identity.get("driver_api_version") == 13040,
         "native-probe-identity-mismatch")
    cap = unique(rows, "kind", "initial-cap-info")
    need(cap.get("total_bytes") == CAP_BYTES, "native-cap-mismatch")
    final = unique(rows, "kind", "final")
    need(final.get("status") == final_status and final.get("production_qualified") is False,
         "native-probe-not-completed")
    cuda = [r for r in rows if r.get("kind") == "cuda"]
    need(bool(cuda), "missing-cuda-records")
    timestamps(cuda, "time_ns")
    for row in cuda:
        exact_result(row.get("result"), 2 if row.get("phase") == oom_phase else 0)
        need(row.get("production_qualified") is False, "unexpected-production-claim")
    return rows


def phase(rows: list[dict], name: str) -> dict:
    return unique([r for r in rows if r.get("kind") == "cuda"], "phase", name)


def vmm_direct(src: Inputs, gpu: str) -> dict:
    rows = native_rows(src, "vmm-direct.jsonl", gpu, "vmm-over-cap-never-touch")
    oom = phase(rows, "vmm-over-cap-never-touch")
    for name in ("vmm-create-64", "fill-64", "readback"):
        hits = [r for r in rows if r.get("kind") == "cuda" and r.get("phase") == name]
        need(len(hits) >= 2 and any(r["time_ns"] > oom["time_ns"] for r in hits),
             "missing-vmm-recovery")
    return {"status": "passed", "over_cap_cuda_result": 2, "recovery": "raw CUDA allocation/touch/readback after OOM"}


def workaround(src: Inputs) -> dict:
    record = src.json("manual-socket-mode-workaround.json")
    need(record.get("state") == "operator-workaround-applied" and record.get("mode") == "0600"
         and record.get("production_workaround") is False
         and isinstance(record.get("scopes"), list)
         and set(record["scopes"]) == {"same-ipc", "cross-vmm"}, "missing-explicit-socket-workaround")
    return {"applied": True, "mode": "0600", "production_workaround": False,
            "scope": ["same-ipc", "cross-vmm"]}


def same_ipc(src: Inputs, gpu: str) -> dict:
    applied = workaround(src)
    exporter = native_rows(src, "same-ipc-export.jsonl", gpu)
    initial = native_rows(src, "same-ipc-import.jsonl", gpu, final_status="inconclusive")
    importer = native_rows(src, "same-ipc-import-corrected.jsonl", gpu)
    phase(exporter, "ipc-export")
    for name in ("ipc-import", "import-readback", "ipc-close"):
        phase(importer, name)
    need(not any(r.get("phase") == "ipc-import" for r in initial), "unexpected-initial-ipc-result")
    return {"status": "passed-with-operator-workaround", "cuda_import_result": 0,
            "initial_attempt": "inconclusive", "manual_socket_mode_workaround": applied,
            "source_socket_fix_live_qualified": False}


def cross_vmm(src: Inputs, gpu: str, uids: set[str]) -> dict:
    applied = workaround(src)
    exporter = native_rows(src, "cross-vmm-export.jsonl", gpu)
    importer = native_rows(src, "cross-vmm-import.jsonl", gpu)
    phase(exporter, "vmm-export")
    released = phase(exporter, "exporter-references-released-importer-retains")["time_ns"]
    phase(importer, "vmm-import")
    start = phase(importer, "importer-retained-backing-start")["time_ns"]
    end = phase(importer, "importer-retained-backing-end")["time_ns"]
    need(abs(released - start) <= 1000000000 and end - start >= 9000000000,
         "missing-retained-backing-window")
    samples = src.rows("cross-vmm-accounting.jsonl")
    sample_times = timestamps(samples)
    for row in samples:
        parents = row.get("parents")
        need(isinstance(parents, list) and {p.get("pod_uid") for p in parents} == uids,
             "accounting-parent-mismatch")
        for parent in parents:
            limits = parent.get("limits", {})
            need(parent.get("gpu_uuid") == gpu and limits.get("soft") == CAP_BYTES
                 and limits.get("hard") == CAP_BYTES, "accounting-cap-mismatch")
            integer(limits.get("used"), "invalid-accounting-used")
    in_window = sum(start <= t <= end for t in sample_times)
    return {"status": "partial", "functional_import_cuda_result": 0,
            "exporter_references_released": True, "retained_seconds": (end - start) / 1e9,
            "retention_accounting": {"status": "unmeasured" if not in_window else "observed-not-qualified",
                                     "samples_in_window": in_window, "samples_total": len(samples),
                                     "observer_ended_before_retention": sample_times[-1] < start},
            "manual_socket_mode_workaround": applied,
            "cross_import_ownership_qualified": False}


def peer_brackets(src: Inputs, phases: list[dict]) -> dict:
    rows = src.rows("mps-peer-120.jsonl")
    times = timestamps(rows)
    context = unique(rows, "state", "context-ready")
    memory(context.get("memory"))
    need(context.get("mode") == "heartbeat" and context.get("attributes") == {"88": 0, "100": 0},
         "peer-context-mismatch")
    final = unique(rows, "state", "measurement-passed")
    need(final.get("mode") == "heartbeat" and final.get("production_qualified") is False,
         "peer-did-not-complete")
    need(final["observed_ns"] - context["observed_ns"] >= 120000000000, "peer-duration-too-short")
    ticks = [r for r in rows if r.get("state") == "peer-tick"]
    need(len(ticks) >= 100, "insufficient-peer-ticks")
    monotonic = []
    tick_times = []
    for row in ticks:
        tick = row.get("tick", {})
        exact_result(tick.get("cuda_result"), 0)
        memory(tick.get("memory"))
        monotonic.append(integer(tick.get("monotonic_ns"), "invalid-monotonic-clock", 1))
        tick_times.append(row["observed_ns"])
    need(all(b > a for a, b in zip(monotonic, monotonic[1:])), "nonmonotonic-peer-clock")
    need(max(b - a for a, b in zip(monotonic, monotonic[1:])) <= 1000000000, "peer-tick-gap")
    brackets = []
    for row in phases:
        t = row["observed_ns"]
        before = [v for v in tick_times if v < t]
        after = [v for v in tick_times if v > t]
        need(bool(before) and bool(after) and t - before[-1] <= 1000000000
             and after[0] - t <= 1000000000, "phase-not-bracketed-by-healthy-peer")
        brackets.append({"phase": row["phase"], "tick_before_ns": before[-1], "tick_after_ns": after[0]})
    return {"status": "passed", "duration_seconds": (times[-1] - times[0]) / 1e9,
            "successful_ticks": len(ticks), "phase_brackets": brackets}


def mps(src: Inputs, uids: set[str]) -> dict:
    registration = src.json("mps-two-client-charge.json")
    lines = src.text("mps-two-clients.txt").splitlines()
    need(len(lines) == 2 and all(re.fullmatch(r"[1-9][0-9]*", line) for line in lines),
         "invalid-mps-client-list")
    clients = {int(line) for line in lines}
    registered = registration.get("registered_clients")
    need(isinstance(registered, list) and len(registered) == 2
         and all(type(pid) is int and pid > 0 for pid in registered)
         and set(registered) == clients and len(clients) == 2, "mps-registration-mismatch")
    server = integer(registration.get("registered_server"), "invalid-mps-server", 1)
    need(server not in clients, "mps-server-is-client")
    processes = registration.get("processes")
    need(isinstance(processes, list), "missing-mps-process-bindings")
    server_process = unique(processes, "pid", server)
    need(str(server_process.get("cmd", "")).startswith("nvidia-cuda-mps-server"), "missing-mps-server-binding")
    bindings = {}
    for pid in sorted(clients):
        proc = unique(processes, "pid", pid)
        integer(proc.get("start"), "invalid-process-start", 1)
        path = proc.get("cgroup", "")
        need(isinstance(path, str), "invalid-client-cgroup")
        matches = [uid for uid in uids if "pod" + uid.replace("-", "_") + ".slice/" in path]
        need(len(matches) == 1 and matches[0] not in bindings.values(), "mps-client-parent-mismatch")
        bindings[pid] = matches[0]
    parents = registration.get("parents")
    need(isinstance(parents, list) and len(parents) == 2 and {p.get("uid") for p in parents} == uids,
         "mps-native-parent-mismatch")
    charges = {}
    for parent in parents:
        cap = parent.get("cap", {})
        need(cap.get("soft") == CAP_BYTES and cap.get("hard") == CAP_BYTES, "mps-native-cap-mismatch")
        used = integer(cap.get("used"), "invalid-mps-charge", 1)
        need(used < CAP_BYTES and used == 434192064, "unexpected-mps-pilot-charge")
        charges[parent["uid"]] = used
    rows = src.rows("mps-main-held.jsonl")
    timestamps(rows)
    names = ["context-held-before-alloc", "ordinary64-held", "overcap", "managed-denial", "bounded-sequence-passed"]
    need([r.get("phase") for r in rows] == names, "mps-phase-order-mismatch")
    memory(rows[0].get("memory"))
    ordinary = rows[1].get("result", {})
    exact_result(ordinary.get("cuda_result"), 0)
    exact_result(ordinary.get("touch_result"), 0)
    memory(ordinary.get("memory"))
    exact_result(rows[2].get("result"), 2)
    managed = rows[3].get("result", {})
    exact_result(managed.get("cuda_result"), 801)
    memory(managed.get("memory"))
    need(managed.get("touch_result") is None and managed.get("prefetch_result") is None,
         "mps-managed-attempt-touched")
    need(rows[-1].get("production_qualified") is False, "unexpected-production-claim")
    # This executed source is evidence, never imported/executed. The exact reviewed
    # script asserts successful recovery before its later completion marker, but
    # omitted a separate recovery record. Keep that distinction in the output.
    source = src.raw("mps-main-held.py")
    need(hashlib.sha256(source).hexdigest() == MPS_HELD_SOURCE_SHA256, "mps-executed-source-mismatch")
    peer = peer_brackets(src, rows)
    integer(registration.get("observed_ns"), "invalid-registration-timestamp", 1)
    need(rows[0]["observed_ns"] <= registration["observed_ns"] <= rows[-1]["observed_ns"],
         "mps-registration-outside-held-window")
    return {"status": "passed-bounded-pilot", "server_host_pid": server,
            "clients": [{"host_pid": pid, "pod_uid": uid, "native_used_bytes": charges[uid],
                         "cap_bytes": CAP_BYTES} for pid, uid in sorted(bindings.items())],
            "ordinary_cuda_result": 0, "over_cap_cuda_result": 2, "managed_cuda_result": 801,
            "recovery": {"status": "source-asserted-before-completion", "raw_phase_recorded": False,
                         "executed_source_sha256": MPS_HELD_SOURCE_SHA256}, "independent_peer": peer}


def collect(rootdir: str | Path) -> dict:
    """Return whitelisted evidence; missing/invalid critical raw input is an error."""
    src = Inputs(Path(rootdir))
    report: dict[str, Any] = {"schema": "cps-native-live-evidence/v1", "status": "partial-live-evidence",
                             "production_qualified": False, "group_sharing_enabled": False,
                             "source_import_guard_qualified": False, "cases": {}, "errors": [],
                             "limitations": ["Cross-import retention accounting is not qualified.",
                                             "IPC functional runs required an explicit operator socket-mode workaround.",
                                             "MPS recovery is asserted by pinned executed source, not a separate raw phase.",
                                             "CPU collector tests do not establish GPU isolation.",
                                             "Input authenticity, complete journal binding and source guard remain separate gates."]}
    def case(name: str, action) -> Any:
        try:
            result = action()
            report["cases"][name] = result
            return result
        except EvidenceError as exc:
            report["cases"][name] = {"status": "invalid-or-missing-evidence"}
            report["errors"].append({"case": name, "code": str(exc)})
        except (KeyError, TypeError, AttributeError, ValueError, IndexError):
            report["cases"][name] = {"status": "invalid-or-missing-evidence"}
            report["errors"].append({"case": name, "code": "malformed-evidence-structure"})
        return None
    pair = case("automatic_caps_and_controller_restart", lambda: identities(src))
    case("ordinary_oom", lambda: session_case(src, "ordinary-oom.jsonl", "oom"))
    case("ordinary_oom_concurrent", lambda: session_case(src, "ordinary-oom-concurrent.jsonl", "oom"))
    case("fresh_managed_denial", lambda: session_case(src, "managed-denial.jsonl", "managed", True))
    if pair:
        gpu = pair["pods"][0]["gpu_uuid"]
        uids = {p["pod_uid"] for p in pair["pods"]}
        case("vmm_direct", lambda: vmm_direct(src, gpu))
        case("same_ipc", lambda: same_ipc(src, gpu))
        case("cross_vmm", lambda: cross_vmm(src, gpu, uids))
        case("mps", lambda: mps(src, uids))
    else:
        for name in ("vmm_direct", "same_ipc", "cross_vmm", "mps"):
            report["cases"][name] = {"status": "blocked-by-invalid-authority-evidence"}
    report["provenance"] = [{"file": name, **value} for name, value in sorted(src.provenance.items())]
    if report["errors"]:
        report["status"] = "incomplete-or-invalid-live-evidence"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rootdir", type=Path)
    parser.add_argument("--output", type=Path, help="Write sanitized JSON here instead of stdout")
    args = parser.parse_args()
    report = collect(args.rootdir)
    encoded = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        # A new inode prevents hardlinks, aliases and races from truncating raw
        # evidence. Preserve every existing destination, even an earlier report.
        try:
            fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(encoded)
        except OSError as exc:
            print("output-already-exists" if exc.errno == errno.EEXIST else
                  "output-unwritable", file=sys.stderr)
            return 1
    else:
        print(encoded, end="")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Offline, fail-closed review of the recovered GPU2 5/10 GiB evidence.

This tool reads saved evidence only. It never contacts Kubernetes, the node,
the driver, or a GPU, and it never changes qualification labels or receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

GPU = "GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6"
BOOT = "a464df41-e391-4443-b8e8-ad7ecd052318"
GENERATION = "4ebffc96-e25e-4583-a3b8-0d853fd90efd"
NODE_UID = "3336cdd5-d245-436e-b57c-2f66c6dcaa41"
NODE = "k3s-wk-gpu2"
COHORTS = {
    "pressure": {"uid": "a565adb6-6dcc-4699-8064-89227400ad79", "a": ("native-second-card-a-a565adb6", "b348c96e-0b4f-4e12-a79c-91980e921036", 5120, 1260272), "b": ("native-second-card-b-a565adb6", "6bdeaa43-f5f6-4b44-a14e-bf3e7ab750f1", 10240, 1260430)},
    "remaining": {"uid": "9442c844-5ca2-477f-956c-e3e752a09393", "a": ("native-second-card-a-9442c844", "21a75417-3a19-414e-8c06-92909da6a2fe", 5120, 1262901), "b": ("native-second-card-b-9442c844", "fac42cb0-e624-430f-8e8b-c1594e7968bf", 10240, 1263059)},
    "restart": {"uid": "81b2a90a-7a09-49a1-8d05-c067bdb8095e", "a": ("native-second-card-a-81b2a90a", "03a7de35-ea10-485d-995d-2e921c64e25c", 5120, 1264819), "b": ("native-second-card-b-81b2a90a", "2f924a59-3724-4f44-bec8-da33759e1f84", 10240, 1264977)},
}
MAX_FILE = 16 * 1024 * 1024


class EvidenceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def read_json(path: Path):
    raw = path.read_bytes()
    require(0 < len(raw) <= MAX_FILE, f"missing, empty, or oversized evidence: {path}")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_pairs,
                           parse_constant=lambda _v: (_ for _ in ()).throw(EvidenceError("non-finite JSON number")))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EvidenceError(f"invalid JSON: {path}") from exc
    require(type(value) in (dict, list), f"expected JSON object/list: {path}")
    return value


def read_jsonl(path: Path):
    raw = path.read_bytes()
    require(0 < len(raw) <= MAX_FILE, f"missing, empty, or oversized JSONL evidence: {path}")
    rows = []
    for line in raw.splitlines():
        require(line, f"blank JSONL row: {path}")
        rows.append(json.loads(line, object_pairs_hook=_unique_pairs))
    require(rows and all(type(row) is dict for row in rows), f"invalid JSONL rows: {path}")
    return rows


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(manifest, family: str):
    expected = COHORTS[family]
    require(manifest.get("cohort_uid") == expected["uid"], f"wrong {family} cohort UID")
    require(type(manifest.get("pods")) is dict, f"missing {family} manifest pods")
    for side in ("a", "b"):
        name, uid, cap, _inode = expected[side]
        row = manifest["pods"].get(side)
        require(type(row) is dict and row.get("name") == name and row.get("uid") == uid
                and row.get("cap_mib") == cap, f"wrong {family} {side} manifest identity/cap")
    return expected


def validate_host_pair(snapshot, family: str):
    expected = COHORTS[family]
    host = snapshot.get("host") if type(snapshot) is dict else None
    require(type(host) is dict and host.get("hardware_qualified") is False
            and host.get("production_qualified") is False, f"{family} host evidence must remain nonqualified")
    targets = host.get("targets")
    require(type(targets) is list and len(targets) == 2, f"{family} requires two native target proofs")
    by_uid = {row.get("pod_uid"): row for row in targets if type(row) is dict}
    require(len(by_uid) == 2, f"{family} target UIDs are ambiguous")
    for side in ("a", "b"):
        name, uid, cap, inode = expected[side]
        target = by_uid.get(uid)
        require(type(target) is dict, f"{family} missing {side} target")
        ident, intent, limit = target.get("identity"), target.get("intent"), target.get("limit")
        require(type(ident) is dict and type(intent) is dict and type(limit) is dict,
                f"{family} missing {side} identity/intent/limit")
        require(ident.get("pod_uid") == uid and ident.get("node_uid") == NODE_UID
                and ident.get("gpu_uuid") == GPU and ident.get("boot_id") == BOOT
                and ident.get("driver_generation") == GENERATION
                and ident.get("cgroup_inode") == inode,
                f"{family} {side} identity does not match pinned current hardware tuple")
        require(intent.get("name") == name and intent.get("node") == NODE
                and intent.get("node_uid") == NODE_UID and intent.get("pod_uid") == uid
                and intent.get("gpu_uuid") == GPU and intent.get("cap_mib") == cap,
                f"{family} {side} sealed intent mismatch")
        require(limit.get("soft") == cap * 1024 * 1024 and limit.get("hard") == cap * 1024 * 1024,
                f"{family} {side} cap readback mismatch")
    inventory_data = host.get("inventory", {})
    require(inventory_data.get("gpu_uuid") == GPU, f"{family} raw host inventory GPU UUID mismatch")
    inventory = inventory_data.get("entries", [])
    rows = {r.get("cgroup_id"): r for r in inventory if type(r) is dict}
    for side in ("a", "b"):
        _name, _uid, cap, inode = expected[side]
        row = rows.get(inode)
        require(type(row) is dict and row.get("hard") == cap * 1024 * 1024
                and row.get("soft") == cap * 1024 * 1024
                and row.get("pinned") is True and row.get("offline") is False
                and row.get("default_hierarchy") is True,
                f"{family} {side} device inventory cap does not match")
    return host


def assess_cross_parent(receipt, positive_result, denied_result, cleanup_receipts):
    """Assess measured VMM deny + same-parent control separately from promotion flags."""
    ok = (receipt.get("state") == "bounded-cross-parent-vmm-kernel-denial-measured"
          and receipt.get("production_qualified") is False
          and receipt.get("cross_parent_isolation_qualified") is False
          and receipt.get("same_parent_positive_control") is True
          and receipt.get("kernel_witness_correlated") is True
          and receipt.get("peer_vector_continuity") is True
          and receipt.get("final_postflight_observed") is True
          and receipt.get("remote_endpoint_cleanup") == "verified"
          and receipt.get("unchanged_native_authorities") is True
          and {"cross-parent-importer", "exporter", "same-parent-positive"} <= set(receipt.get("explicitly_completed_endpoints", []))
          and positive_result.get("expect") == "allow" and positive_result.get("cuda_result") == 0
          and positive_result.get("cuda_name") == "CUDA_SUCCESS"
          and denied_result.get("expect") == "deny" and denied_result.get("cuda_result") == 800
          and denied_result.get("cuda_name") == "CUDA_ERROR_NOT_PERMITTED"
          and cleanup_receipts >= 2)
    status = "measured_pass" if ok else "unproved"
    return {
        "measurement_status": status,
        "cross_parent_isolation_qualified": False,
        "qualification_flag_explanation": "The runner's assess() returns cross_parent_isolation_qualified=False unconditionally; it is a non-promotion label, not a failed measured denial.",
        "reason": None if ok else "Missing or mismatched positive control, typed denial, endpoint cleanup, kernel witness, or peer proof.",
    }


def _notebook_status(pod):
    status = pod.get("status", {})
    rows = [row for row in status.get("containerStatuses", []) if row.get("name") == "notebook"]
    require(len(rows) == 1, "exactly one notebook container status required")
    return rows[0]


def assess_restart(api_before, api_after, stop, peer_events, post_oom, cleanup, postflight_saved,
                   restart_before=None, post_oom_before=None):
    """Combine captured API, exact CRI stop, continuity, recovery, and cleanup proofs."""
    old, new = _notebook_status(api_before), _notebook_status(api_after)
    old_id = old.get("containerID", "").removeprefix("containerd://")
    new_id = new.get("containerID")
    lifecycle_ok = (api_before.get("metadata", {}).get("uid") == api_after.get("metadata", {}).get("uid")
                    and old.get("restartCount") == 0 and new.get("restartCount") == 1
                    and old_id and new_id != old.get("containerID") and stop.get("stopped_exact_original_cid") == old_id
                    and stop.get("old_pid_lifetime_absent") is True)
    ticks = [row.get("monotonic_ns") for row in peer_events if row.get("phase") == "peer_tick"]
    begin, end = stop.get("stop_begin_monotonic_ns"), stop.get("stop_end_monotonic_ns")
    continuity_ok = (type(begin) is int and type(end) is int and begin < end and len(ticks) >= 2
                     and all(type(t) is int for t in ticks)
                     and min(ticks) < begin < end < max(ticks))
    oom_ok = (post_oom.get("measurement_passed") is True
              and post_oom.get("typed_oom", {}).get("kind") == "torch.OutOfMemoryError"
              and post_oom.get("unchanged_seals_and_processes") is True
              and post_oom.get("recovery_byte") == 37 and post_oom.get("production_qualified") is False)
    cleanup_ok = all(cleanup.get(key) is True for key in (
        "all10_retired_offline_pinned_used0", "both_gpu_clients_zero", "whole10_original_journals_verified"))
    snapshot_ok = False
    if restart_before is not None and post_oom_before is not None:
        pre_host, post_host = restart_before.get("host", {}), post_oom_before.get("host", {})
        pre_targets, post_targets = pre_host.get("targets", []), post_host.get("targets", [])
        pre_processes, post_processes = pre_host.get("processes", []), post_host.get("processes", [])
        stable_targets = (len(pre_targets) == len(post_targets) == 2 and all(
            a.get(k) == b.get(k) for k in ("pod_uid", "intent", "identity", "seal_id", "journal_sha256", "gate_sha256")
            for a, b in zip(pre_targets, post_targets)))
        snapshot_ok = (stable_targets and len(pre_processes) == len(post_processes) == 2
                       and pre_processes[0] != post_processes[0] and pre_processes[1] == post_processes[1])
    ok = lifecycle_ok and continuity_ok and oom_ok and cleanup_ok and snapshot_ok
    unproved = []
    if not snapshot_ok:
        unproved.append("No independent pre/post host snapshot proves that only A's process lifetime changed while both native seals and B's process stayed fixed.")
    return {
        "measurement_status": "measured_pass" if ok else "unproved",
        "production_qualified": False,
        "independent_snapshot_comparison_passed": snapshot_ok,
        "original_restart_runner_postflight_saved": bool(postflight_saved),
        "original_runner_note": (None if postflight_saved else
            "Original runner's bounded postflight failed without retaining command status/output size; independent pre-restart and post-restart OOM host snapshots supply the comparison."),
        "restart_run_assertions": {"api_and_exact_stop": lifecycle_ok, "peer_bracketed_stop": continuity_ok,
                                   "postrestart_oom_recovery": oom_ok, "all10_retirement": cleanup_ok},
        "unproved": unproved,
        "reason": None if ok else "At least one independent restart/recovery assertion is absent or mismatched.",
    }


def _case(name, paths, evaluate, manifest_path=None):
    evidence = {}
    try:
        for path in paths:
            require(path.is_file(), f"missing required evidence: {path}")
            evidence[str(path)] = sha(path)
        details = evaluate()
        status = details.pop("measurement_status", "unproved")
        return {"name": name, "measurement_status": status,
                "manifest_sha256": sha(manifest_path) if status == "measured_pass" and manifest_path else None,
                "evidence_sha256": evidence, **details}
    except (EvidenceError, OSError, KeyError, TypeError, ValueError, IndexError) as exc:
        return {"name": name, "measurement_status": "unproved", "manifest_sha256": None,
                "evidence_sha256": evidence, "reason": str(exc)}


def _event(rows, phase, trial):
    matches = [row for row in rows if row.get("phase") == phase and row.get("trial_id") == trial]
    require(len(matches) == 1, f"expected one {phase} event for {trial}")
    return matches[0]


def _same_parent_case(root: Path, mode: str):
    base = root / f"imports-{mode}"
    receipt, before, after = (read_json(base / n) for n in ("receipt.json", "before.json", "after.json"))
    validate_host_pair(before, "remaining")
    validate_host_pair(after, "remaining")
    require(receipt.get("manifest_sha256") == sha(root / "manifest.actual.json"), f"{mode} manifest SHA mismatch")
    require(receipt.get("mode") == mode and receipt.get("same_parent_measurement") is True
            and receipt.get("peer_continuity") is True and receipt.get("unchanged_native_authorities") is True
            and receipt.get("cross_parent_isolation_qualified") is False
            and receipt.get("production_qualified") is False, f"{mode} same-parent receipt not a bounded pass")
    return {"measurement_status": "measured_pass", "scope": "same-parent import only",
            "cross_parent_import_proved": False, "reason": "Receipt and before/after host anchors match the 9442c844 current tuple."}


def _cross_parent_case(root: Path, direction: str):
    base = root / ("vmm-cross-" + direction + "-r6")
    receipt = read_json(base / "receipt.json")
    before = read_json(base / "before.json")
    validate_host_pair(before, "remaining")
    positive_rows = read_jsonl(base / "same-parent-positive.jsonl")
    denied_rows = read_jsonl(base / "cross-parent-importer.jsonl")
    exporter_rows = read_jsonl(base / "exporter.jsonl")
    trial = receipt.get("trial_id")
    positive = _event(positive_rows, "import-result", trial)
    denied = _event(denied_rows, "import-result", trial)
    cleanup = sum(_event(rows, "receipt", trial).get("explicit_native_cleanup_completed") is True
                  for rows in (positive_rows, denied_rows, exporter_rows))
    require(positive.get("api") == denied.get("api") == "cuMemImportFromShareableHandle"
            and positive.get("call_started_monotonic_ns", 0) > 0
            and denied.get("call_started_monotonic_ns", 0) > 0,
            "raw positive/denied CUDA calls are absent")
    for rows in (positive_rows, denied_rows):
        for phase in ("importer-before-kernel", "importer-after-kernel"):
            event = _event(rows, phase, trial)
            require(event.get("vector_verified") is True and event.get("vector_elements") == 256
                    and event.get("cuda_result") == 0,
                    f"importer vector kernel did not survive: {phase}")
    ready = _event(exporter_rows, "exporter-ready", trial)
    ticks = [row for row in exporter_rows if row.get("phase") == "exporter-tick" and row.get("trial_id") == trial]
    recovery = _event(exporter_rows, "exporter-recovery", trial)
    times = [row.get("monotonic_ns") for row in ticks]
    require(ready.get("backing_bytes") == 67108864 and len(ticks) >= 2
            and [row.get("tick") for row in ticks] == list(range(1, len(ticks) + 1))
            and all(row.get("vector_verified") is True and row.get("vector_elements") == 256 for row in ticks)
            and times[0] < denied["call_started_monotonic_ns"] <= denied["call_ended_monotonic_ns"] < times[-1]
            and recovery.get("monotonic_ns", 0) > denied["call_ended_monotonic_ns"]
            and recovery.get("vector_verified") is True and recovery.get("vector_elements") == 256
            and all(0 < b - a <= 5_000_000_000 for a, b in zip(times, times[1:])),
            "raw exporter vector continuity/recovery does not bracket denied import")
    bridges = [read_json(base / "positive-bridge.json"), read_json(base / "cross-bridge.json")]
    require([bridge.get("transfer") for bridge in bridges] == ["positive", "cross"]
            and all(bridge.get("state") == "one-bounded-vmm-descriptor-forwarded"
                    and bridge.get("trial_id") == trial and bridge.get("descriptor_count") == 1
                    and bridge.get("backing_bytes") == 67108864
                    and bridge.get("network_namespace_entered") is False for bridge in bridges)
            and bridges[0].get("fd_identity") == bridges[1].get("fd_identity") == ready.get("fd_identity"),
            "positive/cross bridge does not forward exactly the same bounded VMM backing")
    attribution = read_json(base / "importer-host-attribution.json")
    expected_importer = {row.get("pod_uid"): row for row in read_json(base / "before.json")["host"]["targets"]}
    imported_target = expected_importer.get(attribution.get("pod_uid"))
    require(imported_target is not None and attribution.get("gpu_uuid") == GPU
            and attribution.get("boot_id") == BOOT and attribution.get("driver_generation") == GENERATION
            and attribution.get("pod_cgroup_inode") == imported_target["identity"].get("cgroup_inode"),
            "importer host attribution does not bind to exact current cohort parent")
    positive_exporter, cross_exporter = (bridge.get("exporter_attribution", {}) for bridge in bridges)
    stable_exporter_keys = ("boot_id", "driver_generation", "gpu_id", "gpu_uuid", "host_pid", "host_tgid",
                            "pid_start_ticks", "pod_uid", "pod_cgroup_inode", "source_sha256",
                            "network_namespace_inode", "pid_namespace_inode", "process_cgroup_relative")
    require(bridges[1].get("importer_attribution") == attribution
            and all(positive_exporter.get(key) == cross_exporter.get(key) for key in stable_exporter_keys),
            "bridge endpoint attribution does not match saved root attribution")
    correlation = read_json(base / "kernel-witness-correlation.json")
    require(correlation.get("kernel_witness_correlated") is True
            and correlation.get("trial_id") == trial
            and correlation.get("host_tgid") == attribution.get("host_tgid")
            and correlation.get("pid_start_ticks") == attribution.get("pid_start_ticks")
            and correlation.get("kernel_status") == 27 and correlation.get("kernel_reason") == 6
            and correlation.get("client_kind") == 4,
            "raw kernel witness does not match importer attribution")
    capture = read_json(base / "kernel-witness-capture.json")
    witness_rows = read_jsonl(base / "kernel-witness.jsonl")
    completed = [row for row in witness_rows if row.get("phase") == "witness-completed"
                 and row.get("trial_id") == trial]
    require(len(completed) == 1 and completed[0].get("capture") == capture
            and completed[0].get("correlation") == correlation
            and completed[0].get("root_capture_raw_sha256") == "sha256:" + sha(base / "kernel-witness-capture.json")
            and capture.get("kind") == "root-kernel-vmm-sequence-witness"
            and capture.get("identity_verified") is True and capture.get("truncated") is False
            and capture.get("overruns") == 0 and capture.get("trial_id") == trial
            and capture.get("boot_id") == BOOT and capture.get("driver_generation") == GENERATION
            and capture.get("node_uid") == NODE_UID and capture.get("node") == NODE,
            "raw kernel witness capture is incomplete, stale, or mismatched")
    final = read_json(base / "final-postflight.json")
    final_host = validate_host_pair(final, "remaining")
    before_host = read_json(base / "before.json")["host"]
    before_targets = {row["pod_uid"]: row for row in before_host["targets"]}
    for row in final_host["targets"]:
        old = before_targets[row["pod_uid"]]
        require(all(old.get(k) == row.get(k) for k in
                    ("intent", "identity", "seal_id", "journal_sha256", "gate_sha256"))
                and row.get("limit", {}).get("used", 0) <= old.get("limit", {}).get("used", 0),
                "final postflight changed native authority or leaked charge")
    require(receipt.get("direction") == direction, "cross-parent direction mismatch")
    source_dir = root / "full-import-sources-r6/vmm-cross-parent"
    source_pins = receipt.get("source_sha256", {})
    require(type(source_pins) is dict and source_pins, "cross-parent source hash pins absent")
    for name, digest in source_pins.items():
        require(Path(name).name == name and source_dir.joinpath(name).is_file()
                and sha(source_dir / name) == digest, f"cross-parent source SHA mismatch: {name}")
    runner_source = (source_dir / "run_vmm_cross_parent.py").read_text()
    require("'cross_parent_isolation_qualified':False" in runner_source,
            "recorded runner no longer has the reviewed unconditional non-promotion flag")
    verdict = assess_cross_parent(receipt, positive, denied, cleanup)
    return {**verdict, "trial_id": trial, "raw_requirements_independently_checked": {
                "positive_allow_and_typed_cross_deny": True, "both_importer_vector_kernels": True,
                "exporter_peer_ticks_bracket_denial_and_recover": True, "same_fd_positive_and_cross_bridges": True,
                "importer_attribution_matches_current_parent": True, "raw_kernel_capture_matches_correlation": True,
                "endpoint_cleanup_and_final_seal_postflight": True},
            "qualification_flag_source": "full-import-sources-r6/vmm-cross-parent/run_vmm_cross_parent.py assess() hard-codes cross_parent_isolation_qualified=False",
            "source_sha_pins_verified": True,
            "kernel_witness": "correlated to importer host PID/start lifetime",
            "no_cross_parent_ipc": True}


def _owner_case(root: Path, side: str):
    base = root / f"vmm-owner-exit-{side}" if side == "cit" else root / "vmm-owner-exit-cps-r5"
    receipt = read_json(base / "receipt.json")
    before, after = read_json(base / "before.json"), read_json(base / "after.json")
    validate_host_pair(before, "remaining")
    validate_host_pair(after, "remaining")
    m = receipt.get("measurement", {})
    ok = (receipt.get("state") == "same-parent-vmm-creator-exit-retention-measured"
          and m.get("creator_exited_before_hold") is True
          and m.get("verified_kernel_ticks", 0) >= 20
          and m.get("verified_retained_hold_seconds", 0) >= 20
          and receipt.get("actual_final_charge_zero") is True
          and receipt.get("unchanged_authorities_and_finalzero") is True
          and receipt.get("production_qualified") is False)
    require(ok, f"{side} owner-exit measurement incomplete")
    return {"measurement_status": "measured_pass", "singleuser_baseline_present": bool(receipt.get("singleuser_baseline_sha256")),
            "singleuser_baseline_sha256": receipt.get("singleuser_baseline_sha256"),
            "review_note": "A single-user baseline hash is null; retained backing and cleanup were measured, but that comparison is not established."}


def _managed_case(root: Path, side: str):
    base = root / f"managed-{side}"
    receipt, probe = read_json(base / "receipt.json"), read_json(base / "probe-result.json")
    require(receipt.get("state") == "typed-managed-api-denial-controls-and-cleanup-observed"
            and receipt.get("measurement", {}).get("typed_managed_denial") is True
            and receipt.get("measurement", {}).get("cuda_result") == 801
            and receipt.get("unchanged_authorities_and_charge_recovered") is True,
            f"{side} managed API receipt incomplete")
    raw = probe.get("probe", {})
    events = raw.get("events", [])
    before = [e for e in events if e.get("phase") == "ordinary-before"]
    denied = [e for e in events if e.get("phase") == "managed-attempt"]
    after = [e for e in events if e.get("phase") == "ordinary-recovery"]
    require(len(before) == len(denied) == len(after) == 1
            and denied[0].get("cuda_result") == 801
            and denied[0].get("error_name") == "CUDA_ERROR_NOT_SUPPORTED"
            and before[0].get("vector_verified") is True and after[0].get("vector_verified") is True,
            f"{side} managed raw events mismatch")
    return {"measurement_status": "measured_pass", "promotion_pending": receipt.get("pending", []),
            "scope": "typed managed-API denial plus ordinary recovery"}


def review_bundle(pressure_root: Path, remaining_root: Path, restart_root: Path):
    reports = []
    pressure_manifest = pressure_root / "manifest.actual.json"
    remaining_manifest = remaining_root / "manifest.actual.json"
    restart_manifest = restart_root / "manifest.actual.json"

    def peer_case():
        manifest = read_json(pressure_manifest); validate_manifest(manifest, "pressure")
        summary = read_json(pressure_root / "peer-oom-both-actual-summary.json")
        require(summary.get("manifest_sha256") == sha(pressure_manifest), "OOM summary does not pin exact manifest bytes")
        for name, direction, held in (("oom-a5-peer-b10", "b-to-a", 4608), ("oom-b10-peer-a5", "a-to-b", 9728)):
            base = pressure_root / name
            before, after = read_json(base / "before.json"), read_json(base / "after.json")
            validate_host_pair(before, "pressure"); validate_host_pair(after, "pressure")
            assessment = read_json(base / "assessment.json")
            require(assessment.get("measurement_passed") is True and assessment.get("production_qualified") is False
                    and assessment.get("direction") == direction and assessment.get("held_before_oom_mib") == held
                    and assessment.get("typed_oom", {}).get("kind") == "torch.OutOfMemoryError"
                    and assessment.get("peer_ticks_inside_oom_hold", 0) >= 16
                    and assessment.get("physical_samples") == 4 and assessment.get("recovery_byte") == 37
                    and assessment.get("unchanged_seals_and_processes") is True,
                    f"OOM/peer assessment incomplete: {name}")
        return {"measurement_status": "measured_pass", "directions": ["b-to-a", "a-to-b"],
                "scope": "bounded OOM and peer continuity"}
    reports.append(_case("oom-peer-both-directions", [pressure_manifest,
        pressure_root / "peer-oom-both-actual-summary.json", pressure_root / "oom-a5-peer-b10/assessment.json",
        pressure_root / "oom-b10-peer-a5/assessment.json"], peer_case, pressure_manifest))

    def aggregate_case():
        manifest = read_json(remaining_manifest); validate_manifest(manifest, "remaining")
        base = remaining_root / "aggregate-b10-holder-a5-peer"
        before, after, assessment = (read_json(base / n) for n in ("before.json", "after.json", "assessment.json"))
        validate_host_pair(before, "remaining"); validate_host_pair(after, "remaining")
        require(assessment.get("measurement_passed") is True and assessment.get("same_parent_aggregate") is True
                and assessment.get("holder_tensor_mib") == 2048 and assessment.get("held_before_oom_mib") == 6912
                and assessment.get("typed_oom", {}).get("kind") == "torch.OutOfMemoryError"
                and assessment.get("ordinary_peer_ticks_inside_oom_hold", 0) >= 16
                and assessment.get("peer_ticks_inside_oom_hold", 0) >= 16
                and assessment.get("physical_samples") == 4 and assessment.get("recovery_byte") == 37
                and assessment.get("unchanged_seals_and_processes") is True,
                "same-parent aggregate measurement incomplete")
        return {"measurement_status": "measured_pass", "scope": "same-parent aggregate cap"}
    reports.append(_case("aggregate", [remaining_manifest, remaining_root / "aggregate-b10-holder-a5-peer/before.json",
        remaining_root / "aggregate-b10-holder-a5-peer/after.json",
        remaining_root / "aggregate-b10-holder-a5-peer/assessment.json"], aggregate_case, remaining_manifest))

    for mode in ("ipc", "vmm", "vmm-direct"):
        paths = [remaining_manifest] + [remaining_root / f"imports-{mode}/{n}" for n in
                 ("receipt.json", "before.json", "after.json", "native-events.json", "peer-events.json")]
        reports.append(_case(f"same-parent-{mode}", paths,
            lambda mode=mode: _same_parent_case(remaining_root, mode), remaining_manifest))

    for direction in ("cit-to-cps", "cps-to-cit"):
        base = remaining_root / f"vmm-cross-{direction}-r6"
        sources = remaining_root / "full-import-sources-r6/vmm-cross-parent"
        paths = [remaining_manifest] + [base / n for n in
            ("receipt.json", "before.json", "same-parent-positive.jsonl", "cross-parent-importer.jsonl",
             "exporter.jsonl", "kernel-witness-correlation.json", "importer-host-attribution.json",
             "kernel-witness.jsonl", "kernel-witness-capture.json", "cross-bridge.json",
             "positive-bridge.json", "final-postflight.json")] + [sources / n for n in (
                 "run_vmm_cross_parent.py", "vmm_endpoint.py", "vmm_bridge.py",
                 "kernel_witness_collector.py", "kernel_witness_validator.py", "kernel_witness_transport.py")]
        reports.append(_case(f"cross-parent-vmm-{direction}", paths,
            lambda direction=direction: _cross_parent_case(remaining_root, direction), remaining_manifest))

    for side in ("cit", "cps"):
        base = remaining_root / (f"vmm-owner-exit-{side}" if side == "cit" else "vmm-owner-exit-cps-r5")
        paths = [remaining_manifest] + [base / n for n in
            ("receipt.json", "before.json", "after.json", "endpoint.jsonl", "participants-final.json")]
        reports.append(_case(f"owner-exit-{side}", paths,
            lambda side=side: _owner_case(remaining_root, side), remaining_manifest))

    for side in ("cit", "cps"):
        base = remaining_root / f"managed-{side}"
        paths = [remaining_manifest, base / "receipt.json", base / "probe-result.json",
                 base / "before.json", base / "after.json"]
        reports.append(_case(f"managed-api-{side}", paths,
            lambda side=side: _managed_case(remaining_root, side), remaining_manifest))

    def restart_case():
        validate_manifest(read_json(restart_manifest), "restart")
        base = restart_root / "restart-a-once-b-peer"
        api_before, api_after = read_json(base / "api-before.json"), read_json(base / "api-after.json")
        stop = read_json(base / "stop.actual.json")
        before_snapshot = read_json(base / "before.json")
        post_dir = restart_root / "post-restart-a5-oom-b10-peer"
        post_before, post_after = read_json(post_dir / "before.json"), read_json(post_dir / "after.json")
        validate_host_pair(before_snapshot, "restart")
        validate_host_pair(post_before, "restart"); validate_host_pair(post_after, "restart")
        assessment = read_json(post_dir / "assessment.json")
        peer_events = read_jsonl(base / "peer.jsonl")
        cleanup = read_json(restart_root / "cleanup-safe-summary.json")
        result = assess_restart(api_before, api_after, stop, peer_events, assessment, cleanup,
                                postflight_saved=False, restart_before=before_snapshot,
                                post_oom_before=post_before)
        require(result["independent_snapshot_comparison_passed"] is True,
                "independent restart snapshots do not prove only A main lifetime changed")
        require(all(t["limit"].get("used") == 0 for t in post_after["host"]["targets"]),
                "post-restart OOM did not return both caps to zero")
        return {**result, "original_runner_error": "Bounded actual Root observation failed; exit status versus >4 MiB output is not retained.",
                "independent_postrestart_snapshot_pair": True,
                "postrestart_snapshot_comparison": "native seals/identities stable; A main process changed; B main process stable"}
    restart_paths = [restart_manifest,
        restart_root / "restart-a-once-b-peer/api-before.json", restart_root / "restart-a-once-b-peer/api-after.json",
        restart_root / "restart-a-once-b-peer/stop.actual.json", restart_root / "restart-a-once-b-peer/peer.jsonl",
        restart_root / "restart-a-once-b-peer/before.json", restart_root / "post-restart-a5-oom-b10-peer/before.json",
        restart_root / "post-restart-a5-oom-b10-peer/after.json",
        restart_root / "post-restart-a5-oom-b10-peer/assessment.json",
        restart_root / "cleanup-safe-summary.json", restart_root / "restart-once.runner.log"]
    reports.append(_case("restart-cleanup-recovery", restart_paths, restart_case, restart_manifest))

    unproved = [
        "Cross-parent IPC: no cross-parent IPC run/receipt exists; same-parent IPC does not establish cross-parent IPC behavior.",
        "Cross-parent VMM promotion: both directions measured typed CUDA_ERROR_NOT_PERMITTED with kernel-correlated witnesses and same-parent positive controls, but receipt and runner keep cross_parent_isolation_qualified=false unconditionally; this is a review/promotion gate, not a failed VMM measurement.",
        "Managed API promotion: receipts record pending Root review of exact UVM guard origin/ENOSYS evidence and closed libcuda status mapping.",
        "Owner-exit single-user comparison: both owner-exit receipts have singleuser_baseline_sha256=null, so comparison to a single-user baseline remains unproved.",
    ]
    return {
        "review_only": True, "api_calls": False, "gpu_calls": False,
        "hardware_qualified": False, "production_qualified": False,
        "tuple": {"gpu_uuid": GPU, "node": NODE, "node_uid": NODE_UID,
                  "boot_id": BOOT, "driver_generation": GENERATION, "driver": "615.71.09"},
        "cases": reports, "unproved": unproved,
        "manifest_hash_policy": "manifest SHA256 is emitted only for cases whose required evidence validated as measured_pass; it identifies bytes, it does not promote qualification.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pressure-root", type=Path, default=Path("/tmp/cps-second-card-pressure-20261027"))
    parser.add_argument("--remaining-root", type=Path, default=Path("/tmp/cps-second-card-remaining-20261027"))
    parser.add_argument("--restart-root", type=Path, default=Path("/tmp/cps-second-card-mps-restart-20261027"))
    args = parser.parse_args(argv)
    print(json.dumps(review_bundle(args.pressure_root, args.remaining_root, args.restart_root),
                     sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()

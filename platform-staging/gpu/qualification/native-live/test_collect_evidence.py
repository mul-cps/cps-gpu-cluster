"""CPU tests of interpretation/sanitization; no hardware qualification claims."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

MODULE_PATH = Path(__file__).with_name("collect_evidence.py")
spec = importlib.util.spec_from_file_location("native_evidence_collector", MODULE_PATH)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)

MAIN = "11111111-1111-4111-8111-111111111111"
PEER = "22222222-2222-4222-8222-222222222222"
GPU = "GPU-33333333-3333-4333-8333-333333333333"
CAP = collector.CAP_BYTES
SECRET = "private-token-MUST-NOT-APPEAR"


def write(root, name, value):
    path = root / name
    if name.endswith(".jsonl"):
        path.write_text("".join(json.dumps(row) + "\n" for row in value))
    elif name.endswith(".json"):
        path.write_text(json.dumps(value))
    else:
        path.write_text(value)


def read(root, name):
    return json.loads((root / name).read_text())


def rows(root, name):
    return [json.loads(line) for line in (root / name).read_text().splitlines()]


def mem():
    return {"cuda_result": 0, "total_bytes": CAP, "free_bytes": CAP - 1000}


def native(phases, *, final="bounded-measurement-completed", base=1000000000):
    return [{"kind": "identity", "gpu_uuid": GPU, "uid": 1000, "gid": 100,
             "driver_api_version": 13040}, {"kind": "initial-cap-info", "total_bytes": CAP}] + [
        {"kind": "cuda", "phase": name, "result": result, "time_ns": base + i * 1000000,
         "production_qualified": False} for i, (name, result) in enumerate(phases)] + [
        {"kind": "final", "status": final, "production_qualified": False}]


@pytest.fixture
def capture(tmp_path, monkeypatch):
    for role, uid in [("main", MAIN), ("peer", PEER)]:
        pod_spec = {"nodeName": "fixture-node", "containers": [{"name": "user",
                    "env": [{"name": "SECRET", "value": SECRET}]}]}
        digest = hashlib.sha256(json.dumps(pod_spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        write(tmp_path, f"native-cap-{role}-intent.json", {
            "namespace": "fixture", "name": role, "pod_uid": uid,
            "node": "fixture-node", "node_uid": "44444444-4444-4444-8444-444444444444",
            "gpu_uuid": GPU, "cap_mib": 5120, "policy_hash": "sha256:" + "a" * 64,
            "spec_sha256": digest, "api_token": SECRET})
        write(tmp_path, f"native-cap-{role}-actual.json", {"kind": "Pod",
            "metadata": {"namespace": "fixture", "name": role, "uid": uid, "token": SECRET},
            "spec": pod_spec, "private": SECRET})
    write(tmp_path, "controller-restarted.jsonl", [{"pod_uid": uid, "state": "sealed",
        "iteration": iteration, "production_qualified": False} for iteration in (0, 1) for uid in (MAIN, PEER)])
    write(tmp_path, "guard-load-receipt.json", {"state": "guard-loaded-trusted-epoch-issued",
        "driver_generation": "55555555-5555-4555-8555-555555555555", "private": SECRET,
        "params": {"uvm_deny_managed_mmap": "Y", "uvm_disable_hmm": "Y", "uvm_ats_mode": "0",
                   "uvm_enable_builtin_tests": "0", "uvm_disable_sam_migration": "Y"}})
    for name, mode in [("ordinary-oom.jsonl", "oom"), ("ordinary-oom-concurrent.jsonl", "oom"),
                       ("managed-denial.jsonl", "managed")]:
        sequence = [{"state": "context-ready", "mode": mode, "attributes": {"88": 0, "100": 0},
                     "memory": mem(), "observed_ns": 1000000000}]
        sequence.append({"state": "over-cap-attempt", "cuda_result": 2, "observed_ns": 2000000000}
                        if mode == "oom" else {"state": "managed-attempt", "observed_ns": 2000000000,
                            "result": {"cuda_result": 801, "memory": mem(), "touch_result": None,
                                       "prefetch_result": None}})
        sequence.append({"state": "measurement-passed", "mode": mode,
                         "observed_ns": 3000000000, "production_qualified": False})
        write(tmp_path, name, sequence)
    write(tmp_path, "vmm-direct.jsonl", native([(name, result) for name, result in [
        ("vmm-create-64", 0), ("fill-64", 0), ("readback", 0), ("vmm-over-cap-never-touch", 2),
        ("vmm-create-64", 0), ("fill-64", 0), ("readback", 0)]]))
    write(tmp_path, "same-ipc-export.jsonl", native([("ipc-export", 0)]))
    write(tmp_path, "same-ipc-import.jsonl", native([("initialize", 0)], final="inconclusive"))
    write(tmp_path, "same-ipc-import-corrected.jsonl", native([
        ("ipc-import", 0), ("import-readback", 0), ("ipc-close", 0)]))
    write(tmp_path, "manual-socket-mode-workaround.json", {"state": "operator-workaround-applied",
        "mode": "0600", "scopes": ["same-ipc", "cross-vmm"], "production_workaround": False})
    write(tmp_path, "cross-vmm-export.jsonl", native([
        ("vmm-export", 0), ("exporter-references-released-importer-retains", 0)], base=9999000000))
    importer = native([("vmm-import", 0), ("importer-retained-backing-start", 0),
                       ("importer-retained-backing-end", 0)])
    for r in importer:
        if r.get("kind") == "cuda":
            r["time_ns"] = {"vmm-import": 9000000000, "importer-retained-backing-start": 10000000000,
                            "importer-retained-backing-end": 19000000000}[r["phase"]]
    write(tmp_path, "cross-vmm-import.jsonl", importer)
    write(tmp_path, "cross-vmm-accounting.jsonl", [{"observed_ns": t, "apps": SECRET,
        "parents": [{"pod_uid": uid, "gpu_uuid": GPU, "cgroup": SECRET,
                     "limits": {"soft": CAP, "hard": CAP, "used": 434192064}} for uid in (MAIN, PEER)]}
        for t in (7000000000, 8000000000)])
    write(tmp_path, "mps-two-clients.txt", "101\n102\n")
    write(tmp_path, "mps-two-client-charge.json", {"observed_ns": 20000000000,
        "registered_server": 100, "registered_clients": [101, 102],
        "parents": [{"uid": uid, "cap": {"soft": CAP, "hard": CAP, "used": 434192064}}
                    for uid in (MAIN, PEER)], "processes": [
            {"pid": 100, "cmd": "nvidia-cuda-mps-server ", "private": SECRET}] + [
            {"pid": pid, "start": 10000, "cgroup": "0::/kubepods/pod" + uid.replace("-", "_") +
             ".slice/scope", "cmd": SECRET} for pid, uid in [(101, MAIN), (102, PEER)]]})
    write(tmp_path, "mps-main-held.jsonl", [
        {"phase": "context-held-before-alloc", "memory": mem(), "observed_ns": 2000000000},
        {"phase": "ordinary64-held", "result": {"cuda_result": 0, "touch_result": 0, "memory": mem()},
         "observed_ns": 10000000000},
        {"phase": "overcap", "result": 2, "observed_ns": 20000000000},
        {"phase": "managed-denial", "result": {"cuda_result": 801, "touch_result": None,
         "prefetch_result": None, "memory": mem()}, "observed_ns": 21000000000},
        {"phase": "bounded-sequence-passed", "production_qualified": False, "observed_ns": 30000000000}])
    source = "CPU fixture source; never executed\n"
    monkeypatch.setattr(collector, "MPS_HELD_SOURCE_SHA256", hashlib.sha256(source.encode()).hexdigest())
    write(tmp_path, "mps-main-held.py", source)
    heartbeat = [{"state": "context-ready", "mode": "heartbeat", "attributes": {"88": 0, "100": 0},
                  "memory": mem(), "observed_ns": 100000000}]
    heartbeat.extend({"state": "peer-tick", "observed_ns": t,
                      "tick": {"cuda_result": 0, "memory": mem(), "monotonic_ns": t + 9999}}
                     for t in range(500000000, 120000000001, 500000000))
    heartbeat.append({"state": "measurement-passed", "mode": "heartbeat",
                      "observed_ns": 120200000000, "production_qualified": False})
    write(tmp_path, "mps-peer-120.jsonl", heartbeat)
    return tmp_path


def test_valid_partial_capture_distinguishes_measurements_and_never_leaks(capture):
    report = collector.collect(capture)
    assert report["status"] == "partial-live-evidence"
    assert report["errors"] == []
    assert report["production_qualified"] is report["group_sharing_enabled"] is False
    assert report["source_import_guard_qualified"] is False
    assert SECRET not in json.dumps(report)
    assert str(capture) not in json.dumps(report)
    assert report["cases"]["cross_vmm"]["retention_accounting"]["status"] == "unmeasured"
    assert report["cases"]["same_ipc"]["status"] == "passed-with-operator-workaround"
    assert report["cases"]["mps"]["recovery"]["raw_phase_recorded"] is False
    assert report["cases"]["mps"]["independent_peer"]["duration_seconds"] >= 120
    assert len(report["cases"]["mps"]["independent_peer"]["phase_brackets"]) == 5
    for item in report["provenance"]:
        assert item["sha256"] == hashlib.sha256((capture / item["file"]).read_bytes()).hexdigest()


@pytest.mark.parametrize("missing", ["ordinary-oom.jsonl", "vmm-direct.jsonl", "cross-vmm-accounting.jsonl",
    "mps-peer-120.jsonl", "controller-restarted.jsonl", "manual-socket-mode-workaround.json"])
def test_missing_critical_log_fails(capture, missing):
    (capture / missing).unlink()
    report = collector.collect(capture)
    assert report["status"] == "incomplete-or-invalid-live-evidence"
    assert report["errors"]


@pytest.mark.parametrize("result", [0, 1, True, "2", 801])
def test_oom_requires_typed_result_two(capture, result):
    data = rows(capture, "ordinary-oom.jsonl")
    data[1]["cuda_result"] = result
    write(capture, "ordinary-oom.jsonl", data)
    assert {e["case"] for e in collector.collect(capture)["errors"]} == {"ordinary_oom"}


def test_actual_spec_hash_is_recomputed_instead_of_trusting_hint(capture):
    data = read(capture, "native-cap-main-actual.json")
    data["spec"]["containers"][0]["env"][0]["value"] = "changed executable configuration"
    write(capture, "native-cap-main-actual.json", data)
    report = collector.collect(capture)
    assert report["errors"][0]["code"] == "actual-spec-hash-mismatch"
    assert report["cases"]["mps"]["status"] == "blocked-by-invalid-authority-evidence"


def test_sealed_marker_is_insufficient_without_repeat_restart_observation(capture):
    write(capture, "controller-restarted.jsonl", rows(capture, "controller-restarted.jsonl")[:2])
    assert collector.collect(capture)["errors"][0]["code"] == "restart-not-repeatedly-sealed"


def test_missing_vmm_post_oom_touch_readback_fails(capture):
    data = rows(capture, "vmm-direct.jsonl")
    data = [r for r in data if not (r.get("phase") == "readback" and r.get("time_ns", 0) > 1003000000)]
    write(capture, "vmm-direct.jsonl", data)
    assert any(e["code"] == "missing-vmm-recovery" for e in collector.collect(capture)["errors"])


def test_observed_retention_window_does_not_promote_ownership_qualification(capture):
    data = rows(capture, "cross-vmm-accounting.jsonl")
    data[-1]["observed_ns"] = 15000000000
    write(capture, "cross-vmm-accounting.jsonl", data)
    case = collector.collect(capture)["cases"]["cross_vmm"]
    assert case["retention_accounting"]["status"] == "observed-not-qualified"
    assert case["cross_import_ownership_qualified"] is False


def test_mps_clients_must_be_distinct_native_pod_parents(capture):
    data = read(capture, "mps-two-client-charge.json")
    data["processes"][2]["cgroup"] = data["processes"][1]["cgroup"]
    write(capture, "mps-two-client-charge.json", data)
    assert any(e["code"] == "mps-client-parent-mismatch" for e in collector.collect(capture)["errors"])


def test_single_unhealthy_peer_tick_fails_even_with_completion_marker(capture):
    data = rows(capture, "mps-peer-120.jsonl")
    data[25]["tick"]["cuda_result"] = 999
    write(capture, "mps-peer-120.jsonl", data)
    assert any(e["case"] == "mps" for e in collector.collect(capture)["errors"])


def test_peer_tick_gap_bracketing_failure(capture):
    data = rows(capture, "mps-peer-120.jsonl")
    data = [r for r in data if not 18000000000 < r["observed_ns"] < 23000000000]
    write(capture, "mps-peer-120.jsonl", data)
    assert any(e["code"] == "peer-tick-gap" for e in collector.collect(capture)["errors"])


def test_mps_recovery_source_is_not_executed_or_silently_adopted(capture):
    write(capture, "mps-main-held.py", "raise RuntimeError('must never execute')\n")
    assert any(e["code"] == "mps-executed-source-mismatch" for e in collector.collect(capture)["errors"])


def test_duplicate_json_keys_and_symlinks_fail_closed(capture):
    write(capture, "guard-load-receipt.json", {})
    (capture / "guard-load-receipt.json").write_text('{"state": "a", "state": "b"}')
    assert any(e["code"] == "duplicate-json-key" for e in collector.collect(capture)["errors"])
    target = capture / "ordinary-oom.jsonl"
    target.unlink()
    target.symlink_to(capture / "ordinary-oom-concurrent.jsonl")
    assert any(e["code"] == "unsafe-input-file" for e in collector.collect(capture)["errors"])


def test_cli_exit_failure_is_sanitized_and_has_no_hardware_calls(tmp_path):
    result = subprocess.run([sys.executable, str(MODULE_PATH), str(tmp_path)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "incomplete-or-invalid-live-evidence"
    assert result.stderr == ""
    assert str(tmp_path) not in result.stdout


def test_output_hardlink_cannot_destroy_raw_capture(capture, monkeypatch, capsys):
    raw = capture / "native-cap-main-actual.json"
    original = raw.read_bytes()
    elsewhere = capture / "another-directory"
    elsewhere.mkdir()
    output = elsewhere / "report.json"
    os.link(raw, output)
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH), str(capture), "--output", str(output)])
    assert collector.main() == 1
    assert raw.read_bytes() == original and output.read_bytes() == original
    assert capsys.readouterr().err.strip() == "output-already-exists"


def test_new_output_is_sanitized_and_private(capture, monkeypatch, capsys):
    output = capture / "new-report.json"
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH), str(capture), "--output", str(output)])
    assert collector.main() == 0
    report = json.loads(output.read_text())
    assert report["status"] == "partial-live-evidence" and not report["errors"]
    assert SECRET not in output.read_text()
    assert output.stat().st_mode & 0o777 == 0o600
    assert capsys.readouterr().err == ""


def test_input_swapped_to_symlink_at_open_fails_closed(capture, monkeypatch):
    target = capture / "ordinary-oom.jsonl"
    secret = capture / "private-unrelated.txt"
    secret.write_text(SECRET)
    original_os_open, original_io_open = os.open, io.open

    def swap(path):
        if Path(path) == target and not target.is_symlink():
            target.unlink()
            target.symlink_to(secret)

    def open_descriptor(path, *args, **kwargs):
        swap(path)
        return original_os_open(path, *args, **kwargs)

    def open_file(path, *args, **kwargs):
        swap(path)
        return original_io_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", open_descriptor)
    monkeypatch.setattr(io, "open", open_file)
    with pytest.raises(collector.EvidenceError, match="unsafe-input-file"):
        collector.Inputs(capture).raw(target.name)
    assert secret.read_text() == SECRET


def test_input_changed_during_descriptor_read_is_not_published(capture, monkeypatch):
    target = capture / "ordinary-oom.jsonl"
    original_read = os.read
    changed = False

    def append_during_read(fd, count):
        nonlocal changed
        data = original_read(fd, count)
        if not changed:
            changed = True
            with target.open("ab") as output:
                output.write(b" ")
        return data

    monkeypatch.setattr(os, "read", append_during_read)
    inputs = collector.Inputs(capture)
    with pytest.raises(collector.EvidenceError, match="input-changed-during-read"):
        inputs.raw(target.name)
    assert inputs.provenance == {}


@pytest.mark.parametrize("kind", ["file", "symlink"])
def test_existing_output_is_preserved(capture, monkeypatch, capsys, kind):
    output = capture / "existing-report.json"
    if kind == "file":
        output.write_text("existing report")
    else:
        output.symlink_to(capture / "native-cap-main-actual.json")
    original = output.read_bytes()
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH), str(capture), "--output", str(output)])
    assert collector.main() == 1
    assert output.read_bytes() == original
    assert capsys.readouterr().err.strip() == "output-already-exists"

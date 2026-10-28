"""Offline integration checks for the current second-card bundle wrapper."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


HERE = Path(__file__).resolve().parent
BASE_TEST = HERE.parent / "native-second-card" / "test_prepare.py"
BASE_SPEC = importlib.util.spec_from_file_location("base_second_card_tests", BASE_TEST)
BASE_TESTS = importlib.util.module_from_spec(BASE_SPEC)
BASE_SPEC.loader.exec_module(BASE_TESTS)
SPEC = importlib.util.spec_from_file_location("current_group_prepare", HERE / "prepare.py")
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


def raw_file(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_default_invocation_is_inert(capsys):
    PREPARE.main([])
    assert json.loads(capsys.readouterr().out) == {
        "inert": True, "api_calls": False, "gpu_calls": False,
        "hardware_qualified": False, "production_qualified": False,
    }


def test_rejects_changed_base_producer_before_execution(tmp_path):
    original = PREPARE.BUILDER_SHA256
    PREPARE.BUILDER_SHA256 = "0" * 64
    try:
        with pytest.raises(ValueError, match="Pinned source generator"):
            PREPARE.verify_builder()
    finally:
        PREPARE.BUILDER_SHA256 = original


def test_rejects_duplicate_keys_in_bounded_input(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"version":1,"version":1}')
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        PREPARE.read_pinned_json(path, hashlib.sha256(path.read_bytes()).hexdigest(), limit=1024)


def test_delegates_synthetic_fixture_and_emits_complete_unrun_bundle(tmp_path, capsys):
    observations = BASE_TESTS.observations()
    request = BASE_TESTS.request()
    obs_path, request_path = tmp_path / "observations.json", tmp_path / "request.json"
    obs_hash = raw_file(obs_path, observations)
    request_hash = raw_file(request_path, request)
    output = tmp_path / "bundle"

    PREPARE.main([
        "--prepare", "--observations", str(obs_path), "--observations-sha256", obs_hash,
        "--inputs", str(request_path), "--inputs-sha256", request_hash,
        "--output", str(output), "--approve-qa-hostpaths",
    ])

    assert json.loads(capsys.readouterr().out) == {
        "prepared": True, "delegated_to": "native-second-card/prepare.py",
        "api_calls": False, "gpu_calls": False, "launch_authorized": False,
    }
    receipt = json.loads((output / "preparation.json").read_text())
    assert receipt["state"] == "offline-prepared-not-executed"
    assert receipt["launch_authorized"] is False
    assert set(receipt["families"]) == {
        "cap-assignment", "oom-peer", "aggregate", "memory-import",
        "restart-cleanup", "mps", "capacity",
    }
    assert {
        "controller.py", "observe.py", "run_peer_oom.py", "run_aggregate.py",
        "imports/run_imports.py", "restart/run_peer_oom.py", "mps/run_mps.py",
        "gate-source.configmap.json", "a.proposed.json", "b.proposed.json",
    } <= {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()}
    assert all(row["state"] == "unrun" and row["receipts"] == []
               for row in receipt["families"].values())
    assert (output / "bundle/cps_compute/native_gpu_controller.py").is_file()
    assert (output / "imports/run_imports.py").is_file()
    assert (output / "mps/run_mps.py").is_file()


def test_cli_rejects_bad_input_hash_without_creating_output(tmp_path):
    obs_path, request_path = tmp_path / "observations.json", tmp_path / "request.json"
    raw_file(obs_path, BASE_TESTS.observations())
    raw_file(request_path, BASE_TESTS.request())
    output = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="SHA256"):
        PREPARE.main([
            "--prepare", "--observations", str(obs_path), "--observations-sha256", "0" * 64,
            "--inputs", str(request_path), "--inputs-sha256", hashlib.sha256(request_path.read_bytes()).hexdigest(),
            "--output", str(output), "--approve-qa-hostpaths",
        ])
    assert not output.exists()

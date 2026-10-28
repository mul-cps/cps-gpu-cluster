"""CPU-only closure tests for current GPU2 cross-parent IPC source preparation."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def module():
    return load("prepare_ipc_current", HERE / "prepare_ipc_current.py")


def current_observations():
    fixture = load("native_second_card_fixture", HERE.parent / "native-second-card" / "test_prepare.py")
    value = fixture.observations()
    value["namespace"]["metadata"]["uid"] = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    value["cohort_uid"] = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    value["node"]["status"]["nodeInfo"]["bootID"] = "a464df41-e391-4443-b8e8-ad7ecd052318"
    value["guard"]["boot_id"] = "a464df41-e391-4443-b8e8-ad7ecd052318"
    value["device"]["boot_id"] = "a464df41-e391-4443-b8e8-ad7ecd052318"
    value["guard"]["driver_generation"] = "4ebffc96-e25e-4583-a3b8-0d853fd90efd"
    return value


def request(observations):
    ns = observations["namespace"]["metadata"]
    return {
        "version": 1,
        "pair": "5-10",
        "namespace": ns["name"],
        "namespace_uid": ns["uid"],
        "cohort_uid": observations["cohort_uid"],
        "policy_hash": observations["policy_hash"],
        "gate_image": "ghcr.io/mul-cps/cps-compute@sha256:" + "a" * 64,
    }


def manifest(observations):
    ns = observations["namespace"]["metadata"]
    cohort = observations["cohort_uid"]
    root = f"/var/lib/cps-native-gpu/qualification/{ns['uid']}/cohorts/{cohort}/tools"
    return {
        "version": 1,
        "cohort_uid": cohort,
        "namespace_uid": ns["uid"],
        "pods": {
            key: {
                "namespace": ns["name"],
                "name": f"native-second-card-{key}-{cohort[:8]}",
                "uid": ("11111111-1111-4111-8111-111111111111" if key == "a" else "22222222-2222-4222-8222-222222222222"),
                "cap_mib": 5120 if key == "a" else 10240,
                "spec_sha256": ("a" if key == "a" else "b") * 64,
            }
            for key in ("a", "b")
        },
        "observer_argv": ["ssh", "root@reviewed", "python3", root + "/observe.py", "--execute", "--cohort-uid", cohort],
        "physical_argv": ["ssh", "root@reviewed", "python3", root + "/physical_samples.py", "--execute"],
    }


def build_inputs():
    observations = current_observations()
    request_value = request(observations)
    manifest_value = manifest(observations)
    raw = json.dumps(manifest_value, sort_keys=True, separators=(",", ":")).encode()
    return observations, request_value, raw


def test_builds_current_gpu2_ipc_closure_with_derived_anchor_and_dynamic_caps():
    tool = module()
    observations, req, raw = build_inputs()
    result = tool.build_bundle(observations, req, raw, hashlib.sha256(raw).hexdigest())
    files = result["files"]
    runner = files["native-fresh-ipc/run_cross_pod.py"].decode()
    root = "/var/lib/cps-native-gpu/qualification/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/cohorts/bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb/ipc-kmsg-witness"

    assert f"ROOT={root!r}" in runner
    assert "6ba3353d-bf13-4cad-9c35-3119dd279a67" not in "\n".join(v.decode() for v in files.values() if v.endswith(b"\n"))
    assert "expected_cap_mib" in runner
    assert b"GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6" in files["native-fresh-ipc/ipc_endpoint.py"]
    assert b"CAPS_MIB = (5120, 10240)" in files["native-fresh-ipc/ipc_endpoint.py"]
    assert b"06:11.0/cps_native_caps" in files["native-fresh-ipc/ipc_host_pid.py"]
    assert b"expected_cap_mib" in files["native-fresh-ipc/ipc_host_pid.py"]
    assert b"GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6" in files["native-fresh-ipc/kernel_witness_validator.py"]
    assert files["native-fresh-domain/fresh_preflight.py"] == tool.load_preparer().build_sources(observations)["files"]["fresh_preflight.py"]
    assert result["hardware_qualified"] is False and result["production_qualified"] is False
    assert result["required_directions"] == ["a-to-b", "b-to-a"]
    assert result["root_stage"]["directory_mode"] == "0700"
    assert set(result["root_stage"]["source_modes"]) == {
        "ipc_host_pid.py", "kernel_witness_collector.py", "kernel_witness_validator.py"
    }

    for name, source in files.items():
        if name.endswith(".py"):
            compile(source, name, "exec")
    assert result["generated_sha256"] == {
        name: hashlib.sha256(source).hexdigest()
        for name, source in files.items() if name != "bundle-manifest.json"
    }
    pins_node = next(node for node in ast.parse(runner).body
                     if isinstance(node, ast.Assign)
                     and isinstance(node.targets[0], ast.Name)
                     and node.targets[0].id == "PINS")
    pins = ast.literal_eval(pins_node.value)
    pin_names = {Path(name).name for name in tool.SOURCE_PINS
                 if name.startswith("native-fresh-ipc/") and Path(name).name != "run_cross_pod.py"}
    assert set(pins) == pin_names
    assert pins == {name: hashlib.sha256(files["native-fresh-ipc/" + name]).hexdigest() for name in pin_names}


def test_rejects_manifest_from_another_or_stale_cohort():
    tool = module()
    observations, req, raw = build_inputs()
    value = json.loads(raw)
    value["cohort_uid"] = "33333333-3333-4333-8333-333333333333"
    stale = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="cohort|namespace|manifest"):
        tool.build_bundle(observations, req, stale, hashlib.sha256(stale).hexdigest())
    with pytest.raises(ValueError, match="retired"):
        tool.current_root(observations["namespace"]["metadata"]["uid"], "9442c844-5ca2-477f-956c-e3e752a09393")


def test_refuses_non_second_gpu_or_changed_reviewed_source():
    tool = module()
    observations, req, raw = build_inputs()
    observations["device"]["gpu_uuid"] = "GPU-16128952-b438-556a-00bb-93039ee24e56"
    with pytest.raises(ValueError, match="second-card|second-card|native GPU identity"):
        tool.build_bundle(observations, req, raw, hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match="source|preimage|SHA"):
        tool.checked_bytes("native-fresh-ipc/run_cross_pod.py", b"changed")


def test_default_mode_is_inert_without_input_file_reads(monkeypatch, capsys):
    tool = module()
    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", lambda *args: (_ for _ in ()).throw(AssertionError("unexpected read")))
        tool.main([])
    output = json.loads(capsys.readouterr().out)
    assert output == {"state": "inert", "api_calls": False, "gpu_calls": False}


def test_prepare_cli_writes_private_offline_bundle(tmp_path, capsys):
    tool = module()
    observations, req, manifest_raw = build_inputs()
    inputs = tmp_path / "inputs"
    inputs.mkdir(mode=0o700)
    values = {
        "observations.json": json.dumps(observations, sort_keys=True, separators=(",", ":")).encode(),
        "request.json": json.dumps(req, sort_keys=True, separators=(",", ":")).encode(),
        "manifest.json": manifest_raw,
    }
    for name, raw in values.items():
        path = inputs / name
        path.write_bytes(raw)
        path.chmod(0o600)
    output = tmp_path / "ipc-source"
    tool.main([
        "--prepare",
        "--observations", str(inputs / "observations.json"), "--observations-sha256", hashlib.sha256(values["observations.json"]).hexdigest(),
        "--request", str(inputs / "request.json"), "--request-sha256", hashlib.sha256(values["request.json"]).hexdigest(),
        "--manifest", str(inputs / "manifest.json"), "--manifest-sha256", hashlib.sha256(manifest_raw).hexdigest(),
        "--output", str(output),
    ])
    summary = json.loads(capsys.readouterr().out)
    bundle = json.loads((output / "bundle-manifest.json").read_bytes())
    assert summary["state"] == "offline-prepared-not-executed"
    assert summary["api_calls"] is False and summary["gpu_calls"] is False
    assert bundle["manifest_sha256"] == hashlib.sha256(manifest_raw).hexdigest()
    assert bundle["input_sha256"]["observations"] == hashlib.sha256(values["observations.json"]).hexdigest()
    assert output.stat().st_mode & 0o777 == 0o700
    for name, pin in bundle["generated_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == pin
        assert (output / name).stat().st_mode & 0o777 == 0o600

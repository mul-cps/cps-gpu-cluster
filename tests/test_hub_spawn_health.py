import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


file_path = (Path(__file__).resolve().parents[1] /
             "cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring/hub-spawn-health.py")
spec = importlib.util.spec_from_file_location("hub_spawn_health", file_path)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def test_unexpected_identity_never_mutates_a_server():
    client = Mock()
    client.request.return_value.status_code = 200
    client.request.return_value.json.return_value = {"kind": "user", "name": "different-user"}
    with pytest.raises(monitor.ProbeFailure, match="identity"):
        monitor.run_profile(client, "cit-probe", "route-check", {"profile": "gpu-mujoco-xpra"}, {}, "cit-shared")
    assert [call.args[0] for call in client.request.call_args_list] == ["GET"]


def test_ready_server_must_return_the_exact_user_options():
    client = Mock()
    def respond(method, path, **kwargs):
        response = Mock()
        response.status_code = {"POST": 202, "DELETE": 204}.get(method, 200)
        if method == "GET":
            response.json.return_value = next(models)
        return response

    models = iter([
        {"kind": "user", "name": "cit-probe", "groups": [], "admin": False},
        {"servers": {}},
        {"servers": {"route-check": {"ready": True, "user_options": {"profile": "cpu-small"}}}},
        {"servers": {}},
    ])
    client.request.side_effect = respond
    with pytest.raises(monitor.ProbeFailure, match="options"):
        monitor.run_profile(client, "cit-probe", "route-check", {"profile": "gpu-mujoco-xpra"}, {}, "cit-shared")
    assert [call.args[0] for call in client.request.call_args_list] == ["GET", "GET", "POST", "GET", "DELETE", "GET"]


def test_route_must_redirect_to_the_trusted_dex_host():
    client = Mock()
    resp = client.request.return_value
    resp.status_code = 302
    resp.headers = {"location": "https://untrusted.invalid/auth"}
    with pytest.raises(monitor.ProbeFailure, match="redirect"):
        monitor.require_dex_redirect(resp)


def test_shared_check_rejects_a_poweruser_fixture_before_spawn():
    client = Mock()
    client.request.return_value.status_code = 200
    client.request.return_value.json.return_value = {
        "kind": "user", "name": "cit-probe", "groups": ["jhub-powerusers"], "admin": False,
    }
    with pytest.raises(monitor.ProbeFailure, match="elevated"):
        monitor.run_profile(client, "cit-probe", "route-check", {"profile": "gpu-mujoco-xpra"}, {}, "cit-shared")
    assert [call.args[0] for call in client.request.call_args_list] == ["GET"]


def test_resource_contract_covers_both_shared_sizes_and_dedicated_hardware():
    for size in (2, 5):
        share = monitor.resource_contract("cit-shared", f"{size}g", 1)
        assert share["vram_mib"] == 1024 * size
        assert share["gpus"] == 1
        assert share["cpu"] == 8
    assert monitor.resource_contract("cit-research", "xlarge-tf", 2)["peer"] is True
    assert monitor.resource_contract("cps-poweruser", "tensorflow-dual", 2)["framework"] == "tensorflow"

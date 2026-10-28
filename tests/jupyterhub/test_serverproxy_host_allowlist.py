from pathlib import Path

import pytest
from traitlets.config import Config
import yaml


VALUES = (
    Path(__file__).parents[2]
    / "cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml"
)


def _execute_mounted_server_config():
    values = yaml.safe_load(VALUES.read_text())
    source = values["singleuser"]["extraFiles"]["jupyter-server-config"]["stringData"]
    config = Config()
    exec(source, {"get_config": lambda: config})
    return config


@pytest.mark.parametrize("host", ("localhost", "LOCALHOST", "127.0.0.1", "::1"))
def test_server_proxy_allows_required_loopback_hosts(host):
    config = _execute_mounted_server_config()

    assert config.ServerProxy["host_allowlist"](None, host) is True


@pytest.mark.parametrize(
    "host",
    (
        "example.com",
        "10.0.0.5",
        "192.168.1.20",
        "169.254.169.254",
        "kubernetes.default.svc",
        "localhost.attacker.example",
        "127.0.0.2",
        "0.0.0.0",
    ),
)
def test_server_proxy_rejects_browser_selected_remote_hosts(host):
    config = _execute_mounted_server_config()

    assert config.ServerProxy["host_allowlist"](None, host) is False


def test_host_policy_does_not_change_existing_xpra_launcher():
    config = _execute_mounted_server_config()

    assert config.ServerApp["jpserver_extensions"] == {
        "jupyter_server_proxy": True,
        "jupyter_code_server": True,
        "jupyter_remote_desktop_proxy": True,
    }
    servers = config.ServerProxy["servers"]
    assert set(servers) == {"xpra"}
    xpra = servers["xpra"]
    assert xpra["launcher_entry"] == {"title": "Desktop (Xpra)"}
    assert xpra["new_browser_tab"] is True
    command = xpra["command"](23999)
    assert "--bind-tcp=0.0.0.0:23999" in command
    assert "--start-child=/usr/local/bin/start-xpra-desktop.sh" in command

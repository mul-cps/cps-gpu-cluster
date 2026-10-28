import ast
from pathlib import Path

import yaml


VALUES_PATH = (
    Path(__file__).parents[2]
    / "cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml"
)
JUPYTERHUB_DIR = VALUES_PATH.parent
DASK_RBAC_DIR = JUPYTERHUB_DIR.parent / "dask-compute-rbac"


def load_policy():
    values = yaml.safe_load(VALUES_PATH.read_text())
    source = values["hub"]["extraConfig"]["02-profiles"]
    return source, ast.parse(source)


def find_assignment(module, name):
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} assignment not found")


def test_fixed_gpu_profiles_and_standard_nfs_mounts_remain_available():
    _, module = load_policy()
    profiles = find_assignment(module, "PROFILE_CONFIGS")
    mounts = find_assignment(module, "STANDARD_NFS_MOUNTS")

    assert {"gpu-pytorch-single", "gpu-3gb", "gpu-student"} <= profiles.keys()
    assert {mount["key"] for mount in mounts} == {
        "personal",
        "persistent1_shared",
        "scratch",
    }
    assert all(mount["kind"] == "pvc" for mount in mounts)


def test_spawn_policy_has_no_free_form_gpu_or_nfs_overrides():
    source, module = load_policy()

    forbidden_inputs = {
        "custom_gpus",
        "custom_nfs_enabled",
        "custom_nfs_server",
        "custom_nfs_path",
        "custom_nfs_mount_path",
        "sanitize_nfs_volume_name",
    }
    assert not any(f'name="{name}"' in source for name in forbidden_inputs)

    functions = {
        node.name: node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    namespace = {}
    subset = ast.Module(
        body=[functions["reject_custom_resources"], functions["form_bool"], functions["options_from_form"]],
        type_ignores=[],
    )
    exec(compile(subset, str(VALUES_PATH), "exec"), namespace)

    parsed = namespace["options_from_form"](
        {
            "profile": ["gpu-3gb"],
            "mount_nfs": ["1"],
            "mount_personal_nfs": ["1"],
        }
    )

    assert parsed["profile"] == "gpu-3gb"
    assert parsed["mount_nfs"] is True
    assert parsed["mount_personal_nfs"] is True
    assert forbidden_inputs.isdisjoint(parsed)


def test_custom_resource_requests_are_rejected_before_spawn_side_effects():
    import pytest
    import asyncio
    from types import SimpleNamespace
    _, module = load_policy()
    functions = {
        n.name: n for n in module.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    validator = functions["reject_custom_resources"]
    apply = functions["apply_profile_settings"]
    assert isinstance(apply.body[0], ast.Expr)
    assert isinstance(apply.body[0].value, ast.Call)
    assert apply.body[0].value.func.id == "reject_custom_resources"
    ns = {}
    exec(compile(ast.Module(body=[validator, functions["form_bool"], functions["options_from_form"], apply], type_ignores=[]), str(VALUES_PATH), "exec"), ns)
    for request in ({"custom_gpus": 2}, {"custom_nfs_server": "unapproved"}, {"custom_nfs_enabled": True}, {"custom_nfs_enabled": False, "custom_nfs_server": "unapproved"}):
        with pytest.raises(ValueError):
            ns["reject_custom_resources"](request)
        with pytest.raises(ValueError):
            asyncio.run(ns["apply_profile_settings"](SimpleNamespace(user_options=request)))
    with pytest.raises(ValueError):
        ns["options_from_form"]({"custom_gpus": ["2"]})
    ns["reject_custom_resources"]({"custom_gpus": "0"})


def test_legacy_disabled_custom_nfs_defaults_do_not_block_restart():
    _, module = load_policy()
    validator = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "reject_custom_resources")
    ns = {}
    exec(compile(ast.Module(body=[validator], type_ignores=[]), str(VALUES_PATH), "exec"), ns)
    ns["reject_custom_resources"]({"custom_nfs_enabled": False, "custom_nfs_server": "193.170.30.58", "custom_nfs_mount_path": "/home/jovyan/custom_nfs", "custom_gpus": 0})


def test_service_account_is_limited_to_authorized_dask_profile():
    import pytest
    _, module = load_policy()
    functions = {
        n.name: n for n in module.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    ns = {}
    exec(compile(ast.Module(body=[functions["notebook_service_account"]], type_ignores=[]), str(VALUES_PATH), "exec"), ns)
    select = ns["notebook_service_account"]
    assert select("cpu-default") == "default"
    assert select("gpu-3gb") == "default"
    with pytest.raises(ValueError, match="disabled until per-user Kubernetes authorization"):
        select("dask-cluster")
    with pytest.raises(ValueError, match="disabled until per-user Kubernetes authorization"):
        select("dask-cluster")
    values = yaml.safe_load(VALUES_PATH.read_text())
    assert values["singleuser"]["serviceAccountName"] == "default"


def test_non_dask_spawns_do_not_mount_kubernetes_credentials():
    import asyncio
    from types import SimpleNamespace

    _, module = load_policy()
    functions = {n.name: n for n in module.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    apply = functions["apply_profile_settings"]
    # Execute the actual beginning of the spawn hook, before external services.
    apply.body = apply.body[:4]
    ns = {"is_power_user": lambda user: user.is_power_user}
    exec(compile(ast.Module(body=[functions["reject_custom_resources"], functions["notebook_service_account"], apply], type_ignores=[]), str(VALUES_PATH), "exec"), ns)
    for profile, power, account, mount in [("cpu-default", False, "default", False), ("gpu-3gb", True, "default", False)]:
        spawner = SimpleNamespace(user_options={"profile": profile}, user=SimpleNamespace(is_power_user=power))
        asyncio.run(ns["apply_profile_settings"](spawner))
        assert (spawner.service_account, spawner.automount_service_account_token) == (account, mount)


def test_dask_profile_is_hidden_and_spawn_fails_closed_for_power_users():
    import asyncio
    import pytest
    from types import SimpleNamespace

    _, module = load_policy()
    functions = {
        n.name: n for n in module.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    profile_config = next(
        n for n in module.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "PROFILE_CONFIGS" for t in n.targets)
    )
    ns = {
        "is_power_user": lambda user: user.is_power_user,
        "is_student": lambda user: user.is_student,
    }
    exec(compile(ast.Module(body=[profile_config, functions["get_profile_list"]], type_ignores=[]), str(VALUES_PATH), "exec"), ns)
    for is_power_user, is_student in ((False, False), (False, True), (True, False)):
        visible = ns["get_profile_list"](
            SimpleNamespace(
                user=SimpleNamespace(is_power_user=is_power_user, is_student=is_student)
            )
        )
        visible_slugs = {profile["slug"] for profile in visible}
        assert "cpu-default" in visible_slugs
        assert "dask-cluster" not in visible_slugs

    spawn_functions = [
        functions["reject_custom_resources"],
        functions["notebook_service_account"],
        functions["apply_profile_settings"],
    ]
    apply = functions["apply_profile_settings"]
    apply.body = apply.body[:4]
    exec(compile(ast.Module(body=spawn_functions, type_ignores=[]), str(VALUES_PATH), "exec"), ns)
    spawner = SimpleNamespace(
        user_options={"profile": "dask-cluster"},
        user=SimpleNamespace(is_power_user=True, is_student=False),
    )
    with pytest.raises(ValueError, match="disabled until per-user Kubernetes authorization"):
        asyncio.run(ns["apply_profile_settings"](spawner))
    assert not hasattr(spawner, "service_account")


def test_dask_namespace_rbac_is_not_granted_to_a_shared_service_account():
    root = yaml.safe_load((JUPYTERHUB_DIR / "kustomization.yaml").read_text())
    assert "dask-serviceaccount.yaml" in root["resources"]
    service_account = yaml.safe_load((JUPYTERHUB_DIR / "dask-serviceaccount.yaml").read_text())
    assert (service_account["kind"], service_account["metadata"]["name"], service_account["metadata"]["namespace"]) == (
        "ServiceAccount", "dask-sa", "jupyterhub"
    )
    assert not DASK_RBAC_DIR.exists()

    jupyter_manifests = VALUES_PATH.parent.parent
    for path in jupyter_manifests.rglob("*.yaml"):
        text = path.read_text()
        if "{{" in text:  # Skip Helm templates, which are not standalone YAML.
            continue
        for document in yaml.safe_load_all(text):
            if document and document.get("kind") in {"RoleBinding", "ClusterRoleBinding"}:
                assert not any(
                    subject.get("kind") == "ServiceAccount"
                    and subject.get("name") == "dask-sa"
                    for subject in document.get("subjects", [])
                ), f"{path} grants Kubernetes permissions to the shared Dask account"

    documentation = (JUPYTERHUB_DIR / "README.md").read_text()
    assert "Dask Cluster** profile is temporarily disabled" in documentation
    assert "isolated per user" in documentation

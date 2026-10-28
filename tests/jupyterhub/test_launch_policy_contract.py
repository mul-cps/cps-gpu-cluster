import ast
from pathlib import Path

import yaml


VALUES_PATH = (
    Path(__file__).parents[2]
    / "cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml"
)


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
    for request in ({"custom_gpus": 2}, {"custom_nfs_server": "unapproved"}, {"custom_nfs_enabled": True}):
        with pytest.raises(ValueError):
            ns["reject_custom_resources"](request)
        with pytest.raises(ValueError):
            asyncio.run(ns["apply_profile_settings"](SimpleNamespace(user_options=request)))
    with pytest.raises(ValueError):
        ns["options_from_form"]({"custom_gpus": ["2"]})
    ns["reject_custom_resources"]({"custom_gpus": "0"})

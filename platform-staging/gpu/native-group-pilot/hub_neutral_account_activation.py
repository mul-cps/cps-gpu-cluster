"""Offline, private, full-Secret CAS compiler for the reviewed Hub registry.

This emits a separate configuration phase. It performs no Kubernetes access,
database migration, service token creation or GPU policy operation.
"""

from __future__ import annotations

import argparse
import ast
import base64
import copy
import hashlib
import os
from pathlib import Path
import stat

import yaml

import native_group_approval_renderer as r

IMAGE = "ghcr.io/mul-cps/cps-compute@sha256:466b8398285a513499440dd00aaf0abc377cc49afe05f19e5556e79908106486"
SCOPE = "custom:cps:provision:workspace-account"
CLASS_SHA256 = "638789d4d8252ac7c2a0b66e9433415da4d5f3e191c9ce093709879292eae353"
OWNERS = {"cps": ["cpsnativegroupa", "cpsnativegroupb"], "cit": ["citnativegroupa"]}
NAMESPACES = {"cps": "jupyterhub", "cit": "cit-jhub"}
REQUEST = {
    "version",
    "source",
    "target_image",
    "secret",
    "secret_sha256",
    "neutral_owners",
    "legacy_owners",
    "services",
    "roles",
    "backup",
}
BACKUP = {"sha256", "bytes", "source", "hub_version", "secret_uid", "values_sha256"}


def closed(value, keys, message):
    r.require(isinstance(value, dict) and set(value) == set(keys), message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def backup_digest(path):
    """Hash an owned immutable private regular backup without following links."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        r.require(
            stat.S_ISREG(before.st_mode)
            and stat.S_IMODE(before.st_mode) in (0o400, 0o600)
            and before.st_uid == os.getuid()
            and before.st_nlink == 1
            and 0 < before.st_size <= 10 * 1024**3,
            "Owned private regular database backup required",
        )
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        after = os.fstat(descriptor)
        r.require(
            (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ),
            "Database backup changed during capture",
        )
        return digest.hexdigest(), before.st_size
    finally:
        os.close(descriptor)


def span(raw, node):
    lines = raw.splitlines(keepends=True)
    return (
        sum(len(line) for line in lines[: node.lineno - 1]) + node.col_offset,
        sum(len(line) for line in lines[: node.end_lineno - 1]) + node.end_col_offset,
    )


def edit_configuration(code, source, owners, legacy, backup, configured_role=None):
    raw = code.encode("utf-8")
    tree = ast.parse(code)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    r.require(
        len(classes) == 1
        and classes[0].name == "CPSNativeLoginGuard"
        and sha256(ast.dump(classes[0], include_attributes=False).encode())
        == CLASS_SHA256,
        "Exact reviewed inline authentication class required",
    )
    assignments = [
        (ast.unparse(n.targets[0]), n)
        for n in tree.body
        if isinstance(n, ast.Assign) and len(n.targets) == 1
    ]
    owner_nodes = [node for name, node in assignments if name == "_native_owners"]
    authority_nodes = [
        node for name, node in assignments if name == "c.JupyterHub.authenticator_class"
    ]
    r.require(
        len(owner_nodes) == len(authority_nodes) == 1,
        "Unique reviewed owner and authenticator assignments required",
    )
    owner = owner_nodes[0]
    r.require(
        owner is not None
        and isinstance(owner.value, ast.Call)
        and isinstance(owner.value.func, ast.Name)
        and owner.value.func.id == "frozenset"
        and len(owner.value.args) == 1
        and not owner.value.keywords
        and sorted(ast.literal_eval(owner.value.args[0])) == owners,
        "Exact existing Source owner names required",
    )
    authority = authority_nodes[0]
    r.require(
        authority is not None
        and isinstance(authority.value, ast.Name)
        and authority.value.id == "CPSNativeLoginGuard",
        "Reviewed inline authenticator assignment required",
    )
    outside = [
        node
        for statement in tree.body
        if statement is not classes[0]
        for node in ast.walk(statement)
    ]
    r.require(
        all(
            node is authority.value
            for node in outside
            if isinstance(node, ast.Name) and node.id == "CPSNativeLoginGuard"
        )
        and all(
            node is owner.targets[0]
            for node in outside
            if isinstance(node, ast.Name)
            and node.id == "_native_owners"
            and isinstance(node.ctx, (ast.Store, ast.Del))
        )
        and all(
            node is authority.targets[0]
            for node in outside
            if isinstance(node, ast.Attribute)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and ast.unparse(node) == "c.JupyterHub.authenticator_class"
        ),
        "Only the exact reviewed owner and authenticator bindings may be rewritten",
    )
    service = source + "-admin"
    role_name = service + "-api"
    loops = [
        n
        for n in tree.body
        if isinstance(n, ast.For)
        and isinstance(n.target, ast.Name)
        and n.target.id == "_native_preserved"
        and isinstance(n.iter, ast.List)
    ]
    r.require(len(loops) == 1, "Exact captured role-preservation block required")
    for node in loops[0].iter.elts:
        if isinstance(node, ast.Dict):
            keys = [ast.literal_eval(key) for key in node.keys]
            r.require(
                all(isinstance(key, str) for key in keys)
                and len(set(keys)) == len(keys),
                "Unique literal captured role keys required",
            )
    role_nodes = [
        n
        for n in loops[0].iter.elts
        if isinstance(n, ast.Dict) and ast.literal_eval(n).get("name") == role_name
    ]
    r.require(
        len(role_nodes) == 1,
        "Own Source API role required in captured preservation block",
    )
    role = ast.literal_eval(role_nodes[0])
    r.require(
        role.get("services") == [service]
        and role.get("users", []) == []
        and role.get("groups", []) == []
        and isinstance(role.get("scopes"), list)
        and SCOPE not in role["scopes"]
        and not any(s.split("!")[0] == "admin:users" for s in role["scopes"]),
        "Actual Source Service API role may receive only the narrow provisioning scope",
    )
    scope_node = next(
        value
        for key, value in zip(role_nodes[0].keys, role_nodes[0].values)
        if ast.literal_eval(key) == "scopes"
    )
    r.require(
        isinstance(scope_node, ast.List), "Captured literal Source API scopes required"
    )
    inherited_role = copy.deepcopy(role)
    if configured_role is not None:
        r.require(
            isinstance(configured_role, dict) and "name" not in configured_role,
            "Captured own chart role must have its unique mapping-key identity",
        )
        inherited_role = {"name": role_name, **copy.deepcopy(configured_role)}
        normalized = copy.deepcopy(inherited_role)
        for assignment in ("users", "groups", "services"):
            normalized.setdefault(assignment, [])
        r.require(
            normalized == role,
            "Complete own configured API role must match captured actual policy",
        )
    transition = (
        "_native_provisioning_before = " + repr(inherited_role) + "\n"
        "_native_provisioning_matches = [role for role in _native_roles "
        "if role.get('name') == " + repr(role_name) + "]\n"
        "if len(_native_provisioning_matches) > 1:\n"
        "    raise RuntimeError('Duplicate own Source API role')\n"
        "if _native_provisioning_matches:\n"
        "    if _native_provisioning_matches[0] != _native_provisioning_before:\n"
        "        raise RuntimeError('Existing own Source API role differs from captured configuration')\n"
        "    _native_provisioning_matches[0]['scopes'] = "
        + repr(role["scopes"] + [SCOPE])
        + "\n"
    )
    replacement = (
        "from cps_compute_hub import install_workspace_account_provisioning\n"
        "install_workspace_account_provisioning(\n"
        "    c, neutral_owners="
        + repr(owners)
        + ", legacy_owners="
        + repr(legacy)
        + ",\n"
        "    service_sources=" + repr({service: source}) + ",\n"
        "    allow_registry_migration=True,\n"
        "    registry_backup_sha256=" + repr(backup) + ",\n"
        ")"
    )
    edits = [
        (*span(raw, classes[0]), replacement.encode()),
        (*span(raw, authority), b""),
        (*span(raw, scope_node), repr(role["scopes"] + [SCOPE]).encode()),
        (span(raw, loops[0])[0], span(raw, loops[0])[0], transition.encode()),
    ]
    for start, end, value in sorted(edits, reverse=True):
        raw = raw[:start] + value + raw[end:]
    result = raw.decode("utf-8")
    ast.parse(result)
    return result, role


def replace_guard_scalar(raw, replacement, expected):
    """Replace one unique YAML value while preserving every outside byte."""
    text = raw.decode("utf-8")
    node = yaml.compose(text)
    for name in ("hub", "extraConfig", "zy-native-group-access"):
        r.require(
            isinstance(node, yaml.MappingNode), "Unique Hub config mapping required"
        )
        keys = [key.value for key, _value in node.value]
        r.require(
            all(
                isinstance(key, yaml.ScalarNode) and key.tag == "tag:yaml.org,2002:str"
                for key, _value in node.value
            )
            and len(set(keys)) == len(keys),
            "Unique Hub config keys required",
        )
        matches = [value for key, value in node.value if key.value == name]
        r.require(len(matches) == 1, "Unique reviewed guard scalar required")
        node = matches[0]
    r.require(
        isinstance(node, yaml.ScalarNode) and node.tag == "tag:yaml.org,2002:str",
        "Reviewed guard must be a literal YAML string",
    )
    start, end = node.start_mark.index, node.end_mark.index
    scalar = yaml.safe_dump(
        replacement, default_style='"', allow_unicode=True, width=10_000_000
    ).rstrip("\n")
    if text[start:end].endswith("\n"):
        scalar += "\n"
    result = (text[:start] + scalar + text[end:]).encode("utf-8")
    r.require(
        yaml.safe_load(result) == expected,
        "Scalar replacement must preserve complete Hub values semantics",
    )
    return result


def compile_intent(request, *, backup_sha256, backup_bytes):
    closed(
        request, REQUEST, "Closed offline Hub account configuration request required"
    )
    source = request["source"]
    r.require(
        type(request["version"]) is int
        and request["version"] == 1
        and source in OWNERS
        and request["target_image"] == IMAGE,
        "Exact reviewed image and Source required",
    )
    owners = request["neutral_owners"]
    legacy = request["legacy_owners"]
    r.require(
        owners == OWNERS[source]
        and isinstance(legacy, list)
        and len(set(legacy)) == len(legacy)
        and legacy == sorted(legacy)
        and set(legacy) <= set(owners),
        "Permanent reviewed owner list and explicit legacy compatibility required",
    )
    secret = request["secret"]
    r.require(
        isinstance(secret, dict)
        and secret.get("apiVersion") == "v1"
        and secret.get("kind") == "Secret"
        and secret.get("type") == "Opaque"
        and secret.get("immutable") in (None, False)
        and secret.get("metadata", {}).get("namespace") == NAMESPACES[source]
        and secret["metadata"].get("name") == "hub"
        and isinstance(secret["metadata"].get("resourceVersion"), str)
        and isinstance(secret["metadata"].get("uid"), str)
        and request["secret_sha256"] == r.canonical_sha256(secret),
        "Exact actual Hub Secret identity and full preimage required",
    )
    data = secret.get("data")
    r.require(
        isinstance(data, dict)
        and "values.yaml" in data
        and all(isinstance(v, str) for v in data.values()),
        "Complete actual Hub Secret data required",
    )
    try:
        raw = base64.b64decode(data["values.yaml"], validate=True)
        values = yaml.safe_load(raw)
        code = values["hub"]["extraConfig"]["zy-native-group-access"]
    except Exception:
        raise ValueError(
            "Actual Hub values and inline guard configuration required"
        ) from None
    r.require(isinstance(code, str), "Inline guard bytes required")
    backup = request["backup"]
    closed(
        backup,
        BACKUP,
        "Explicit matching actual private Hub database backup proof required",
    )
    r.require(
        backup["sha256"] == backup_sha256
        and backup["bytes"] == backup_bytes
        and backup_bytes > 0
        and isinstance(backup_sha256, str)
        and len(backup_sha256) == 64
        and backup["source"] == source
        and backup["hub_version"] == "5.5.2"
        and backup["secret_uid"] == secret["metadata"]["uid"]
        and backup["values_sha256"] == sha256(raw),
        "Actual backup bytes, Source, Hub version and configuration custody must match",
    )
    service = source + "-admin"
    role_name = service + "-api"
    configured_roles = values["hub"].get("loadRoles", {})
    r.require(
        isinstance(configured_roles, dict), "Captured chart role mapping required"
    )
    replacement, role = edit_configuration(
        code, source, owners, legacy, backup_sha256, configured_roles.get(role_name)
    )
    actual_service = (
        request["services"].get(service)
        if isinstance(request["services"], dict)
        else None
    )
    actual_role = (
        request["roles"].get(role_name) if isinstance(request["roles"], dict) else None
    )
    r.require(
        isinstance(actual_service, dict)
        and actual_service.get("kind") == "service"
        and actual_service.get("name") == service
        and role_name in actual_service.get("roles", [])
        and isinstance(actual_role, dict)
        and actual_role.get("name") == role_name
        and actual_role.get("services") == [service]
        and actual_role.get("users", []) == []
        and actual_role.get("groups", []) == []
        and actual_role.get("scopes") == role["scopes"],
        "Actual own Source Service registry and assigned API role must match captured policy",
    )
    target = copy.deepcopy(values)
    target["hub"]["extraConfig"]["zy-native-group-access"] = replacement
    target_data = copy.deepcopy(data)
    target_raw = replace_guard_scalar(raw, replacement, target)
    target_data["values.yaml"] = base64.b64encode(target_raw).decode()
    metadata = secret["metadata"]
    patch = [
        {"op": "test", "path": "/metadata/uid", "value": metadata["uid"]},
        {
            "op": "test",
            "path": "/metadata/resourceVersion",
            "value": metadata["resourceVersion"],
        },
        {"op": "test", "path": "/type", "value": secret["type"]},
        {"op": "test", "path": "/data", "value": data},
        {"op": "replace", "path": "/data", "value": target_data},
    ]
    return {
        "version": 1,
        "kind": "reviewed-hub-neutral-account-configuration",
        "source": source,
        "target_image_required": IMAGE,
        "secret_identity": {k: metadata[k] for k in ("namespace", "name", "uid")},
        "previous_secret_sha256": request["secret_sha256"],
        "backup": copy.deepcopy(backup),
        "previous_values_sha256": sha256(raw),
        "next_values_sha256": sha256(target_raw),
        "secret_patch": patch,
        "only_added_service_scope": {
            "service": service,
            "role": role_name,
            "scope": SCOPE,
        },
        "migration_enabled": True,
        "live_applied": False,
        "requires_controlled_registry_readback_and_migration_flag_retirement": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.compile:
        print("Inert: no API, database, Source, GPU or filesystem mutation performed.")
        return 0
    r.require(
        args.input is not None and args.backup is not None and args.output is not None,
        "Private request, actual private backup and new private output required",
    )
    request = r._private_json(args.input)
    digest, size = backup_digest(args.backup)
    intent = compile_intent(request, backup_sha256=digest, backup_bytes=size)
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    target = args.output / "intent.json"
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(r.canonical(intent) + "\n")
    print(
        r.canonical(
            {
                "version": 1,
                "source": request["source"],
                "live_applied": False,
                "output_sha256": "sha256:" + sha256(target.read_bytes()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prepare the existing marked IPC denial runner for one fresh GPU2 5/10 pair.

Default mode is inert. --prepare only reads pinned local inputs and writes a new
source bundle; it does not contact Kubernetes, a Hub, a node, or a GPU.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types
import uuid

HERE = Path(__file__).resolve().parent
QUALIFICATION = HERE.parent
PREPARER_PATH = QUALIFICATION / "native-second-card" / "prepare.py"
PREPARER_SHA256 = "971aff6b1eb1c266f7f96ebde34eae09d522740bcb13ab3e848921ec4169fa6d"
SECOND_GPU = "GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6"
BOOT = "a464df41-e391-4443-b8e8-ad7ecd052318"
GENERATION = "4ebffc96-e25e-4583-a3b8-0d853fd90efd"
NODE = "k3s-wk-gpu2"
NODE_UID = "3336cdd5-d245-436e-b57c-2f66c6dcaa41"
CAPS_MIB = (5120, 10240)
ROOT_PREFIX = "/var/lib/cps-native-gpu/qualification"
OLD_ROOT = (ROOT_PREFIX + "/1f7d941a-872d-4453-a1ba-fd489d8aff14/cohorts/"
            "6ba3353d-bf13-4cad-9c35-3119dd279a67/ipc-kmsg-witness")
RETIRED_COHORTS = {
    "a9fc091b-f388-4f21-8771-b6ae7b4734dc",
    "3b217fe8-5750-4ead-954a-09286afd7d3f",
    "9442c844-5ca2-477f-956c-e3e752a09393",
}

SOURCE_PINS = {
    "native-fresh-ipc/run_cross_pod.py": "db60d19fe64e6414c8229c4622c63bf4df310affb1ea8863429618c36022e833",
    "native-fresh-ipc/ipc_engine.py": "a4478f7d2bfeb0e85e826f26ac1c30800800e0910db0df10e4d5cc67c2423ce3",
    "native-fresh-ipc/ipc_endpoint.py": "20b36695ae6b5a9a6d3807ff4646c2928d0ba72017aa2fec4c20cb1fdcd4712b",
    "native-fresh-ipc/ipc_host_pid.py": "d3f43d1d5fb02a4f83aac8a1360bffb673e7f3d77f58669cf1f789a569499f95",
    "native-fresh-ipc/kernel_witness_collector.py": "78d0db27fe46ee28ee7cb6d01d2eb6f123596038e0f94c183dd7d0fd9621b1bf",
    "native-fresh-ipc/kernel_witness_validator.py": "030f5faec77d1db819944f85ec09bb0117480c6f3b2ce85915830c793f9cb795",
    "native-fresh-ipc/kernel_witness_transport.py": "ce703a63de29c8d6e9447c2c92bd08bbbddd77d757b2789c21b9b3fc86167850",
    "native-fresh-imports/run_imports.py": "5ad010a9823f8c02276eebb99779071b98d81bb45561ba7f9383e9b9bfedb802",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def parse_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key refused")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _value: require(False, "Non-finite JSON refused"))


def checked_bytes(name, raw=None):
    """Return reviewed repository source bytes, refusing changed preimages."""
    pins = {**SOURCE_PINS, "native-second-card/prepare.py": PREPARER_SHA256}
    require(name in pins, "Unlisted source refused")
    path = (QUALIFICATION / name) if name.startswith("native-") else PREPARER_PATH
    raw = path.read_bytes() if raw is None else raw
    require(sha(raw) == pins[name], "Reviewed source preimage SHA mismatch: " + name)
    return raw


def load(name, path, raw):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def load_preparer():
    raw = checked_bytes("native-second-card/prepare.py")
    return load("current_second_card_preparer", PREPARER_PATH, raw)


def replace_assignment(source, name, expression):
    tree = ast.parse(source)
    matches = [node for node in tree.body if isinstance(node, ast.Assign)
               and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
               and node.targets[0].id == name]
    require(len(matches) == 1, "Exact source assignment required: " + name)
    node = matches[0]
    lines = source.splitlines(keepends=True)
    replacement = f"{name}={expression}\n"
    lines[node.lineno - 1:node.end_lineno] = [replacement]
    return "".join(lines)


def replace_once(source, old, new, label):
    require(source.count(old) == 1, "Exact source span required: " + label)
    return source.replace(old, new)


def validate_request(request, context):
    fields = {"version", "pair", "namespace", "namespace_uid", "cohort_uid", "policy_hash", "gate_image"}
    require(type(request) is dict and set(request) == fields and type(request["version"]) is int
            and request["version"] == 1 and request["pair"] == "5-10"
            and request["namespace"] == context["namespace"]
            and request["namespace_uid"] == context["namespace_uid"]
            and request["cohort_uid"] == context["cohort"]
            and request["policy_hash"] == context["policy_hash"],
            "Request must bind the prepared current 5/10 cohort")
    require(type(request["gate_image"]) is str and re.fullmatch(
        r"ghcr\.io/mul-cps/cps-compute@sha256:[a-f0-9]{64}", request["gate_image"]),
        "Reviewed immutable qualification image reference required")


def current_root(namespace_uid, cohort_uid):
    for value in (namespace_uid, cohort_uid):
        require(type(value) is str and str(uuid.UUID(value)) == value and uuid.UUID(value).int > 0,
                "Canonical nonzero current namespace/cohort UUID required")
    root = f"{ROOT_PREFIX}/{namespace_uid}/cohorts/{cohort_uid}/ipc-kmsg-witness"
    require(root != OLD_ROOT and cohort_uid not in RETIRED_COHORTS,
            "Historical/retired IPC witness anchor reuse refused")
    return root


def adapt_sources(preflight_sha, root):
    """Rebase only fixed GPU2/5-10 cohort authorities and their source pins."""
    files = {}
    for name, pin in SOURCE_PINS.items():
        files[name] = checked_bytes(name)

    endpoint = files["native-fresh-ipc/ipc_endpoint.py"].decode()
    endpoint = replace_assignment(endpoint, "GPU", repr(SECOND_GPU))
    endpoint = replace_once(endpoint, "CAP = 5368709120", "CAPS_MIB = (5120, 10240)", "IPC allowed parent caps")
    endpoint = replace_once(endpoint, "class Native:\n    def __init__(self):",
        "class Native:\n    def __init__(self, expected_cap_mib):\n        require(type(expected_cap_mib) is int and expected_cap_mib in CAPS_MIB,\n                'Exact manifest-bound 5/10GiB parent required')\n        cap = expected_cap_mib * 1048576", "IPC expected-cap constructor")
    endpoint = replace_once(endpoint,
        "require(total.value == CAP and 0 <= free.value < CAP, 'Exact finite5GiB capped CUDA client required')",
        "require(total.value == cap and 0 <= free.value < cap, 'Exact manifest-bound finite 5/10GiB CUDA cap required')",
        "IPC finite cap assertion")
    endpoint = replace_once(endpoint,
        "p.add_argument('--gpu-uuid'); p.add_argument('--trial-id'); p.add_argument('--handle-b64')",
        "p.add_argument('--gpu-uuid'); p.add_argument('--expected-cap-mib', type=int, choices=CAPS_MIB, required=True); p.add_argument('--trial-id'); p.add_argument('--handle-b64')",
        "IPC expected cap CLI")
    endpoint = replace_once(endpoint, "native = Native()", "native = Native(args.expected_cap_mib)", "IPC expected cap binding")
    files["native-fresh-ipc/ipc_endpoint.py"] = endpoint.encode()

    host = files["native-fresh-ipc/ipc_host_pid.py"].decode()
    host = replace_assignment(host, "GPU", repr(SECOND_GPU))
    host = replace_once(host, "driver/nvidia/gpus/0000:06:10.0/cps_native_caps",
                        "driver/nvidia/gpus/0000:06:11.0/cps_native_caps", "GPU2 native inventory path")
    host = replace_once(host,
        "    actual = rows.get(identity['cgroup_inode'])\n    require(actual is not None and actual['offline'] is False and actual['pinned'] is True\n        and actual['default_hierarchy'] is True and actual['soft'] == actual['hard'] == 5368709120\n        and actual['used'] <= 5368709120, 'Importing parent must still have an active finite5GiB cap')",
        "    cap_mib = identity.get('expected_cap_mib')\n    require(type(cap_mib) is int and cap_mib in (5120, 10240), 'Exact manifest-bound 5/10GiB importer cap required')\n    cap_bytes = cap_mib * 1048576\n    actual = rows.get(identity['cgroup_inode'])\n    require(actual is not None and actual['offline'] is False and actual['pinned'] is True\n        and actual['default_hierarchy'] is True and actual['soft'] == actual['hard'] == cap_bytes\n        and actual['used'] <= cap_bytes, 'Importing parent must retain its exact active finite cap')",
        "GPU2 importer cap binding")
    files["native-fresh-ipc/ipc_host_pid.py"] = host.encode()

    validator = files["native-fresh-ipc/kernel_witness_validator.py"].decode()
    validator = replace_assignment(validator, "GPU", repr(SECOND_GPU))
    files["native-fresh-ipc/kernel_witness_validator.py"] = validator.encode()

    collector = files["native-fresh-ipc/kernel_witness_collector.py"].decode()
    collector = replace_assignment(collector, "ROOT", f"Path({root!r})")
    files["native-fresh-ipc/kernel_witness_collector.py"] = collector.encode()

    transport = files["native-fresh-ipc/kernel_witness_transport.py"].decode()
    transport = replace_assignment(transport, "ROOT", repr(root))
    files["native-fresh-ipc/kernel_witness_transport.py"] = transport.encode()

    runner = files["native-fresh-ipc/run_cross_pod.py"].decode()
    runner = replace_assignment(runner, "ROOT", repr(root))
    runner = replace_assignment(runner, "PREFLIGHT_SHA", repr(preflight_sha))
    runner = replace_once(runner,
        "        base=['--execute','--gpu-uuid',current.GPU,'--trial-id',trial]\n        exporter=engine.Session(exporter_target,[*base,'--role','exporter'],raw['ipc_endpoint.py'],'exporter',a.output)",
        "        base=['--execute','--gpu-uuid',current.GPU,'--trial-id',trial]\n        def endpoint_args(target):\n            return [*base,'--expected-cap-mib',str(target['cap_mib'])]\n        exporter=engine.Session(exporter_target,[*endpoint_args(exporter_target),'--role','exporter'],raw['ipc_endpoint.py'],'exporter',a.output)",
        "GPU2 IPC per-target cap CLI")
    runner = replace_once(runner,
        "positive=engine.Session(exporter_target,[*base,'--role','importer','--wait-for-root','--expect','allow',",
        "positive=engine.Session(exporter_target,[*endpoint_args(exporter_target),'--role','importer','--wait-for-root','--expect','allow',",
        "GPU2 same-parent cap CLI")
    runner = replace_once(runner,
        "denied=engine.Session(importer_target,[*base,'--role','importer','--wait-for-root','--expect','deny',",
        "denied=engine.Session(importer_target,[*endpoint_args(importer_target),'--role','importer','--wait-for-root','--expect','deny',",
        "GPU2 cross-parent cap CLI")
    runner = replace_once(runner,
        "        identity=next(row['identity'] for row in before['host']['targets'] if row['pod_uid']==importer_target['uid'])\n        request={'trial_id':trial,'namespace_pid':ready['namespace_pid'],'identity':identity}",
        "        identity=dict(next(row['identity'] for row in before['host']['targets'] if row['pod_uid']==importer_target['uid']))\n        identity['expected_cap_mib']=importer_target['cap_mib']\n        request={'trial_id':trial,'namespace_pid':ready['namespace_pid'],'identity':identity}",
        "GPU2 current importer cap attribution")

    pin_values = {Path(name).name: sha(raw) for name, raw in files.items()
                  if name.startswith("native-fresh-ipc/") and Path(name).name in ast.literal_eval(
                      next(node.value for node in ast.parse(runner).body if isinstance(node, ast.Assign)
                           and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                           and node.targets[0].id == "PINS"))}
    required = set(ast.literal_eval(next(node.value for node in ast.parse(runner).body if isinstance(node, ast.Assign)
                                      and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                                      and node.targets[0].id == "PINS")))
    require(set(pin_values) == required, "Complete closed IPC component source set required")
    runner = replace_assignment(runner, "PINS", repr(pin_values))
    files["native-fresh-ipc/run_cross_pod.py"] = runner.encode()
    return files


def build_bundle(observations, request, manifest_raw, manifest_sha256, input_sha256=None):
    require(type(manifest_raw) is bytes and 0 < len(manifest_raw) <= 65536
            and sha(manifest_raw) == manifest_sha256,
            "Exact bounded raw fresh manifest SHA required")
    preparer = load_preparer()
    generated = preparer.build_sources(observations)
    context = generated["context"]
    require(context["boot"] == BOOT and context["generation"] == GENERATION,
            "Only the pinned current GPU2 boot/driver generation is supported")
    validate_request(request, context)
    preflight_raw = generated["files"]["fresh_preflight.py"]
    preflight_sha = sha(preflight_raw)
    current = load("current_gpu2_manifest_contract", PREPARER_PATH.parent / "fresh_preflight.py", preflight_raw)
    manifest = json.loads(manifest_raw, object_pairs_hook=current.unique)
    targets = current.validate_targets(manifest)
    require(targets["namespace_uid"] == context["namespace_uid"]
            and targets["cohort_uid"] == context["cohort"],
            "Manifest namespace/cohort must match the freshly prepared source anchor")
    root = current_root(targets["namespace_uid"], targets["cohort_uid"])
    adapted = adapt_sources(preflight_sha, root)
    adapted["native-fresh-domain/fresh_preflight.py"] = preflight_raw
    adapted["native-fresh-imports/run_imports.py"] = checked_bytes("native-fresh-imports/run_imports.py")
    for name, raw in adapted.items():
        if name.endswith(".py"):
            compile(raw, name, "exec")
    generated_sha256 = {name: sha(raw) for name, raw in sorted(adapted.items())}
    input_sha256 = input_sha256 or {
        "observations": sha(canonical(observations)),
        "request": sha(canonical(request)),
    }
    require(type(input_sha256) is dict and set(input_sha256) == {"observations", "request"}
            and all(type(value) is str and re.fullmatch("[a-f0-9]{64}", value)
                    for value in input_sha256.values()),
            "Exact pinned observation/request source hashes required")
    closure = {
        "schema": "cps-gpu2-cross-parent-ipc-source-closure/v1",
        "state": "offline-prepared-not-executed",
        "hardware_qualified": False,
        "production_qualified": False,
        "cross_parent_isolation_qualified": False,
        "context": {"namespace_uid": targets["namespace_uid"], "cohort_uid": targets["cohort_uid"],
                    "gpu_uuid": SECOND_GPU, "node": NODE, "node_uid": NODE_UID,
                    "boot_id": BOOT, "driver_generation": GENERATION,
                    "caps_mib": list(CAPS_MIB)},
        "witness_root": root,
        "entrypoint": "native-fresh-ipc/run_cross_pod.py",
        "required_directions": ["a-to-b", "b-to-a"],
        "root_stage": {
            "owner": "root:root",
            "directory_mode": "0700",
            "source_modes": {name: "0400" for name in
                              ("ipc_host_pid.py", "kernel_witness_collector.py", "kernel_witness_validator.py")},
        },
        "manifest_sha256": manifest_sha256,
        "input_sha256": input_sha256,
        "preparer_sha256": PREPARER_SHA256,
        "input_source_sha256": {**SOURCE_PINS, "native-second-card/prepare.py": PREPARER_SHA256},
        "generated_sha256": generated_sha256,
    }
    closure["closure_sha256"] = sha(canonical(closure))
    adapted["bundle-manifest.json"] = canonical(closure) + b"\n"
    return {"files": adapted, **closure}


def read_private(path, pin, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        raw = os.read(fd, limit + 1)
        after = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
                and stat.S_IMODE(before.st_mode) == 0o600 and 0 < len(raw) <= limit
                and all(getattr(before, key) == getattr(after, key) for key in
                        ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")),
                "Stable private current qualification input required")
        require(sha(raw) == pin, "Input SHA mismatch: " + Path(path).name)
        return raw
    finally:
        os.close(fd)


def write_bundle(output, files):
    output.mkdir(mode=0o700)
    for name, raw in files.items():
        path = output / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--observations-sha256")
    parser.add_argument("--request", type=Path)
    parser.add_argument("--request-sha256")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.prepare:
        print(json.dumps({"state": "inert", "api_calls": False, "gpu_calls": False}))
        return
    require(all((args.observations, args.observations_sha256, args.request, args.request_sha256,
                 args.manifest, args.manifest_sha256, args.output)),
            "Pinned observations/request/finalized manifest and fresh output required")
    observed = read_private(args.observations, args.observations_sha256, 1048576)
    request_raw = read_private(args.request, args.request_sha256, 65536)
    manifest_raw = read_private(args.manifest, args.manifest_sha256, 65536)
    result = build_bundle(parse_json(observed), parse_json(request_raw), manifest_raw,
                          args.manifest_sha256,
                          {"observations": sha(observed), "request": sha(request_raw)})
    write_bundle(args.output, result.pop("files"))
    print(json.dumps({"state": result["state"], "api_calls": False, "gpu_calls": False,
                      "hardware_qualified": False, "production_qualified": False,
                      "closure_sha256": result["closure_sha256"], "generated_source_count": len(result["generated_sha256"])}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate pinned current observations, then delegate offline bundle preparation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUILDER = ROOT / "platform-staging/gpu/qualification/native-second-card/prepare.py"
BUILDER_SHA256 = "971aff6b1eb1c266f7f96ebde34eae09d522740bcb13ab3e848921ec4169fa6d"
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
REQUIRED_FAMILIES = {
    "cap-assignment", "oom-peer", "aggregate", "memory-import",
    "restart-cleanup", "mps", "capacity",
}
REQUIRED_ARTIFACTS = {
    "controller.py", "observe.py", "run_peer_oom.py", "run_aggregate.py",
    "imports/run_imports.py", "restart/run_peer_oom.py", "mps/run_mps.py",
    "gate-source.configmap.json", "a.proposed.json", "b.proposed.json",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify_builder():
    raw = BUILDER.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == BUILDER_SHA256,
            "Pinned source generator changed; review and update this wrapper deliberately")
    return raw


def read_pinned_json(path, expected_sha256, limit):
    require(type(expected_sha256) is str and SHA256.fullmatch(expected_sha256),
            "Lowercase raw-input SHA256 required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
                "Bounded single-link regular input file required")
        raw = os.read(fd, limit + 1)
        after = os.fstat(fd)
        require(len(raw) == before.st_size and len(raw) <= limit and all(
            getattr(before, key) == getattr(after, key)
            for key in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")),
            "Stable input file required")
    finally:
        os.close(fd)
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, "Raw input SHA256 mismatch")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key in input")
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda _v: (_ for _ in ()).throw(ValueError("Invalid JSON number")))
    require(type(value) is dict, "Top-level JSON object required")
    return raw, value


def validate_prepared(output):
    receipt_path = output / "preparation.json"
    receipt = json.loads(receipt_path.read_bytes())
    require(receipt.get("state") == "offline-prepared-not-executed"
            and receipt.get("launch_authorized") is False,
            "Delegated preparer did not leave the bundle offline and unlaunched")
    families = receipt.get("families")
    require(type(families) is dict and set(families) == REQUIRED_FAMILIES,
            "Delegated preparer did not emit the expected qualification families")
    require(all(row.get("state") == "unrun" and row.get("receipts") == []
                for row in families.values()), "A family has unexpected execution evidence")
    require(all((output / name).is_file() for name in REQUIRED_ARTIFACTS),
            "Delegated preparer omitted a required source, controller, or proposed Pod")
    for name, digest in receipt["generated_sha256"].items():
        path = output / name
        require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                "Generated artifact hash mismatch: " + name)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", help="explicitly prepare a new offline source bundle")
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--observations-sha256")
    parser.add_argument("--inputs", type=Path, help="exact renderer request JSON")
    parser.add_argument("--inputs-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--approve-qa-hostpaths", action="store_true",
                        help="acknowledge the source bundle contains narrowly scoped QA hostPath proposals")
    args = parser.parse_args(argv)
    if not args.prepare:
        print(json.dumps({"inert": True, "api_calls": False, "gpu_calls": False,
                          "hardware_qualified": False, "production_qualified": False}, separators=(",", ":")))
        return
    require(all((args.observations, args.observations_sha256, args.inputs,
                 args.inputs_sha256, args.output, args.approve_qa_hostpaths)),
            "--prepare requires pinned observations/request, new output, and explicit QA hostPath acknowledgement")
    verify_builder()
    observations_raw, observations = read_pinned_json(args.observations, args.observations_sha256, 1024 * 1024)
    inputs_raw, request = read_pinned_json(args.inputs, args.inputs_sha256, 65536)
    require(request.get("pair") == "5-10" and request.get("cohort_uid") == observations.get("cohort_uid")
            and request.get("policy_hash") == observations.get("policy_hash"),
            "Request must bind the observed fresh cohort, policy, and 5/10 pair")
    require(not args.output.exists(), "Output must be a new directory")

    # Give the pinned producer private immutable copies so an input pathname swap
    # between validation and delegation cannot change the bytes it consumes.
    with tempfile.TemporaryDirectory(prefix="current-group-probes-inputs-") as temp:
        tempdir = Path(temp)
        obs_copy, request_copy = tempdir / "observations.json", tempdir / "request.json"
        for path, raw in ((obs_copy, observations_raw), (request_copy, inputs_raw)):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
        command = [sys.executable, "-I", "-B", str(BUILDER), "--prepare",
                   "--observations", str(obs_copy), "--observations-sha256", args.observations_sha256,
                   "--inputs", str(request_copy), "--inputs-sha256", args.inputs_sha256,
                   "--output", str(args.output), "--approve-qa-hostpaths"]
        completed = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    validate_prepared(args.output)
    print(json.dumps({"prepared": True, "delegated_to": "native-second-card/prepare.py",
                      "api_calls": False, "gpu_calls": False, "launch_authorized": False}, separators=(",", ":")))


if __name__ == "__main__":
    main()

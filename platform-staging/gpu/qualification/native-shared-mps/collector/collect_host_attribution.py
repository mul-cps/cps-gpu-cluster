#!/usr/bin/env python3
"""Capture read-only host evidence for CUDA MPS client attribution.

Run on the GPU node as a principal allowed to read /proc and query the MPS
control pipe. This does not start/stop MPS or change any daemon settings.
It intentionally captures observations only; a separate verifier must bind
them to reviewed Pod/container IDs and workload receipts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def parse_pids(text: str) -> list[int]:
    fields = text.split()
    if any(not field.isdecimal() or int(field) <= 0 for field in fields):
        raise ValueError("MPS returned a malformed PID list")
    pids = [int(field) for field in fields]
    if len(pids) != len(set(pids)):
        raise ValueError("MPS returned duplicate PIDs")
    return pids


def parse_compute_apps(text: str) -> dict[int, list[str]]:
    apps: dict[int, set[str]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = [field.strip() for field in line.split(",")]
        if (len(fields) != 2 or not fields[0].isdecimal() or
                not re.fullmatch(r"GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", fields[1])):
            raise ValueError("nvidia-smi returned a malformed compute-app row")
        apps.setdefault(int(fields[0]), set()).add(fields[1])
    return {pid: sorted(uuids) for pid, uuids in apps.items()}


def validate_compute_app_coverage(server_pids: list[int], apps: dict[int, list[str]]) -> None:
    # MPS clients are not consistently exposed as independent nvidia-smi
    # compute-app rows; their device attribution comes from the MPS server and
    # workload-side evidence. Require server visibility, but retain missing
    # client rows as an observation rather than failing the capture.
    missing_servers = set(server_pids) - set(apps)
    if missing_servers:
        raise ValueError(f"MPS server PIDs absent from nvidia-smi compute-apps: {sorted(missing_servers)}")


def proc_start_ticks(stat_text: str, pid: int) -> int:
    # comm (field 2) can contain spaces and parentheses; the last ') ' ends it.
    if not stat_text.startswith(f"{pid} (") or ") " not in stat_text:
        raise ValueError("/proc stat PID or command field is malformed")
    fields = stat_text.rsplit(") ", 1)[1].split()
    # The remainder starts at field 3; starttime is field 22 => index 19.
    if len(fields) < 20 or not fields[19].isdecimal():
        raise ValueError("/proc stat lacks a valid process start time")
    return int(fields[19])


def parse_status(text: str) -> dict[str, list[int]]:
    wanted = {"Uid", "Gid", "NSpid"}
    values: dict[str, list[int]] = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key in wanted:
            parts = value.split()
            if not parts or any(not part.isdecimal() for part in parts):
                raise ValueError(f"/proc status has malformed {key}")
            values[key] = [int(part) for part in parts]
    if values.keys() != wanted:
        raise ValueError("/proc status is missing UID, GID, or namespace PID data")
    return values


def safe_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value):
        raise ValueError("run ID must contain 1-64 safe filename characters")
    return value


def collect(run_id: str, pipe_dir: str, proc_root: Path = Path("/proc")) -> dict:
    run_id = safe_name(run_id)
    if not pipe_dir.startswith("/") or "\n" in pipe_dir:
        raise ValueError("MPS pipe directory must be an absolute path")

    def mps(command: str) -> str:
        env = dict(os.environ, CUDA_MPS_PIPE_DIRECTORY=pipe_dir)
        result = subprocess.run(["nvidia-cuda-mps-control"], input=f"{command}\n",
                                text=True, capture_output=True, check=True,
                                timeout=10, env=env)
        return result.stdout.strip()

    observed_start = dt.datetime.now(dt.timezone.utc).isoformat()
    servers = parse_pids(mps("get_server_list"))
    server_rows = []
    client_pids: list[int] = []
    for server_pid in servers:
        status = mps(f"get_server_status {server_pid}")
        clients = parse_pids(mps(f"get_client_list {server_pid}"))
        client_pids.extend(clients)
        server_rows.append({"pid": server_pid, "status": status, "clients": clients})
    if len(client_pids) != len(set(client_pids)):
        raise ValueError("MPS listed one client under multiple servers")

    # The fixed executable and command arguments avoid shell interpretation.
    env = dict(os.environ, CUDA_MPS_PIPE_DIRECTORY=pipe_dir)
    app_text = subprocess.run(
        ["nvidia-smi", "--query-compute-apps=pid,gpu_uuid", "--format=csv,noheader,nounits"],
        text=True, capture_output=True, check=True, timeout=10, env=env).stdout
    apps = parse_compute_apps(app_text)
    validate_compute_app_coverage(servers, apps)
    records = []
    for pid in sorted(set(servers + client_pids)):
        base = proc_root / str(pid)
        before = proc_start_ticks((base / "stat").read_text(), pid)
        status = parse_status((base / "status").read_text())
        cgroup = (base / "cgroup").read_text()
        after = proc_start_ticks((base / "stat").read_text(), pid)
        if before != after:
            raise RuntimeError(f"PID {pid} changed during collection")
        records.append({"pid": pid, "startTimeTicks": before,
                        "uid": status["Uid"], "gid": status["Gid"],
                        "namespacePids": status["NSpid"], "cgroup": cgroup,
                        "gpuUuids": apps.get(pid, [])})
    observed_finish = dt.datetime.now(dt.timezone.utc).isoformat()
    return {"schema": "native-shared-mps-host-attribution/v1", "runId": run_id,
            "observedAtStart": observed_start, "observedAtFinish": observed_finish,
            "mpsPipeDirectory": pipe_dir, "servers": server_rows,
            "computeApps": [{"pid": pid, "gpuUuids": uuids}
                            for pid, uuids in sorted(apps.items())],
            "processes": records,
            "attributionQualified": False,
            "qualificationNote": "Capture only; bind to reviewed Pod/container and workload receipts offline."}


def write_private(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mps-pipe-dir", required=True)
    parser.add_argument("--output", required=True, type=Path,
                        help="new file path on private evidence storage (mode 0600)")
    args = parser.parse_args(argv)
    try:
        value = collect(args.run_id, args.mps_pipe_dir)
        write_private(args.output, value)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"host attribution capture failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"captured": True, "processes": len(value["processes"]),
                      "servers": len(value["servers"]),
                      "attributionQualified": False, "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

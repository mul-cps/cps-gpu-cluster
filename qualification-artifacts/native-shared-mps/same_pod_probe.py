#!/usr/bin/env python3
"""Run two independent CUDA clients in one Pod for an aggregate MPS cap test.

This is a bounded probe, not a deployment tool. It never changes MPS settings
or Kubernetes resources. Run only as a reviewed one-Pod GPU workload.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import multiprocessing as mp
import os
from pathlib import Path
import queue
import re
import sys
import time
import traceback


def validate_plan(cap_bytes: int, survivor_bytes: int, challenger_bytes: int,
                  recovery_bytes: int) -> dict:
    values = (cap_bytes, survivor_bytes, challenger_bytes, recovery_bytes)
    if any(not isinstance(value, int) or value <= 0 for value in values):
        raise ValueError("all byte limits must be positive integers")
    if survivor_bytes >= cap_bytes or challenger_bytes >= cap_bytes:
        raise ValueError("each client allocation must individually fit below the cap")
    if survivor_bytes + challenger_bytes <= cap_bytes:
        raise ValueError("combined client allocations must exceed the aggregate cap")
    if survivor_bytes + recovery_bytes >= cap_bytes:
        raise ValueError("survivor plus recovery allocation must fit below the cap")
    return {"capBytes": cap_bytes, "survivorBytes": survivor_bytes,
            "challengerBytes": challenger_bytes, "recoveryBytes": recovery_bytes}


def validate_identity(run_id: str, pod_uid: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", run_id):
        raise ValueError("run ID must contain 1-64 safe characters")
    if not isinstance(pod_uid, str) or not pod_uid.strip() or len(pod_uid) > 256:
        raise ValueError("a valid Pod UID is required")


def build_workload_receipt(run_id: str, pod_uid: str, plan: dict,
                           survivor: dict, challenger: dict, *,
                           hold_started_at: str | None = None,
                           hold_finished_at: str | None = None) -> dict:
    validate_identity(run_id, pod_uid)
    if survivor.get("namespacePid") == challenger.get("namespacePid"):
        raise ValueError("survivor and challenger must be different processes")
    if survivor.get("heldBytes") != plan["survivorBytes"]:
        raise ValueError("survivor allocation does not match the reviewed test plan")
    if challenger.get("overCapRequestedBytes") != plan["challengerBytes"]:
        raise ValueError("challenger allocation does not match the reviewed test plan")
    if challenger.get("recoveryBytes") != plan["recoveryBytes"]:
        raise ValueError("recovery allocation does not match the reviewed test plan")
    if challenger.get("overCapRejected") is not True:
        raise ValueError("challenger allocation was not rejected by CUDA OOM")
    if challenger.get("recoverySucceeded") is not True:
        raise ValueError("challenger recovery allocation did not succeed")
    if not (isinstance(survivor.get("progressBefore"), int) and
            isinstance(survivor.get("progressAfter"), int) and
            survivor["progressAfter"] > survivor["progressBefore"]):
        raise ValueError("survivor did not make CUDA progress during the challenger test")
    hold_started_at = hold_started_at or dt.datetime.now(dt.timezone.utc).isoformat()
    hold_finished_at = hold_finished_at or dt.datetime.now(dt.timezone.utc).isoformat()
    hold_start = dt.datetime.fromisoformat(hold_started_at.replace("Z", "+00:00"))
    hold_finish = dt.datetime.fromisoformat(hold_finished_at.replace("Z", "+00:00"))
    if hold_start.tzinfo is None or hold_finish.tzinfo is None or hold_finish < hold_start:
        raise ValueError("probe hold timestamps must be ordered timezone-aware timestamps")
    return {
        "schema": "native-shared-mps-same-pod-workload/v1",
        "runId": run_id,
        "podUid": pod_uid,
        "probeSucceeded": True,
        "capBytes": plan["capBytes"],
        "survivor": survivor,
        "challenger": challenger,
        "holdStartedAt": hold_started_at,
        "holdFinishedAt": hold_finished_at,
        "observedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def write_private(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def _is_cuda_oom(torch, exc: BaseException) -> bool:
    oom_type = getattr(torch.cuda, "OutOfMemoryError", ())
    return ((oom_type and isinstance(exc, oom_type)) or
            "out of memory" in str(exc).lower())


def _survivor_worker(held_bytes: int, ready_queue, stop_event, progress):
    try:
        import torch
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError("probe requires exactly one visible CUDA device")
        torch.cuda.set_device(0)
        held = torch.empty(held_bytes, dtype=torch.uint8, device="cuda").fill_(1)
        work = torch.empty(1024 * 1024, dtype=torch.uint8, device="cuda")
        torch.cuda.synchronize()
        ready_queue.put({"role": "survivor-ready", "namespacePid": os.getpid(),
                         "heldBytes": held_bytes})
        while not stop_event.is_set():
            work.add_(1)
            torch.cuda.synchronize()
            with progress.get_lock():
                progress.value += 1
            time.sleep(0.02)
        torch.cuda.synchronize()
        # Keep the holding allocation live until after the challenger is done.
        if held.numel() != held_bytes:
            raise RuntimeError("survivor allocation changed unexpectedly")
        ready_queue.put({"role": "survivor-done", "namespacePid": os.getpid(),
                         "heldBytes": held_bytes})
    except BaseException as exc:
        ready_queue.put({"role": "survivor-error", "error": str(exc),
                         "traceback": traceback.format_exc()})


def _challenger_worker(request_bytes: int, recovery_bytes: int, result_queue,
                       release_event):
    try:
        import torch
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError("probe requires exactly one visible CUDA device")
        torch.cuda.set_device(0)
        over_cap_rejected = False
        try:
            rejected = torch.empty(request_bytes, dtype=torch.uint8, device="cuda")
            rejected.fill_(1)
            torch.cuda.synchronize()
            del rejected
        except BaseException as exc:
            if not _is_cuda_oom(torch, exc):
                raise
            over_cap_rejected = True
        if not over_cap_rejected:
            raise RuntimeError("challenger allocation succeeded; aggregate cap was not enforced")
        torch.cuda.empty_cache()
        recovered = torch.empty(recovery_bytes, dtype=torch.uint8, device="cuda").fill_(1)
        torch.cuda.synchronize()
        result_queue.put({"role": "challenger-done", "namespacePid": os.getpid(),
                          "overCapRequestedBytes": request_bytes,
                          "overCapRejected": True,
                          "recoveryBytes": recovery_bytes,
                          "recoverySucceeded": recovered.numel() == recovery_bytes})
        # Keep the recovery allocation alive while the survivor continues work.
        release_event.wait()
        del recovered
    except BaseException as exc:
        result_queue.put({"role": "challenger-error", "error": str(exc),
                          "traceback": traceback.format_exc()})


def _wait_for_role(messages, processes, role: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            message = messages.get(timeout=min(0.25, max(0.01, deadline - time.monotonic())))
        except queue.Empty:
            dead = [process.name for process in processes if process.exitcode not in (None, 0)]
            if dead:
                raise RuntimeError(f"probe child exited early: {dead}")
            continue
        if message["role"].endswith("-error"):
            raise RuntimeError(f"{message['role']}: {message['error']}\n{message['traceback']}")
        if message["role"] == role:
            return message
        raise RuntimeError(f"unexpected probe child message: {message['role']}")
    raise TimeoutError(f"timed out waiting for {role}")


def run_probe(run_id: str, pod_uid: str, plan: dict, *, timeout: float,
              peer_hold_seconds: float) -> dict:
    validate_identity(run_id, pod_uid)
    pipe_dir = os.environ.get("CUDA_MPS_PIPE_DIRECTORY", "")
    if not pipe_dir or not Path(pipe_dir).is_dir():
        raise RuntimeError("CUDA_MPS_PIPE_DIRECTORY must name the mounted MPS pipe directory")
    # Avoid initializing CUDA in this parent. Only the two child processes may
    # become MPS clients, so the capture is exactly two test clients.
    context = mp.get_context("spawn")
    messages = context.Queue()
    stop_survivor = context.Event()
    release_challenger = context.Event()
    progress = context.Value("Q", 0)
    survivor_process = context.Process(
        name="same-pod-mps-survivor", target=_survivor_worker,
        args=(plan["survivorBytes"], messages, stop_survivor, progress))
    challenger_process = context.Process(
        name="same-pod-mps-challenger", target=_challenger_worker,
        args=(plan["challengerBytes"], plan["recoveryBytes"], messages, release_challenger))
    processes = [survivor_process, challenger_process]
    try:
        survivor_process.start()
        ready = _wait_for_role(messages, processes, "survivor-ready", timeout)
        with progress.get_lock():
            progress_before = int(progress.value)
        challenger_process.start()
        challenge = _wait_for_role(messages, processes, "challenger-done", timeout)
        hold_started_at = dt.datetime.now(dt.timezone.utc).isoformat()
        print(f"MPS aggregate recovery hold active for {peer_hold_seconds:g}s; collect host attribution now",
              file=sys.stderr, flush=True)
        time.sleep(peer_hold_seconds)
        hold_finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
        release_challenger.set()
        challenger_process.join(timeout)
        if challenger_process.is_alive() or challenger_process.exitcode != 0:
            raise RuntimeError("challenger process failed to exit cleanly")
        stop_survivor.set()
        survivor_done = _wait_for_role(messages, processes, "survivor-done", timeout)
        survivor_process.join(timeout)
        if survivor_process.is_alive() or survivor_process.exitcode != 0:
            raise RuntimeError("survivor process failed to exit cleanly")
        with progress.get_lock():
            progress_after = int(progress.value)
        survivor = {"namespacePid": ready["namespacePid"],
                    "heldBytes": ready["heldBytes"],
                    "progressBefore": progress_before,
                    "progressAfter": progress_after}
        if survivor_done["namespacePid"] != survivor["namespacePid"]:
            raise RuntimeError("survivor PID changed during the probe")
        challenger = {key: challenge[key] for key in
                      ("namespacePid", "overCapRequestedBytes", "overCapRejected",
                       "recoveryBytes", "recoverySucceeded")}
        return build_workload_receipt(run_id, pod_uid, plan, survivor, challenger,
                                      hold_started_at=hold_started_at,
                                      hold_finished_at=hold_finished_at)
    finally:
        stop_survivor.set()
        release_challenger.set()
        for process in processes:
            if process.pid is not None and process.is_alive():
                process.terminate()
                process.join(timeout=5)
        messages.close()
        messages.join_thread()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--pod-uid", required=True)
    parser.add_argument("--cap-bytes", required=True, type=int)
    parser.add_argument("--survivor-bytes", required=True, type=int)
    parser.add_argument("--challenger-bytes", required=True, type=int)
    parser.add_argument("--recovery-bytes", required=True, type=int)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--peer-hold-seconds", type=float, default=30,
                        help="keep both CUDA clients alive after recovery so host capture can run")
    parser.add_argument("--output", required=True, type=Path,
                        help="new private evidence file; never overwritten")
    args = parser.parse_args(argv)
    try:
        plan = validate_plan(args.cap_bytes, args.survivor_bytes,
                             args.challenger_bytes, args.recovery_bytes)
        validate_identity(args.run_id, args.pod_uid)
        if not 0 < args.timeout_seconds <= 600 or not 0 <= args.peer_hold_seconds <= 120:
            raise ValueError("timeout must be 1-600 seconds and peer hold 0-120 seconds")
        receipt = run_probe(args.run_id, args.pod_uid, plan,
                            timeout=args.timeout_seconds,
                            peer_hold_seconds=args.peer_hold_seconds)
        write_private(args.output, receipt)
    except (OSError, ValueError, RuntimeError, TimeoutError, TypeError) as exc:
        print(f"same-Pod MPS probe failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"probeSucceeded": True, "runId": args.run_id,
                      "podUid": args.pod_uid, "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

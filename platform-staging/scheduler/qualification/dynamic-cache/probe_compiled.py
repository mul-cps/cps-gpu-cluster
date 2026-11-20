#!/usr/bin/env python3
"""Controlled CUDA probe; no host cache or GPU configuration mutations.

Only the reviewed suspended fixture runs this module with GPUs. Offline imports
and tests never load libcuda. The final production/isolation gate stays false.
"""
import ctypes
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
import tempfile
import time

CACHE_KEY = "CUDA_DEVICE_MEMORY_SHARED_CACHE"
CACHE_PATH = "/tmp/cps-workspace-usage.cache"
REQUESTED_MIB = 5120
SCHEDULER_INJECTED_MIB = 5324
CANONICAL_LIMIT_MIB = 5120
ALLOCATION_MIB = 3072
ROUNDS = 16
MAX_SKEW_NS = 25_000_000
HAMI_REVISION = "5496322f2fb3e71bf1eca014fba3c9bc59ab8ffd"
HAMI_PATH = "/usr/local/vgpu/libvgpu.so"
COMPILER_SOURCE = "2f43f59aa319f8a114bae41ff89226018e3e5089"
COMPILER_MODULE_SHA256 = "93f4e01c3682e52192d43c130073b3daf50c59ea7bd06342971f5f4add0a2b68"
REVIEWED_IDENTITIES = {(10001, 10001), (1000, 1000), (1000, 100)}
HOLD_SECONDS = 20
HOLD_TICKS = 40


def emit(value):
    print(json.dumps({"observedNs": time.time_ns(),
                      "podUid": os.environ.get("FIXTURE_POD_UID"),
                      "runId": os.environ.get("FIXTURE_RUN_ID"), **value}), flush=True)


def normalized_uuid(value):
    if not isinstance(value, str):
        raise ValueError("GPU UUID must be a string")
    digits = value.removeprefix("GPU-").replace("-", "").lower()
    if len(digits) != 32 or any(c not in "0123456789abcdef" for c in digits):
        raise ValueError("Expected a physical GPU UUID, not a MIG device")
    return digits


def runtime_identity():
    pair = (int(os.environ["FIXTURE_UID"]), int(os.environ["FIXTURE_GID"]))
    if pair not in REVIEWED_IDENTITIES or pair != (os.getuid(), os.getgid()):
        raise RuntimeError("Actual identity differs from the explicitly reviewed UID/GID pair")
    return pair


def compiler_provenance():
    distribution = importlib.metadata.distribution("cps-compute")
    path = distribution.locate_file("cps_compute/gpu_runtime.py")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if distribution.version != "0.1.0" or digest != COMPILER_MODULE_SHA256:
        raise RuntimeError("Installed runtime compiler does not match the verified package")
    return {"sourceCommit": COMPILER_SOURCE, "moduleSha256": digest, "version": distribution.version}


def cache_identity(path=CACHE_PATH, *, require_mapping=False):
    if os.environ.get(CACHE_KEY) != path:
        raise RuntimeError("Explicit workspace cache path is required")
    info = os.stat(path, follow_symlinks=False)
    uid, gid = runtime_identity()
    if (not stat.S_ISREG(info.st_mode) or (info.st_uid, info.st_gid) != (uid, gid)
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
        raise RuntimeError("Workspace cache must be a private regular file owned by the reviewed identity")
    maps = Path("/proc/self/maps").read_text().splitlines()
    mapped = []
    alternate = []
    for line in maps:
        fields = line.split(maxsplit=5)
        if len(fields) != 6:
            continue
        filename = fields[5]
        if filename == path:
            major, minor = (int(x, 16) for x in fields[3].split(":"))
            mapped.append((os.makedev(major, minor), int(fields[4])))
        elif filename.endswith("/usage.cache") or "cudevshr.cache" in filename:
            alternate.append(filename)
    identity = (info.st_dev, info.st_ino)
    verified = bool(mapped) and all(item == identity for item in mapped)
    if require_mapping and (not verified or alternate):
        raise RuntimeError("HAMi cache mapping does not match the fixed file inode")
    return {"device": info.st_dev, "inode": info.st_ino, "uid": info.st_uid, "gid": info.st_gid,
            "path": path, "mappingVerified": verified,
            "noTmpFallback": verified and not alternate}


def hami_provenance():
    """Require the observed preloaded bytes; their source revision is unverified."""
    if os.environ.get("EXPECTED_HAMI_REVISION") != HAMI_REVISION:
        raise RuntimeError("Pinned HAMi reference source revision is required")
    expected = os.environ.get("EXPECTED_HAMI_SHA256", "")
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise RuntimeError("Observed HAMi binary SHA256 is required")
    if (os.environ.get("CUDA_DEVICE_MEMORY_LIMIT") != "5324m" or
            os.environ.get("GPU_PORTION") != "0.13" or
            os.environ.get("CUDA_DEVICE_MEMORY_LIMIT_0") != "5120m" or
            os.environ.get("EXPECTED_HAMI_LIMIT_MIB") != "5120"):
        raise RuntimeError("Reviewed global 5324m/portion 0.13 and canonical per-device 5120m limit required")
    path = Path(HAMI_PATH)
    before = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) or digest != expected:
        raise RuntimeError("HAMi binary does not match the observed byte identity")
    maps = Path("/proc/self/maps").read_text().splitlines()
    mapped = []
    for line in maps:
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5] == HAMI_PATH:
            major, minor = (int(x, 16) for x in fields[3].split(":"))
            mapped.append((os.makedev(major, minor), int(fields[4])))
    if not mapped or any(item != (after.st_dev, after.st_ino) for item in mapped):
        raise RuntimeError("Expected HAMi binary is not loaded from the reviewed inode")
    configured = os.environ.get("LD_PRELOAD", "").replace(":", " ").split()
    preload = Path("/etc/ld.so.preload")
    if preload.exists():
        text = preload.read_text()
        if len(text) > 4096:
            raise RuntimeError("Unexpectedly large preload configuration")
        configured.extend(word for line in text.splitlines()
                          for word in line.split("#", 1)[0].split())
    if HAMI_PATH not in configured:
        raise RuntimeError("The reviewed HAMi library was not configured as preload")
    # RTLD_NOLOAD prevents this check from loading an absent hook itself.
    core = ctypes.CDLL(HAMI_PATH, mode=os.RTLD_NOLOAD | os.RTLD_NOW)
    core.get_current_device_memory_limit.argtypes = [ctypes.c_int]
    core.get_current_device_memory_limit.restype = ctypes.c_uint64
    limit = core.get_current_device_memory_limit(0)
    if limit != CANONICAL_LIMIT_MIB * 1024**2:
        raise RuntimeError(f"Effective HAMi quota is {limit} bytes, expected 5120 MiB")
    return core, {"referenceSourceRevision": HAMI_REVISION, "sourceRevisionVerified": False, "libraryPath": HAMI_PATH,
                  "sha256": digest, "loaded": True, "preloadVerified": True,
                  "schedulerInjectedLimitBytes": SCHEDULER_INJECTED_MIB * 1024**2,
                  "canonicalLimitBytes": CANONICAL_LIMIT_MIB * 1024**2,
                  "perDeviceLimitVerified": True,
                  "effectiveLimitBytes": limit, "device": after.st_dev, "inode": after.st_ino}


class Cuda:
    """Use the same CUDA driver API allocation core as the existing probe."""

    def __init__(self):
        self.lib = ctypes.CDLL("libcuda.so.1")
        signatures = {
            "cuInit": [ctypes.c_uint],
            "cuDeviceGetCount": [ctypes.POINTER(ctypes.c_int)],
            "cuDeviceGet": [ctypes.POINTER(ctypes.c_int), ctypes.c_int],
            "cuCtxCreate_v2": [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint, ctypes.c_int],
            "cuDeviceGetUuid": [ctypes.c_void_p, ctypes.c_int],
            "cuMemAlloc_v2": [ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t],
            "cuMemFree_v2": [ctypes.c_uint64],
            "cuMemGetInfo_v2": [ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)],
            "cuMemsetD8_v2": [ctypes.c_uint64, ctypes.c_ubyte, ctypes.c_size_t],
            "cuCtxSynchronize": [],
            "cuCtxDestroy_v2": [ctypes.c_void_p],
        }
        for name, args in signatures.items():
            getattr(self.lib, name).argtypes = args
            getattr(self.lib, name).restype = ctypes.c_int
        self.check(self.lib.cuInit(0), "cuInit")
        count = ctypes.c_int()
        self.check(self.lib.cuDeviceGetCount(ctypes.byref(count)), "cuDeviceGetCount")
        if count.value != 1:
            raise RuntimeError("Per-device suffix candidate requires exactly one visible CUDA device")
        device = ctypes.c_int()
        self.check(self.lib.cuDeviceGet(ctypes.byref(device), 0), "cuDeviceGet")
        self.context = ctypes.c_void_p()
        self.check(self.lib.cuCtxCreate_v2(ctypes.byref(self.context), 0, device), "cuCtxCreate")
        uid = (ctypes.c_byte * 16)()
        self.check(self.lib.cuDeviceGetUuid(ctypes.byref(uid), device), "cuDeviceGetUuid")
        self.gpu = bytes(uid).hex()
        if self.gpu != normalized_uuid(os.environ["EXPECTED_GPU_UUID"]):
            self.close()
            raise RuntimeError("Scheduler assigned a different physical GPU")
        self.allocations = {}
        self.core, self.hami = hami_provenance()
        self.hami["singleVisibleDeviceVerified"] = True

    @staticmethod
    def check(result, operation):
        if result != 0:
            raise RuntimeError(f"{operation} CUDA error {result}")

    def allocate(self, label, mib):
        if self.core.get_current_device_memory_limit(0) != CANONICAL_LIMIT_MIB * 1024**2:
            raise RuntimeError("Effective workspace quota changed")
        if label in self.allocations:
            raise ValueError("Allocation label already held")
        ptr = ctypes.c_uint64()
        start = time.monotonic_ns()
        result = self.lib.cuMemAlloc_v2(ctypes.byref(ptr), mib * 1024**2)
        end = time.monotonic_ns()
        if result == 0:
            self.allocations[label] = ptr
            self.tick(label)
        free, total = ctypes.c_size_t(), ctypes.c_size_t()
        self.check(self.lib.cuMemGetInfo_v2(ctypes.byref(free), ctypes.byref(total)), "cuMemGetInfo")
        return {"label": label, "allocationMiB": mib, "cudaResult": result,
                "startMonotonicNs": start, "endMonotonicNs": end,
                "freeBytesAfter": free.value, "totalBytes": total.value}

    def tick(self, label):
        ptr = self.allocations[label]
        self.check(self.lib.cuMemsetD8_v2(ptr, 17, 1024**2), "cuMemsetD8")
        self.check(self.lib.cuCtxSynchronize(), "cuCtxSynchronize")
        return {"label": label, "cudaResult": 0}

    def free(self, label):
        ptr = self.allocations.pop(label)
        self.check(self.lib.cuMemFree_v2(ptr), "cuMemFree")
        return {"label": label, "cudaResult": 0}

    def close(self):
        for label in list(getattr(self, "allocations", {})):
            self.free(label)
        if getattr(self, "context", None):
            self.check(self.lib.cuCtxDestroy_v2(self.context), "cuCtxDestroy")
            self.context = None


def child():
    before = cache_identity()
    cuda = Cuda()
    try:
        cache = cache_identity(require_mapping=True)
        if (before["device"], before["inode"]) != (cache["device"], cache["inode"]):
            raise RuntimeError("Cache inode changed during initialization")
        emit({"event": "ready", "gpu": cuda.gpu, "pid": os.getpid(), "cache": cache, "hami": cuda.hami})
        for line in sys.stdin:
            request = json.loads(line)
            action = request["action"]
            if action == "stop":
                break
            if action == "allocate":
                target = request.get("atMonotonicNs")
                if target is not None:
                    delay = (target - time.monotonic_ns()) / 1e9
                    if delay > 0:
                        time.sleep(delay)
                value = cuda.allocate(request["label"], request["mib"])
            elif action == "tick":
                value = cuda.tick(request["label"])
            elif action == "free":
                value = cuda.free(request["label"])
            else:
                raise ValueError("Unknown controlled probe operation")
            current = cache_identity(require_mapping=True)
            if (current["device"], current["inode"]) != (cache["device"], cache["inode"]):
                raise RuntimeError("Cache inode changed")
            emit({"event": "response", "id": request["id"], "action": action,
                  "pid": os.getpid(), "gpu": cuda.gpu, "cache": current, "hami": cuda.hami, **value})
    finally:
        cuda.close()


class Child:
    def __init__(self, name):
        self.name = name
        self.stderr = tempfile.TemporaryFile(mode="w+")
        # Ordinary children inherit the exact same environment, without changes.
        self.process = subprocess.Popen([sys.executable, "-u", __file__, "child"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            text=True, bufsize=1)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        try:
            self.ready = self.receive()
            if self.ready.get("event") != "ready":
                raise RuntimeError(f"Child did not initialize: {self.ready.get('error', 'unknown')}")
        except Exception:
            self.close()
            raise

    def receive(self, timeout=20):
        if not self.selector.select(timeout):
            raise TimeoutError("Controlled CUDA child timed out")
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f"Controlled CUDA child exited {self.process.poll()}")
        value = json.loads(line)
        emit({"event": "child-evidence", "child": self.name, "value": value})
        return value

    def send(self, request):
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

    def request(self, ident, action, label="ordinary", **extra):
        self.send({"id": ident, "action": action, "label": label, **extra})
        result = self.receive()
        if result.get("event") != "response" or result.get("id") != ident:
            raise RuntimeError("CUDA response mismatch")
        return result

    def close(self):
        if self.process.poll() is None:
            try:
                self.send({"action": "stop"})
                self.process.wait(timeout=5)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        self.selector.close()
        self.process.stdin.close()
        self.process.stdout.close()
        self.stderr.close()


def ordinary_verdict(results):
    """Only actual CUDA OOM (2), preserved writes, and recovery count as pass."""
    return (all(results[key]["allocationMiB"] == ALLOCATION_MIB
                for key in ("aHold", "bDenied", "bAfterFree"))
            and results["aHold"]["cudaResult"] == 0
            and results["bDenied"]["cudaResult"] == 2
            and results["aContinued"]["cudaResult"] == 0
            and results["aFree"]["cudaResult"] == 0
            and results["bAfterFree"]["cudaResult"] == 0
            and results["bContinued"]["cudaResult"] == 0)


def concurrent_verdict(results):
    if len(results) != 2 or any(value["allocationMiB"] != ALLOCATION_MIB for value in results):
        return "inconclusive-allocation-sizes"
    try:
        starts = [value["startMonotonicNs"] for value in results]
        ends = [value["endMonotonicNs"] for value in results]
        if any(type(n) is not int or n < 0 for n in [*starts, *ends]) or any(
                end < start for start, end in zip(starts, ends)):
            return "inconclusive-invalid-intervals"
    except (KeyError, TypeError):
        return "inconclusive-invalid-intervals"
    codes = sorted(value["cudaResult"] for value in results)
    if codes == [0, 0]:
        return "aggregate-limit-exceeded"
    if codes != [0, 2]:
        return "inconclusive-cuda-results"
    skew = abs(starts[0] - starts[1])
    if skew > MAX_SKEW_NS:
        return "inconclusive-launch-skew"
    if max(starts) >= min(ends):
        return "inconclusive-nonoverlapping-intervals"
    return "bounded-round-passed"


def hold_contexts(workers):
    """Keep both real CUDA clients active for an operator-owned MPS snapshot.

    This phase proves child writes and stable runtime identities only. An actual
    MPS daemon/client-list receipt is separately required for a three-client claim.
    """
    allocations = [w.request(f"hold-{w.name}-allocate", "allocate", "mps-hold", mib=64)
                   for w in workers]
    if any(v["cudaResult"] != 0 for v in allocations):
        raise RuntimeError("Both controlled MPS-hold allocations must succeed")
    started = time.time_ns()
    emit({"event": "mps-hold-start", "startedNs": started, "durationSeconds": HOLD_SECONDS,
          "childPids": [w.ready["pid"] for w in workers], "mpsThreeClientQualified": False})
    receipts = []
    for tick in range(HOLD_TICKS):
        values = [w.request(f"hold-{tick}-{w.name}", "tick", "mps-hold") for w in workers]
        if any(v["cudaResult"] != 0 for v in values):
            raise RuntimeError("MPS-hold CUDA client stopped progressing")
        observed = time.time_ns()
        receipts.append({"tick": tick, "observedNs": observed, "values": values})
        emit({"event": "mps-hold-progress", **receipts[-1], "mpsThreeClientQualified": False})
        time.sleep(HOLD_SECONDS / HOLD_TICKS)
    finished = time.time_ns()
    frees = [w.request(f"hold-{w.name}-free", "free", "mps-hold") for w in workers]
    if any(v["cudaResult"] != 0 for v in frees):
        raise RuntimeError("MPS-hold allocation cleanup failed")
    result = {"startedNs": started, "finishedNs": finished, "durationSeconds": HOLD_SECONDS,
              "childPids": [w.ready["pid"] for w in workers], "ticks": receipts,
              "allocations": allocations, "frees": frees, "mpsThreeClientQualified": False}
    emit({"event": "mps-hold-finished", "startedNs": started, "finishedNs": finished,
          "childPids": result["childPids"], "mpsThreeClientQualified": False})
    return result


def workspace():
    workers = []
    started = time.time_ns()
    report = {"event": "workspace-result", "productionQualified": False,
              "hostileIsolationQualified": False, "tamper": {"status": "not-run"},
              "startedNs": started, "requestedMiB": REQUESTED_MIB,
              "schedulerInjectedMiB": SCHEDULER_INJECTED_MIB,
              "canonicalLimitMiB": CANONICAL_LIMIT_MIB,
              "effectiveHamiLimitMiB": None,
              "schedulerQuotaDrift": True, "canonicalQuotaDrift": None,
              "exactProfileQuotaQualified": False, "mpsThreeClientQualified": False,
              "compiler": None, "hold": None,
              "status": "incomplete", "ordinary": {}, "concurrency": []}
    try:
        report["compiler"] = compiler_provenance()
        runtime_identity()
        for name in ("a", "b"):
            workers.append(Child(name))
        a, b = workers
        identities = {(c.ready["cache"]["device"], c.ready["cache"]["inode"]) for c in workers}
        if len(identities) != 1 or len({c.ready["gpu"] for c in workers}) != 1:
            raise RuntimeError("Children do not share one cache inode and physical GPU")
        report["cache"] = a.ready["cache"]
        report["gpu"] = a.ready["gpu"]
        report["hami"] = a.ready["hami"]
        report["effectiveHamiLimitMiB"] = report["hami"]["effectiveLimitBytes"] // 1024**2
        report["canonicalQuotaDrift"] = report["effectiveHamiLimitMiB"] != REQUESTED_MIB
        report["hold"] = hold_contexts(workers)
        r = report["ordinary"]
        r["aHold"] = a.request("a-hold", "allocate", mib=ALLOCATION_MIB)
        if r["aHold"]["cudaResult"] != 0:
            raise RuntimeError("First ordinary allocation failed")
        r["bDenied"] = b.request("b-denied", "allocate", mib=ALLOCATION_MIB)
        r["aContinued"] = a.request("a-continued", "tick")
        if r["bDenied"]["cudaResult"] == 0:
            b.request("b-unexpected-free", "free")
        r["aFree"] = a.request("a-free", "free")
        r["bAfterFree"] = b.request("b-after-free", "allocate", mib=ALLOCATION_MIB)
        if r["bAfterFree"]["cudaResult"] != 0:
            raise RuntimeError("Allocation did not recover after freeing A")
        r["bContinued"] = b.request("b-continued", "tick")
        b.request("b-free", "free")
        report["ordinaryPassed"] = ordinary_verdict(r)
        for number in range(ROUNDS):
            ident = f"concurrent-{number}"
            target = time.monotonic_ns() + 500_000_000
            for worker in workers:
                worker.send({"id": ident, "action": "allocate", "label": ident,
                             "mib": ALLOCATION_MIB, "atMonotonicNs": target})
            results = [worker.receive() for worker in workers]
            if any(v.get("id") != ident or v.get("action") != "allocate" for v in results):
                raise RuntimeError("Concurrent CUDA response mismatch")
            verdict = concurrent_verdict(results)
            ticks = []
            for worker, value in zip(workers, results):
                if value["cudaResult"] == 0:
                    ticks.append(worker.request(f"{ident}-tick", "tick", ident))
                    worker.request(f"{ident}-free", "free", ident)
            report["concurrency"].append({"round": number, "verdict": verdict,
                                           "results": results, "successfulTicks": ticks})
            if verdict != "bounded-round-passed":
                break
        concurrency_passed = (len(report["concurrency"]) == ROUNDS and
            all(r["verdict"] == "bounded-round-passed" for r in report["concurrency"]))
        report["status"] = ("bounded-standard-cases-passed" if
            report["ordinaryPassed"] and concurrency_passed else "standard-cases-failed-or-inconclusive")
    except Exception as error:
        report["errorType"] = type(error).__name__
        report["error"] = str(error)
    finally:
        for worker in workers:
            worker.close()
        report["finishedNs"] = time.time_ns()
        emit(report)
    return 0 if report["status"] == "bounded-standard-cases-passed" else 1


def peer():
    runtime_identity()
    compiler = compiler_provenance()
    cuda = Cuda()
    try:
        cache = cache_identity(require_mapping=True)
        allocation = cuda.allocate("peer", 256)
        if allocation["cudaResult"] != 0:
            emit({"event": "peer-error", "allocation": allocation, "gpu": cuda.gpu})
            return 1
        emit({"event": "peer-ready", "gpu": cuda.gpu, "cache": cache, "allocation": allocation, "hami": cuda.hami, "pid": os.getpid(), "compiler": compiler})
        for tick in range(675):
            value = cuda.tick("peer")
            current = cache_identity(require_mapping=True)
            if (cache["device"], cache["inode"]) != (current["device"], current["inode"]):
                raise RuntimeError("Peer cache inode changed")
            emit({"event": "peer-alive", "gpu": cuda.gpu, "tick": tick,
                  "cache": current, "hami": cuda.hami, **value})
            time.sleep(0.2)
        emit({"event": "peer-completed", "gpu": cuda.gpu, "cudaResult": 0})
        return 0
    finally:
        cuda.close()


if __name__ == "__main__":
    role = sys.argv[1] if len(sys.argv) == 2 else ""
    if role == "child":
        try:
            child()
        except Exception as error:
            emit({"event": "child-error", "errorType": type(error).__name__, "error": str(error)})
            raise SystemExit(1)
    elif role == "workspace":
        raise SystemExit(workspace())
    elif role == "peer":
        raise SystemExit(peer())
    else:
        raise SystemExit("Expected workspace, peer, or child role")

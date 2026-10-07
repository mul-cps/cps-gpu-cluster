This is a separate, disabled manual fixture for the packaged runtime compiler. The original `render.py`, `probe.py`, `evaluate.py` and `dyn071421c` evidence remain unchanged. No production profile, MPS configuration, device allocation, NFS ownership or firewall setting is changed by rendering.

The fixed source is `cps-compute` commit `2f43f59aa319f8a114bae41ff89226018e3e5089`. Its qualification image is `ghcr.io/mul-cps/cps-compute:qualification-2f43f59aa319@sha256:38dad2077eb1552683cdb54c1ee50ffdf42d63e4a7dcd322f95f9f0236261c04`. The renderer reads the actual verified wheel, checks SHA256 `06939b3e4cefc882f419635129e982f46d40f376e9f6b3122e51ab4bed96febe`, loads only its stdlib runtime module, and checks module SHA256 `93f4e01c3682e52192d43c130073b3daf50c59ea7bd06342971f5f4add0a2b68`. The running probe independently checks those installed module bytes and package version.

Use a freshly reviewed GPU2 preflight with `image` set to that exact new image. The prior node/GPU/HAMi/KAI-rounding/Ready-MPS checks remain mandatory. The primary identity is UID/GID `10001/10001`. Separate compatibility runs may select only `1000/100` (the observed Hub process identity) or `1000/1000` (the trusted JobSet identity). A passing `10001/10001` run does not establish UID1000 compatibility with the existing MPS daemon. Do not change daemon UID, multiuser mode, pipe modes or server memory limits to make a compatibility probe pass.

Render outside Git; this writes two suspended Jobs and an immutable ConfigMap:

```bash
python3 render_compiled.py \
  --preflight /absolute/operator-evidence/fresh-preflight.json \
  --compiler-wheel /home/bjoern/cps-platform-evidence/2026-10-07/dynamic-runtime-packaging/2f43f59aa319/dist/cps_compute-0.1.0-py3-none-any.whl \
  --run-id dyncompiled1 --uid 10001 --gid 10001 \
  --output /absolute/operator-evidence/dyncompiled1-rendered.json
```

The compiler generates `cps-gpu-cache-init`, which runs `python -m cps_compute.gpu_runtime initialize-cache --directory /cache-root --uid 10001 --gid 10001` in the pinned image. It creates a new private directory and cache file as that identity; main mounts only `private/usage.cache` at `/tmp/cps-workspace-usage.cache`. The actual compiler's three volumes, mounts, security contexts, annotations and device-0 quota are used without recreating their definitions in the fixture. Global `CUDA_DEVICE_MEMORY_LIMIT=5324m`, `GPU_PORTION=0.13` and physical device selection must come from actual KAI-owned ConfigMaps; the fixture sets no device override and no scheduler global quota override.

The trusted operator must refresh identity and inventory immediately before execution, apply the reviewed suspended artifact, then release the peer first. After KAI binds a Pod, review its actual UID/resourceVersion, current node UID, complete effective Pod, image digest, private initialized cache, library bytes/preload, and every referenced ConfigMap's namespace/name/UID/resourceVersion/Pod owner/data. CAS-patch only `compute.cps.unileoben.ac.at/reviewed-gpu-uuid` to KAI's actual selected observed GPU UUID. Release workspace only when KAI independently selected the same physical card as the live peer. A different card is an inconclusive run; do not alter KAI selection or NVIDIA_VISIBLE_DEVICES.

The second init container is a CPU-only review gate. It performs no CUDA call, shell command, network or Kubernetes request and expires after 60 seconds. Create one new, mode0600 regular marker as the selected workload identity, only inside that Pod's owned cache emptyDir at `/cache-root/operator-approved.json`. The marker must contain exactly these fields:

```json
{
  "runtimeReviewed": true,
  "role": "peer",
  "podUid": "actual-owned-peer-pod-uid",
  "runId": "dyncompiled1",
  "nodeUid": "fresh-observed-node-uid",
  "uid": 10001,
  "gid": 10001,
  "gpuUuid": "actual-KAI-selected-observed-GPU-uuid",
  "hamiSha256": "fresh-observed-library-sha256",
  "probeSha256": "rendered-preflight-probe-sha256",
  "compilerWheelSha256": "06939b3e4cefc882f419635129e982f46d40f376e9f6b3122e51ab4bed96febe"
}
```

Use the workspace Pod UID and `role=workspace` for its gate. Marker UID/GID and proof must match the exact chosen pair. Save both init logs and before/after ConfigMap snapshots. A gate timeout, unknown identity, stale node, changed ConfigMap or unexpected effective limit fails closed. No marker can enable a production profile.

After both workspace children establish actual CUDA contexts, each holds 64 MiB and performs 40 distinct successful writes over a fixed 20-second `mps-hold-start` → `mps-hold-finished` phase. The independent peer holds 256 MiB and writes for 135 seconds; all Jobs retain a 180-second deadline and zero retries. Capture the real MPS server status/client list during this hold. Map the two logged child container PIDs and independent peer PID to actual host PIDs using their Pod/process namespaces. Save the actual server PID, physical GPU UUID, current node UID, Pod UIDs, host/container PID mappings, observation timestamp and full three-client list. The daemon receipt must show all three mapped clients on the same existing server while the hold and independent peer are progressing. A hold event or three CUDA contexts alone is not an MPS client-list receipt; this evaluator intentionally keeps `mpsThreeClientQualified=false`.

After hold cleanup, the unchanged ordinary 3 GiB + 3 GiB OOM/recovery and 16 strict-overlap concurrency cases run. The evaluator requires exact child write receipts, stable shared cache inode/ownership, observed preload/hash/exported 5120 MiB hook limit, scheduler-injected 5324 MiB observations, and independent peer heartbeats covering the entire hold/test interval. A successful result is bounded compiler-runtime evidence; hostile isolation, exact full profile qualification, 10/20 GiB, exit/crash/kernel restart, public Argo, native RTC and production activation remain pending.

Evaluate saved actual receipts with the same wheel and original rendered artifact:

```bash
python3 evaluate_compiled.py \
  --workspace-log /absolute/operator-evidence/workspace.log \
  --peer-log /absolute/operator-evidence/peer.log \
  --workspace-pod /absolute/operator-evidence/workspace-pod.json \
  --peer-pod /absolute/operator-evidence/peer-pod.json \
  --node /absolute/operator-evidence/node.json \
  --preflight /absolute/operator-evidence/fresh-preflight.json \
  --configmaps /absolute/operator-evidence/configmaps-before-after.json \
  --fixture /absolute/operator-evidence/dyncompiled1-rendered.json \
  --compiler-wheel /home/bjoern/cps-platform-evidence/2026-10-07/dynamic-runtime-packaging/2f43f59aa319/dist/cps_compute-0.1.0-py3-none-any.whl \
  --output /absolute/operator-evidence/evaluation.json
```

The evaluator verifies compiler fragments in the actual final Pod, UID/GID, init order, gate, file subPath and unchanged owned KAI ConfigMap receipts. Its synthetic unit fixtures test refusal behavior; they are not live qualification. Run offline checks from this directory with the verified wheel available:

```bash
CPS_QUALIFICATION_COMPILER_WHEEL=/absolute/path/to/the/verified/cps_compute-0.1.0-py3-none-any.whl \
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_dynamic_cache test_compiled_runtime -q
```

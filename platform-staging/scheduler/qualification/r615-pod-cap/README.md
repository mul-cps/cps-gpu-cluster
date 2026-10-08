# Inactive R615 Pod-parent memory-cap prototype

This directory contains a small **inert by default** prototype and CPU tests.
No GPU, node, driver, image, scheduler or cluster changes were made to qualify
this source. Hardware enforcement, managed memory, hostile isolation and
automatic KAI integration remain **unqualified**. Use only the separately
reviewed, drained, non-MIG R615 canary with its prepared driver rollback.

`pod_cap.py` binds a reviewed Pod UID/spec/node/GPU and the actual CRI first-init
PID, PID start ticks, boot ID, cgroup path/device/inode. It sets and reads back a
single Pod-parent soft/hard cap before releasing `gate_wait.py`. Unknown state,
an already started main container, restarted gate, another child cap (at any
depth), symlink, stale PID, changed Pod resourceVersion or failed readback denies
release. A prepared receipt precedes the driver write; failures retain any
possible cap and never release the gate. This is a manual startup window,
not a production runtime hook or a proof against concurrent privileged writers.

The pinned KAI PreBind occurs before a CRI Pod parent exists. It can seal intent;
actual enforcement must occur after sandbox creation and before **any** user
init, native sidecar or main CUDA process. This prototype does not alter KAI or
HAMi. Require an exclusively controlled canary, no user cgroup delegation or
privilege, no later child native caps, no driver reload during a fixture, and
`restartPolicy: Never`. Reboot/reload recovery and hostile lifecycle races need
separate qualification.

## Native operator and first init

On the actual canary node, native root needs Python, its R615
`libnvidia-ml.so.1`, host `/proc`, host `/sys/fs/cgroup`, `crictl` with the real
containerd socket, and existing `kubectl` authorization to freshly read the
exact Pod. A node-agent container needs equivalent host mounts and API access;
this source does not provision those privileges. The full CLI cannot run in a
driver container that lacks kubectl. A manually applied `nvidia-smi` cap is a
separate measurement route; it does not qualify this orchestration.

Prepare a root-owned mode0600 intent JSON in a mode0700 directory:

```json
{"pod_uid":"<exact UUID>","namespace":"<fixture namespace>","name":"<fixture name>","node":"<canary node>","gpu_uuid":"GPU-<physical UUID>","cap_mib":128,"spec_sha256":"<SHA256 of canonical actual Pod spec>"}
```

Canonical spec bytes use `json.dumps(spec,sort_keys=True,separators=(',',':'))`.
Review the whole actual spec, including the pinned first-init image/command,
mounts, security context and absence of user execution before the gate. Never
derive intent from an unreviewed Pod, environment quota or a rounded KAI portion.

The first init must be named `cps-driver-cap-gate`. Execute Python directly as
its CRI PID1, with no shell child wrapper. The trusted CPU-only init receives
the Pod UID via Downward API and a read-only mount of its root-owned receipt
directory. It needs UID0 to read the0600 receipt, no CUDA access or API token;
the main container receives no receipt mount or write authority.
The gate waits at most600seconds for manual canary setup and then fails closed.

```sh
python /qualification/gate_wait.py --execute \
  --receipt /cap-receipts/POD_UID.json --pod-uid POD_UID \
  --gpu-uuid GPU_UUID --cap-mib 128
```

On the native node operator, while that init is waiting:

```sh
python pod_cap.py apply --execute --intent /private/intent.json \
  --container-id EXACT_64_HEX_GATE_CRI_ID --receipt /private/caps/POD_UID.json
```

The receipt host directory must be the same directory mounted read-only in the
init. CLI defaults are `/proc`, `/sys/fs/cgroup` and
`unix:///run/k3s/containerd/containerd.sock`. If mounted in a node-agent, specify
`--proc-root /host/proc --cgroup-root /host/sys/fs/cgroup` and its actual socket
endpoint. NVML must be able to open the **literal absolute cgroup path in that
operator's mount namespace**. The helper resolves the parent from actual
`/proc/PID/cgroup`, not just CRI's shortened systemd cgroupsPath.

Read-only GPU2 evidence confirmed containerd2.2.5-k3s2/systemd cgroup v2 layout:

```text
/kubepods.slice/kubepods-besteffort.slice/kubepods-besteffort-podUID_WITH_UNDERSCORES.slice/cri-containerd-CONTAINER_ID.scope
```

Its parent is the Pod slice. The existing node driver580.95.05 was unsupported;
that observation is not R615 hardware evidence. The helper rejects dmem backend
and enabled/pending MIG; this implementation covers only misc cgroup limits.

## Bounded raw driver measurement

Use the existing reviewed Python CUDA fixture image with the actual canary
host driver libraries. The probe directly loads `libcuda.so.1`, records the
resolved symbol object, uses supported Driver API entry points and checks
CUDA13.4. It runs two **distinct** processes/contexts in the same Pod parent.
It bypasses HAMi's `LD_PRELOAD` entry points; no MPS or HAMi accounting is assumed.

First start a separate capped peer Pod on the same physical GPU, with its own
Pod-parent cgroup. Then run the main fixture:

```sh
python cuda_probe.py --execute --mode heartbeat --cap-mib 128 \
  --device-uuid GPU_UUID --parent-cgroup /host/sys/fs/cgroup/PEER_POD_PARENT \
  --pod-uid PEER_POD_UID
python cuda_probe.py --execute --mode all --cap-mib 128 \
  --device-uuid GPU_UUID --parent-cgroup /host/sys/fs/cgroup/MAIN_POD_PARENT \
  --pod-uid MAIN_POD_UID
```

Paths must point to actual host Pod slices as visible inside each fixture;
their basenames must contain the exact respective Pod UID. NVML's unprivileged
getter opens that literal path and must read the exact128MiB soft/hard cap.
`memory.current` is read from that same parent. The peer defaults to120seconds
and performs a device memset/synchronize/readback every200ms. Start it before
main setup and stop it only after the main report ends (SIGTERM frees its
allocation/context). Both logs must cover the entire main started_ns/finished_ns
interval; a short or dead peer cannot qualify independence. Exceeding120seconds
is inconclusive and requires a new bounded review, not an automatic campaign.

Fixed64/128MiB plans allocate38/76MiB per ordinary context, deny the second while
the first remains live, then free the first and retry the second. Managed cases
allocate80/144MiB, call raw `cuMemPrefetchAsync_v2` toward the GPU, synchronize,
GPU-memset the whole allocation and synchronize. **No CPU dereference or CPU
population of managed pages occurs.** Parent memory.current and NVML used/cap
are captured before and while the GPU-touched allocation remains held. Success
above the cap is reported explicitly; managed-memory qualification stays false.
Explicit probe allocations remain below512MiB, excluding opaque driver context
overhead. Context initialization can itself exceed a small cap; that returns
hardware-inconclusive. Do not automatically enlarge quotas or claim enforcement.

R615's misc implementation can return `NOT_SUPPORTED` (NVML code3) for a virgin
cgroup without any nearest limit, as well as for an unsupported backend.
The helper preserves this as `unset-or-unsupported`, permits only a prepared
setter attempt, and requires successful set plus exact cap readback to release.
Code3 is never an unlimited/cleanup proof or a feature-qualified verdict.
See the [actual615 getter](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/src/nvidia/src/kernel/mem_mgr/memacct.c#L324-L346).

After the exact Pod is gone/terminal and parent `populated` is0:

```sh
python pod_cap.py cleanup --execute --intent /private/intent.json \
  --container-id EXACT_64_HEX_GATE_CRI_ID --receipt /private/caps/POD_UID.json
```

Cleanup requires the same boot, cgroup inode/device and exact tracked cap; it
never clears a replacement/foreign/live group. Removed cgroups are recorded as
already cleared. Child CUDA workers explicitly free allocations and contexts;
failed frees retain pointers for retry, and bounded subprocess termination
provides final process cleanup without an isolation claim.

## Source evidence and CPU verification

The official CUDA13.4 NVML header is from
[NVIDIA cuda-nvml-dev-13-4_13.4.92-1_amd64.deb](https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-nvml-dev-13-4_13.4.92-1_amd64.deb).
Package SHA256: `844489d9b7e21ca07bd6225e757b8bac0b9a6cc637e4008418e7ceb84fe6f1aa`.
Header SHA256: `c9b494b7c8015b6ae7aca62b2ce98e6b13f3277a2bec80de528371e725d54012`.
The actual ABI uses `nvmlSetMemoryLimits_v1_t` (namespace pointer, soft/hard
uint64) and `nvmlGetMemoryLimits_v1_t` (plus currentUsed uint64),24/32bytes on
x86_64. Clearing uses soft0/hardUINT64_MAX. The setter requires native root.
See [NVML setter ABI](https://docs.nvidia.com/deploy/nvml-api/latest/api/structnvmlSetMemoryLimits__v1__t.html) and [getter ABI](https://docs.nvidia.com/deploy/nvml-api/latest/api/structnvmlGetMemoryLimits__v1__t.html),
[MPS cgroup limits and ancestor behavior](https://docs.nvidia.com/deploy/mps/615/mpsv3-memory-partitioning.html)
and [CUDA managed memory API](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__UNIFIED.html).

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover \
  -s platform-staging/scheduler/qualification/r615-pod-cap -v
python platform-staging/scheduler/qualification/r615-pod-cap/cuda_probe.py
```

28 CPU tests pass, including exact NVML ABI bytes, real temporary proc/cgroup
paths, foreign identity/PID/inode/boot denial, nested child limits, gate release,
shared-versus-per-context budget, managed observer timing and failed cleanup.
External CUDA/NVML calls are faked in these tests; no GPU evidence is implied.

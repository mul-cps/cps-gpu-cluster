# Bounded extended GPU2 witnesses

Preparation only until the parent releases the hardware window. These fixtures
use the existing immutable Python/libcuda image and stock mandatory Fractioning
annotations. They do not alter any driver, runtime, KAI configuration or user
workspace. Default operation renders JSON; it makes **no kubectl or SSH call**.

```sh
python3 tests/upstream-sharing/hardware/extended_run.py \
  --node k3s-wk-gpu2 --node-ip 10.21.0.43 \
  --gpu-uuid GPU-16128952-b438-556a-00bb-93039ee24e56 \
  --output /tmp/extended-gpu2-card-a-prepared
```

After the parent explicitly releases GPU2, use a **new** output directory and
append `--execute --ssh-target USER@10.21.0.43 --parent-idle-release REFERENCE`.
The SSH account must support noninteractive `sudo python3` for the included
read-only host observer. Use the second card's independently read physical UUID
for the second run; never guess it. `--cases vmm` etc. allows bounded individual
cases. Run the full default sequence on each card for both-card evidence.

The runner refuses existing active/pending GPU workloads on GPU2, existing
compute processes on the selected card, mismatched node IP, host name or UUID,
and more than 64 MiB idle physical use. The parent remains responsible for
serializing this window with app starts; the preflight cannot lock out another
actor. It never uncordons, changes labels, or adds tolerations.

| Case | Exact witness |
| --- | --- |
| `vmm` | Pinned `cuMemCreate`, reserve/map/access/fill/unmap/release: 1 GiB succeeds, 6 GiB returns CUDA error 2, 2 GiB recovery succeeds. |
| `pool` | Explicit default-pool handle and nonblocking stream: 1 GiB succeeds, 6 GiB typed OOM, two 2 GiB allocation/free cycles retain and reuse pool storage; reserved/used counters and final trim are recorded. |
| `ipc` | Export 3 GiB, exec importer in the same container, verify data, reject additional 3 GiB, accept 1 GiB, close importer before freeing exporter, then recover 4 GiB. |
| `crash` | Three fresh child processes hold 4 GiB, are SIGKILLed and reaped; each is followed by a fresh process checking 6 GiB OOM and 4 GiB allocation/fill/free, allowing at most 20 seconds for cleanup convergence with every typed OOM logged. |
| `race` | Two independent processes concurrently request 3 GiB each in one 5 GiB cgroup. Exactly one succeeds, the other gets error 2; release and fresh 4 GiB recovery follow. |
| `recovery` twice | Recreate the same Pod name with new Pod UID/container ID/cgroup, then check 6 GiB OOM and 4 GiB recovery in each generation. |

These typed-OOM expectations test consistency with the **measured ordinary
5 GiB hard limit**. Unexpected success is preserved as a diagnostic discrepancy;
it is not, by itself, rejection of the user's policy permitting idle borrowing.
Do not introduce driver patches solely to enforce idle overage. Contentious
peer protection is a separate acceptance gate. Unsupported API/error results
fail the case explicitly; they are never silently counted as passes.

The IPC witness is intra-container/process aggregation, not cross-tenant IPC
authorization. The default-pool witness does not qualify exported/custom pools.
The reuse test exercises reused Pod names and container PID 1 with changed host
PID/cgroup identities; it **does not claim forced numeric host PID reuse**.
The exporter remains alive until its IPC importer closes: accessing an imported
allocation after exporter destruction would exercise undefined CUDA lifetime.

Every Pod has a 240-second active deadline; individual gate/process/API waits
are bounded. Only processes created by the probe receive SIGKILL. Normal Pod
cleanup uses exact UID/resourceVersion preconditions, 15-second grace and a
45-second disappearance deadline. A replacement or ambiguous CREATE is retained
for inspection, never force-deleted. The runner stops at the first failure and
records incomplete cleanup explicitly. It does not retry an ambiguous CREATE.

Evidence includes exact rendered inputs/probe SHA; node UID, boot ID, driver
version, physical GPU UUID; CRI container ID, host PID/start time, cgroup path and
inode, namespaced PIDs, leaf misc/memory counters; JSON CUDA results; host NVML
samples and post-cleanup baseline. Container CRI credentials/environment are not
printed. A passed API probe requires a successful process exit and observed
physical-memory return after removal. Persist resulting run directories under
`docs/operations/evidence/upstream-sharing-20261116/extended-api/`.

ABI references: [NVIDIA CUDA header](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/cuda_8h_source.html),
[VMM API](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__VA.html),
[stream ordered allocator](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-driver-api/group__CUDA__MALLOC__ASYNC.html).
Local syntax/ABI-layout/render checks validate preparation only; actual hardware
results must be recorded separately.

Every CUDA identity now also records device attribute 100,
`CU_DEVICE_ATTRIBUTE_PAGEABLE_MEMORY_ACCESS_USES_HOST_PAGE_TABLES`, before
context creation. See the [official enum](https://docs.nvidia.com/cuda/archive/12.8.2/cuda-driver-api/group__CUDA__TYPES.html).
This readback does not change GPU configuration or alter case expectations.

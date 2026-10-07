# Dynamic workspace cache qualification fixture

Status: disabled, source and offline tests only. Dynamic GPU sharing remains the
target. This package uses no MIG and changes no GPU mode, MPS server ceiling,
device plugin, policy catalog, or user Pod. It is outside Fleet deployment paths.
The renderer always emits suspended Jobs and has no execute/unsuspend option.

The retained aggregate probe at
`/home/bjoern/cps-platform-evidence/2026-10-06/gpu-runtime/aggregate-probe-final-pod.json`
unlinked `/tmp/cudevshr.cache` before each 3072 MiB child. Its simultaneous 6144
MiB allocation is evidence of deliberate cache replacement. It is not an
ordinary two-process test against one unchanged accounting inode. That
distinction does not invalidate the separately observed hostile bypass.

The pinned HAMi-core revision
`5496322f2fb3e71bf1eca014fba3c9bc59ab8ffd` declares
`CUDA_DEVICE_MEMORY_SHARED_CACHE` as the explicit cache key. Its initialization
uses the explicit file when present; fallback from an inaccessible synthesized
container directory applies when that key is absent. See the pinned
[cache header](https://github.com/Project-HAMi/HAMi-core/blob/5496322f2fb3e71bf1eca014fba3c9bc59ab8ffd/src/multiprocess/multiprocess_memory_limit.h#L24-L29)
and [initialization](https://github.com/Project-HAMi/HAMi-core/blob/5496322f2fb3e71bf1eca014fba3c9bc59ab8ffd/src/multiprocess/multiprocess_memory_limit.c#L1079-L1143).
The pinned allocator performs quota checks and accounting around allocation;
its allocator mutex is process-local. The synchronized case tests a possible
cross-process check/commit race; the source alone is not proof of a runtime
failure. See the
[allocator](https://github.com/Project-HAMi/HAMi-core/blob/5496322f2fb3e71bf1eca014fba3c9bc59ab8ffd/src/allocator/allocator.c#L101-L137).

The exact existing trusted image is:

```text
ghcr.io/mul-cps/cps-compute:qualification-a7abe7d13465a8ea@sha256:f107b407f3e6c9218a4a9b5ec4df9f0ea013f4abd0a177e474013ff6b682c893
```

The KAI admission injector supplies the runtime HAMi library and GPU selection.
Before execution, the operator must capture the actual injected library byte
identity. Its source revision is currently unverified; the pinned source above
is a reference for the hypothesis. An annotation does not prove which source
produced a binary. Preserve the final mutated Pod specs, image IDs, library
hash, any available build receipt, and injector version as evidence. The root
operator observed GPU2 `/usr/local/vgpu/libvgpu.so` SHA256
`79bdbf5bf819de4fda3710235c9eac6bf91ece674eb2891728069a9d0b0c8542`
through existing toolkit Pod UID `e0b860b6-cc2d-498a-986d-14d2a0266a3e`.
The installed library sync image was
`docker.io/projecthami/kai-resource-isolator:v1.1.0@sha256:2743f1684721f6368e87f98a17d7e7392805786cdb70b44ce0e8fdc10b1e13d0`,
on library sync Pod UID `2f455157-6902-44d4-abd6-08a7dcf327c2`.
Those observations do not establish correspondence to the reference source.

## Controlled scope and preflight

Only the root operator may perform live actions. GPU1 and existing user sessions
remain protected. This renderer accepts only `k3s-wk-gpu2`, one physical GPU UUID
observed on that node, its observed node UID, the fixed image, no active GPU
workloads/reservations on that node, and an already Ready MPS server for that
UUID. It neither starts nor configures MPS. The active server's nominal 5 GiB
per-client ceiling remains unchanged. Qualifying 10/20 GiB profiles requires
separate authorized maintenance; this fixture cannot provide that evidence.

Capture fresh inventory outside Git, with the following JSON shape. Replace the
example identifiers with actual observations; invented values are not evidence.
Inventory must be at most 15 minutes old when rendering.

```json
{
  "observedAt": "2026-10-07T14:00:00+00:00",
  "node": {"name": "k3s-wk-gpu2", "uid": "OBSERVED_NODE_UID"},
  "image": "FIXED_IMAGE_FROM_ABOVE",
  "hami": {
    "referenceSourceRevision": "5496322f2fb3e71bf1eca014fba3c9bc59ab8ffd",
    "sourceRevisionVerified": false,
    "libraryPath": "/usr/local/vgpu/libvgpu.so",
    "sha256": "ACTUAL_OBSERVED_INJECTED_BINARY_SHA256"
  },
  "targetGpuUuid": "OBSERVED_PHYSICAL_GPU_UUID",
  "gpus": [{"uuid": "OBSERVED_PHYSICAL_GPU_UUID", "index": 0}],
  "activeGpuPods": [],
  "mpsServers": [{"gpuUuid": "OBSERVED_PHYSICAL_GPU_UUID", "pid": 1234, "ready": true}]
}
```

The operator must check all namespaces for GPU requests, KAI fractional GPU
annotations, pending reservations and unmanaged GPU processes. An empty Pod
list alone does not establish a quiescent device. Verify namespace isolation,
no new GPU workloads, the same node UID, the exact card UUID, and the unchanged
MPS server immediately before any unsuspension. The namespace is the existing
`cps-gpu-qualification`; this package creates no namespace or RBAC privileges.

Render locally (this performs no network or cluster calls):

```bash
python3 render.py --preflight /PRIVATE_EVIDENCE/preflight.json \
  --run-id UNIQUELOWERCASEID --output /PRIVATE_EVIDENCE/suspended-fixture.json
```

Inspect the resulting immutable ConfigMap and two `suspend: true` Jobs. Retain
the rendered bytes and their hash. Any manual application or unsuspension is a
separate root operation after the fresh checks. Start the independent peer Job
first. Each Pod initializes its private cache, then a non-GPU init gate waits
up to 60 seconds for the root operator to review the fully injected Pod before
any CUDA probe executes. In that gate container, root can create the private
`/cache-root/operator-approved.json` after verifying the final image IDs,
preload/library mounts, exact explicit quota/cache environment, target node UID,
card UUID and unchanged MPS configuration. The marker must match this exact
shape, with observed values from the rendered proof (no additional fields):

```json
{
  "runtimeReviewed": true,
  "role": "peer",
  "podUid": "OBSERVED_ACTUAL_POD_UID",
  "runId": "UNIQUELOWERCASEID",
  "nodeUid": "OBSERVED_NODE_UID",
  "gpuUuid": "OBSERVED_PHYSICAL_GPU_UUID",
  "hamiSha256": "ACTUAL_OBSERVED_INJECTED_BINARY_SHA256",
  "probeSha256": "SHA256_OF_RENDERED_PROBE_SOURCE"
}
```

Use `role: workspace` and that Pod's actual UID for the other Pod. The gate binds
the actual Pod UID supplied by the Downward API, the renderer's run ID, expected
node UID, observed library bytes, card UUID and probe source hash. Root must
recheck Pod UID/resourceVersion and the live node UID immediately before
writing each marker. The marker must be owned by UID 10001;
write it using the already nonroot gate container, and preserve its bytes as
an operator receipt. Missing, late or mismatched approval fails the Job. This
is a root execution control, not an identity or source-build attestation. No
Pod API credentials are installed. Wait for `peer-ready` and successful
heartbeats on the expected physical GPU, then start and review/release the
workspace Job promptly. Both stop within their 180-second active
deadline and have no retries. Neither accesses Kubernetes credentials. The
peer holds 256 MiB for approximately 90 seconds. If scheduling puts either Job
on the other GPU2 card, it stops before memory allocation and the result is
inconclusive. Do not substitute a same-workspace child for the independent peer.

## Cache and allocation contract

Each Job has a separate Pod-private `emptyDir`. A nonroot UID 10001 initializer
creates one new regular `usage.cache` using `O_CREAT|O_EXCL|O_NOFOLLOW` and mode
0600. Existing files/symlinks fail initialization. The workload mounts only
that file at `/tmp/cps-workspace-usage.cache` using `subPath`, with the exact
explicit HAMi key. Its parent cache directory is absent from the main
container. It does not mount, chmod, delete, or reset the host cache tree.
The workload root filesystem is read-only; writable scratch is Pod-private.
The only explicit host mounts are the existing MPS pipe and MPS shared-memory
directories needed by the baseline trusted probe. KAI's trusted admission
mutation must be reviewed in the captured final Pod spec.

Two child processes inherit the same unmodified environment and retain one
cache device/inode throughout initialization, allocation and free. Their cache
file must actually appear in `/proc/self/maps` with matching device/inode; a
default or synthesized alternative cache mapping makes the test fail. The
JSON evidence records cache identity, CUDA GPU UUID, actual CUDA return codes,
memory accounting reported by CUDA, and allocation timing. The environment
explicitly sets the HAMi quota to `5120m`. Before allocation, the probe verifies
the library's actual SHA256 and mapped device/inode, confirms its preload
configuration, obtains its already loaded handle using `RTLD_NOLOAD`, and reads
`get_current_device_memory_limit(0)`. A missing preload, unreviewed binary or
effective quota other than 5120 MiB fails. These checks do not load an absent
hook merely to manufacture positive evidence. The expected binary hash comes
from actual node observation. Runtime receipts explicitly retain
`sourceRevisionVerified: false`; reconstructing source provenance is a separate
qualification gate. No library replacement is performed by this fixture.

1. Child A allocates and holds 3072 MiB. Child B attempts 3072 MiB against the
   same nominal 5120 MiB workspace. Only `CUDA_ERROR_OUT_OF_MEMORY` (code 2)
   counts as quota denial; another failure is not accepted as isolation.
2. A performs synchronized CUDA writes after B's attempt. A frees only its
   own allocation; B must then allocate 3072 MiB and write successfully.
3. Sixteen rounds start both allocations at one future monotonic deadline.
   One success plus one OOM is bounded success. Two successes are an aggregate
   quota failure; two OOMs, another error, launch skew over 25 ms or allocation
   calls without strict actual interval overlap are inconclusive. Both intervals
   must have valid `end >= start` timestamps and satisfy
   `max(starts) < min(ends)`; close start times alone do not prove concurrency.
   Every successful allocation needs its exact same-process successful CUDA
   write receipt in the child log and is freed before the next round. This
   sample cannot exclude a rare race.
4. The independent workspace peer must keep writing to its own allocation,
   using its own cache inode on the same physical GPU, before, during and after
   the workspace window. Missing, stale, wrong-GPU or interrupted peer progress
   fails the combined gate. The final heartbeat before the workspace starts
   must be at most one second old; the first heartbeat after it finishes must
   follow within one second. Every gap in that complete inclusive interval
   must also be at most one second. Distant outside-window heartbeats cannot
   cover an outage at either boundary.

No case unsets preload, changes quota/MPS/cache environment variables, replaces
the cache, or edits library bytes. Ordinary and synchronized cases are reported
separately from tamper tests. `tamper.status` remains `not-run`, and existing
hostile bypass evidence remains applicable. A subPath mount prevents pathname
replacement but does not by itself protect writable accounting contents or
prevent a user process from changing its own environment. This package does
not lower the threat model or claim a hard isolation boundary.

## Receipts and offline validation

Save full workspace/peer logs (including CUDA errors), their final Pod JSON,
the observed node JSON, and the same preflight JSON outside Git. Retain Pod
UIDs and Job UIDs; remove only operator-created resources after checking their
UIDs. Preserve logs before any cleanup. Do not remove pre-existing ConfigMaps,
jobs, cache files, Pods or MPS processes.

```bash
python3 evaluate.py --workspace-log /PRIVATE_EVIDENCE/workspace.log \
  --peer-log /PRIVATE_EVIDENCE/peer.log \
  --workspace-pod /PRIVATE_EVIDENCE/workspace-pod.json \
  --peer-pod /PRIVATE_EVIDENCE/peer-pod.json --node /PRIVATE_EVIDENCE/node.json \
  --preflight /PRIVATE_EVIDENCE/preflight.json \
  --output /PRIVATE_EVIDENCE/bounded-result.json
python3 -m unittest -v test_dynamic_cache.py
```

The evaluator requires successful completed Pods with the exact image, fixed
file mount, unchanged node UID and distinct workspace UIDs. It rechecks actual
CUDA outcomes and synchronized timing rather than trusting a `passed` string.
It can return only bounded standard-case evidence. `productionQualified` and
`hostileIsolationQualified` stay false in every outcome. The GPU catalog and
group-sharing feature remain disabled until the remaining actual isolation,
dynamic profile matrix and reservation/revocation gates pass.

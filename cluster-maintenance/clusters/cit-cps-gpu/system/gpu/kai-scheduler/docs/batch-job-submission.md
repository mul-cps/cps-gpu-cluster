# Submitting Batch Jobs to KAI

This covers how to submit workloads to the `batch` queue, when to use
MPS-sharing vs. a full-exclusive GPU, and the checkpointing requirement
for batch jobs. See `../kai-policy/README.md` for the general queue/priority
overview and `../examples/batch-gang-job.yaml` for the manifests referenced
below.

## Quick start

```
kubectl apply -f ../examples/batch-gang-job.yaml
```

This creates both example patterns described below in the `default`
namespace. Delete or rename resources as appropriate before reusing them
for a real workload.

To route a workload to the `batch` queue:

1. Set `spec.schedulerName: kai-scheduler` in the pod spec.
2. Add the label `kai.scheduler/queue: batch` to the pod (or, for a gang
   job, set `queue: batch` in the explicit `PodGroup` - see below).
3. Set `priorityClassName: kai-batch-low`.

The `batch` queue has zero guaranteed quota (`quota: 0`) but a high
`overQuotaWeight` (10), so it can burst hard into idle cluster capacity -
it just has no reserved floor and is preempted first by `courses` and
`phd-interactive` workloads whenever they need the capacity back.

## MPS-shared vs. full-exclusive GPUs

All 8 A100 GPUs in this cluster (`k3s-wk-gpu1..4`, 2 GPUs each) run in
full (non-MIG) mode. There is no longer a static split between "MIG
nodes" and "full nodes" - every GPU can serve either mode, and which one
you get is determined entirely by what you request:

- **Single-GPU, embarrassingly-parallel batch jobs** should request a
  modest `gpu-memory` tier (an unprefixed pod annotation, MiB value, e.g.
  `gpu-memory: "10240"` for ~10GB) so KAI can bin-pack them alongside
  other MPS-shared workloads on the same physical GPU. Pair this with a
  matching `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT` container env var (e.g.
  `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT=0=10240M`) - **KAI only schedules
  against the `gpu-memory` annotation, it does not enforce it**. Actual
  memory enforcement on the shared GPU comes from NVIDIA MPS honoring
  that env var, so the two values must match or your pod can still
  exceed its declared share and starve neighbors. The pod also needs a
  `hostPath` mount of the node's MPS pipe directory
  (`/tmp/nvidia-mps` by default) to actually talk to the MPS control
  daemon - see the `single-gpu-mps-shared-job` example, which mirrors
  KAI's own upstream `docs/gpu-sharing/mps/gpu-sharing-with-mps.yaml`
  example.

  **Important:** a `gpu-memory`/`gpu-fraction`-annotated pod should
  **not** also request an integer `nvidia.com/gpu` limit/request. KAI's
  own upstream gpu-sharing examples (`docs/gpu-sharing/gpu-memory.yaml`,
  `docs/gpu-sharing/gpu-sharing.yaml`, both from
  `github.com/kai-scheduler/KAI-Scheduler`) only ever set the annotation,
  never an `nvidia.com/gpu` limit on the same pod. Adding an integer
  `nvidia.com/gpu` limit routes the pod through the stock NVIDIA device
  plugin's whole-GPU allocation, which defeats sharing.

- **Distributed multi-GPU jobs that need real NVLink/P2P** (e.g. PyTorch
  DDP spanning multiple GPUs/pods) should request a whole GPU per pod via
  plain `nvidia.com/gpu: "1"` in `resources.limits`, with **no**
  `gpu-memory`/`gpu-fraction` annotation at all, combined with an explicit
  `PodGroup` for gang scheduling (see below). See the
  `distributed-gang-job` example.

  An earlier draft of this design combined `nvidia.com/gpu: "1"` with a
  full-device `gpu-memory: "40960"` annotation, on the theory that
  requesting the whole ~40GB via the annotation would prevent KAI from
  also MPS-sharing that GPU. On checking KAI's upstream gpu-sharing
  examples, `gpu-memory`/`gpu-fraction` and an integer `nvidia.com/gpu`
  limit are never combined on the same pod in any upstream example -
  the annotation-based path and the device-plugin integer-request path
  are presented as **alternatives**, not additive. The manifest here uses
  the plain integer-request path (no `gpu-memory` annotation) instead,
  which is the standard, non-fractional whole-GPU allocation route and
  the safer choice for genuine exclusivity.

  **Open item, still unverified:** whether a pod with no `gpu-memory`
  annotation is fully protected from ever being co-scheduled with an
  MPS-shared pod on the same physical GPU has not been validated against
  the running cluster as of this writing - this depends on how KAI's
  scheduler plugin accounts for GPUs already claimed via the plain
  device-plugin path when placing fractional/`gpu-memory` pods. Validate
  this in a test environment (schedule a small MPS-shared pod while a
  plain `nvidia.com/gpu: 1` pod already occupies a GPU, and confirm the
  shared pod is placed on a different device) before relying on it for
  production distributed training jobs.

  **Also unverified/not guaranteed by this manifest:** NVLink/P2P is
  intra-node. Four single-GPU pods with `minMember: 4` are gang-scheduled
  together, but nothing in this manifest guarantees they land on the same
  physical node's NVLink domain rather than spread across up to 4
  different nodes. If your workload genuinely requires intra-node NVLink
  between specific ranks, add a KAI topology constraint (see KAI's
  `docs/topology/`) or node affinity/anti-affinity on top of this
  example - do not assume the manifest as written enforces co-location.

## Gang scheduling multi-pod distributed jobs

KAI's podgrouper webhook automatically creates a `PodGroup` only for a
**single pod** carrying `schedulerName: kai-scheduler` plus the
`kai.scheduler/queue` label (this is how JupyterHub single-user pods get
scheduled). A distributed job that spans **multiple pods that must all be
scheduled together or not at all** (e.g. PyTorch DDP rank 0..N) needs an
**explicit `PodGroup`** custom resource, using KAI's documented "external
PodGroups" contract:

```yaml
apiVersion: scheduling.run.ai/v2alpha2
kind: PodGroup
metadata:
  name: distributed-gang-job
spec:
  minMember: 4        # must equal the number of worker pods
  queue: batch
  priorityClassName: kai-batch-low
```

Each worker pod then:

- Sets the `pod-group-name: distributed-gang-job` **annotation** on the
  pod (this is what attaches the pod to the explicit PodGroup).
- Sets `kai.scheduler/skip-podgrouper: "true"` so KAI's podgrouper webhook
  does not try to create/rewrite its own PodGroup for these pods.
- Does **not** need the `kai.scheduler/queue` label - `PodGroup.spec.queue`
  is authoritative once a pod is attached to an explicit PodGroup.

With `minMember: 4`, KAI will not start any of the 4 worker pods unless
all 4 can be scheduled simultaneously - this is the gang-scheduling
guarantee distributed training needs.

**Where this was verified:** the `PodGroup` CRD shape above (API group
`scheduling.run.ai`, version `v2alpha2`, `spec.minMember`, `spec.queue`,
`spec.priorityClassName`) was read directly out of the vendored KAI
v0.12.10 chart's CRD manifest
(`kai-scheduler/crds/scheduling.run.ai_podgroups.yaml`, extracted from
`kai-scheduler-v0.12.10.tgz` in the repo root). The pod-side contract
(`pod-group-name` annotation, `kai.scheduler/skip-podgrouper` annotation,
`kai.scheduler/subgroup-name` label for subgroups) was confirmed against
NVIDIA's KAI-Scheduler v0.12.10-tagged upstream docs and example
(`docs/batch/README.md` "External PodGroups" section and
`examples/batch/external-podgroup-job.yaml` in
`github.com/kai-scheduler/KAI-Scheduler`, formerly `NVIDIA/KAI-Scheduler`)
- not guessed. The `gpu-memory`/`gpu-fraction` vs. `nvidia.com/gpu`
mutual-exclusivity noted above was similarly confirmed against
`docs/gpu-sharing/README.md`, `docs/gpu-sharing/gpu-memory.yaml`,
`docs/gpu-sharing/gpu-sharing.yaml`, and
`docs/gpu-sharing/mps/gpu-sharing-with-mps.yaml` in the same upstream repo.

## Checkpointing requirement

A separate Kubernetes `descheduler` (deployed independently of this
bundle) will periodically evict low-priority `batch`-queue pods for
consolidation/bin-packing as the cluster fills up. KAI will attempt to
reschedule evicted pods elsewhere, **but this is not a live migration** -
any job that does not checkpoint its own progress will lose all progress
made since its last checkpoint.

**This is a documented requirement for batch users, not something the
platform enforces.** Batch job authors are responsible for:

- Checkpointing periodically (not just at the end of a run) to the
  cluster's shared storage, not local/ephemeral storage.
- Resuming from the latest checkpoint on restart, since KAI/Kubernetes
  will simply restart the pod (per `restartPolicy`) after eviction or
  preemption - your application code must handle resumption itself.

Use the `longhorn-overcommit` StorageClass (replicated block storage,
supports `ReadWriteMany`) for checkpoint PVCs - see
`../../../storage/storageclasses/storageclasses.yaml` for the
authoritative list of storage classes available in this cluster. Note:
`nfs-client` no longer exists on this cluster (removed without a
documented replacement path - see CLAUDE.md and
`docs/troubleshooting.md`); a PVC referencing it stays `Pending` forever.
`longhorn-overcommit` is the current default for `ReadWriteMany`
checkpoint directories shared across a job's pods, as used in the
examples in this file.

Both example jobs in `../examples/batch-gang-job.yaml` mount a
`/checkpoints` path backed by a `longhorn-overcommit` PVC to illustrate
this pattern; replace the placeholder image/args with your actual
training code, which must write checkpoints to that path on a schedule
shorter than your expected eviction interval.

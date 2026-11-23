# Submitting batch jobs

Submit tenant workflows through the compute gateway using `kubectl cps submit`,
the Python `ComputeClient`, or the `/v1/workflows` API. Use a gateway credential
for your Hub and project. The gateway resolves your identity, checks project
membership and profile entitlement, and creates the workload in the appropriate
KAI queue. Use the gateway workflow ID to check status, retrieve logs and
artifacts, or cancel the workflow.

| Action | Gateway API |
| --- | --- |
| Submit | `POST /v1/workflows` |
| List your workflows | `GET /v1/workflows` |
| Check a workflow | `GET /v1/workflows/{key}` |
| Read logs | `GET /v1/workflows/{key}/logs` |
| List artifacts | `GET /v1/workflows/{key}/artifacts` |
| Cancel | `POST /v1/workflows/{key}/terminate` |

Keep the returned workflow key. Use the same idempotency key if you retry
the same submission after losing the response.

## GPU profiles

The production gateway currently accepts CPU batch through `batch-cpu`.
GPU batch profiles remain disabled. The first planned GPU pilot uses
`batch-shared-5` and requires reviewed user and CI access. CPU Small and
GPU Shared (5 GiB) are interactive Hub choices.

For the GPU pilot, one active GPU workload is allowed per canonical person
across CPS, CIT, and batch, with one waiting batch submission. A CI key
submitting GPU work must map to a verified quota owner. When you request an
interactive session, the gateway holds your queued batch or requests a
checkpoint from your running batch. If checkpoint acknowledgement is still
missing after 120 seconds, batch keeps running and the interactive request
continues waiting. Check workflow status for the waiting reason. A resumable
workflow must persist its checkpoint outside the container filesystem.

For the pilot, a checkpoint client uses an authorized gateway credential
for the workflow owner. The gateway supplies the submission ID in
`CPS_GPU_BATCH_SUBMISSION`. Use `cps_compute.sdk.checkpoint_request()` to
read the current attempt and deadline, then call
`acknowledge_checkpoint(attempt=..., deadline=..., reference=...)`
after persisting the checkpoint. The resumed attempt reads the stored
reference from `CPS_GPU_BATCH_CHECKPOINT`. A stale acknowledgement returns
HTTP 409. Confirm how the pilot will provide the checkpoint client with
an authorized credential before running a checkpointable job.

For a fixed GPU share, KAI accounts for the requested memory using NvFractions.
The operator-managed Fractioning stack and required NRI plugin handle runtime
device assignment and memory enforcement. Tenant submissions specify the
gateway profile. The gateway renders the GPU requests and runtime settings.
Whole-device profiles request integer GPUs. Production SM sharing and elastic
VRAM borrowing have separate qualification gates.

## Operator examples

The [KAI fixture](../examples/batch-gang-job.yaml) illustrates the older direct
Kubernetes scheduling contract for operator testing. Its MPS settings represent
the historical path. The active tenant gateway owns queue selection, admission,
and workload creation.

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

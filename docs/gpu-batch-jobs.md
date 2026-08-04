# Running GPU Jobs Without an Interactive Session

This covers submitting Kubernetes Jobs directly via `kubectl` -- for
long-running or unattended GPU work you don't want tied to a live
JupyterHub notebook session (multi-day training runs, sweeps, anything
that shouldn't die when you close your laptop or your notebook gets
culled for inactivity).

## Getting kubectl access (prerequisite)

Batch jobs are **not** submitted from inside a JupyterHub notebook pod --
you need your own kubeconfig:

1. Log into Rancher at <https://rancher.dshl.unileoben.ac.at>.
2. Select this cluster, then use Rancher's **Kubeconfig File** download
   (top-right of the cluster's dashboard) and save it locally (e.g.
   `~/.kube/config`, or point `KUBECONFIG` at it).
3. Permissions are granted via Rancher's Cluster/Project **Members** tab,
   bound to your Authentik group name (group-name matching is manual, not
   autocompleted -- see `docs/rancher-authentik-sso-plan.md`). If
   `kubectl` commands come back `Forbidden`, ask a cluster admin/
   technician to add you to the appropriate group -- there's no
   self-service group-membership flow today.

This is separate from your JupyterHub login -- no kubeconfig or
Job-creation permissions are issued to JupyterHub notebook pods (see
**Future work** below).

## All supported combinations

Two independent axes -- how the job shares (or doesn't share) a GPU, and
whether it's a single pod or a gang-scheduled distributed job -- cover
every supported combination. Each row below is a working, ready-to-adapt
example under
`cluster-maintenance/clusters/cit-cps-gpu/system/gpu/kai-scheduler/examples/`:

| GPU mode | Topology | Framework | Example file |
|---|---|---|---|
| MPS-shared (fractional `gpu-memory`) | Single pod | Generic/any | `batch-gang-job.yaml` (`single-gpu-mps-shared-job`) |
| Full-exclusive (`nvidia.com/gpu: 1`) | Distributed gang (multi-pod) | Generic/any | `batch-gang-job.yaml` (`distributed-gang-job`) |
| Full-exclusive | Single pod | PyTorch | `pytorch-single-gpu-training-job.yaml` |
| Full-exclusive | Distributed gang (DDP via `torchrun`) | PyTorch | `pytorch-multi-gpu-training-job.yaml` |
| Full-exclusive | Single pod | TensorFlow | `tensorflow-single-gpu-training-job.yaml` |
| Full-exclusive | Distributed gang (`MultiWorkerMirroredStrategy`) | TensorFlow | `tensorflow-multi-gpu-training-job.yaml` |

Two hard rules to keep in mind when adapting any of these:

- **`gpu-memory` (MPS-shared) and an integer `nvidia.com/gpu` limit are
  mutually exclusive on the same pod.** Use one or the other, never both
  -- combining them defeats sharing and isn't how KAI's upstream examples
  are structured.
- **A multi-pod distributed job needs an explicit `PodGroup`.** KAI's
  podgrouper webhook only auto-creates a `PodGroup` for a single pod; for
  gang-scheduled jobs (all pods start together or none) you need your own
  `PodGroup` resource, with each worker pod annotated
  `pod-group-name: <podgroup-name>` and
  `kai.scheduler/skip-podgrouper: "true"`.

## Required label/annotation/priorityClass quick reference

| Queue | PriorityClass | Use |
|---|---|---|
| `courses` | `kai-course-high` | Course/student work |
| `phd-interactive` | `kai-phd-interactive` | General/PhD interactive |
| `batch` | `kai-batch-low` | Batch jobs (this doc's focus) |
| `ci` | `kai-ci-lowest` | GPU-requesting CI |

Source: `kai-policy/priorityclasses.yaml` and `kai-policy/queues.yaml` in
the path below. See `kai-policy/README.md` for the full policy rationale
(note: that README's own values table has drifted from the live YAML in
places -- trust the YAML files, not the table, if they ever disagree).

## Checkpointing

Batch-queue jobs can be evicted at any time the cluster is busy -- see
["User-facing implication: jobs can be killed, always checkpoint"](gpu-scheduling-architecture.md#user-facing-implication-jobs-can-be-killed-always-checkpoint)
in the GPU Scheduling Architecture doc for the rationale and a concrete
PyTorch checkpoint/resume example. The same requirement applies here:
checkpoint periodically to shared storage (not local/ephemeral), and
resume from the latest checkpoint on restart.

## Deep dive / full reference

For the complete rationale, the gang-scheduling contract details, and the
MPS-memory-enforcement caveat (`CUDA_MPS_PINNED_DEVICE_MEM_LIMIT` must
match the `gpu-memory` annotation -- KAI schedules against the annotation
but does not enforce it), see:

`cluster-maintenance/clusters/cit-cps-gpu/system/gpu/kai-scheduler/docs/batch-job-submission.md`

and the example manifests + their own README in
`cluster-maintenance/clusters/cit-cps-gpu/system/gpu/kai-scheduler/examples/`.

## Future work

Submitting batch Jobs from inside a running JupyterHub notebook pod
(instead of via a separately-issued Rancher kubeconfig) is **not
supported today**. The notebook pod's service account (`dask-sa`) only
has RBAC for Dask CRDs in the `dask-compute` namespace
(`cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/dask-rbac.yaml`)
-- no permissions on `batch/v1 Jobs` or KAI `PodGroup`s. Enabling this
would require either broadening that RBAC or issuing users their own
scoped ServiceAccount token inside the notebook; noted here as a roadmap
item, not designed further.

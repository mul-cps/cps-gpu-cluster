# CPS Compute Platform Evolution

> **Status:** proposed architecture and implementation backlog. This document
> makes no live configuration change. The GitOps manifests remain the source
> of truth for the current deployment.

## Baseline verified in this repository

The cluster currently runs KAI Scheduler `v0.16.3`. Its production hierarchy
is rooted at `default-parent-queue` and has `courses` (GPU quota 4),
`phd-interactive` (GPU quota 2, weight 10), `batch` (quota 0, weight 2),
`ci` (quota 0, weight 1), and `default`. JupyterHub authenticates through
Dex and intentionally uses `preferred_username` so existing PVC-backed home
directories remain continuous.

The current public scheduling architecture still says `phd-interactive` has a
quota of 1.5 and a weight of 2. That is documentation drift: the live policy
manifest is authoritative and specifies 2 and 10 respectively.

Kubernetes Descheduler is also already deployed. Its global priority threshold
of 11 makes only priority-10 batch work eligible; priority-50 interactive and
priority-90 course work are structurally protected.

## Target separation of responsibilities

```text
Dex identity -> JupyterHub -> CPS control plane -> KAI Scheduler -> A100 pool
                         |              |
                  Submit as Job     cps-notifier
```

- **JupyterHub** provides authenticated interactive sessions and preserves its
  established username/PVC compatibility contract.
- **CPS control-plane services** derive trusted workload identity, allocation,
  queue, priority and provenance; users do not submit arbitrary scheduler
  labels, priorities or manifests.
- **KAI** remains the only tenant-fairness, quota-reclaim, priority and GPU
  placement scheduler.
- **cps-notifier** reduces raw Kubernetes, KAI, Hub, quota and storage events
  to durable user-facing domain transitions, then delivers them through Hub,
  Gotify and approved external channels.

Normal research batch belongs below the same per-user parent as that user's
interactive and desktop workloads. This prevents one person competing twice:
once through an interactive tree and again through an unrelated global batch
tree. Opportunistic sweeps/backfill remain a separate, low-weight branch.

## Migration shape

Preserve the current top-level guarantees first, then extend underneath them:

```text
default-parent-queue
|- courses (quota 4)
|  `- course -> user -> interactive | batch
|- phd-interactive (quota 2, weight 10)
|  `- allocation -> user -> interactive | desktop | normal-batch
|- batch (quota 0, weight 2)
|  `- user -> opportunistic | sweep
|- ci (quota 0, weight 1)
`- default
```

Time-based fair share is a later qualification step, after per-user queues
exist. It may influence surplus distribution but must not replace guarantees,
PriorityClass policy, or a separately enforced GPU-hour/storage quota.

## Product boundaries

`Submit as Job` is a trusted Hub-authenticated service. It records image
digest, command, working directory, Git revision and dirty state, mounts,
resources, allocation, submitting user and timestamp. It creates a workload
that continues after JupyterHub is stopped.

Remote desktop has two separate profiles: CPU uses XFCE/TigerVNC/noVNC; GPU
uses XFCE/Xpra/VirtualGL and must prove KAI allocation, CUDA, `nvidia-smi`,
and a hardware NVIDIA OpenGL renderer rather than llvmpipe.

The notifier emits reduced events such as `job.queued`, `job.started`,
`job.completed`, `job.failed`, `job.preempted`, wait-reason transitions,
session idle transitions, and compute/storage quota thresholds. It requires a
durable state store and outbox. Gotify personal routing uses a user-owned
application/token reference held only by the notifier; no Gotify token is
placed in a notebook or submitted job.

## KAI and Descheduler qualification

First qualify KAI `0.16.3 -> 0.17.x` against the existing conformance suite.
Until evidence shows KAI alone retains acceptable multi-GPU placement,
interactive startup latency and utilization, retain Descheduler solely as a
batch-only GPU-consolidation actuator. A/B test with `LowNodeUtilization`
disabled before deciding whether to remove it.

## Evidence gates

No proposal above is complete from a rendered chart, HTTP response, or
successful rollout alone. Each implementation issue must define and collect
live evidence for identity/PVC continuity, KAI queue accounting and reclaim,
real GPU occupancy, persistent job completion after Hub shutdown, notification
delivery/deduplication, and the relevant security boundary.

## Related implementation issues

See the production repository issue tracker for the umbrella, controller,
notifier, Submit-as-Job, desktop, quota/dashboard, KAI hierarchy, KAI upgrade,
Descheduler qualification and documentation-drift issues created with this
document.

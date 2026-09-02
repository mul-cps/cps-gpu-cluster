# Karta as the CPS Workload Description Layer

> **Status:** proposed; do not deploy Karta independently of a KAI version
> qualification. Karta is not a scheduler and does not replace KAI policy.

## Decision

Adopt Karta with the qualified KAI 0.17.x upgrade as a GitOps-managed,
cluster-admin-owned catalog of workload definitions. Use it for advanced CRDs
and leave ordinary `Pod` and Kubernetes `Job` workloads on KAI's simple path.

```text
Submit as Job -> workload CRD -> Karta definition -> KAI PodGroup/SubGroups
                                      |                    |
                              status/tree discovery     scheduling
                                      |
                         notifier and dashboard adapters
```

Karta supplies a declarative description of a workload's pod templates,
components, replica counts, group/gang boundary and status locations. KAI
continues to make fairness, quota, reclaim, priority and placement decisions.

## Uses in CPS

- Advanced Submit-as-Job types such as JobSet, PyTorch, Ray, MPI and
  LeaderWorkerSet can share one workload abstraction instead of requiring a
  separate in-house adapter for every CRD.
- KAI can derive generic PodGroups/SubGroups and gang/topology information
  from vetted definitions.
- `cps-notifier` and the usage dashboard can consume normalized workload state
  and tree information rather than duplicate CRD-specific status parsers.
- Trusted CPS services can apply policy metadata to every discovered pod
  template consistently, including `schedulerName: kai-scheduler`, the KAI
  queue, allocation and immutable CPS identity labels.

## Non-goals

Karta does not replace KAI Scheduler, per-user queue fairness, Dex identity,
GPU-hour or storage quota enforcement, the CPS controller, Submit-as-Job,
notifier, Gotify, or the dashboard. It reduces per-workload CRD adaptation;
it is not a user-controlled scheduling API.

## Security and version boundary

Users may submit approved workload kinds but must not create or alter Karta
definitions. Definitions disclose where pod templates and status fields live,
how replicas are grouped, and potentially how metadata is modified; they are
therefore infrastructure policy, reviewed and delivered by Fleet GitOps.

Pin the Karta CRD/API revision to the version tested by the selected KAI
release. Do not pair KAI 0.17.x with an arbitrary newer pre-1.0 Karta release.
The KAI upgrade issue must record the exact KAI image/chart and Karta module or
CRD revision qualified together.

## Rollout gate

1. Qualify KAI 0.17.x without changing fair-share policy.
2. Install only the corresponding Karta CRD/API revision.
3. Add a small GitOps catalog, starting with one workload type (JobSet or
   PyTorchJob).
4. Demonstrate workload CRD -> Karta -> KAI PodGroup/SubGroup generation.
5. Verify queue/priority metadata reaches every actual pod template.
6. Verify normalized terminal status and topology are sufficient for notifier
   and dashboard use.
7. Keep plain Jobs on the existing simple path unless the extra abstraction is
   materially useful.

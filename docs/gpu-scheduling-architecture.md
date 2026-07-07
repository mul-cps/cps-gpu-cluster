# GPU Scheduling Architecture

This is the single source of truth for how GPU scheduling actually works on
this cluster: KAI Scheduler internals, the three-tier priority/queue model,
NVIDIA MPS-based sharing, and the "elastic unified pool" design. It exists
because the mechanisms here were pieced together the hard way, through real
incidents (see `docs/troubleshooting.md`) — this doc consolidates the
verified facts in one place instead of leaving them scattered across
incident write-ups.

Every scheduler-internals claim below was checked against the actual
KAI-Scheduler Go source (not secondhand descriptions) at the version
confirmed running on this cluster. File paths and line-level behavior are
cited so they can be re-verified.

## Verified version (2026-07-07)

| | Value |
|---|---|
| Repo-pinned (`cluster-maintenance/.../system/gpu/kai-scheduler/fleet.yaml`) | `oci://ghcr.io/kai-scheduler/kai-scheduler/kai-scheduler` @ **v0.14.6** |
| Live cluster (`kubectl get pods -n kai-scheduler -o jsonpath='{...spec.containers[*].image}'`) | every component image tag: **v0.14.6** (`admission`, `binder`, `operator`, `scheduler`, `podgrouper`, `podgroupcontroller`, `queuecontroller`, all `ghcr.io/kai-scheduler/kai-scheduler/...`) |

**Repo-pinned and live match: v0.14.6.** A claim surfaced mid-session that
v0.12.10 was "the exact version actually running" — that claim is **false**;
it was not corroborated by a live check and is contradicted by the
`kubectl` output above (checked 2026-07-07). The GHCR org for this chart
is `ghcr.io/kai-scheduler/kai-scheduler` (moved from `ghcr.io/nvidia/kai-scheduler`
at some point before this check); the upstream source repo is
`github.com/NVIDIA/KAI-Scheduler` (an org-to-org redirect currently exists
from `kai-scheduler/KAI-Scheduler` to `NVIDIA/KAI-Scheduler` — clone
either, they resolve to the same commit history). All source citations
below are against the `v0.14.6` tag of that repo.

## Why MPS, not MIG

- The A100s in this cluster are PCIe-passthrough to Proxmox VMs, not
  bare-metal with DRA-capable firmware paths. NVIDIA's DynamicMIG DRA
  feature (on-demand MIG geometry changes without a reboot) is excluded on
  this hardware/virtualization combination.
- Without DynamicMIG, changing MIG *mode* (MIG-enabled vs MIG-disabled) or
  geometry requires a full GPU reset that, on these passthrough VMs, a
  plain in-guest reboot does not reliably deliver — see
  `docs/troubleshooting.md` ("MIG mode toggle needs a REAL reset").
  That makes static MIG partitioning workable but MIG-based *elastic*,
  on-demand sharing impractical: you cannot flip a GPU between "3x sliced"
  and "whole" fast enough to respond to actual demand.
- MPS has none of that constraint: it shares one physical GPU across
  processes at the CUDA-context level, with no GPU mode change, and works
  identically whether the workload later needs 1 GPU or wants to burst to
  a multi-GPU job on the same node.
- Conclusion: all 4 GPU workers run in **full (non-MIG) mode permanently**;
  sharing for small/interactive workloads is done entirely via MPS,
  arbitrated by KAI Scheduler's fractional GPU-memory model, not MIG.

## Why three priority tiers with these specific values

| PriorityClass | Value | Queue | GPU quota | overQuotaWeight | Use |
|---|---|---|---|---|---|
| `kai-course-high` | 90 | `courses` | 4 | 1 | Course/student Jupyter, small fixed MPS slices (3-5 GiB) |
| `kai-phd-interactive` | 50 | `phd-interactive` | 1.5 | 2 | General/PhD interactive Jupyter, larger or full-GPU |
| `kai-batch-low` | 10 | `batch` | 0 | 10 | Batch jobs, pure burst/opportunistic filler |
| (implicit) | — | `default` | unlimited | 10 | Fallback for unlabeled workloads |

Source: `cluster-maintenance/clusters/cit-cps-gpu/system/gpu/kai-scheduler/kai-policy/priorityclasses.yaml`
and `.../kai-policy/queues.yaml`.

**Quota semantics for `gpu-memory`-annotated (MPS-fractional) pods are
fractional, not integer-per-pod (source-verified, v0.14.6, 2026-07-07).**
A bound pod's charge against its queue's GPU quota is
`count × ceil((gpuMemory / MemoryOfEveryGpuOnNode) * 100) / 100`
(`getGpuMemoryFractionalOnNode` /  `GetRequiredInitQuota` /
`setAcceptedResources` in `pkg/scheduler/api/node_info/node_info.go`),
tallied into `Queue.Status.Allocated` via the pod's post-bind
`AcceptedResource`, not its raw pre-bind resource request. Concretely: on
this cluster's 40960 MiB A100s, a 5120 MiB MPS session charges only
`ceil(5120/40960*100)/100 = 0.13` quota-units, so `courses`' `quota: 4`
guarantees roughly `4 / 0.13 ≈ 30` concurrent 5 GiB sessions, not 4. Do
not read a queue's numeric `gpu.quota` as "N whole GPUs / N pods" for
MPS-shared workloads — see `docs/troubleshooting.md`'s "can 30 concurrent
5GB student MPS sessions actually run?" entry for the full derivation and
the real blocker that was found instead (a JupyterHub pod-spec bug
combining `nvidia.com/gpu` and `gpu-memory` on the same pod, which the
KAI admission webhook rejects outright, independent of quota math).

**Load-bearing constraint: all three values are deliberately kept under
100.** This is not an arbitrary numbering choice — it is required by KAI's
own behavior. `DefaultPriorityClass`/queue logic in KAI treats any pod
whose PriorityClass value is `>= 100` as **non-preemptible**, and
non-preemptible pods are additionally hard-capped at their queue's
*deserved* quota — they can never burst over quota regardless of
`overQuotaWeight`. This was discovered via a real incident: a `batch`
pod was originally assigned priority `1000`; since `batch`'s GPU quota is
deliberately `0` (batch is pure-burst, it "owns" nothing), a non-preemptible
`batch` pod could never be scheduled at all — every attempt failed with
`NonPreemptibleOverQuota`. Confirmed live 2026-07-06; full incident in
`docs/troubleshooting.md`. The fix was rescaling all three PriorityClass
values below 100 (90 / 50 / 10), preserving the same relative ordering
(course > interactive > batch) while keeping every tier preemptible and
able to participate in the burst/reclaim model below.

Relative spacing (90 vs 50 vs 10) reflects intent, not a hard constraint
KAI enforces beyond ordering: courses need to reliably displace anything
else on demand (highest, closest to the 100 ceiling with headroom),
interactive PhD work sits in the middle (can be reclaimed by courses, can
itself reclaim from batch), and batch is bottom with `quota: 0` — it only
ever runs in genuinely idle capacity and yields first.

`cpu`/`memory` quota dimensions mirror the `gpu` shape per queue (any
unspecified resource dimension defaults to `quota=0, limit=0` in KAI — a
hard cap, not just "unguaranteed" — so every queue explicitly sets
cpu/memory alongside gpu; see the comment block at the top of
`kai-policy/queues.yaml` and the "CPU/memory hard cap" incident in
`docs/troubleshooting.md`).

## Why an elastic unified pool, not a static node/GPU split

The alternative design would statically partition nodes/GPUs: e.g. some
GPUs always in MPS-sharing mode for courses, others always plain/exclusive
for PhD/batch multi-GPU jobs. This cluster does **not** do that — any of
the 8 physical GPUs can serve either an MPS-shared course/interactive pod
or a genuine exclusive/multi-GPU pod, arbitrated automatically by KAI's
own reservation-pod mechanism.

**Verification status: executed and confirmed, not just planned.** An
earlier design-time assumption ("no single device-plugin config can serve
both request types, a static split is required") was tested live, found to
be wrong on retest, and the cluster was subsequently rolled out cluster-wide
on the elastic model. See `docs/troubleshooting.md`, section "RESOLVED
(corrected, 2026-07-06): MPS-shared and multi-GPU-exclusive requests DO
coexist on the same node" for the full test log, and the following
"UPDATE (2026-07-06, later same day): rolled out cluster-wide" section for
the production rollout (switching `gpu-operator/values.yaml`'s
`devicePlugin.config.default` to a `plain` key, with the
`nvidia.com/mps.capable=true` node-label fix needed to keep the MPS control
daemon alive). As of this writing that rollout is live cluster-wide.

**Does `reclaim` itself honor this unified-pool model, or are exclusive and
fractional workloads secretly two separate reclaim pools?** Checked against
source 2026-07-07 (see `docs/troubleshooting.md`, "RESOLVED (2026-07-07):
does `reclaim` cross the exclusive vs. fractional boundary?" for full
citations): no type-pool separation exists in KAI `v0.14.6`. The
node-level predicate (`node_info.go:345-366`,
`isTaskAllocatableOnNonAllocatedResources`) counts any freed whole GPU —
including one vacated by evicting an *exclusive* `nvidia.com/gpu`-only
victim — toward satisfying a *fractional* `gpu-memory` requester's
device-count need, via the `nodeIdleOrReleasingWholeGpus` term. Neither the
victim-candidate filter nor the queue fair-share gate discriminate by
request style either. This is consistent with (and reinforces) the elastic
unified pool design above: reclaim, not just plain `allocate`, treats all 8
GPUs as one arbitrable pool regardless of how they're currently claimed.
**Caveat:** this is a source-verified mechanism finding, not yet re-confirmed
by a clean live test — see the troubleshooting entry for why (cluster was
fully saturated by real workloads and scheduler log verbosity was too low to
capture the decision path during the one live attempt made so far).

Why this matters operationally: it means capacity is not wasted holding a
GPU "reserved for course use" while idle, nor "reserved for batch" while a
course session is queued — the same physical GPU inventory serves all
three tiers, and KAI's bin-packing (below) decides case by case whether a
given GPU should host several small shared sessions or one exclusive job.

## The KAI action pipeline

Default action list and execution order, confirmed in
`pkg/scheduler/conf_util/scheduler_conf_util.go:37`:

```
"allocate, consolidation, reclaim, preempt, stalegangeviction"
```

Each action also carries a numeric priority (higher runs first), confirmed
in `pkg/apis/kai/v1/schedulingshard_types.go:118-119`:

```
allocate=500, consolidation=400, reclaim=300, preempt=200, stalegangeviction=100
```

```
┌─────────────────────────────────────────────────────────────────────┐
│                     KAI scheduling cycle (per session)                │
│                                                                         │
│   pending pod                                                         │
│       │                                                               │
│       ▼                                                               │
│  ┌──────────┐  placed?──yes──▶ done, pod bound                       │
│  │ ALLOCATE │  (fits on an idle/fitting GPU as-is, no disruption)     │
│  └────┬─────┘                                                        │
│       │ no                                                            │
│       ▼                                                               │
│  ┌──────────────┐  placed?──yes──▶ done, pod bound                   │
│  │ CONSOLIDATION│  (KAI reshuffles/repacks OTHER already-running     │
│  └────┬─────────┘   pods to free room — no cross-queue/priority      │
│       │ no           eviction, just bin-packing existing workloads)  │
│       ▼                                                               │
│  ┌──────────┐  placed?──yes──▶ done, pod bound (victim(s) evicted,   │
│  │ RECLAIM  │  (cross-queue: pull back capacity a DIFFERENT queue     │  cross-queue)
│  └────┬─────┘   borrowed over its fair share — e.g. courses           │
│       │ no       reclaiming from phd-interactive or batch)            │
│       ▼                                                               │
│  ┌──────────┐  placed?──yes──▶ done, pod bound (victim(s) evicted,   │
│  │ PREEMPT  │  (same-queue only: higher-priority job in the SAME      │  same-queue)
│  └────┬─────┘   queue displaces a lower-priority job in that queue)   │
│       │ no                                                             │
│       ▼                                                               │
│  ┌──────────────────┐                                                 │
│  │ STALEGANGEVICTION│  evicts gang-scheduled jobs stuck partially     │
│  └──────────────────┘  allocated past a timeout, to unblock others    │
│       │                                                               │
│       ▼                                                               │
│  still pending → retried next scheduling cycle                        │
└─────────────────────────────────────────────────────────────────────┘
```

Why the order matters: cheaper, less-disruptive strategies are always
attempted before eviction. `allocate` tries the simple case first (does
this pod fit somewhere with zero side effects). `consolidation` still
causes zero *cross-workload* disruption in the priority/quota sense — it
only repacks pods that are already free to move, e.g. onto more-filled
GPUs (see bin-packing plugins below), before anything is evicted. Only if
neither succeeds does the scheduler resort to `reclaim` (taking back
over-fair-share capacity from another queue) and only after that fails
does it fall through to `preempt` (same-queue, lower-priority job in the
same queue gets displaced). `stalegangeviction` is the last-resort cleanup
for stuck gang jobs. A pod exits the pipeline the moment any stage
successfully places it — it does not continue through later, more
disruptive stages once satisfied.

### Reclaim vs. preempt: cross-queue vs. same-queue (source-verified)

This is the mechanism that makes the three-tier model actually work, and
it is a real code-level distinction, not just a naming convention:

- **`reclaim` is cross-queue only.** In
  `pkg/scheduler/actions/reclaim/reclaim.go`, the victim-candidate builder
  (`getOrderedVictimsQueue`, lines ~123-143) explicitly *excludes* jobs in
  the reclaimer's own queue:
  ```go
  for _, job := range ssn.ClusterInfo.PodGroupInfos {
      if job.Queue == reclaimer.Queue {
          continue
      }
      if !ssn.ReclaimVictimFilter(reclaimer, job) {
          continue
      }
      ...
  }
  ```
  This is the exact mechanism by which the `courses` queue can displace
  `phd-interactive` or `batch` (different queues) — a pending course pod
  can only ever *reclaim* from a queue it is not itself in.

- **`preempt` is same-queue only.** In
  `pkg/scheduler/actions/preempt/preempt.go`, `buildFilterFuncForPreempt`
  requires the candidate victim's queue to match the preemptor's queue,
  and its priority to be strictly lower:
  ```go
  if job.Priority >= preemptor.Priority {
      return false
  }
  if job.Queue != preemptor.Queue {
      return false
  }
  ```
  So `preempt` only ever resolves priority conflicts *within* one queue
  (e.g. two different-priority workloads both submitted into `batch`);
  it never reaches across queues — that job belongs entirely to `reclaim`.

`Reclaimable`-ness itself (whether a reclaimer is even allowed to reclaim
right now) is gated by fair-share accounting in
`pkg/scheduler/plugins/proportion/reclaimable/reclaimable.go`
(`CanReclaimResources`): a reclaimer can only reclaim while its own queue's
allocation-plus-request stays within its fair share, and non-preemptible
reclaimers are additionally capped at the queue's deserved share — this is
the same `>=100 → non-preemptible` mechanic from the priority-tier section
above, applied on the reclaiming side too.

**Important refinement (source- and live-verified 2026-07-07, see
`docs/troubleshooting.md`'s "can inflating phd-interactive's quota armor
it against reclaim" entry): the victim side of the decision is gated the
same way, by quota/fair-share headroom, with no priority comparison
anywhere.** `pkg/scheduler/plugins/proportion/reclaimable/strategies/strategies.go`'s
`GuaranteeDeservedQuotaStrategy` explicitly refuses to reclaim from a
queue whose current usage is at or under its own deserved quota,
regardless of the reclaimer's priority; `MaintainFairShareStrategy`
likewise only allows reclaiming from a queue that is over its own
(fair-share-adjusted) allocatable share. Read together with the
reclaimer-side gate above, this means: **priority class value never
directly decides which queue gets reclaimed from — it only decides
ordering/eligibility to attempt reclaim at all (via the scheduler action
priorities and `preempt`'s in-queue priority check); the actual
victim-selection decision is 100% quota/fair-share arithmetic.** A
concrete, practical consequence for this cluster: a queue's GPU `quota`
must track real expected usage, not be rounded up "to be safe" —
inflating a lower-priority queue's quota well above its actual usage can
make its running jobs immune to reclaim by a higher-priority queue for as
long as usage stays under the inflated ceiling, silently defeating the
`courses` (90) > `phd-interactive` (50) > `batch` (10) priority ordering
this whole design relies on. Prefer raising `overQuotaWeight` (which only
affects how *surplus* capacity is split, not a reclaim-proof floor) over
raising `quota` itself if more headroom is wanted.

## Bin-packing / placement scoring

Three plugins jointly decide *where* a fitting pod lands, all
source-confirmed at v0.14.6 (default plugin priorities from
`deployments/kai-scheduler/crds/kai.scheduler_schedulingshards.yaml:145`:
`gpupack/gpuspread=300, nodeplacement=200, gpusharingorder=100`):

- **`gpupack`** (`pkg/scheduler/plugins/gpupack/gpupack.go`): for
  fractional/MPS placements, scores a candidate GPU by
  `node.GetUsedGpuPortion(gpuIdx)` — the *more* of a GPU's memory is
  already claimed, the higher (better) the score. This directly biases new
  MPS pods toward GPUs that already host other MPS sessions rather than
  spreading onto empty ones.
- **`gpusharingorder`** (`pkg/scheduler/plugins/gpusharingorder/gpusharingorder.go`):
  adds a bonus score when a node already has a compatible shared-GPU group
  the pod can join (`node.IsTaskFitOnGpuGroup`), reinforcing the same
  "join an existing shared GPU" preference at the node-selection level.
- **`nodeplacement`** (`pkg/scheduler/plugins/nodeplacement/nodeplacement.go`):
  general resource-packing plugin, defaults both GPU and CPU strategies to
  `BinpackStrategy` unless explicitly overridden to `SpreadStrategy` via
  plugin arguments (`New()`, lines ~34-45). This cluster does not override
  it, so GPU placement is binpack by default.

**Why this matters for this cluster's specific goal:** small course/MPS
sessions should pack tightly onto GPUs that already have MPS sessions
running, preserving whole/mostly-free GPUs for large PhD/interactive or
batch jobs that need real P2P/exclusive multi-GPU access. Eviction
(reclaim/preempt) is meant to be a genuine last resort — only reached when
bin-packing and consolidation truly cannot place a pending higher-priority
pod anywhere.

### Concrete before/after packing example

```
BEFORE                                                       
┌─────────────── GPU0 (40 GiB) ───────────────┐  ┌── GPU1 (40 GiB) ──┐  ┌── GPU2 (40 GiB) ──┐
│ course-pod-A (5G) │ course-pod-B (4G) │ free │  │  phd-large (40G)  │  │  batch-job (40G)  │
│      MPS          │       MPS         │ 31G  │  │  exclusive, full  │  │  exclusive, full  │
└───────────────────────────────────────────────┘  └───────────────────┘  └───────────────────┘
queue: courses (used ~9G of 4-GPU quota)            queue: phd-interactive   queue: batch
                                                     (used 1 of 1.5 quota)   (used 1, quota=0,
                                                                              pure burst)

Scenario A — new small course pod arrives, requests gpu-memory: 4G
  → gpupack scores GPU0's partially-used GPU higher than GPU1/GPU2 (which
    are full anyway) → ALLOCATE succeeds, pod packs onto GPU0's free 31G.
  → No eviction needed. Whole/mostly-free capacity elsewhere untouched.

AFTER (scenario A)
┌─────────────── GPU0 (40 GiB) ───────────────────────┐
│ course-A(5G) │ course-B(4G) │ course-C(4G, NEW) │ free 27G │
└──────────────────────────────────────────────────────┘

Scenario B — a burst of course pods fills GPU0 entirely, and courses'
queue is still under its fair share, but a NEW course pod can no longer
fit on GPU0 (full) or any other GPU (GPU1/GPU2 fully claimed by
phd-interactive/batch exclusive jobs):
  → ALLOCATE fails (nothing fits as-is).
  → CONSOLIDATION fails (nothing else can be repacked to free room; the
    other two GPUs hold single exclusive jobs, not fragmentable shares).
  → RECLAIM: courses (different queue) is within fair share and entitled
    to reclaim from either phd-interactive or batch (different queues from
    courses) per the fair-share check in reclaimable.go. batch has
    quota=0 and is the designated pure-burst/lowest tier, so it is
    reclaimed from first in practice — the batch-job pod on GPU2 is
    evicted, freeing GPU2 entirely for the new course pod (oversized for
    the need, but the only reclaim target that fits).
  → The phd-large pod on GPU1 is left untouched — reclaim only evicts as
    many/whichever victims the solver's scenario search finds sufficient
    to satisfy the pending pod; it does not preemptively also evict GPU1
    if GPU2 alone satisfies the request. (Which specific victim(s) get
    picked when more than one is eligible is exactly the open question in
    the next section — here there is only one plausible candidate, batch,
    so it's not itself illustrative of the general case.)
```

## RESOLVED (2026-07-07): consolidation vs. reclaim — which one actually defragments already-running work, and victim selection

**Status: source-verified against the actual v0.14.6 code (`github.com/NVIDIA/KAI-Scheduler`
tag `v0.14.6`) AND confirmed with a live synthetic test on this cluster.
This replaces the previously-open "intelligent victim selection" question
below with a concrete, evidence-backed answer.**

### Does `consolidation` evict/relocate already-*running* lower-priority pods, or only repack pending work?

Source says it *can* target running work: `buildPreemptibleFilterFunc`
in `pkg/scheduler/actions/consolidation/consolidation.go` builds its
victim candidate set with `job.IsPreemptibleJob()` and
`job.GetActiveAllocatedTasksCount() == 0 → excluded` — i.e. candidates
must have at least one *already-running* task, not just be pending. This
is gated by `ssn.GetMaxNumberConsolidationPreemptees()`
(`consolidation.go:36`, `if ... == 0 { skip }`), which defaults to **16**
(`cmd/scheduler/app/options/options.go:38,114`,
`defaultMaxConsolidationPreemptees = 16`, flag
`--max-consolidation-preemptees`). This cluster's live `SchedulingShard/default`
has no `args`/`actions` overrides (confirmed via
`kubectl get schedulingshard default -o yaml`), so consolidation runs at
this default — **enabled, out of the box, no config change was needed or made.**

However, **consolidation's scenario-feasibility check requires victims to
be *reallocated* (moved to another node), not merely deleted**:
`allPodsReallocated()` (`consolidation.go:120-129`) fails the scenario if
any victim task is still `pod_status.Releasing` — i.e. consolidation is a
genuine *repacking* pass: it only succeeds if there is somewhere else for
the victim to go. If the cluster has no spare capacity to relocate a
victim to (true on this 4-node/8-GPU cluster whenever the other GPUs are
also full), consolidation will report "Didn't find a consolidation
strategy" even though evicting the victim outright would free the needed
capacity.

### Live test (2026-07-07, synthetic pods, cleaned up after)

1. Filled `k3s-wk-gpu2` and `k3s-wk-gpu3` each down to 1 free GPU with
   two synthetic `kai-batch-low`/queue=`batch` filler pods, leaving free
   GPUs fragmented 1(gpu2)+1(gpu3)+1(gpu4) — no node with 2 free, same
   shape as the real 2026-07-07 `gpu-pytorch-dual` incident.
2. Submitted a synthetic 2-GPU pod at `kai-phd-interactive`/queue
   `phd-interactive`. Scheduler logs showed **consolidation entered every
   cycle and logged "Didn't find a consolidation strategy"**; **reclaim
   also failed** ("Didn't find a reclaim strategy") — because
   `phd-interactive`'s queue was already at/over its fair share
   (`queue phd-interactive` quota=1.5, already `allocated: nvidia.com/gpu: 2`
   at test time), and `reclaimable.Reclaimable`/`CanReclaimResources`
   (`pkg/scheduler/plugins/proportion/reclaimable/reclaimable.go:30-42`)
   unconditionally blocks reclaim once
   `allocatedResources.Add(requestedResources)` would exceed
   `reclaimerQueue.GetFairShare()`, independent of physical GPU
   availability. This is a real, source-confirmed gate distinct from
   physical placement feasibility.
3. Deleted that pod, resubmitted the same 2-GPU request at
   `kai-course-high`/queue `courses` (quota 4, effectively idle at test
   time — plenty of fair-share headroom). Result, from live scheduler
   logs and cluster events:
   - `consolidation` again logged **"Didn't find a consolidation
     strategy"** — consistent with the repacking constraint above: there
     was nowhere free to relocate the batch filler pods *to*.
   - `reclaim` succeeded: `reclaim/reclaim.go:92` logged *"Reclaimed
     resources for job ... evicting reclaimee tasks:
     <[.../consol-test-filler-gpu3]>"*, and the k8s event confirmed
     `Evict: Pod .../consol-test-filler-gpu3 was preempted by workload
     .../pg-consol-test-pending-2gpu-b...`. The pending 2-GPU `courses`
     pod was then bound to the now-fully-freed `k3s-wk-gpu3`
     (`Successfully allocated ... Creating bind request for task ...
     to node <k3s-wk-gpu3>`).

### Conclusion

**It is `reclaim` (`pkg/scheduler/actions/reclaim/reclaim.go`), not
`consolidation`, that performs the active defragmentation this cluster
actually needs.** Reclaim evicts a lower-priority, different-queue,
already-running pod outright (no requirement to relocate it anywhere) to
free physical capacity for a pending higher-priority job — exactly the
"evict the `ablator-*` batch job so both free GPUs land on one node"
behavior wanted for the `gpu-pytorch-dual` scenario, and it already works
today with the cluster's existing/default KAI config (courses(90) >
phd-interactive(50) > batch(10) priority tiers, batch quota=0). No config
change was required or made — this is default v0.14.6 behavior, verified
live.

`consolidation` is a real, separate mechanism that also targets
already-*running* preemptible jobs (not just pending ones, correcting the
prior framing of this question) — but it is a strict bin-*repacking* pass
that only succeeds when a victim can be moved elsewhere; on a
tightly-packed cluster with no spare node capacity it is expected to keep
losing to `reclaim`, which needs no such relocation target. Both actions
are gated by the `proportion` plugin's fair-share accounting
(`reclaimable.go`), which blocks a request from over-drawing its own
queue's fair share regardless of physical GPU availability — a
requester's own queue being over quota, not a lack of physical capacity,
can be why a "there's obviously a free GPU that would satisfy this" case
still doesn't schedule.

**Residual, lower-priority gap (not exercised live, flagged from source
only):** `buildPreemptibleFilterFunc` in `consolidation.go` filters
victims solely via `job.IsPreemptibleJob()` (priority < 100 → default
`Preemptible`, `pkg/apis/scheduling/v2alpha2/podgroup_types.go:85`), with
**no check that the victim's own priority is lower than the preemptor's**.
Since this cluster's three tiers (courses=90, phd-interactive=50,
batch=10) are *all* under the 100 threshold, all three are `Preemptible`
by this default rule, so in principle a lower-priority pending job could
target a strictly-higher-priority running job as a consolidation victim.
In practice this is constrained by (a) `reclaim`'s separate,
priority/queue-independent fair-share gate above, and (b) queue-order and
job-order traversal generally favoring the higher-priority queue's own
pending jobs first — but there is no explicit "victim priority <
preemptor priority" guard in the consolidation code path itself. This is
a real, narrow gap worth a future look (e.g. an explicit non-preemptible
`spec.preemptibility` override on `courses`/`phd-interactive` PodGroups if
this ever becomes a practical problem), not something fixed in this
pass.

## Known caveat: MPS memory limit is per-process, not per-pod

`CUDA_MPS_PINNED_DEVICE_MEM_LIMIT` (set by KubeSpawner to match KAI's
`gpu-memory` scheduling annotation — see `docs/troubleshooting.md`'s MPS
sections for the full env var / hostPath wiring) is enforced by the MPS
control daemon **per CUDA client process**, not per pod. A pod that spawns
multiple CUDA-using processes (e.g. a notebook that forks several worker
processes, or launches more than one training script) can have *each*
process independently claim up to the configured limit — so a pod's
*aggregate* VRAM usage can exceed its intended tier if it runs more than
one CUDA client concurrently.

This is an **open risk**, particularly for the less-trusted student/course
track, since course sessions get the smallest, most tightly-packed slices
(this is exactly the tier where over-claiming most directly harms
neighbors sharing the same physical GPU).

- **Current accepted mitigation**: an informal "one CUDA kernel/process per
  session" expectation for course workloads — not technically enforced,
  just the operating assumption.
- **A stronger fix, if ever built**, would look like: aggregate
  per-pod/per-cgroup GPU memory usage monitoring (e.g. via
  `nvidia-smi`/DCGM per-process stats correlated back to pod) with
  automatic kill/eviction of a pod whose combined CUDA client usage
  exceeds its tier — not implemented today.

## Diagrams

### 1. Three-tier priority/queue hierarchy

```
                    ┌─────────────────────────────┐
                    │      queue: courses          │
                    │  kai-course-high, value 90    │
                    │  gpu quota: 4, weight: 1       │
                    └───────────┬───────────────────┘
                                │  reclaim (cross-queue, highest
                                │  priority tier pulls back capacity
                                │  from any other queue over its
                                ▼  fair share)
                    ┌─────────────────────────────┐
                    │   queue: phd-interactive      │
                    │  kai-phd-interactive, value 50 │
                    │  gpu quota: 1.5, weight: 2      │
                    └───────────┬───────────────────┘
                                │  reclaim (phd-interactive can in
                                │  turn reclaim from batch, and can
                                │  itself be reclaimed FROM by courses)
                                ▼
                    ┌─────────────────────────────┐
                    │       queue: batch             │
                    │  kai-batch-low, value 10        │
                    │  gpu quota: 0, weight: 10        │
                    │  (pure burst/opportunistic       │
                    │   filler — owns no guaranteed    │
                    │   capacity, yields first)        │
                    └─────────────────────────────┘

  preempt arrows (same-queue only, not drawn as cross-tier): within any
  one of these queues, a higher-priority job submitted to that SAME queue
  can preempt a lower-priority job already running in that same queue.
  preempt never crosses the queue boundaries drawn above — only reclaim
  does.
```

### 2. Action pipeline flowchart

See "The KAI action pipeline" section above for the annotated box diagram
(allocate → consolidation → reclaim → preempt → stalegangeviction, each
stage's placed?/no branch shown explicitly).

### 3. Concrete packing example

See "Concrete before/after packing example" above.

## Related docs

- `docs/troubleshooting.md` — full incident write-ups this doc draws on:
  MIG mode/reset behavior, MPS setup and enforcement gotchas, the
  PriorityClass `>=100` incident, the CPU/memory quota-gap incident, and
  the elastic-pool coexistence test (both the flawed first pass and the
  corrected/rolled-out result).
- `cluster-maintenance/clusters/cit-cps-gpu/system/gpu/kai-scheduler/kai-policy/README.md` —
  quick reference for how to route a workload to a queue/priority class.
- `cluster-maintenance/clusters/cit-cps-gpu/system/gpu/kai-scheduler/kai-policy/priorityclasses.yaml`
  and `queues.yaml` — the live source of truth for current values (verify
  these directly if this doc and the manifests ever appear to disagree —
  the manifests win).

# GPU2 second physical card: bounded six-gate review

Operator review accepted the retained six measured gate scopes for GPU UUID
`GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6`, Node `k3s-wk-gpu2`,
boot `a464df41-e391-4443-b8e8-ad7ecd052318`, driver generation
`4ebffc96-e25e-4583-a3b8-0d853fd90efd`, driver 615.71.09.

The candidate is limited to 5/10 GiB profiles, two workspaces and 15 GiB
aggregate. It is an evidence artifact, not an installed ConfigMap or permission
to start a workload. No device mode, driver, kernel or live policy was changed.

## Evidence and independent verification

The six reviewer-composed receipts preserve hashes of 65 original source files.
The primary agent independently recomputed all 65 source hashes and each receipt
hash against `qualification.json`. Capacity evidence preserves its separate
original sources. The real v3 qualification codec also accepted the candidate
under a clearly synthetic CPU-only ConfigMap identity; that identity is neither
published here nor used as an API object.

- Cap assignment: fresh original 5/10 GiB journals and seals, independent cap
  inventory, exact Pod/spec/device identities, both identity init results.
- OOM/peer: both directions reject over-cap allocation, preserve peer progress
  and recover ordinary allocation.
- Aggregate: same-parent held allocations reach the cap, reject excess and
  recover while the ordinary peer continues.
- MPS: bounded over-cap rejection and 282 peer progress iterations; original
  MPS process lifetimes and cap rows are clean after termination.
- Restart/cleanup: same Pod, replacement container/PID, cap readback,
  post-restart OOM/recovery/peer progress, exact retirement.
- Memory import: both-direction CUDA IPC and VMM denial, same-parent positive
  controls and owner-exit charge retention; managed allocation returns typed
  CUDA 801 while ordinary allocations before/after succeed.

## Preserved caveats

The earlier incorrect-CDI attempt was a hold, not a pass. The fresh controller's
nonzero final empty-accounting check is retained; an independent continuation
verified the original seals and exact cap inventory without rerunning the
controller. The restart observer rejected the expected restart count of one;
actual API/process identity and post-restart measurements establish that scope.
Raw MPS and managed receipts retain their review-pending/production-false fields;
these summaries record the reviewed bounded assertions without rewriting them.
Managed source-patch/errno attribution is not an additional gate in the measured
public CUDA API contract and is not claimed here.

Raw host/kernel/process captures remain private. Source paths in receipts are
local evidence pointers, not downloadable public artifacts.

## Remaining deployment boundary

This closes review of these hardware measurements, not the complete platform.
KAI-selected placement, immutable compiler/selection publication, automatic Node
consumption, cross-Hub membership accounting and connected lifecycle acceptance
must still pass for the installed combination. The first physical GPU's proof
is separate; this evidence does not qualify the other six cluster GPUs.

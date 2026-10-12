# Current 5/10 GiB cap, MPS and terminal supplement

This separate 2026-10-12 supplement reviews the actual CPS 5 GiB / CIT 10 GiB
memory-cap, peer-continuity and private two-client MPS measurements, followed by
normal Stop and exact restoration of eight temporary fixture records. It leaves
the initial [import report](README.md) and [measurement](measurement.json)
unchanged. Complete isolation, general GPU access, production, 20 GiB and
SM compute distribution remain unqualified.

[cap-mps-terminal-supplement.json](cap-mps-terminal-supplement.json) binds the
terminal inputs and protected evidence by raw SHA256. The notebook image,
current Pod lifetimes, policy `d48f6553…`, controller model `630d43cc…`, selected
GPU and protected seals remain the exact scope of the initial measurement.
No MIG operation was performed.

| Actual measurement | Retained result |
|---|---|
| Cross-pod 10 GiB cap | 9,728 MiB held; typed OOM at a 9,984 MiB attempt; CPS peer completed 342 ticks and recovery succeeded |
| Same-pod aggregate cap | 6,912 MiB victim plus 2,048 MiB holder and a working peer; typed OOM at a 7,168 MiB victim attempt; 342 peer ticks and recovery succeeded |
| Physical held samples | A 30-second held window was verified for each cap trial; native charges stayed within the two finite caps' 15 GiB total |
| Private CIT10 MPS | Two non-root clients alternated allocations to 9,216 MiB; CUDA result 2 at 9,472 MiB; both clients recovered while the CPS peer completed 282 ticks |
| MPS identity and cleanup | Four exact host PID/start/namespace/parent lifetimes were attributed; both clients exited 0; private daemons and host endpoint processes were absent after cleanup |
| Final authority | Exact seals and 23 prior finite retirements remained unchanged; both target charges returned to zero |

The MPS probe used the pinned raw CUDA client and checked 256-element vector
kernel goldens with bias 37 inside the probe. Individual vector values were
not retained as external result arrays. These memory-cap and MPS measurements
do not establish enforced SM compute distribution or creator-exit retention.

The retained Root terminal receipt is dated 20:13:39 UTC. CPS normal Stop
returned HTTP 200 and the workspace was stopped; CIT normal Stop reported a
stopped workspace and inactive reservation. The shutdown ledger contains 37
released allocations. All 38 inventory entries on the **selected GPU** were
offline with zero charge; the two current rows kept their original finite
5/10 GiB limits. This is not a statement about every GPU in the cluster.

Independent direct Pod reads at 20:17:22 UTC returned success with empty
`--ignore-not-found` results for both exact target Pods. The post-restoration
raw cap inventory is byte-identical to the shutdown capture. Both sources'
restoration responses exactly match their original two memberships and two
grants, including all original fields, sources and expiries: eight records,
zero remaining changes. This does not qualify a whole Hub database restore.

The captured profile API requests returned HTTP 200. The unscoped request
returned the two CPU profiles; the CPS `native-group-b` workspace context also
returned the enabled `interactive-shared-5` profile. This is backend permission
and source context, not proof of browser rendering.

The separate [status API record](status-api-record-20261012.json) captures CPS
HTTP 200 with the limited 5/10 GiB pilot assessment updated at 20:16:02 UTC.
CIT's configured mounted status read had the same state, title and timestamp.
The assessment declares a 15-minute lifetime, ending at 20:31:02 UTC; this
capture does not prove a later refresh or the state after expiry. Browser
rendering and human OAuth were not verified by this report.

All earlier counterexamples, including the failed v3 VMM staging trial, remain
preserved. Protected original captures and fixture identities remain private;
only sanitized summaries and evidence hashes are committed. This report made
no live API calls, GPU operations or activation changes.

Follow the canonical [compute operations guide](../../../../../docs/compute-platform/operations.md)
and [measurement protocol](../README.md) for the remaining gates: SM compute
distribution, creator-exit retention, 20 GiB and maximum-profile overhead,
production packing and broader rollout.

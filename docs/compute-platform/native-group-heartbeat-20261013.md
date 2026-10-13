# Native group heartbeat, acknowledgment and abort-release fixes — 2026-10-13

**Normal GPU sharing passed for the two existing approved CPS/CIT workspaces.**
The [source qualification record](native-group-heartbeat-20261013.json) pins
the SDK fix and deployed gateway image. The byte-pinned
[sanitized lifecycle receipt](native-group-normal-lifecycle-20261013.receipt.json)
records the normal audited Start/Stop path for CPS 5 GiB and CIT 10 GiB.
This qualifies those existing approved fixtures; broader group availability
and production qualification remain pending.

SDK commit `ed9777ea9361587d185228268f73c5c7bf59bb7c` includes the acquisition
fix `601ecb9b172d6eabcd7bd77e8200e02132d5541f` and registration fix
`6a490c2dca19b853ca2df175925328cab8c6af49`. Synchronous native acquisition and
registration authority checks and SQLite transactions run in worker
threads. Fresh Source, node-document and reservation checks keep their
existing order, including the authorizer inside the reservation transaction.
The async ledger CAS and neutral-owner checks remain in place. No
acknowledgment TTL, readiness cache, profile or GPU configuration was changed.

The preceding SDK revision `bfe20f29d73804966043de30f484d72a6cd7112d`
performed repeated synchronous four-component readiness reads on the gateway
event loop. In the two-member source fixture, initial native acquisition
performed 117 readiness observations and four node-reference observations,
equivalent to 2,420 named Kubernetes GETs with the full reader. This delayed
the acknowledgment heartbeat the acquisition checks depended on. A synthetic
2 ms observation delay and 40 ms acknowledgment lifetime reproduced native
HTTP 422 after a successful generic reservation, with no heartbeat renewal
during the native request. These timings describe the offline regression,
not cluster performance.

The repaired handler passes the same regression with heartbeat renewal and
HTTP 200. An expired proof still produces HTTP 422 without a native ledger
claim. Repeated cancellation retains acquisition ownership until the
reservation worker finishes, preventing shutdown from racing a late commit.
The existing packing race test now uses a bounded two-arrival CAS barrier to
exercise its intended same-revision conflict deterministically.

Both normal release routes also require fresh immutable abort custody before
releasing members of an operator-aborted attempt. A released ledger flag
alone is insufficient. Missing, replaced or changed abort records, changed
enrollment references and an existing Pod retain the reservation. The repair
does not publish cleanup, change the ledger or bypass unfinished enrollment.

The complete SDK source suite passed **1,497 tests, with three existing skips**,
as reported by the release operator. Independent focused verification passed
76 native authority, reservation and aborted-release tests on the pinned
revision. The three skips remain unexecuted checks.

Node source `c62ef06c251c001a3b996168f1d84581f2990ff0` fixes a separate
publication race. A new valid immutable enrollment could arrive after a
complete custody pass and before acknowledgment publication, causing the
node to exit and its acknowledgment to expire. Only a fully validated
append of current-reference enrollments now triggers an immediate new
complete custody iteration. Changed, removed, duplicate and foreign
enrollments still fail. Mounted document, process, epoch and original
journal checks remain mandatory. No acknowledgment TTL or cache changed.
The operator reports 132 source tests passed without skips. Independent
publisher verification passed eight tests with one safe-capture test skipped.
An append detected before the acknowledgment CAS publishes no acknowledgment;
an append detected after a successful CAS is handled by the next full pass.

The gateway image under acceptance is
`ghcr.io/mul-cps/cps-compute@sha256:eb964da6de7b46884c1168a1c69abc5489e50f9eca5690943d84a0543d935db4`.
The operator reported all four real component proofs ready at
`2026-10-13T14:51:11.79+00:00`, under registry revision
`sha256:45d00c4cdbbd0617dfb64abebf4d279d274ccace324756cb75a1fa49f7cf14a5`
and the unchanged 30-second acknowledgment TTL, after restoring the node
publisher. This is a timestamped readiness observation.

The operator verified recovery at `2026-10-13T14:29:14+00:00` using source
`2253bab90d9ad0ff61933b6b3ce441d0d2273312`. The held fence repeatedly proved
zero GPU memory, clients, compute applications and target Pod tasks while
preserving all 35 raw journals and 42 physical rows. Original cleaned-history
receipts were verified. An immutable abort was published, and full UID,
resource-version and ledger-data checks released only the failed attempt;
the other 45 allocations were unchanged. The restored node recorded the
original protected abort completion. Normal Source close then confirmed no
Hub server and an inactive member reservation with no remaining attempt.
The JSON record pins the abort UID, body hash and audit hash. These are
operator-reported live facts; this report has not independently inspected
the private receipt.

The operator reported acquisition HTTP 200 and Pod
creation on the earlier acquisition-only fix, followed by registration HTTP
422; native release and Source close initially returned HTTP 409. The failed
attempt was recovered. A subsequent Start on the latest SDK reached
registration HTTP 422 when the node publication race made its acknowledgment
stale. The second attempt was also recovered with all 35 historical journals
and 42 physical rows preserved, no target journal or gate, and zero GPU
memory, applications, clients and target tasks. Normal Source close confirmed
no Hub server or active member lease. The original two members and two grants
were restored exactly. The fixed node was running and all four component
proofs were subsequently ready at the timestamp above.

The fresh normal CPS 5 GiB Start passed at `2026-10-13T14:50:06+00:00`.
The actual Pod `fd3fb4ed-34c5-40fb-b31b-f8a79f20c302` was running with gate
exit code zero and a 5,120 MiB native cap. Source reported the workspace
running without a notice and the expected member reservation active.
The operator also read back the sealed physical cap: pinned, online, and
5,368,709,120 bytes for both soft and hard limits. The JSON record pins its
exact native binding, original inode and reservation attempt. These are
operator-reported facts; no private receipt was inspected by this report.

The normal CIT 10 GiB Start then passed. Both actual workspaces ran together
on `k3s-wk-gpu2`, on the same physical GPU, with sealed online 5,120 and
10,240 MiB caps. Each held the correct group Share, had a ready Hub server,
and allocated, filled and freed a bounded 64 MiB GPU buffer. Direct user
Shares remained absent. The receipt binds the actual Pod identities,
reservation attempts and native allocation keys to these observations.

CPS Stop confirmed shutdown, revoked its Share and released its member
reservation while the same CIT Pod stayed ready and completed another
64 MiB GPU allocation. CIT Stop then confirmed shutdown, revoked its Share
and released its member reservation. Both consoles restored their original
two memberships and two grants exactly. Final cleanup confirmed both Pods
absent, all 49 native allocations released, no online caps, every physical
row at zero use and both observed GPUs at zero MiB. Both journals retained
their original `retired-inert-cap` custody.

The sanitized receipt was captured at
`2026-10-13T15:05:40.910607+00:00`; its exact byte hash is
`sha256:de7f7ae434889538092dba11577dbc739ce30763e46adcd5ef5a765e966a4a35`.
It was independently checked against the report's limited acceptance fields.
No private activation files were inspected. This run covers normal audited
application paths with operator authentication; human browser OAuth was not
tested. New-console-group approval delivery, general group GPU access,
compute-percentage enforcement, the eight-GPU fleet and distributed
workloads remain unqualified. Existing controlled isolation evidence and
the broader [platform acceptance gates](qualification.md) remain separate.

# Abort an unacknowledged native policy handover

This is the operator procedure for abandoning a partially published native
policy handover before any target acknowledgment or allocation. It is a
separately reviewed recovery operation, **not an existing automated SDK abort
API**, an ordinary delivery retry, or an image-tag rollback. Use it together
with [deployment and recovery](operations.md). A different observed state needs
a new reviewed recovery plan.

The outcome below describes one actual execution reported by Root on
2026-10-21. Its canonical evidence destination is the
[abort receipt](../../platform-staging/gpu/native-group-pilot/current-group-kai/evidence/20261021-addon-handover-aborted.json),
which is published separately by Root. This single execution does not qualify
arbitrary policy rollback, a completed or acknowledged handover, or rollback
while native work is active.

## Preconditions and stop conditions

Before the first mutation, freeze the exact old and target policy catalogs,
Source revisions, all four immutable approval references, pointer payloads and
UIDs, consumer configurations, permission rules, and delivery journal bytes in
a reviewed plan. Its digest must bind the complete expected preimages, not just
generation numbers. Keep configuration containing credentials in private
operator storage; publish only reviewed, sanitized evidence.

All of the following must hold throughout recovery:

- Sources remain fenced, Binder admission is disabled, and the normal delivery
  writer and handover operator Jobs are stopped. Target-capable publishers are
  stopped and their owned Pods are confirmed absent before ACK absence is used.
  A retained old Node must be independently pinned to its unchanged old
  configuration, head and physical epoch; it cannot act as a target publisher.
- Every actual allocation is released. Reservations and workspace bindings are
  empty, and an independent fresh external quiescence check returns literal
  `True`. An empty database alone does not prove external quiescence.
- Fresh reads authenticate all four ACK object identities and payloads after
  publishers stop, then repeat the check before mutation. No target-policy ACK
  may exist, even an expired one. Missing readiness is not proof of missing
  ACKs. Unknown receipts, replacement objects, read errors, or evidence that a
  target ACK was published stop this procedure.
- The journal remains pending, its completed prefix is unchanged, and every
  selected pointer is either its exact journaled prior value or its exact
  journaled target value. There is no foreign pointer, unrecorded publication,
  target allocation, or completed target handover.
- The original anchor, checkpoint, all retained archives, and the archived
  completed predecessor state authenticate byte for byte. The predecessor is
  restored from those bytes; counters and history are never reconstructed.
- Both SQLite writer locks and the existing exclusive delivery-journal lock
  can be held for their respective recovery mutations. No second recovery or
  normal writer may overlap.

Any mismatch leaves the fences in place. Do not add a permissive
`AlreadyExists`, stale-preimage, or "already rolled back" fallback.

## Reviewed execution order

There is no atomic transaction spanning Kubernetes, SQLite and the journal
filesystem. The recovery packet must record durable phase completion and
exact readbacks so an interruption can be resumed under the same abort identity.
Neither a partial failure nor a retry authorizes service restoration.

1. **Preserve the failed attempt.** Create and durably seal an immutable private
   abort capsule and an independently verified off-cluster copy before rollback.
   Include the pending journal, its new archives, complete retained-archive
   manifest, original anchor/checkpoint, exact predecessor state/configuration,
   SQL history/head, and pointer/ACK/permission/configuration preimages. Record
   the reviewed plan digest and operator identity. Keep the failed immutable
   approvals and policy/software proofs; they remain historical evidence.

2. **Revert only the published selection.** With both database writer locks
   held, recheck the complete revision-row digest and current head, empty
   reservations/bindings, external quiescence, ACK absence and all four pointers.
   Restore only the journaled promoted pointer using UID, resourceVersion and
   complete data-preimage JSON Patch tests. The observed recovery used the
   delivery ServiceAccount and a temporary admission exception restricted to
   the exact pointer identity and old/target payloads. Do not weaken the general
   monotonic pointer policy or grant a general rollback permission. Read back
   all four selections.

3. **Audit the Source-head reversal.** A new explicit recovery transaction CASes
   the SQL head from the exact target revision to the exact retained predecessor.
   It appends a distinct abort audit event binding actor, plan digest, old/target
   policies and both revisions. Retain the target revision row, every prior
   revision and audit, grants, business data and schema. Recheck complete
   retained rows, exact head, empty reservations/bindings and fresh quiescence
   before commit. Exceptions must roll back the SQL transaction. A failed
   cross-system phase still leaves admission fenced.

4. **Restore configuration and permissions.** Use exact UID/resourceVersion and
   complete field-preimage CAS for each reviewed consumer configuration and
   controller spec. Restore the four operator reader Roles to the predecessor
   journal's exact `pregrants`; leftover target-only GET names can make the old
   writer reject its state. Any temporary admission bridge must allow only the
   exact typed field change, and the original admission policy must be restored.
   Restart consumers that observed the target head: an existing Reader's
   antirollback state must not be bypassed to accept a lower generation.

5. **Restore journal custody.** Under the existing exclusive journal lock,
   atomically replace `state.json` with the exact authenticated predecessor
   archive bytes and durably verify the result. Do not alter the anchor,
   checkpoint, earlier archives, or completed history. Only after preserving
   and verifying the failed attempt may its now-unreferenced new archives move
   to a separate audited sibling backup directory. Insert no abort fields into
   the SDK's closed journal schema. The external capsule records the abort; it
   does not become current readiness authority.

6. **Prove restored operation before opening access.** Verify full restored
   controller specs and actual Ready owner chains, the original policy/epoch,
   genuine four-component ACKs for the restored selection, and the full journal
   through the unchanged read-only SDK validator. Remove temporary recovery
   permissions and Pods and confirm their absence. Require an ordinary normal
   writer tick to return Ready with its exact restored configuration and
   checkpoint. Only then restore the captured Source Service specs and normal
   admission settings. Preserve protected notebook UIDs, containers, storage and
   GPU state throughout.

## Recorded 2026-10-21 outcome

The actual attempt appended Source generation 9 and left delivery handover 68
pending. Only Gateway's pointer selected generation 9; the other three still
selected generation 8. Target consumers could not become Ready because of a
historical cohort-validation defect. No target ACKs or allocations were accepted.

Root's recovery passed 31 focused checks: nine recovery-guard cases, nine real
two-database SQL cases, and thirteen journal rejection cases, followed by actual
server dry-runs. The completed recovery recorded:

| Boundary | Restored and retained evidence |
| --- | --- |
| Selection and SQL | Delivery-SA Gateway pointer CAS 9 to 8 under both database locks; audited SQL head 9 to 8; all ten revision rows retained, including aborted generation 9 |
| Journal | Exact completed state 67 and all 335 prior archives retained; original anchor/checkpoint unchanged; five failed-attempt archives preserved in audited sibling backup |
| Configuration | Four reader Roles restored; original admission policy restored; six old controller full specs Ready |
| Independent validation | Full read-only SDK journal validation and four actual old-policy ACKs Ready |
| Normal operation | Thirteen temporary RBAC/Pod objects deleted before the ordinary normal-writer tick returned Ready; all five Service full specs restored |
| Preserved workload | Protected notebook UID unchanged with zero restarts; no MIG, driver or GPU-work changes |
| HTTP checks | CPS login route returned 200; CIT returned 302. These route checks do not constitute a new browser-login or GPU-workload qualification |

The private capsule has an off-cluster backup. That fact alone does not qualify
the separate full-platform disaster-recovery or connected restore gates.

## Future release and retry constraints

Aborted revision 9 remains immutable forensic history; it must not be deleted,
rewritten, relabeled as current, or treated as a successful publication. Ordinary
policy-upgrade APIs require exactly one generation advance and a target revision
that is absent. With head 8 restored and revision 9 retained, simply invoking the
same upgrade again is unsupported. Reusing the exact aborted revision or choosing
a new generation requires a separately reviewed explicit protocol and tests.

Before another attempt, qualify the historical-cohort fix on the actual normal
Gateway, Hub, Node and observer/writer consumer paths, not only an operator image
or synthetic plan. Capture fresh actual references and preimages; do not reuse
this incident's UID/resourceVersion or temporary admission exception.

Future release rollback qualification must cover target ACK appearance, running
publishers, active reservations/bindings, pointer and SQL CAS conflicts, complete
history drift, altered archives/anchor/checkpoint, permission/configuration
drift, late quiescence failure and interruption after each durable phase. A
completed handover, any acknowledged target, schema migration, or active native
workload needs its own recovery design. This one unacknowledged abort does not
prove those cases safe.

## Staged exact-revision retry tooling

The [2026-10-21 tooling receipt](../../platform-staging/gpu/native-group-pilot/current-group-kai/evidence/20261021-aborted-source-reuse-tooling.json) records the separately reviewed SQL kernel and operator-only image. The [application API documentation](https://github.com/mul-cps/cps-compute/blob/859a814139ea89939b18f66a90b38a0a4d3ce3d8/docs/native-addon-policy-transition.md) describes its exact-row reuse and audit contract. This staged qualification did not reselect Source revision 9.

The operational [physical observer](../../platform-staging/native-approval-delivery/aborted_reuse_guard.py) checks the sealed abort capsule, reviewed paused successor specs, permissions, heads, ACKs, allocation ledger and authenticated Node epoch. It rejects active publisher ServiceAccount Pods and nonterminal publisher Jobs, including pending Jobs without Pods. Pod/Job LISTs must be complete; continuation or remaining items cannot establish absence.

Root must independently seal and pin the exact successor plan/capsule, provide fresh Source quiescence, and bind this real observer into both SQL boundaries. The observer must not recurse into Source APIs or databases while the two writer locks are held. A synthetic test, descriptor hash, or read-only rejection of the currently open system does not authorize the live operation. Use a separately reviewed operator identity and exact permissions; never use this operator image for normal consumers.

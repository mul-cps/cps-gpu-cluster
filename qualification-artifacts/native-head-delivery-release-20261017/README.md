# Dynamic head delivery release candidate — 17 October 2026

Latest: [live head advancement](live-head-advance-result.json) verifies a real
owning-source approval update from generation 6 to 7. All four current consumers
acknowledged the new revision without restarting during the update; the continuous
writer recovered after the expected fail-closed propagation interval. This is
not a GPU workload start or sealed-peer continuation/revocation test.

A subsequent [live coordinator activation](coordinator-activation-attempt-result.json)
passed fresh actual/prospective observer rendering but failed startup validation:
the authenticated current head contains five PVC claims, while the Gateway's
older static authority contains four. The previous Gateway spec was restored
exactly and is Ready; all four component acknowledgements verify. Both Hub
rollouts remain unapplied and the binder bridge remains disabled. Dynamic-head
claim validation is the next required fix; shrinking the authorized head is not
a solution.

The [coordinator staging checkpoint](coordinator-staging-result.json) verifies 17
created configuration/RBAC objects and two immutable Hub settings objects. The
Gateway and both Hub Secret/Deployment patches passed server dry-run. Independent
review found and regression-tested inherited SGID and initializer-retry faults;
the corrected Gateway/Hub materializers pass focused tests. No Gateway/Hub rollout
or binder bridge activation has occurred at this checkpoint. Matching Gateway
SQLite and both Hub PostgreSQL backups were captured, but not restore-tested.

Production admission and original-journal adoption remain verified by the
[earlier live delivery record](live-delivery-result.json). Sealed-peer
continuation/revocation and the remaining no-MIG GPU and full production gates
are still open. The records below are historical checkpoints.

Source `551379c6902791d0dd192596046669f1fe274562` implements the automatic
approval producer and explicit legacy-journal adoption. The full SDK/Hub matrix
passed 3,282 tests and 49 subtests (three environment-specific skips); the addon
scope passed seven tests and 19 subtests (three skips). All six skipped cases
were subsequently run in their required environments. All four exact-source CI
jobs succeeded in run `39019600947`.

SDK wheel SHA-256: `7b38c882b8c76ed4faccaa20fb8aea0c05af036d61a6149ce8d935762d6c2c05`.
Hub wheel SHA-256: `2ee2475c06e33731b3e7ed132911ca53198af4ccb4954133279e3e71f5932fc2`.
The actual installed Node image passed six CPU-only functional cases; all 72 SDK
modules matched the qualified wheel. These are not GPU hardware tests.

The four image receipts record published registry manifests and config digests,
independently read back from GHCR. These receipts describe publication time. The subsequent [live adoption](live-adoption-result.json) now verifies all four component consumers and the observer on those successor images.

The actual staging receipt proves five immutable objects and a held bootstrap
were created and bound using actual Kubernetes identities. Five immutable
candidates first passed API-server dry-run. Staging changed no process, activated
no GPU, preserved the four personal notebook Pods and retained GPU2's cordon.
Private configuration/Secrets, snapshots and original migration journals remain
outside Git. These receipts intentionally contain no raw authority documents.

At publication, remaining work was matching database backups and writer quiescence; coordinated image adoption;
actual four-component ACK checks; one-time v4 head adoption and original-journal
migration; continuous delivery and no-MIG GPU lifecycle qualification. The Job
renderer and dynamic delivery renderer passed 74 source checks together. Runtime
migration, production admission, wider GPU caps/routes/MPS, cross-Hub bursts,
recovery and full production release remain open.

The coordinated v3-compatible rollout completed at 2026-10-17T09:30:17.418103+00:00. Both public installed Gateway readiness calls verified all four actual fresh ACKs. All seven observer permission bindings verified before Node release. Three pre-upgrade database backup Jobs succeeded. Four personal Pods and all 117 released claims were preserved, with empty SQL reservation/binding tables. The old delivery writer remains paused for the explicit v4 migration; no dynamic-head or new GPU hardware qualification follows from this rollout.

## Subsequent v4 staging

Four fixed pointers, four immutable anchors, three binding files and the v4
Node configuration have now been CREATEd and validated from actual UID/RV
readbacks. All candidates first passed server dry-run. SDK validation read 17
actual named ConfigMaps, reconstructed the v4 Node configuration and consumed
all four initial heads. The Gateway readiness candidate retains the exact old
ACK/process/epoch authority. These steps changed no process or GPU activation;
the live cohort still uses the verified v3-compatible configuration. See
[v4 staging](v4-stage-result.json) and [validation](v4-validation-result.json).
Sixteen bootstrap/readiness source tests passed, including five new checks
observed failing before the helper implementation and passing afterward.
The coordinated v4 capture/observer/runtime rollout and journal migration are
still required; actual Root reads do not prove service-account permissions.

The coordinated runtime helper now has nine CPU tests, plus 16 bootstrap tests
(25 total), independently rerun during review. Review found no blocking
Secret-preservation, authority, readback or CAS issue. Two further actual staged
objects hold the new Node bootstrap and immutable capture v2 seed. The four
Deployment patches and Gateway runtime Secret patch all passed server dry-run.
See [runtime staging](v4-runtime-stage-result.json) and
[API dry-run](v4-runtime-dryrun-result.json). This does not establish observer
composition, runtime migration, new GPU access or journal adoption.

## Verified live v4 adoption

The [live v4 receipt](v4-live-adoption-result.json) supersedes staging-only state.
All four controllers are Ready with exact proposed specs; the installed Gateway
consumer verifies four genuine v2 acknowledgements. The actual observer has no
pending changes across its seven fixed Role targets. The
[authenticated HTTPS Source export](v4-source-freshness-result.json) passes the
SDK packet validator and still matches generation 6 in all four initial heads.

The actual-state observer render used 63 actual named ConfigMaps, seven actual
Roles and four actual controllers, and passed server dry-run before activation.
Its final release digest is
`sha256:0272704ce1749a4debc425543a38a66f94351b66eb797f7ac577f2a039a9fd64`.
The earlier prospective digest is historical planning evidence, not this release.
The source matrix (bootstrap, runtime composer, observer composer and observer
renderer) passes 77 tests. Independent reviewers separately passed their 25,
67 and 17-check selections, with no blocking findings; these counts are not
added together as unique tests.

The maintenance guard initially stopped before restarting controllers because
Kubernetes inserted `defaultMode: 420` into the seven new ConfigMap volumes.
The helper now emits that exact effective mode explicitly; a new regression
failed before this fix and passed afterward. Root verified full stored and
server-returned spec equality for all four controllers, regenerated the observer
template hash, and resumed without weakening the equality guard.
[Defaulting correction](v4-defaults-verified-result.json).

Three matching pre-upgrade database backup Jobs succeeded. Four protected
personal Pods, all 117 released claim records, empty SQL reservation/binding
tables and GPU2's cordon were preserved. No driver change, reset, reboot, MIG
configuration or new GPU hardware qualification occurred. The original delivery
writer remains paused. Original-journal adoption, continuous delivery, remaining
GPU lifecycle gates and full production qualification are still open.

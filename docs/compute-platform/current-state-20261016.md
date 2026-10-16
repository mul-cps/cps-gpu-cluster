# CPS/CIT current state — 16 October 2026

The platform remains **limited-pilot**. Production qualification and the full
project are unfinished. This record supersedes current-state statements in the
older completion ledger; their dated acceptance results remain historical evidence.

## Verified deployment and recovery

Gateway `9e695015` from compute source `de90610f` is now deployed. Both Hubs
retain `e906c9ab`, JupyterHub 5.5.2, KubeSpawner 7.1.0 and chart 4.4.2. Both
separate admin consoles now run consumer `dbaad518` with Core `de90610f` and
their original separate databases. All 16 source-closure modules match in both
live Pods; both are Ready with zero restarts. Their backup images are aligned
and new matching backups passed independent checksum/SQLite integrity checks.
Policy `d48f6553` and the existing driver, NFS paths and canonical mappings remain
unchanged. The gateway deployment changed; the Hub deployments did not restart.

The gateway checks each acknowledgment against the clock after its API reads.
The approved freshness limit changed from 30 to 60 seconds: actual node
acknowledgments had exceeded 30 seconds during complete custody checks. Stale
and future acknowledgments still fail validation. Four-process readback and the
new controller journal passed. The old journal remains retained.

Normal Source Start of `shared-gpu-lab` returned HTTP 200 and Running. Its new Pod
is Ready with zero restarts, a pinned native 5 GiB hard/soft cap, one binding and
three global member reservations. The workspace-scoped admin API exposes
`interactive-shared-5` with `nativeGroupReady=true`. All 45 readiness samples
over 80 seconds passed. Five existing personal Pod UIDs, readiness and zero
restart counts were preserved. The temporary operator token was revoked.

This verifies start and cap assignment. It does **not** repeat CUDA execution,
two-browser RTC, OOM isolation, or GPU916 SDK/addon acceptance. GPU916's ordinary
SDK/addon compatibility remains an open problem. The replacement notebook531
has not completed current 5+20 GiB qualification.

The scheduled gateway backup image and `BACKUP_IMAGE` now match `9e695015`.
A pre-change backup and a new matching-image backup passed checksums and
read-only SQLite integrity checks. Their files were retained; only their owned
completed Jobs/Pods were selected for cleanup. Connected and off-host restore
qualification remain open.

See the [bounded adoption receipt](../../platform-staging/jupyter-extensions-20261013/gateway-clock-readiness-adoption-actual-20261016.json)
for immutable image identifiers, journal/plan hashes and evidence boundaries.

## Full plan status

| Area | Implemented or demonstrated | Still required |
| --- | --- | --- |
| Ownership and policy | Separate application/deployment repositories and shared policy | Integrate and promote a complete tested consumer matrix |
| Hubs and consoles | Stable baseline, two persistent consoles, local management APIs/UI | Complete current-release identity/group migration, instructor boundaries, grant expiry/login survival |
| Identity and sharing | Reviewed aliases; live retained student sessions preserve visitor identity and exact personal-server sharing | CIT Mikasa/Armin mapping, full directory coverage, removal of existing connections |
| Dynamic GPU groups | Historical bounded native R615/cgroup isolation; current 5 GiB group Start and cap assignment restored | Current 5/20 GiB qualification, broader packing and all runtime variants; no MIG |
| Shared reservations | Historical cross-Hub contention/retry; current three-member reservation | Live different-member partial-conflict rollback and full lifecycle/revocation matrix |
| Account/session APIs | All six API families, grants and pooled allowance | Effective permission/membership information and live allocation, age, idle/lifetime projection |
| SDK and notebook jobs | Actual CPS CPU success/failure, parameters, helper files, logs, executed artifacts and ownership checks | Current GPU/shared-kernel/CIT matrix |
| Hera and distributed jobs | Ordinary inline Hera DAGs/steps/scripts/containers | Referenced templates, approved resource launchers and configured 4/8-GPU JobSet execution/retry |
| Lab addon and snippets | Prebuilt packages, polling, five snippet revisions and CPS CPU GUI evidence | Complete account/session/workspace cards; GPU/CIT acceptance; demo integration into release source |
| Argo user access | Owner-filtered operations and artifact downloads | Deploy OAuth revocation fix and qualify ordinary browser authentication/revocation |
| Scheduling | Live KAI 0.18.1; interactive quota/limit 8/8, batch 0/8; planned priorities | Reconcile Fleet's older pin; GPU2 remains cordoned, six stock GPUs schedulable; teaching reclaim, protection, fairness and distributed retry |
| Startup/defragmentation | Executors and acceptance limits defined | Representative p95 ≤180s/max ≤300s bursts and required KAI/fallback comparison |
| Storage | Preserved NFS; SeaweedFS through the accepted NetBird relay; controlled retention tests | Actual new CIT NAS endpoint/export; active workload lifecycle, archives, scheduled retention and recovery |
| Monitoring | Four dashboards, Hub/KAI scrapes, Loki retention, node-local Alloy | Current rendering/promotion, physical capacity and cap/protection metrics, alert delivery |
| Recovery | Automatic backups; gateway schedule now aligned and matching backup verified | Coordinated current-version capture, connected login/spawn and populated NFS/artifact/off-host restore |
| Releases | Wheels, immutable images and compatibility tooling | Qualified pilot → RC → production tags/releases, complete notebook matrix, checksums/SBOMs and Fleet promotion |

The no-MIG enforcement pilot uses native driver/cgroup caps, rather than the
originally proposed HAMi-only enforcement path. KAI placement is not evidence of
memory isolation. Earlier measured 5/10 GiB isolation and older 5/20 GiB results
do not qualify notebook531 or the full eight-GPU service.

## Immediate remaining blockers

1. The Source531 consumer blocker is cleared: both consoles now run
   [consumer `dbaad518`](../../platform-staging/admin/qualification/compute-consumer-531-20261016/adoption-receipt.json).
   Their live 16-module closures, matching backups and the authenticated capture
   API passed. A fresh CPU-to-qualification Source handover adapter now passes real provider
   and ASGI registration tests for both5 and20, retaining the frozen admin,
   freeze, grants and storage guards. Source restoration now passes 27 application/API tests, including completed
   enrollments, typed cleanup and retry after partial commits. A separate physical-release adapter now replays the full Node custody validator
   in all three failure phases before producing a fresh Source proof (14 tests).
   Wiring the actual live collector and coordinated execution remain required; image adoption does not qualify notebook531 hardware.
2. Qualification history support now accepts 128 records in the offline
   candidate and prospective Node generator; replay validated all 85 allocations
   and 75 terminal entries without truncation. The deployed Node is unchanged.
   Fresh CPS+CPS Node restoration and its UID/spec-tested Deployment inverse
   are now implemented and CPU-tested separately from the legacy CPS+CIT path.
   Gateway policy/runtime forward and inverse CAS planning and Node rollback
   for unstarted, one-started and both-started cases are now CPU-tested. Integration
   with Source handover/restoration and coherent execution
   remains required before the hardware test. A CPS-only Hub configuration/hook
   forward/inverse planner now projects both operator targets and image-pull owners;
   CIT is unchanged. Qualification planning disables and restores the incompatible
   dynamic group reader/heartbeat explicitly.
3. Execute the current-image 5+20 GiB test after those prerequisites pass.
4. Close the API/Hera/distributed gaps, adopt the Argo revocation fix, then finish
   the scale, lifecycle, recovery and release gates above.

Moodle stays planned, disabled and inert, with local management active. Email
verification is optional. Direct university Keycloak awaits ICT registration;
Hub 6 remains separately staged. These are not required v1 promotions.

## Runtime-limit correction staged

Policy catalog 0.2.0 now specifies CPU batch72h, GPU batch24h, interactive CPU8h
(idle1h), shared GPU4h (idle30m), debugging GPU1h (idle15m). Generated artifacts
and policy tests agree. GPU enablement remains unchanged. The live CPS generic
culler was independently read with idle48h and no maximum-age flag, so advertised
CPU profile limits are not proof of enforcement. CIT currently uses idle24h and
max-age24h, independently read from its Hub configuration. A stable-chart culler overlay
is staged outside Fleet. Coordinated live policy/hash and enforcement promotion
is still required; the running D48 qualification scope is unchanged.

## Fresh operator membership check

The 16 October Source capture initially failed because both controlled QA
memberships had expired. Normal owning-console API updates changed only the
two expiry fields to 17:18 UTC on 16 October; all other membership records were
read back unchanged. Grants, registrations, workspaces and Pods were untouched.
The temporary administrator token was revoked (DELETE204, subsequent read403).
Fresh genuine Source application readback now resolves both canonical member
sets, verifies both stopped CPU registrations/no reservations and matches the
reviewed16-module Source531 closure. The native ledger has86 allocations, one
active; the controlled running group must be normally stopped in the coordinated
transition before a zero-charge proof or qualification handover is valid.
No current-image GPU qualification was performed by this renewal.

## Latest controlled shutdown and release baseline

The controlled shared-gpu-lab workspace is now **stopped**, superseding the
earlier Running state above. Normal Source Stop initially returned409 during
cleanup; actual Pod disappearance, native cleanup and inactive reservations were
read back before a second normal Stop returned200/stopped. Both temporary tokens
were revoked. All four personal-server Pod UIDs present at operation start were
preserved. Actual post-stop device observation shows zero active entries, zero
charge and all86 ledger claims released.

Full inventory reconciliation now checks65 finite retirements, one existing
authenticated recovery and12 explicitly pinned unattributed default rows. Those
12 complete rows were unchanged since the previous evening in the same epoch;
they cannot replace workflow evidence or admit unknown additions. The new helper
passes13 focused tests and the full pilot suite passes768 tests/851 subtests
(14 skipped). No notebook531 handover or current5+20 hardware test is claimed.
Fresh full custody collection and coordinated transition remain the next steps.

## Fresh proposal integration

Actual post-stop capture now contains86 released allocations and76 terminal
entries, including the independently retained immutable configuration references.
The Source16-module declaration matches the reviewed manifest; original serialized
capture bytes are retained separately from the verified canonical manifest.
Provisioned storage includes server/evidence metadata, which previously broke
proposal construction. The proposal now verifies the complete captured metadata
and projects only the strict seven-field native descriptor, preserving the full
registration in its target snapshot. Unknown or untyped metadata fails. All33
prospective tests pass; the real capture now produces a typed two-workspace
proposal and validates actual Gateway/CPS Hub forward artifacts.

A separate live Node mismatch was caught before apply: code is supplied by the
Node8c image, with no existing code ConfigMap volume. The earlier Node inverse
assumed such a volume. An explicit image-backed code-overlay transition and
matching inverse are therefore required before handover. No handover deployment
changes were applied; the controlled workspace remains stopped.

## Image-backed Node transition correction

The actual Node8c image-backed shape now has a separate forward/inverse planner.
It overlays only the exact Root-generated Node/epoch files as read-only mounts,
preserves the image/driver/host mounts and removes four dynamic approval argument
pairs during operator mode. Inverse tests cover zero/one/two completed lifetimes
and restore the original group bootstrap. With zero new lifetimes the complete
original image-backed spec returns. Actual image source hashes match the frozen
references. The two ConfigMap creates and Deployment patch passed server dry-run
with exact spec readback; explicit0644 avoids API-default drift. All17 focused
tests pass. No live handover or current5+20 hardware run occurred in this step.

## Source maintenance preparation

A restricted idle operator Pod is prepared on the original Source node using the
reviewed dbaad consumer and original configuration/PVC bindings. It exposes no
HTTP service and opens no SQLite provider. All16 runtime module hashes match;
the SDK exec transport is installed. Actual service-account token checks deny
Deployment patch, Pod create, Secret get and Pod exec. No RoleBindings were added.
Both admin frontends remain Ready1/1 with unchanged specs; freeze is not armed.
The new exclusive-writer verifier passes15 tests, and the full suite passes804
tests/851 subtests with14 skipped. Scoped reader permissions and genuine
application callback wiring remain necessary before pausing frontends/migrating.
The idle Pod expires after one hour; inspect live state before reuse.

## Scoped live Gateway reader

The maintenance runtime now has a Root-contract-scoped SDK registration reader.
It retains every byte of the frozen readonly logic except the exact allowed
workspace guard. A short fixed argv plus length-framed stdin avoids ingress URL
limits. UID/spec/image checks fence both sides of each read.22 focused tests
pass, including real unchanged SQLite reads and bounded websocket failures.

Actual own-token reviews permit GET of only the current Gateway Pod and its
exec subresource, while rejecting other-Pod exec, Secrets and Deployment patch.
Both actual registrations were read and match full captured Source records.
No application/provider was instantiated in the operator, neither Source
database was opened and both frontends remain active. Context/operation callback
wiring and actual freeze/handover remain next; current5+20 is still unexecuted.

## Genuine Source context factory

The pair operator now composes the genuine released CourseServiceApp loader with
fresh Source writer exclusion and the scoped Gateway reader. Forward/restoration
policy modes are explicit. Exact module closure, Root members/caps, existing
SQLite/config paths and local-only provider settings are checked. Registration
callbacks revalidate the actual freeze, and altered reader code is rejected.
Eleven focused CPU tests pass. This is implementation evidence, not a live
freeze, Source migration or notebook531 hardware result. Both frontends have not
been intentionally paused by this change; observer RBAC and live execution remain.

## Live Source context rejection and bounded grant renewal

The existing operator Pod executed the actual context factory with the reviewed
installed application closure and real Kubernetes clients. A truthful unarmed
freeze review was rejected before any provider/configuration was opened. This
proves the live unarmed-review denial, not successful acquisition of a freeze.
Both console Deployment specs remained unchanged and active.

The operator's own token now permits GET of the named CPS/CIT Deployments and
namespace Pod LIST through `cps-qa531-source-observer`. Deployment PATCH and Secret
GET remain denied. This complements the earlier exact-Gateway reader Role. These
operator-only RoleBindings must be removed with the owned runtime after the run.

The two existing dedicated operator CPU grants were renewed by expiry only via
the authenticated owning-console API, with full person grant lists read back.
They expire at2026-10-16T14:38:39.930258+00:00. Other grants remain unchanged; no GPU
profile was granted. The temporary admin token was revoked204 and reread403.
GPU qualification aliases are absent from live D48; their bounded grants belong
after the candidate policy handover. The current5+20 hardware run remains open.

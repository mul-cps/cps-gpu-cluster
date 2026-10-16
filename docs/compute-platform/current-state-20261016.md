# CPS/CIT current state — 16 October 2026

The platform remains **limited-pilot**. Production qualification and the full
project are unfinished. This record supersedes current-state statements in the
older completion ledger; their dated acceptance results remain historical evidence.

## Latest verified checkpoint

The current notebook531 image passed GPU2 5/20 GiB ordinary PyTorch OOM/recovery,
restart/reacquisition, bidirectional CUDA IPC and VMM/POSIX-FD isolation, and
private MPS aggregate OOM/recovery with cleanup. VMM same-parent controls passed;
both cross-parent imports returned CUDA800 with correlated kernel denials.
Unprivileged NVML quota changes returned NO_PERMISSION; managed allocation was
rejected with CUDA801; removing visibility environment variables still exposed
only the assigned GPU. This is measured scope, not full production approval.

Both QA workspaces are stopped CPU workspaces with GPU grants removed. All92
allocations are released, all82 terminal records retained, native active entries
and charged bytes are zero, and four personal Pod UIDs are unchanged. Full
Gateway/Hub/Source specs and policy/runtime/Hub Secret data were restored. Both
consoles, gateway, Hub and node agent are ready; the node progressed beyond its
first reconciliation iteration. CPU registrations were reconciled through the
normal owning-console API without changing workspace rows; its token was revoked.

Restoration exposed a32 KiB reader guard that covered the temporary policy but
not its growing baseline history. The generated reader now applies the same
256 KiB bound to every semantically valid configuration, with unchanged0400,
owner, no-symlink, link-count, policy, cap and provenance checks. A regression
reproduced the failure before the fix. The combined suite passed886 tests and880
subtests, with14 skipped. No driver, MIG or hardware settings changed.

The immediate work is released controller/policy/admin integration and the
remaining lifecycle, all-runtime/all-GPU, scheduling, recovery and release gates.
Avoid extending one-off qualification as a substitute for that integration.
See the [final current-image isolation receipt](../../platform-staging/gpu/native-group-pilot/prospective-pair/current531-final-isolation-20261016.json).
The dated sections below preserve the earlier sequence and its then-open gates;
this checkpoint supersedes their current-status claims.

## Application-owned node backend foundation

`cps-compute` commit `5c8b4de7032487cb274221235243589bf5ebe672` now packages the
injected backend, NVML adapter, exact identity discovery, Kubernetes/CRI transport
and pure Pending-gate decision in the existing SDK wheel. There are no Root
contracts, physical GPU/workspace defaults, driver loaders or manual cap scripts
in this extraction. The installed transaction core/health verifier are reused.
Per-instance gate binding replaces helper-module mutation; failed NVML
construction now closes a successfully initialized session.

The full application suite passed 2,537 tests and 68 subtests (six skipped).
A fresh lean virtualenv passed dependency checks, inert module imports and 32
backend unittest cases from the installed wheel. Wheel rebuilding from the
sdist was byte-identical. Separate CPU performance review found no added hot-path
I/O/NVML calls; Pending decisions took 12.49/12.62 microseconds in the two measured
cases. CI now exercises installed native-module imports alongside SDK imports.
[CI run 38932949445](https://github.com/mul-cps/cps-compute/actions/runs/38932949445)
passed all four jobs: build, installed SDK/Hub, and Lab 4.5.7/4.6.4. Its Python 3.12
suite passed 2,536 tests and 68 subtests, with seven skipped. Local Python 3.13
results are reported above. Both are CPU/build evidence; live adoption is open.

See [canonical application documentation](https://github.com/mul-cps/cps-compute/blob/5c8b4de7032487cb274221235243589bf5ebe672/docs/native-node-package.md)
and its [artifact/CPU verification receipt](https://github.com/mul-cps/cps-compute/blob/5c8b4de7032487cb274221235243589bf5ebe672/docs/contracts/native-node-package-verification.json).
This is application ownership and packaging, not a deployed node service.
Generic orchestration, history/custody migration,
immutable image/RBAC/GitOps adoption and live qualification of the packaged
artifacts remain open. Existing node deployments are unchanged by this commit.

## Packaged CDI reader: live read-only comparison

Application commit `84a6263d08ebff1d17f474302364225a28101898` adds explicit,
immutable CDI/runtime pins and a protected read-only observer to the SDK wheel.
The local application suite passed 2,597 tests and 68 subtests (six skipped).
The wheel rebuilt byte-identically from its source distribution and passed
installed SDK/native-module checks in a lean environment.

The installed candidate reader was compared with the deployed reader in the
existing GPU2 node agent. Both produced identical current CDI mapping, search
proof and two-GPU physical inventory. Pins came from the deployed reader's
reviewed constants, rather than candidate defaults. No GPU API, driver or
configuration change occurred. The complete allocation ledger, node Pod UID,
Deployment specification and driver epoch stayed unchanged; the owned temporary
wheel and staging directory were removed.

See the [read-only receipt](../../platform-staging/jupyter-extensions-20261013/native-node-cdi-read-qualification-20261016.json).
This validates reader compatibility, not workload isolation or node-service
adoption. Initial CI run 38935616473 failed in a coordinator test whose real
100 ms deadline expired during preparation. Runtime correctly rejected the
closed fence. Commit `80d16f6b70bd8f8e9853fab134112d3c4e97ecfb` replaces the
wall-clock sleep with manual triggering of the real deadline and explicit
cleanup completion. Runtime deadlines and safety checks are unchanged. The full
local suite again passed 2,597 tests and 68 subtests (six skipped).
[CI run 38937037169](https://github.com/mul-cps/cps-compute/actions/runs/38937037169)
passed all four jobs: build, installed SDK/Hub, and installed Lab 4.5.7/4.6.4.
Its Python 3.12 suite passed 2,596 tests and 68 subtests (seven skipped); local
Python 3.13 results are above. All three wheels and source distributions built
and rebuilt successfully. This is build/package qualification only. Generic
service orchestration, complete custody migration and
immutable deployment adoption remain the next integration gates.

## Shared authority and node configuration v3

Application commit `3be38cdae748fab133a35629567b8355bbfdef27` adds explicit
qualification authority pinned independently by trusted deployment configuration.
The gateway, Hub, capture/export, registry and approval consumers retain that
authority when reconstructing deployments. V3 permits only the measured pool,
immutable runtime image and 5/10/20 GiB profiles covered by its actual immutable
qualification object. Existing V1/V2 image/device restrictions remain unchanged.
New V3 starts require a current authenticated approval reference.

The node configuration resolves the pinned node → deployment → qualification
chain and derives resources from that deployment. It validates a terminal-index
reference but does not yet consume terminal custody or run the node service.
Those lifecycle modules are unfinished and excluded from this commit.

The exact committed source snapshot passed 2,638 tests and 68 subtests (six
skipped). Independent boundary review found no blocking issue. Installed lean
SDK/node verification passed after fixing an eager optional-Kubernetes import;
a regression now rejects that dependency during import. The wheel rebuilt
byte-identically from its source distribution, SHA-256
`d5e5bcb7ca4bdf111d483dd7c9cf31f26dc9d9adfb18d89996a42fa853f2f489`.
[CI run 38938819760](https://github.com/mul-cps/cps-compute/actions/runs/38938819760)
is in progress. No deployment or hardware setting changed. Complete custody,
service execution, migration and released-image live qualification remain open.

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
| Dynamic GPU groups | Historical bounded native R615/cgroup isolation; current 5 GiB group Start and cap assignment restored | Released integration, current 10 GiB/all GPUs/runtime variants and broader packing; no MIG |
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

## Immediate remaining production work

1. Package and integrate the node lifecycle as a released application component.
   The current `cps-compute` wheel now owns the injected backend as well as
   transaction/approval modules, but its Dockerfile starts only the gateway. Its native controller documentation still
   explicitly requires qualification-only operation. The deployed node loop and
   generated compatibility overlay live here in cluster staging. Hardware
   evidence alone does not close that application/release gap. Move ownership
   without weakening gate, cap, epoch, journal or completion checks; qualify the
   packaged entrypoint against the current full retained state before adoption.
2. Replace finite policy/physical-scope patches and manual exact Pod/ReplicaSet
   RBAC refreshes with the released controller lifecycle. Introduce reviewed
   archival/migration so retained history and the allocation ledger do not reach
   their128-record limits. The current92 allocations/82 terminal records remain
   complete; do not truncate them to make a deployment pass.
3. Finish current-image10GiB/all intended GPUs and runtime variants, automatic
   MPS lifecycle, and the live workspace/reservation/revocation matrix. Current
   GPU2 5/20GiB evidence is now complete for the listed isolation probes; no-MIG
   dynamic sharing remains the selected approach.
4. Close the API/Hera/distributed gaps, adopt and qualify Argo OAuth revocation,
   then finish scheduling/scale, observability, connected/off-host recovery and
   pilot/RC/production releases against the full plan table above. Apply the
   agreed lifetime catalog through the supported policy migration, not a live
   edit that invalidates existing grants or retained provenance.

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

## Genuine Source context positively exercised live

Both Source frontends were temporarily paused with UID/full-spec compare-and-swap
and restored automatically to their exact original specs. The first attempt
rejected valid CoreV1 PodList items because item GVK was omitted by the API.
Four regression cases now cover absent/null and conflicting type fields; the
verifier inherits only missing type from the validated enclosing v1 PodList.

The retry constructed the genuine configured application twice under the actual
exclusive writer observation and read both current Gateway registrations. Both
QA records remained stopped CPU workspaces. A4,599,808-byte SQLite backup passed
integrity and was exported to private host storage. The complete logical dump
before/after application construction was identical. Both consoles returned
Ready1/1 and all four personal server Pod UIDs remained unchanged.

Full qualification suite:841 passed,14 skipped,851 subtests passed. The live
Source loader path is now exercised; Source migration, candidate grants and
current notebook5315+20 hardware qualification remain unexecuted.

## Actual rollout boot findings and fixes

Two controlled unstarted switches exercised actual runtime boot. The first
revealed that qualification mode disabled the dynamic group runtime but retained
its capture sidecar, preventing Gateway readiness. The planner now removes only
the exact pinned capture server; the inverse restores the full original spec.
The second attempt used a real loop-progress readiness check and exposed Node
operator configuration0644 projection plus a32 KiB reader limit for56,968 bytes
of preserved history. Projection now uses0400. Only the Root-pinned pair receives
a256 KiB reader bound; other modes retain32 KiB. The real full candidate passes
the generated reader in the deployed Node image without driver calls.

Rollback was verified against complete original Node/Gateway/Hub/Source specs,
policy/runtime/Hub Secret data, ledger contents and personal Pod UIDs. All are
restored; Node progressed beyond iteration1. Exact Pod GET targets in three
control-plane Roles were refreshed after replacement. Future rollout/rollback
must refresh those bindings and restore configuration data before waiting for
restarted processes. A Kubernetes Ready count alone was too weak for Node boot.

The normal console profile-change API was exercised for both QA CPU workspaces;
all workspace records remained unchanged. This existing guarded API is the path
for the QA profile transition. The expired Source operator, its SA/helper map and
two temporary Roles/Bindings were deleted by UID; backups/PVCs remain intact.
850 tests/851 subtests pass;14 skipped. No GPU alias grants or GPU Starts occurred.
The current notebook5315+20 isolation run remains the next unfinished gate.

## Full historical enrollment compatibility

The third unstarted candidate boot exposed38 completed dynamic enrollments whose
`approval_ref` was rejected by the static qualification parser. The generated
Node now bridges only the exact Root-pinned terminal history through the frozen
approval consumer, retaining full original document/protected-mirror custody and
all completion/journal/ledger/Pod-absence checks. A read-only check on the actual
Node validated all76 records and rejected four individual tampering cases. No
driver was opened, authority written or GPU workload started. The850-test suite
plus851 subtests passes (14 skipped). The actual5/20GiB hardware run is still open.

## Current531 actual GPU5/20 Start, OOM/recovery and Stop

The normal console grant/profile APIs selected the two bounded operator aliases,
and both normal Start calls returned200. The node agent automatically sealed the
5GiB and20GiB caps. Both current531 notebook Pods ran on GPU2. Concurrent PyTorch
clients saw their exact assigned memory limits, rejected a cap+64MiB allocation
with typed `torch.OutOfMemoryError`, recovered with a verified small allocation,
and continued computing while their peer crossed OOM/recovery. Each client
touched at most128MiB; unexpected large allocations would never be touched.
Both Pod UIDs and zero restart counts survived.

Both normal Stop calls returned200. All88 allocations are released; actual node
inventory reports zero active entries and zero charged bytes. Both QA workspaces
returned to CPU and their original CPU grants. MIG current/pending remain0 and
the driver is615.71.09. Complete terminal inverse validation passed for all78
records, including physical zero witnesses and original protected raw files.
The baseline rollout completed: complete original Gateway/Hub specs and policy/runtime/Hub
Secret data are restored. Both Source consoles are ready with their original specs;
all four personal Pod UIDs survive. Node retains the exact generated compatibility
source and restored D48 configuration with the two new immutable qualification
references. It progressed through iteration2. The new Node ReplicaSet required
refreshing exact GET targets in two Roles; no other rules changed.

This closes the current-image5/20 ordinary PyTorch OOM/recovery gate. It does not
close restart/reacquisition, memory-import, MPS, or broader production gates.
Evidence hashes and limits are recorded in
`platform-staging/gpu/native-group-pilot/prospective-pair/current531-torch-isolation-20261016.json`.

## Second current531 GPU cycle: restart, CUDA IPC and MPS

Both QA workspaces restarted through the normal console APIs with fresh Pod
UIDs and native parent inodes in the same physical GPU/boot/driver epoch. Their
old lifetimes stayed retired. Automatic5/20GiB caps and concurrent PyTorch
OOM/recovery passed again. CUDA IPC same-parent positive controls succeeded;
cross-parent imports returnedCUDA_ERROR_NOT_PERMITTED in both directions with
correlated kernel denial evidence, distinct namespace PIDs and explicit cleanup.

Two MPS clients in the5GiB parent hit aggregate OOM, recovered and cleaned up
while the20GiB peer progressed. A bounded20GiB variant held19456MiB before typed
OOM and both clients recovered while the5GiB peer progressed. Its daemon scan
reportedPermissionError. Both clients exited0;32 subsequent independent root
samples showed no MPS process and zero charge in that parent. The automated
20GiB cleanup gate therefore remains open. A fail-closed PID-descriptor observer
fix and cap-forwarding probe have11 passing CPU tests; a live rerun is required.
CUDA IPC evidence does not qualify current-image cross-parent VMM/FD imports.

Both workspaces stopped through normal APIs and returned to CPU with their
original grants. All90 allocations are released; zero active entries and zero
charged bytes remain. The complete inverse retained80 terminal records. Original
Gateway/Hub specs and policy/runtime/Hub Secret data, both ready Source consoles
and all four personal Pod UIDs were restored. CPU registration reconciliation
after policy restoration uses the normal profile API; workspace rows remain
unchanged. Broad GPU access and full production qualification remain disabled.

## Third current531 cycle and completed isolation checks

The latest checkpoint and final receipt above close the earlier20GiB MPS cleanup
and VMM import gates. The restoration reader fix changes only file-size handling,
not semantic authorization. The retained terminal archive now has82 records.
The production qualification flag remains false; ordinary broad GPU rollout is
not implied by operator-only qualification.

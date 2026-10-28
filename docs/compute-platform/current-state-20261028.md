# CPS/CIT implementation checkpoint — 28 October 2026

The platform remains a limited pilot, not a qualified production release. This update supersedes only the named observations in the [27 October audit](current-state-20261027.md); historical acceptance remains evidence for its measured application/policy/device tuple.

## Live outcomes

- Rino (`cit-jhub`, account `m12113877`) has the restored `mujoco-desktop-exclusive` workspace, original home and one A100. CUDA, NVIDIA EGL MuJoCo rendering and the authenticated Xpra endpoint passed bounded checks. A later live check confirmed Ready, zero restarts, CUDA available, MuJoCo 3.12.0 and writable home. This does not qualify fractional MuJoCo or the student's complete training run. See the [restoration receipt](../../qualification-artifacts/rino-mujoco-restoration-20261028/README.md).
- DCGM collection again reports eight fresh physical GPU UUIDs, two per worker. The reviewed coverage alert is loaded and healthy; its incomplete-coverage condition cleared. Only the GPU2 exporter label was restored after the exact collector image passed a temporary probe. Driver, toolkit, sharing and research workloads were preserved. See the [telemetry receipt](../../qualification-artifacts/gpu-telemetry-coverage-20261028/README.md). Eight observable GPUs do not mean eight qualified dynamic-sharing roots. The live rule patch still needs runtime-preserving GitOps promotion.

## Committed software and packages

Compute source `bf532fce21b3ae462314b3d430812c6bfbdf1ae4` includes the managed runtime/shared-lifecycle checkpoint and its direct pinned Hub FastAPI dependency. The preceding checkpoint records real PostgreSQL and signed Node tests for installed ownership, successor-head handling, original terminal cleanup and fresh-read history stability. The focused Hub package suite passes 15 checks; an isolated installed-wheel Hub import and dependency check pass, while Node imports retain the lean optional-dependency boundary. See [compute PR 2](https://github.com/mul-cps/cps-compute/pull/2) and its committed `docs/integration-checkpoint-20261028.md` for exact scopes, not an aggregate test count.

Admin source `53d9dcd50b230102af8ab863ac7aec329dbe6da3` adds lifecycle behavior to the actually routed `AdminRecords` page: runtime status polling, returned removal-operation state and resumption with the exact input hash. Three focused lifecycle cases and all 20 UI tests pass. A clean archive frontend build and installed wheel contain the changed JavaScript. Follow-up admin commit `e90de7b57e7ac2a2642a3ee07b6f1217740f6969` adds authorized read-only discovery of durable operation references after browser reload; execution still requires an explicit resume action. The installed-wheel backend checks passed 44 tests with 78 subtests; focused UI tests, build and lint passed. This is packaged source evidence, not a live deployment. See [admin PR 2](https://github.com/mul-cps/e2x-course-hub/pull/2).

The local Node candidate digest is `sha256:6932965a09f01a34fd87faf4447533aead183990927ed24d929f05ba41ee4661`, built from the exact compute source archive. Its pinned install, package ownership/import checks and network-disabled dependency checks passed. It has not been pushed or deployed. Local build evidence does not qualify a host rollout or physical isolation. The matching Hub candidate is also built at digest `sha256:968e695e048fd6c7a15db731ee0ead1aafe980bfce1b5e0ad47627094e91bbba`; its pinned dependency, installed-file inventory and import checks pass. Neither image is published or deployed. See the [package receipt](../../qualification-artifacts/runtime-packaging-20261028/README.md).

The protected selected-Node peer configuration adapter is now committed in compute source
`9e6ccf3` and passes 11 focused tests in a dependency-complete environment,
including construction against an actually started NodeService fixture. It
reuses HTTPS CA/projected-token transport and Kubernetes TokenReview/SAR.
It is not yet wired into `create_runtime`; this does not close the production
coordinator assembly or live selected-peer exchange gate.

The private Source observation route and matching coordinator HTTPS client are
now implemented, committed and tested across a real TLS connection. Clean,
installed wheels pass 36 compute tests and 15 admin tests plus 20 subtests,
without implementation source paths. They remain unconnected to the production
activation factory; bounded observations are not complete-history or backup
proof. See the [transport receipt](../../qualification-artifacts/source-runtime-transport-20261028/README.md).

## Immediate remaining implementation and activation

1. Complete the final admin image and preserve source/wheel/image provenance; matched local Node/Hub checks are recorded above.
2. Verify the deployed v3 coordinator configuration and retained qualification coverage against the original production requirements. The managed selected-node installation framework is an optional replacement lane, not automatically a prerequisite for the existing path. If that replacement is selected, its dedicated startup/installation boundary remains unfinished; never recreate lost history. See the [review reconciliation](review-reconciliation-20261028.md) and [optional activation preflight](../../qualification-artifacts/native-selected-runtime-activation-20261028/README.md).
3. Complete the managed shared lifecycle beyond the bounded membership slice: standalone admin Stop auditing, assignment closure/archive, full reconciliation and durable UI operation discovery.
4. Verify the installed final tuple on missing/changed hardware scopes, global cross-Hub accounting, scheduling/reclaim, distributed cleanup, startup bursts, session maximum/warnings and the final user-interface/image matrix.
5. Complete coordinated connected restore/off-host recovery and a reviewed compatibility release/promotion. Preserve existing successful RTC, notebook submission, retention and bounded GPU results; rerun only what the changed tuple or unproved requirement requires.

Direct university federation remains deferred to ICT. Email verification remains optional; reviewed directory identity is authoritative. Moodle remains planned and disabled. None of these deferred integrations substitutes for the local implementation and qualification work above.


## Architecture review reconciliation

The live mounted values Secrets, installed application bytes and private compute source were checked alongside GitOps. The legacy repository alone is not the production source of truth.

Confirmed legacy CPS launch gaps have focused source fixes: freeform GPU/image/custom-NFS overrides are rejected before launch side effects; validation resolves the final server-owned KubeSpawner profile callback including native profiles and default REST launches; optional NFS presets default off; unsupported Dask/Slurm choices are filtered; course-priority student profiles require student membership even for power users; and future notebooks use a dedicated unprivileged ServiceAccount with token automount disabled. Existing Dask accounts and running notebooks are preserved. LDAP lookup now uses a bounded positive UID/GID cache and runs off the Hub event loop; permission/group data is not cached there.

KubeSpawner already validates selected profile slugs. The absence of a duplicate check was not proof of an exploitable ordinary-user GPU-profile bypass. The independent freeform resource and storage issues were real configuration gaps.

A four-file compatibility backport is published as [compute PR 4](https://github.com/mul-cps/cps-compute/pull/4), source `16fa7670601546ba7c1ec1bf58eb3e8b38c67619`. Candidate image `ghcr.io/mul-cps/cps-compute@sha256:f00f8c5b63bdce6348153aab6e11c1fd5cbf638ed1b50ef27bdda346ad202b75` was inspected remotely. It retains all 20 existing Hub package files, all 84 SDK files and all 137 installed distribution versions unchanged; only two packaged helper modules are added. The wheel RECORD audit, imports, dependency check and 43 focused helper tests passed. The companion mounted configuration and compatibility image are now deployed to CPS only; a crafted GPU override was rejected and a normal CPU launch reached readiness in 50.37 seconds. See the [live remediation receipt](../../qualification-artifacts/fixed-launch-rollout-20261028/README.md).

The source proxy configuration now restricts remote targets to explicit loopback addresses. CIT desktop registration is gated by the image's actual Xpra executables and assets in [CIT PR 20](https://github.com/bjoernellens1/cit-teaching-platform/pull/20); 13 executable configuration tests passed. Existing Rino image assets satisfy that gate. The CPS proxy predicate is now in the live mounted configuration for future notebook starts; already running notebook processes have not been restarted. CIT capability gating remains source-only. The stale CPS `/hub/ssh` link returned HTTP 404; source documentation now links the canonical SSH guide.

### Lifetime audit correction

Both live Hubs install the profile lifetime controller; its API route returned 403 without credentials, rather than 404. A ConfigMap-only audit missed the actual mounted Secret overlays. Profile-specific current deadlines were not retrieved, so no current per-user deadline is inferred here.

The independent global culler remains a separate constraint: CPS has a 48-hour idle timeout and no max-age argument, while CIT has a 24-hour idle timeout and 24-hour maximum age, with administrators included. The lifetime-controller protected-server records do not exempt users from that independent culler, and their Pod UIDs must match the current generation. Rino's restored CIT account is not listed as protected. A point-in-time GPU utilization sample does not prove an idle duration and does not authorize stopping research work.

Remaining review work includes exact-reference production pre-pull alignment, warm/cold/queue-separated startup measurements and measured caching benefits, the role-specific deployed UI/API matrix, and eventual reduction of legacy embedded configuration through the released adapter. Do not silently combine this remediation with a Hub/chart migration or a broad watched-Fleet reconciliation.

The combined cluster change passed 71 compute-policy tests with 167 subtests and 13 executable proxy configuration tests. These scopes exercise request rejection before side effects, default and final native profile resolution, directory caching, role visibility and ServiceAccount rendering. Those source tests alone do not establish deployment or latency; the subsequent bounded live CPS rollout and single CPU timing sample are recorded separately above.

## Current-group readiness repair

The authenticated existing current-group API now reports `ready: true` for the
5/10 GiB profiles. CIT's stale publisher identity and both stale gateway Hub
image declarations were corrected with guarded reference-only rollouts. All
four component acknowledgments are fresh and agree; the four protected user
notebook UIDs/restart counts remain unchanged. This closes the process-image
readiness mismatch, not fleet qualification. See the [repair receipt](../../qualification-artifacts/group-readiness-repair-20261028/README.md).

## Cross-Hub preflight and assignment archive follow-up

Fresh authenticated read-only preflight still reports the current approval
revision ready for both Source readers, but the current registry contains only
CPS `shared-gpu-lab`; CIT has no approved group workspace. Both historical
`native-group-a` records return HTTP 409 `Workspace policy hash mismatch`,
and neither has an active reservation. Controller readiness is not approval
for every workspace. No historical hash, grant or removed approval was
overwritten. A fresh supported CIT registration/provision/approval flow is
required before the current cross-Hub admission exercise can run.

Compute commit `d909336` extends the existing race exercise to identical full
canonical member sets; 13 focused tests pass. It still submits and terminates
a separately entitled CPU batch workflow, and does not start a notebook or
GPU workload. No current live race is claimed from those tests.

Compute commit `de3a85e` fixes the filesystem adapter actually configured by
both deployed consoles: archive calls partition trusted workspace records by
group, verify every response, and return no aggregate success after a later
group failure. A retried archive re-verifies an already archived group through
the backend; provisioning from archived state stays fenced. Storage and
recovery tests pass 127 cases. This source change is pushed, not deployed.
The preceding admin-only bridge belongs to the newer application lane and
was not the missing RPC in the currently deployed console.

The live admin's three inspected backend files match source `a070050` exactly;
its installed SDK storage module differs from current compute HEAD, although
the HTTP adapter class matches. Deployment therefore requires a bounded
compatible package/backport; replacing whole current modules or promoting
the complete newer runtime without qualification would change unrelated
behavior. The deployed image and running user Pods remain unchanged here.

## Archive compatibility deployment

The bounded archive fixes are now deployed: Gateway source `ad451f5`, SDK
0.1.1, image `sha256:d9053551c63f6844b043cea3cdb7df67a2a8f2091d93b9c6f560818df07ed711`;
both consoles use admin source `a1c554a`, version 0.1.2, image
`sha256:b6856fa9c0ac1ddd42541c5bb629ee31ff8a5fd7420cd152548d6fdc8edde7b7`.
Each console selects the modular course-service filesystem provider while
retaining its installed SDK 0.1.0 and all six existing UI assets. No schema
migration or Lab-package ownership change was introduced. Both provider
imports/configurations and authenticated current-group readiness passed after
the paired guarded rollouts; policy and approval revision remain unchanged.
Four focused provider tests pass, including pending-state and sanitized-503
behavior. Actual controlled NAS archive closure/retry remains open. See the
[deployment receipt](../../qualification-artifacts/archive-compatibility-rollout-20261028/README.md).

Before that rollout, the existing CPS 5 GiB group workspace reached Ready,
completed a CUDA calculation with the measured 5 GiB ceiling, and stopped
through Hub REST; its Pod disappeared and its reservation became inactive.
The four protected research/student Pod generations remained unchanged.
That single launch took approximately 169 seconds; Gateway prepare spent
72.943 seconds, principally registered readiness and enrollment publication.
These are measured optimization targets, not p95/burst qualification.

The post-upgrade repeat GPU start exposed a pre-existing placement-scope gap:
KAI's node-level pool selected GPU2's other physical A100, outside the one-device
qualification contract. The guard correctly held the attempt before prepare.
The fresh controlled Pod and KAI reservation were removed through normal Hub
shutdown, and global accounting is inactive. This is not a confirmed archive
regression, but reliable repeated GPU spawning remains unproved until physical
device selection or the hardware qualification scope is corrected.

### Live assignment closure acceptance

The newly deployed archive path passed a controlled CIT assignment with two
CPU groups through the actual authenticated console API, neutral-account
provisioning, Hub and NAS. Both workspaces reached Ready, retained marker files,
then stopped before verified read-only ZFS/mounted archive. Repeated closure
re-verified both groups. An independent tokenless probe confirmed both marker
hashes and `EROFS` for writes. Both Hub server lists and Share lists are empty;
Source pending flags are clear. Temporary grants, probe and operator token were
cleaned up while retaining archives/audit history. This closes that bounded
assignment archive acceptance, not active GPU membership revocation, full RTC
browser acceptance, cross-Hub accounting or coordinated restore.

The archive Gateway image handover now also includes the Node observer's typed
immediate service-image successor. The exact-template admission rule was
paired with the new ReplicaSet/bootstrap after initially rejecting creation;
positive/negative server-side admission checks pass, the actual Node agent is
Ready, custody snapshots succeed and authenticated group readiness remains
true. Node image, policy history, qualified UUID and persistent state are
preserved. Reliable device placement remains the independent unresolved GPU
gate described above.

## Second-card IPC gap closed; v3 late placement underway

A fresh controlled 5/10 GiB pair on GPU2's second A100 passed cross-parent CUDA
IPC denial in both directions, including same-parent positive controls, exact
kernel witness attribution, exporter continuity/recovery and importer survival.
Root independently bound the receipts to the before/after Pod UID, GPU UUID,
boot, driver-generation and cap observations. Cleanup retired both original
records: all twelve retained rows are offline/pinned/used-zero, both GPU2 cards
have no compute clients, and the QA namespace is empty. Protected user Pod UIDs
and restart counts are unchanged. See the [actual IPC receipt](../../qualification-artifacts/gpu2-cross-parent-ipc-20261028/README.md).

The implementation route is now an extension of the deployed v3 coordinator:
global member custody first, inert placement-pending claim, then authenticated
KAI device selection and one immutable per-device cap/claim CAS. The optional
managed PoolHeads replacement is not imposed as a prerequisite. The current
four affected Gateway module byte hashes match the `ad451f5` backport source.
Typed candidate/selection and pending-claim software stages are being tested;
the coordinator, binder, CPU bootstrap gate and selected Node integration are
not deployed. Existing valid hardware measurements remain reusable for their
verified tuple; this IPC result does not qualify the entire eight-GPU fleet.

## Second-card evidence review and placement implementation

The second physical GPU on GPU2 now has reviewed evidence for all six bounded
5/10 GiB gate scopes on the current 615.71.09 boot/driver generation. The primary
agent independently verified all six receipt hashes and 65 original source-file
hashes. The actual v3 proof codec accepts the evidence candidate; no synthetic
ConfigMap identity is an installed authority object. See the
[second-card review](../../qualification-artifacts/gpu2-second-card-six-gates-20261028/README.md).
Managed-memory public API denial and ordinary recovery passed the defined gate;
an extra source-patch/errno attribution requirement is not being imposed.
This does not qualify the other six GPUs or the whole installed platform.

Compute branch `codex/v3-placement-integration-20261028` now implements current
Hub member reservation before GPU selection, immutable admitted compiler seeds,
actual-Pod-bound inert registries, a CPU-only deferred cap gate and mandatory
GPU identity init, typed logical-approval/physical-qualification separation,
and closed Node selection-map checks. A real software fixture exercises the
current authority/coordinator lease, compile, CREATE, seed readback and registry
path with idempotent retries and override rejection. The Node independently
accepts only protected compiler-backed unselected waiting custody; that phase
has no GPU intent and cannot activate a cap. Separate pending and full future
bound Pod hashes preserve the existing Node seal invariant.

The matching KAI binder source is based on the exact deployed patch revision.
Its new protocol proves the raw Python compiler seed and typed actual Pod spec
before reservation, checks actual KAI-selected UUID/Node/boot against qualified
candidates, and preserves the legacy path. Root review caught and fixed compiler
metadata drift and pending-versus-bound hash assumptions. These are isolated
source changes, not installed images or live connected acceptance.

Still open for this placement path: the complete fenced selection/enrollment/
allocation-ACK producer, selected/bound observation assembly, selected physical
Node epoch/CDI use, per-device snapshot accounting, installed package/image
handover and connected current-group/cross-Hub lifecycle tests. Existing CUDA
hardware results remain valid for their exact tuple. Existing research Pods,
Rino's restored MuJoCo session, drivers, device modes and production policy have
not been changed by this implementation work.

### Selected placement integration follow-up

The compute integration branch now includes an allocation ACK builder from
actual-shaped pre-bind API readbacks, selected Node observation before and
after Binding, and an atomic durable custody transition from the original
placement identifier to the selected binding identifier. The original compiler
seed remains unchanged. New placement acquisition and finalization also use
the existing execution writer guard; contention tests reject both operations
while an execution fence is active.

The Node's bound branch validates the selected allocation codec and independently
rechecks the current Pod, protected registry, enrollment, selected projection and
both frozen KAI maps. The combined focused observation/record/custody checks
passed 82 cases; the writer/custody regression scope passed 44 cases. These are
software checks, not a deployed GPU launch. A protected-seed reconstruction
helper is also committed, with an explicit separately pinned compiler reference.

The connected coordinator contract test now reaches the real remaining seam:
`GroupCoordinator.placement_prepare` does not yet exist. It must authenticate
the actual binder selection, finalize the device claim, retain original custody,
publish enrollment and selection under the existing guards, and issue the ACK
before Binding. That connected flow, lifecycle recovery, package/image handover
and current-group/cross-Hub live acceptance remain unfinished. No production
configuration or running user workload changed in this follow-up.

### Connected selected lifecycle software case

The previously missing `placement_prepare` method is now implemented. The
connected fixture performs the actual authority pending-to-selected CAS,
durable custody handoff, strict Node pending-generation observation, immutable
selected projection and full enrollment publication before opening the existing
execution fence. It builds the ACK from fresh API/ledger readbacks and continues
through current validation, exact Binding authorization, API-visible bound Pod
readback, accepted custody and close. The fixture simulates the API's Binding
result; no GPU workload or Kubernetes Binding was executed by this software test.

Root verification passed 277 focused placement/selected/auth/server checks in
16.86 seconds, including the connected lifecycle. A separate bounded scope
passed 35 cases in 5.94 seconds. The Node enrollment decoder now accepts only
the complete selected protocol provenance and exact qualified candidate/epoch;
the old schema cannot silently discard those fields. The explicit v4 Hub
transport, gated Gateway routes and fresh trusted candidate resolver are also
committed. Existing startup configuration leaves these new routes disabled.

KAI source `99508c2` carries registry/seed-proven placement identity through a
dedicated prepare operation. Root independently passed all binder package
checks (cached exact-source results); the pinned patch and scope are in the
[binder receipt](../../qualification-artifacts/gpu-placement-binder-candidate-20261028/README.md).

The subsequent integration at compute source `edcc5df2ebff99e6d817a24e2e74eaa2b8e33f8b`
connects explicit v4 Hub activation, authenticated Ready-Pod status after the
execution fence closes, and terminal cleanup through original placement custody.
Both enrolled and never-enrolled selected claims retain their immutable compiler
and registry chain; the latter requires actual enrollment absence. A registered
inert waiting Pod now appears in the complete census with zero GPU charge,
without becoming a physical allocation. Root verification passed 306 focused
placement/selected/auth/server cases in 29.07 seconds, plus 28 cleanup/routes
regression cases in 7.75 seconds. These remain software checks.

Exact-source SDK and Hub wheels passed RECORD and package ownership checks;
neither package takes ownership of the other's files or JupyterLab assets.
Build preflight found stale SDK 0.1.0 inputs in Dockerfiles and the Hub dependency
while the source SDK is 0.1.1. Source `f8762de0680bf590205abf55179fe6ac864c8bf8`
corrects those inputs and aligns the Hub component to 0.1.1; 24 packaging/image
checks passed. Local Gateway and Node images built successfully with the exact
SDK wheel checksum. Gateway dependency checks, selected-path imports and the
selected-cap gate CLI passed; Node startup reported inert without API/GPU calls.
These images are uniquely tagged published candidates, not replacement releases or deployed runtimes; the staged wheels have not been published as releases.

Remaining before activation: coherent Gateway/Node/Hub/gate image handover,
actual protected two-device proof/catalog installation and opt-in settings,
then controlled connected GPU/current-group/cross-Hub acceptance. Wider
production gates remain listed above. No production rollout, driver change,
MIG change or user Pod restart occurred in this software work.

The local Hub image also built from a 77-wheel hash-pinned closure. Its installed
distribution inventory differs from the reviewed base only for SDK and Hub
0.1.0 → 0.1.1; Hub 5.5.2, KubeSpawner 7.1.0 and kubernetes-asyncio 36.1.0
remain unchanged. Local IDs and exact source/wheel hashes are retained in the
[software receipt](../../qualification-artifacts/selected-placement-software-20261028/local-image-builds.json).

Read-only activation inventory confirms no second-card proof/configuration or
`candidates.json` catalog is installed, and the resolver environment setting is
absent. The retained second-card proof document has valid bounded hardware
measurements but its ConfigMap wrapper was schema-validated with synthetic
identity only. Its image/policy tuple differs from the installed first-card
deployment. Activation requires a genuine coordinated tuple/proof handover,
not copying a UUID or substituting synthetic references. These local image
builds do not change or extend the existing hardware qualification.

Gateway, Node and Hub candidates were subsequently published to their existing
GHCR packages using unique selected-source tags. Independent registry inspection
matched all three pushed manifest digests; the software receipt records those
exact references. This publishes build artifacts only: no live configuration,
protected proof, approval, user Pod or production policy changed.

### Protected service handover staging

The exact KAI binder candidate `99508c2` is now built and published to the
existing binder package. Independent registry inspection matched digest
`sha256:35f0506a49a6f2c6dd8c658697e6db3ccbe671da1bc8d42d3ff902a2c33f536b`.
It remains undeployed. The built Gateway image passed 16 selected CPU-gate cases
with networking disabled and no checkout SDK mounted; this checks the installed
CLI's validation/wait/exec behavior, without GPU execution.

The active Node bootstrap resolves `cps-native-head-config-6e7caa85a6e0c88a`;
the dormant delivery configuration and historical reg33 declaration are not
its current authority. Root loaded this actual Node chain against policy 0.1.2
through `NodeConfiguration.load`, created a same-policy service-image successor
with the actual predecessor reference, and reloaded the successor successfully
from Kubernetes. Its immutable bootstrap, Gateway publisher and KAI config
inputs are created but not active. Exact created-object identities are in the
[handover receipt](../../qualification-artifacts/selected-placement-software-20261028/staged-service-handover.json).
No approval, anchor, hardware receipt, driver or active user Pod changed.

A fresh gate qualification can use the existing reviewed transition planner:
bumping policy 0.1.2 to 0.1.3 legitimately updates the two shared profiles'
embedded qualification policy versions. No planner/factory relaxation is needed.
The new physical B requires an independent measured root; it must not be
represented as A's physical identity successor. Workload image preservation
from the measured image to the current image must also remain explicit.

### Live service handover and bounded regression follow-up

This observation supersedes the staging-only service statements above. Gateway,
Node and KAI binder now each report one ready replica on the published candidate
images recorded in the [live receipt](../../qualification-artifacts/selected-placement-software-20261028/live-service-handover.json).
Hub and selected-gate activation remain pending; the two-device catalog remains
uninstalled. Existing policy, gate image and physical qualification scope were
not expanded.

The initial Node rollout waited because the bootstrap release sentinel had been
changed from the literal `true`. The bounded rollback restored the services; the
corrected retry preserved that sentinel and reached readiness. This was an
operator staging error, not a driver or GPU isolation failure.

The subsequent current-group launch did not pass: binder held it before binding
with `reserved-gpu`. Source maps that diagnostic to the legacy terminal check
requiring exactly one reserved GPU equal to `nativeApprovedGPU`; the new
placement-pending protocol bypasses that legacy single-device check only through
its separate validated path. This is not evidence of successful two-device
activation. A fresh read confirmed the test Pod and BindRequest absent, the
workspace reservation inactive with no attempt, and no GPU reservation Pods
remaining. Aditya, Gottam, Muslim and Rino retained their original Pod UIDs,
Running state and zero restarts. No protected notebook was restarted.

### Independent second-device measured proof publication

The immutable historical B proof is now an actual API object,
`cps-second-device-qualification-b65a5ca0fb59d8d4`, rather than a synthetic
wrapper. The installed Gateway's real qualification factory accepted its exact
UID/resourceVersion/data hash against the mounted policy. All six referenced
gate-summary hashes and the capacity-summary hash match the retained files.
The [receipt](../../qualification-artifacts/selected-placement-software-20261028/second-device-actual-proof.json)
records the measured tuple and exact reference. This does not activate B or
qualify a changed gate image. Preserve the unchanged kernel measurements; the
remaining gate delta is selected-bootstrap exec and cap assignment, with explicit
workload image preservation and the coherent two-device configuration.

The published Hub candidate was tested by executing its installed interpreter
without networking: SDK and Hub are both 0.1.1, and the placement module imports.
An inherited base-image label is not evidence that this module is absent. Four
focused Hub activation tests passed. The current live Hub remains on its v2
settings and the Gateway candidate resolver remains off.

The current installed SDK subsequently loaded the actual selected Node
configuration and authenticated both preserved workload-image edges,
`542708… → fb9872… → 3eab…`. The local activation preflight independently resolves
the pinned immutable transition/preservation objects by UID, resourceVersion and
data hash. Workload-image continuity is therefore resolved; it is not a reason
to repeat unchanged kernel gates. The remaining measurement is the changed
selected wrapper's same-process sealed-cap handoff and actual B cap assignment.
The live Node UID and boot ID still match B's retained measured epoch.

The actual installed gate executable passed a non-mocked CPU handoff probe in
a network-disabled container with read-only root filesystem and no GPU devices
or native authority mount. After a synthetic fixture selection appeared, the
wrapper executed `wait-for-cap` with unchanged PID and process start ticks.
The [probe receipt](../../qualification-artifacts/selected-placement-software-20261028/selected-gate-real-exec.json)
explicitly excludes hardware cap assignment. Fresh read-only host observations
matched the retained boot/driver generation; both GPU2 A100s reported 40,960 MiB
total and 0 MiB used. The connected cap-assignment delta remains open.

A short CPU-only pod pre-pulled the exact selected-gate image onto GPU2 and
verified its installed runtime import without GPU devices, API token or native
authority mounts. It exited successfully and was removed with UID/resourceVersion
preconditions. The [receipt](../../qualification-artifacts/selected-placement-software-20261028/selected-gate-node-prepull.json)
records the target image and Pod identity. The native runtime namespace's
controller admission policy was left intact. This did not assign a GPU cap.

A static comparison with the actual historical B QA gate ConfigMap found the
unchanged cap-validation and sealed-wait functions in the installed selected
gate, matching all historical top-level assignments; the driver-health module
is byte-identical. This [comparison](../../qualification-artifacts/selected-placement-software-20261028/gate-cap-source-comparison.json)
supports reusing earlier isolation measurements. It does not prove the Python
runtime environment or a cap assignment in the changed gate.

The controlled 5/10 GiB QA pair is now prepared from fresh node, namespace,
driver and CDI observations. Both proposed Pods passed a real Kubernetes
server-side dry-run, and the transformed B specification was finalized with
the original reviewed binding and a recomputed full spec hash. The B identity
init preserves the QA environment's existing CDI device selector. No Pod UID or
cap intent was invented. Seventeen focused renderer/composer tests passed.
The [admission receipt](../../qualification-artifacts/selected-placement-software-20261028/qa-selected-gate-server-dryrun.json)
records the scope: this is not a live GPU or cap-assignment test.

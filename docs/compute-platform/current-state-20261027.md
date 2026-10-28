# CPS/CIT current state — 27 October 2026

The full platform remains **limited-pilot**, not production qualified. This
record separates published source, local software checks and observed runtime.
The [previous ledger](current-state-20261023.md) retains the detailed historical
CUDA and shared-workspace evidence; those results remain valid for their tested
versions and scopes. Later sections record the new second-card CUDA measurements
and the live device-plugin advertisement correction; earlier source/test entries
retain their original commit scope.

## Latest completed boundary

- Eight physical A10040GiB GPUs, all driver615.71.09; Kubernetes capacity and
  allocatable are2/2/2/2. All workers use existing default `plain` device-plugin
  configuration. GPU2's singleton qualification selector was removed without
  driver/image/ConfigMap/status edits. The last completed cleanup restored its
  temporary test scheduling fence.
- Second GPU2 card: actual CUDA identity, native5/10GiB cap assignment, typed
  over-cap rejection/recovery and continuous peer kernels pass in both directions.
  Owned cleanup verifies all retained rows inert/zero-charge and preserves the
  first root's custody. The next controlled cohort also passed aggregate
  same-parent pressure and all nine memory/import cases, including creator-exit
  retention and cross-parent VMM denial with positive controls and correlated
  kernel evidence. Final cleanup verified all eight retained native rows offline,
  pinned and zero-charge; both devices had no QA clients, and the original
  first-device custody, CDI contents and driver epoch were unchanged. GPU2 was
  uncordoned after cleanup. These A/B tests use one QA namespace and do not prove
  cross-Hub accounting.
- After the reviewed exec-aware environment correction, actual second-card MPS
  passed: two clients held 4096 MiB together, the 4352 MiB attempt returned typed
  CUDA OOM, both recovered, and the peer completed 282 progress ticks. The pinned
  original assessor was independently rerun against retained traces. Fresh host
  observations verified both GPUs free of QA clients, all ten retained native
  rows zero-charge, all four mapped MPS process lifetimes absent, and unchanged
  first-device custody/CDI/epoch. Earlier preallocation test setup refusals remain
  recorded. A single exact owned-container stop produced the same Pod UID with
  A1/B0 restart counts and a new A container/process, while original parent cap
  identity, seal, journal, gate and epoch remained unchanged. Nine peer ticks
  bracketed that stop. After correcting the nested restart observer, a separate
  post-restart window passed A5 over-cap rejection/recovery with sixteen peer
  ticks inside the eight-second hold and four physical-memory samples. The two
  windows are retained separately; they do not establish a continuous 120-second
  peer interval across both stages. Final cleanup verified all ten original
  journals and native rows retired/offline/pinned/zero-charge, no QA clients and
  unchanged first-device custody/CDI/epoch. GPU2 scheduling was restored with an
  exact UID/resource-version CAS; all workers advertise two GPUs and are
  schedulable. Complete installed multi-root admission remains open. These are
  physical QA results for the tested 5/10 GiB pair, not full production or
  cross-Hub qualification.
- Neutral stopped-workspace bootstrap is reviewed and published at compute
  `87c5f6d121e2d87476a351aee416ec00bb9471d4` / Source
  `f4c83fd03c2e31b25ff39a4367d4f04d2e0dfb25`. Exact installed wheels pass the
  PostgreSQL preparation chain. Compute`16340ba623015cf0fa86528148251a4672990b58`
  requires the nine-module PostgreSQL lane and critical cases in release CI.
- Full shared membership/Shares/removal/restart lifecycle and remote selected
  Node/Gateway runtime factories are in implementation, not qualified or deployed.
  Original cross-Hub/scheduling/startup/UI/notebook/storage/restore/release
  acceptance remains binding. Hosted run40584252193 cannot start due to account
  billing/spending limits; no hosted pass is inferred from local checks.

The following entries are retained checkpoints, not an assertion that their
versions are the newest installed release.

## Verified software

- The paired Source-authorized ordinary-group dispatcher is published at compute
  `2d42bebaaddb3094979dcff0fdbc81d8ee92b38c` and admin
  `22853170b6bd91cba3977c7b8a888c13b1e1a4f0`:
  [compute draft PR 2](https://github.com/mul-cps/cps-compute/pull/2) and
  [admin draft PR 2](https://github.com/mul-cps/e2x-course-hub/pull/2).
  Remote branch SHAs were verified after publication. Independent review passed,
  including the scoped fixes for native Shares and production-handler evidence.
- Final focused coverage passed 26 paired integration cases and 21 subtests in
  5.23 seconds on the final operator commit, plus six focused admin cases in
  0.284 seconds on the unchanged admin source. The actual
  Source/Hub/coordinator stores are exercised; regular and expired Shares reject
  before preparation. One smoke uses the unmodified production cookie/XSRF
  handler. This does not prove browser OAuth/SSO, ingress or live deployment.
- The earlier Task2 full compute result (6,244 passed, six skipped) and Task3A
  admin result (129 passed) remain historical checkpoints, not full-suite results
  for the final paired commits. Final release-checkpoint suites remain required.
- The final admin Python wheel passed isolated byte/import, optional-dependency
  and disabled-mode checks. Frontend building was skipped for this probe; it is
  not a released UI artifact. Receipt, journal and dispatcher remain disabled by
  default. Shared-workspace lifecycle, installation custody/migrations,
  authenticator hooks and remote operator activation remain open.
- The disabled local operator handoff is independently reviewed and published
  in the same compute commit. It demonstrates durable target commit, immutable
  readback, authenticated committed-target reads, genuine pair consumption and
  active acknowledgments, finalization and a subsequent actual Source write.
  Final focused affected checks passed 94 cases in 7.01 seconds, including 29
  activation cases. The complete chain also passed from an isolated SDK wheel
  install in 1.54 seconds. Review fixes bind local consumer data to original
  retained custody and reject incomplete backup schemas/predecessor history.
  Remote installation/runtime coverage is still missing; this software result
  does not enable managed writes in production or finish shared lifecycle.
- The selected-device V2 enrollment and Node startup lifetime is independently
  reviewed and published at compute `1d5bc274777bc9a67014d194f080d360994889bd`.
  The controlled chain executes actual Hub admission/registration, immutable
  selected-device publication, original ledger CAS/enrollment, Binding, Node
  controller/private seal and the unchanged startup receipt verifier. A review
  found a census race that could omit a concurrent charge; the fix binds the
  census to its exact validated ledger. Its regression reproduced the failure,
  then passed; the two owning lifecycle/claim files passed 64 cases in 19.14s.
  The one earlier affected run recorded 577 passes and two old migration-fixture
  failures; the repaired registration file passed all 24 cases in 1.22s. No broad
  suite was repeated. An isolated SDK wheel passed exact-byte and lean Node-extra
  import checks without admin/Hub/FastAPI imports or SDK/Hub/Lab ownership overlap.
  This is disabled local software embedding. Authenticated remote transport and
  factories, terminal teardown/release and shared roster lifecycle remain open;
  no global/console SQLite databases may be mounted on Nodes as a shortcut.
- Started and original-prepared-journal pooled termination is reviewed and
  published at compute `e1391d8939e5e95fbbdf0147978857a623c1de2a`. Actual native
  cleanup and authenticated immutable receipt plus independent private/native
  observation precede selected-device release and atomic original-member release.
  The affected integration run passed 604 cases in 22.38 seconds. Review found a
  publication/SQL crash window; its regression reproduced the defect, then passed
  after publication intent was durably ordered before private custody creation.
  The scoped owning run passed 61 cases in 36.45 seconds, including the original
  V1 cleanup path; scoped rereview passed without a broad rerun. The final wheel
  passes isolated exact-byte/lean Node import and package-ownership checks.
  Truly never-enrolled cancellation remains open. A lost intent-commit reply
  before the first private write remains an explicit conservative accounting
  hold, not automatic recovery. Remote transport/factories, actual shared roster
  lifecycle and production qualification remain open.
- Directory entitlement handover remains a live integration gap: disabling
  authenticator-wide group replacement preserved local ownership but left no
  automatic directory projection on the legacy selector path. An explicitly
  authorized existing membership was restored through the ordinary Hub API and
  its selector verified, without granting admin or claiming a GPU start. The
  permanent import requires bounded group/grant ownership, authentication hooks,
  real spawn enforcement and coordinator-backed receipt installation. The new
  reviewed receiver is still absent from the live image.
- PostgreSQL15 receipt support is reviewed and published at compute
  `f474485736c2da5d3324bfa133cd020c3fedee29`. It uses explicit migration/reopening,
  retained external installation custody, exact original Engine binding,
  authority-row serialization and independent atomic ORM/receipt transactions.
  Actual PostgreSQL HTTP checks passed 18 cases; the affected run passed 142
  with one Source dependency skip, then that module passed separately with 26
  cases and 21 subtests. A narrow five-case probe passed with the installed
  production driver versions (psycopg2 2.9.12 and SQLAlchemy 2.0.52). The isolated
  Hub wheel imports exact reviewed bytes with the paired installed SDK and has
  no SDK/Lab file overlap. Test container/data/credentials were removed.
  This is the storage primitive, not complete installation/restore authority.
  Genuine coordinator factories, external rollback-history reconciliation,
  asynchronous user hooks and automatic directory import remain open. The
  required PostgreSQL15 release CI lane is now implemented and reviewed at
  compute `49a045765861e52a84eea7da412506a7eb671101`: a digest-pinned disposable
  hosted database, production-compatible driver and explicit real Hub modules
  with a zero-skip JUnit gate covering all four PostgreSQL modules, including
  installation/user creation with genuinely installed pinned Source/RBAC. Fifteen
  gate checks and cleanup-failure simulation passed; review corrected anonymous-
  volume cleanup. Hosted execution remains
  pending. Default test skips cannot qualify release readiness.
- Local installation and supported managed user creation are reviewed and
  published at compute `f5052fa2327f4067b55f7e2fd1569a5cdec013d7` and admin
  `c5d78ffb57a13783c51464996eceeca94140814c`. The actual PostgreSQL/Source/
  coordinator chain executes installation, authenticated user creation, original
  hook/default roles, retained receipts, successor activation and the next
  ordinary group operation. The affected run passed 283 cases and 130 subtests,
  with no skips. Review found an interrupted external activation-acceptance gap;
  the regression reproduced it, then four focused repair cases and 45 owning
  cases passed. Scoped rereview passed. A separate single positive chain passed
  with Python3.12 and production SQLAlchemy2.0.52/psycopg2 2.9.12 using genuinely
  installed admin/RBAC dependencies. This is not a full driver matrix.
  Three wheels passed isolated exact-module-byte/import and package-ownership
  checks; the admin frontend was skipped and release closure remains unproven.
  Only journal/receipt/audit successors are supported in this increment; actual
  changed Source entities/Control grants remain fenced pending Task4C/3C.
  Local logical backup custody does not qualify production backup/restore.
- A user-visible CIT regression is confirmed: the final installed adapter removes
  all legacy GPU choices, including MuJoCo, and rejects legacy GPU spawning.
  Intermediate legacy-selector logs do not prove final profile visibility.
  Central policy lacks the MuJoCo profile/image and personal compatibility path;
  Task4C must restore both final selection and policy-controlled spawning,
  preserving existing homes and NVIDIA EGL/VirtualGL behavior. The native NVML
  cgroup cap is the intended memory boundary; exact-image OpenGL qualification
  remains required alongside preserved historical CUDA evidence. No guard was
  removed, user selection changed or live MuJoCo workload started here.
- Original dirty checkouts remain preserved. No main branch was merged and no
  new application image or live database was changed.

## Monitoring coverage increment

Reviewed per-node GPU telemetry coverage alert source is published at cluster
`c678352182013d36f75c98c6a4c0ae2e6ef3d077`. Eleven actual promtool scenarios
passed, as did the owning rule/dashboard check. It compares fresh advertised
capacity with deduplicated fresh device telemetry, allows legitimate extra
physical UUIDs and retains unknown inventory as unknown. It is not deployed here.

Read-only Prometheus inspection found six reporting UUIDs versus seven advertised
GPUs. GPU2 has no exporter Pod because its explicit exporter-deployment label is
false; the other three targets are healthy. This is a telemetry exclusion, not a
hardware-failure or free-capacity result. Matching numeric driver versions do not
establish compatibility: GPU2's loaded core/UVM source versions and native guard
settings differ from the working-node tuple. Exclusion intent and safe exporter
compatibility still need validation. No label or runtime setting was changed.

## Read-only runtime observation

The [timestamped Kubernetes snapshot](../../platform-staging/qualification-20261027/cluster-readonly.json)
records all seven nodes Ready and uncordoned. This earlier snapshot advertised
2 + 1 + 2 + 2 = seven GPUs; the restoration recorded below supersedes that count. A fresh
[GPU2 inspection](../../platform-staging/qualification-20261027/gpu-inventory-readonly.json)
sees both physical A100s under driver 615.71.09. Its active device-plugin UUID
allowlist contains only `GPU-16128952-b438-556a-00bb-93039ee24e56`, matching
the current native qualification authority. The second UUID,
`GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6`, is excluded from ordinary scheduling
by configuration. The earlier full physical audit counted eight cards; current
full eight-device admission/qualification remains open. No allowlist was widened.
The existing `jupyter-gottam` and `jupyter-muslim` containers were Ready, Running,
with zero restarts. This observation does not prove kernel state or data recovery.

Fleet GitRepo objects report `paused=false`; a blanket statement that Fleet is
paused would be inaccurate. The qualification/reconciliation hold remains in
force: no reconciliation or watched-branch publication was requested here.
No GPU device allowlist, driver, NFS configuration or existing Pod was changed.

## Test effort and hosted CI

Focused receiver tests took about five seconds; the full compute repository run
was 3m42s, not thousands of receiver-specific cases. The latest complete admin
run took under one second. Implementation iterations now use focused tests and
affected interface checks; a full compute run is reserved for a frozen release
checkpoint or an identified cross-cutting regression. Existing safety assertions
and production acceptance requirements remain unchanged.

GitHub [check 122411921461](https://github.com/mul-cps/cps-compute/actions/runs/40567311598/job/122411921461)
for published source `c6b1cc9` was rechecked on 27 October and
failed before any step started. Its annotation reports account payment failure or
a spending limit requiring increase. Local results remain local evidence; hosted
CI is an open release gate until the account issue is resolved and jobs run.

## Personal MuJoCo and directory policy — reviewed partial source

CIT's installed final profile filter removes legacy GPU profiles for administrators
as well as ordinary users. The replacement preserves personal account/home identity
and compiles fixed resources from the shared catalog. The disabled MuJoCo variant
is 10 GiB, 8 hours, with no approved image yet. Directory linkage uses explicit
issuer/client/connector/subject bindings; it does not infer identity from email.

Reviewed source: compute `2c2eab5a153e6e61b0d21a8b8a95b14e64adcc3e`,
admin `6572debab1e9b2bf15ba66a176a75a9ad5a91e73`, catalog
`7cb8bae2bb0db3df51f4c43bccaeb3cbba95feb2`. The initial affected run passed
283 cases and four subtests; a later per-profile correction passed four focused
cases. The final confirmed-stop correction passed 28 cases from rebuilt paired
wheels and one explicit absent-Pod regression. Independent review approved the
partial candidate after fixing missing personal post-stop routing. Missing cleanup
proof retains the reservation; original verified Node cleanup releases it once.
These are software fixtures, not image/native rendering or live deployment proof.

Reviewed Task4D now retains exact supported local reservation and runtime Control
audit successors, including actual directory grant renewal/withdrawal with a
selected allocation live and historical cleanup afterward. Remote installed
factory wiring, actual subject enrollment, exact-image NVML/EGL combined-budget
and desktop qualification remain required. MuJoCo is not restored on the live Hub yet.

## Work still required for production

1. Finish shared-workspace lifecycle integration, one-time custody-preserving
   migrations and asynchronous user hooks. The ordinary-group receiver, Source
   authorization/journal and dispatcher are source-reviewed; runtime activation,
   lifecycle cleanup and restoration across both consoles remain unqualified.
2. Qualify the final deployed software/image/policy tuple, cross-Hub reservations,
   full-pool packing, teaching reclaim, distributed cleanup and startup bursts.
   Preserve passed no-MIG isolation evidence; only uncovered or changed scopes
   need new hardware evidence.
3. Verify student access, native Shares and RTC identity/removal, notebook batch
   success/failure artifacts, dynamic Lab states and consolidated profile UI.
4. Complete runtime-preserving GitOps promotion, monitoring and restore exercises,
   then publish the pinned compatibility matrix and qualified release artifacts.

The acceptance requirements in [qualification](qualification.md) remain binding.
No source-only result closes a live acceptance or release gate.

## Reviewed runtime successors and partial MuJoCo producer update

Compute runtime successor commit `752e709ffdd41a1376d36bf12cacaa2296aec959`
passed independent scoped review after complete argument binding and reopened-store
custody corrections. Its exact paired wheels passed three focused production-driver
cases (24.27 seconds). The earlier 288-case affected run predates these fixes and
is not represented as a final full rerun. Remote factories and maintenance writers
remain outside this local supported-installation result.

CI commit `f747d34c70e26896893982116c1765fcce4691ad` requires 52 cases across
eight PostgreSQL modules and the selected personal cleanup case. Its JUnit gate
passed 37 tests; two actual production-driver cases passed in 42.05 seconds.
Independent review approved the continuation. Hosted CI remains unexecuted due
to the recorded account billing block; local runs do not close that release gate.

Compute `e5f4e520d963fcfb475760a7e78e1c7e94f928b4` and cluster
`25a2ca7844967c1ada9c7a2f6018f1c2a05913b0` add the reviewed partial exact-image
MuJoCo producer and controlled operator-envelope tooling. Exact archived checks
passed 19 compute and six harness tests. Staged per-process CUDA/GL attribution,
separate GL over-cap rejection and original manifest-byte retention are covered
in software. Reset status explicitly remains unknown: the fifth peer-survival
receipt is omitted, so this cannot qualify or enable the personal profile.
Continuous reset observation, envelope-to-target-policy promotion and physical
GPU/EGL/Xpra execution remain required. Both reviewed source branches were pushed
and their remote SHAs verified; no main merge or live deployment occurred.

## Installed event support and eight-device restoration preparation

A [read-only NVML query](../../platform-staging/qualification-20261027/gpu2-event-support-readonly.json)
returned success and supported mask `0xff9f` for both GPU2 A100 UUIDs. The
reviewed bounded observer selects relevant mask `0xc008` (critical Xid plus
supported unavailable/recovery notifications). This confirms advertised API
support on the loaded NVML library; no event registration, CUDA allocation,
reset or continuous-window qualification occurred. Both cards also reported
40 GiB, zero allocated memory and zero volatile uncorrected ECC errors during
the parent read-only check. Those observations do not qualify isolation.

The node-specific two-UUID plugin configuration proposal passed Kubernetes
server dry-run; absence of its new ConfigMap key was verified afterward. It
was not applied; the later restoration uses the existing `plain` configuration instead. Native catalog/budget guards require qualification
for every advertised UUID, and alternate CDI file hashes are retained. A lone
allowlist change would conflict with native starts. Physical advertisement and native sharing qualification are now tracked separately;
the later restoration below supersedes the pending advertisement decision.
No device capacity/status field is patched to manufacture a count. That earlier retained
snapshot counted eight physical and seven advertised GPUs.

## Reviewed qualification handoff and concrete readiness progress

Reviewed published source now includes reset correction `55b59f9`, protected host
loader `b13c2058`/`818263ce`, and final promotion `fd96cc0`/`93ac2cf1`. Reset
correction passed 33+7 owning archive checks; loader passed 34+8. Promotion's final
correction passed 8+2, including actual runner main/execute/finally output fed
unfiltered into promotion under synthetic native/API IO. Original indexed source
and window bytes remain authoritative; terminal partial bytes must equal the
completed stream and both owned cleanup statuses must be exact. These overlapping
owning suites are not a sum of unique tests or hardware evidence. Independent
scoped reviews passed after the recorded findings were corrected.

The [actual corrected host loader](../../platform-staging/qualification-20261027/mujoco-host-loader-actual.json)
now succeeds in the exact host mount/process namespaces using the protected
hash-verified NVML inode. No NVML initialization, event registration or CUDA
allocation occurred in that check. The [exact historical image](../../platform-staging/qualification-20261027/mujoco-image-preload.json)
was pulled to GPU2's cache and its repo digest read back through CRI. Pull took
107.25 seconds and left 75.43 GiB free; the image was not executed. This supersedes
the earlier cache-absence observation, not the remaining image-runtime checks.

Installed Node/Hub packages still lack candidate support; no genuine immutable
two-operator candidate authority or normally started exact-image pair exists yet.
Reviewed package/image installation and genuine Source enrollment must precede
the controlled physical CUDA/EGL/Xpra/window run. No old neutral authority, UID
or pool is relabeled to manufacture it. Actual publication/activation, desktop
and observed user training, second-device/full-pool acceptance and the original
production gates remain open. No main merge or Fleet reconciliation occurred.

## Paired runtime candidates built and published privately

Exact reviewed source `fd96cc0` produced SDK and Hub wheels with complete source,
RECORD, import and nonoverlapping SDK/Hub/Lab ownership verification. The Node
image uses the existing pinned Python 3.12 Node recipe; the Hub overlay inherits
the actual immutable installed Hub base and replaces only the two hash-pinned
distributions. Both builds and dependency checks passed.

[Candidate image evidence](../../platform-staging/qualification-20261027/reviewed-runtime-images.json)
records immutable private registry references and exact remote manifest/config
readback. The Node default command ran inert with no API/GPU calls. Hub image
checks verified 161 installed package records, new module imports and the actual
CPSKubeSpawner entry point on Hub 5.5.2/KubeSpawner 7.1.0. Both runtime checks used
no network, a read-only root filesystem, dropped capabilities and no GPU access.
Repository visibility was verified private before and after publication. These
are distinct candidate tags, not a qualified production release.

No candidate image was deployed. Installed Source/Hub/Node state and existing
research workloads are unchanged. Controlled operator setup requires two genuine
independent canonical operator identities; CPS bjoern and CIT akadmin cannot be
counted twice. The Source supports neutral workspace owners, but Hub service
accounts are not automatically canonical person members. The second operator
account is a requested missing input, not permission to fabricate an identity.
A normal authenticated Source roster/client and custody-preserving installation
are still needed before genuine operator workspaces and the physical run.

## Actual installation and Source bootstrap prerequisites

The reviewed SDK's real `NodeConfiguration.load` accepted the mounted current
authority and 43 distinct retained immutable configuration captures. Existing
image-successor custody supports a Node-only edge followed by a paired-Hub edge;
a combined Node-plus-Hubs edge remains refused. No new generic transition is
needed. Actual retained runtime binary hashes match the packaged bootstrap, and
the installed CPU-only native health validator passed. Persistent custody was
read without rewriting it. Released-only ledger rows do not prove a drained
runtime or provide permission to replace its history.

The existing proposal helper currently refuses both actual Hub baselines: their
private-input init helper is independently pinned to image `435c0806`, while the
main Hub image is `46ffa869`. Its equality assumption is incompatible with those
actual full Deployment specs. A narrow correction must bind the real separate
helper and preserve its exact inverse before rendering an executable upgrade.
No Deployment image was patched around that refusal.

The current paired admin source `6572deb` also differs from the historical
`42526e4` adapter branch. Its workspace creation persists only a stopped local
record; start requires a pre-existing neutral owner and an injected qualified
filesystem adapter. It lacks the older branch's genuine account-receipt adapter,
stopped CPU preparation and registration/provision client operations. Those
historical APIs must not be treated as current or installed capabilities.
Integrating this normal account/storage prerequisite remains necessary; it does
not by itself complete managed roster removal, Shares/access closure or the full
Task3C lifecycle. No account, membership, workspace or storage was created here.

A [fresh full-worker read-only inventory](../../platform-staging/qualification-20261027/eight-gpu-inventory-current.json)
now records eight distinct physical A100 UUIDs: two 40 GiB cards on each worker,
all reporting driver615.71.09. At that capture, capacity and allocatable were2/1/2/2.
GPU2's captured active plugin config permitted only its first UUID. This verifies inventory
and the exact configuration mismatch, not device isolation or restoration.

The narrow existing upgrade-helper correction has now passed independent scoped
review and a fresh current-tree run: nine focused cases passed in2.78seconds.
It accepts only the exact independently pinned actual435c helper containers,
retains them unchanged through Node-only and paired-Hub rotations, and preserves
the original coupled-helper path and full-spec CAS inverse. Altered image,
command, seed, mount or security bytes are refused. Both exact captured helper
commands also passed CPU-only candidate-image checks using actual nonsecret seed
bytes, including unsafe-file refusals. No live installation or native authority
transition follows automatically from these checks.


## Eight-GPU advertisement restored (21:06 UTC)

The [live post-change verification](../../platform-staging/qualification-20261027/eight-gpu-advertisement-restored.json)
records **capacity and allocatable 2/2/2/2: eight GPUs**. All four workers now
select the same existing `plain` device-plugin configuration, already the
Helm/Fleet default. The only live mutation was a UID/resource-version/old-label
conditional update of GPU2's `nvidia.com/device-plugin.config` label from its
singleton qualification configuration to `plain`. No ConfigMap, driver, image,
capacity/status field or running user Pod was changed. Config-manager logged
the successful reload, and Kubernetes reported the actual two-device inventory.

Before restoration, two dedicated QA Pods assigned native 5/10 GiB caps on
GPU2's second UUID, passed actual CUDA device-identity checks and reached
Running/Ready. Both were deleted with exact UID preconditions, and the original
controller verified cleanup: all four retained second-card cap records were
offline/pinned with zero charge and no application clients. This verifies
device access and cleanup, not pressure/isolation/MPS/restart qualification.

After the plugin reload, both devices' complete native inventories, the first
root's entire retained custody, driver generation and boot identity matched the
pre-change capture. The complete CDI file set, bytes, hashes, owner and mode
matched; the plugin atomically replaced its provider file, changing its inode.
Native shared admission retains its separate qualification requirements; eight
advertised devices do not constitute eight qualified native sharing roots.


## Reviewed neutral bootstrap packages and release gate

Compute `87c5f6d121e2d87476a351aee416ec00bb9471d4` and Source
`f4c83fd03c2e31b25ff39a4367d4f04d2e0dfb25` close the software-only neutral
account and stopped central workspace/PVC preparation increment. Independent
frozen-source review passed. The owning checks passed three actual PostgreSQL
vertical cases, 163 affected compute/Hub checks and 33 Source tests with 85
subtests. These overlapping lanes are not a combined unique-test count.

Exact committed SDK/Hub/Source wheels passed RECORD, source and installed-byte
checks for all 197 packaged Python files. One full stopped-preparation PostgreSQL
case then passed against the installed wheels, verifying 112 loaded module
origins against wheel bytes. Source frontend hooks were disabled: this proves
the backend package boundary, not frontend or production image qualification.
NAS/Kubernetes fixture I/O remains synthetic; no live account or PVC was created
by this acceptance test. Normal managed Start remains closed pending the full
shared lifecycle and installed runtime writer coverage.

Compute `16340ba623015cf0fa86528148251a4672990b58` publishes the mandatory
nine-module PostgreSQL release gate, pins the paired Source commit above, and
requires all three neutral acceptance identities plus original critical cases
and selected cleanup with zero skips. Fifty focused report-gate checks pass.
Hosted run40584252193 failed before job steps; its actual annotation still
reports account payments/spending limits. No hosted execution pass is claimed.


## Second-card peer OOM/recovery measured

The [trusted second-card measurements](../../platform-staging/qualification-20261027/second-card-peer-oom-20261027.json)
pass both 5/10 GiB directions using the reviewed exact-image/source runner.
The 5 GiB victim retained4608MiB and the 10 GiB victim retained9728MiB; each
rejected cap+256MiB with typed PyTorch OOM, retained pressure for at least eight
seconds, and completed the synchronized64MiB recovery kernel. Each peer
completed16 synchronized kernel ticks inside the held OOM interval and continued
across rejection/recovery. Four independent physical samples per direction
confirmed more than6GiB of physical headroom. Original seals/processes stayed
unchanged and both native charges returned to baseline. Root independently
reassessed the retained actual traces with the unchanged pinned assessor.

Owned exact-UID Pod deletion and the original controller verified cleanup. All
six retained second-card rows are offline/pinned with finite equal soft/hard
limits and zero charge. Complete first-root custody matched the pre-stage
capture. GPU2's temporary scheduling fence was removed after cleanup; all four
workers remain uncordoned and advertise two GPUs each. These results cover
over-cap rejection, recovery and peer survival on this card/image. Aggregate
pressure, memory imports, restart, MPS and installed multi-root admission remain
open; no full production qualification is inferred.

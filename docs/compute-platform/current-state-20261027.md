# CPS/CIT current state — 27 October 2026

The full platform remains **limited-pilot**, not production qualified. This
record separates published source, local software checks and observed runtime.
The [previous ledger](current-state-20261023.md) retains the detailed historical
CUDA and shared-workspace evidence; those results remain valid for their tested
versions and scopes. No new CUDA qualification or deployment was performed here.

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
records all seven nodes Ready and uncordoned. GPU resources advertised by workers
are 2 + 1 + 2 + 2 = **seven**, so full eight-device acceptance remains open.
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

GitHub [check 122222776712](https://github.com/mul-cps/cps-compute/actions/runs/40513932030/job/122222776712)
for published PostgreSQL source `f474485` was rechecked on 27 October and
failed before any step started. Its annotation reports account payment failure or
a spending limit requiring increase. Local results remain local evidence; hosted
CI is an open release gate until the account issue is resolved and jobs run.

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

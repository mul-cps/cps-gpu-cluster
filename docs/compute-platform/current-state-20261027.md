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
- Original dirty checkouts remain preserved. No main branch was merged and no
  new application image or live database was changed.

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

GitHub [check 122134979594](https://github.com/mul-cps/cps-compute/actions/runs/40488132906/job/122134979594)
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

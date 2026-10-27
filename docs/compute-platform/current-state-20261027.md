# CPS/CIT current state — 27 October 2026

The full platform remains **limited-pilot**, not production qualified. This
record separates published source, local software checks and observed runtime.
The [previous ledger](current-state-20261023.md) retains the detailed historical
CUDA and shared-workspace evidence; those results remain valid for their tested
versions and scopes. No new CUDA qualification or deployment was performed here.

## Verified software

- Compute receipt and ordinary-group executor changes are published on
  `codex/hub-permission-receipts-20261027` at `f53d634d05f98caa57422de5375c9c7139c61858`:
  [draft PR 2](https://github.com/mul-cps/cps-compute/pull/2).
  The full suite passed 6,244 tests with six skips and 68 subtests; all 114
  focused permission tests passed. Six skips remain pending. The 626 existing
  framework/test warnings were reviewed and originate outside these modules.
- Admin Hub request-boundary fixes are published at
  `6a299d3f46e5c7713a4d578734fca1a025dac725`:
  [draft PR 2](https://github.com/mul-cps/e2x-course-hub/pull/2).
  All 129 admin tests passed, including 20 real-SQLite journal tests. Requests
  pin the intended Hub API,
  prohibit redirects and reject unsafe paths while preserving encoded spaces.
- The receiving Service-token API passed independent review and remains disabled
  by default. Source-console journaling is under implementation; installation
  custody and authenticator hooks remain
  outstanding. The internal Source journal now passes independent review; actual
  authorization, dispatcher and lifecycle integration remain open. An executor or unwired receiver does not enable managed writes.
- Original dirty checkouts remain preserved. No main branch was merged and no
  new application image was deployed. A private Hub wheel build verified module
  ownership, but is not a production release.

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

## Work still required for production

1. Finish and review the authenticated receiver, Source authorization/journal,
   one-time custody-preserving migration and asynchronous user hooks. Exercise
   retries, revocation, lifecycle cleanup and restoration across both consoles.
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

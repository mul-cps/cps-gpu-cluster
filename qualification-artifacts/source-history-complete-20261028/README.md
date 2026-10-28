# Complete remote Source history — 28 October 2026

Status: committed and published candidate; not deployed or activation-qualified.

The distributed coordinator can now reconstruct both complete retained reference
sets through the authenticated Source HTTPS API instead of trusting the old
32-entry window's claimed full-set hash. The original no-query observation
response remains unchanged. Pages expose references only, never Source payloads.

Paired sources:

- Compute `858f2b940b4f213711c90d826c78b765482d27db`, branch
  `codex/source-history-complete-compute-20261028` in `mul-cps/cps-compute`.
- Admin `33311f09826c9a2046405b9e2155581bb37ccf71`, branch
  `codex/source-history-complete-admin-20261028` in `mul-cps/e2x-course-hub`.

Root independently reran the bounded suites: 77 compute checks and 19 admin
checks passed. Actual local TLS coverage includes 65 retained receipts, complete
reference reconstruction, same-count mutation between pages, foreign Source
rejection, process changes and compatibility of the original observation.
Adversarial cases reject missing, duplicate, reordered or changed references,
incorrect counts/hashes, foreign database/schema/guard and malformed cursors.
An actual Source Hub journal containing 33 operations exercises paging too.
Remote branch SHAs match both local commits.

Each page's full-set commitment and canonical rows come from one SQLite read
transaction. The client independently hashes all returned records, checks the
original window is a subset, and closes the read by checking the observation
and first page again. A process nonce establishes read continuity only: it
does not attest the installed Kubernetes process, storage, backup custody or
permission to activate a pool. Those independent bindings remain required.

This change is a prerequisite for distributed installation inspection. It does
not wire or enable `nativePoolHeads`, change GPU placement, or qualify a live
cross-Hub reservation. The paired application candidates require integration
and package/deployment qualification before promotion.

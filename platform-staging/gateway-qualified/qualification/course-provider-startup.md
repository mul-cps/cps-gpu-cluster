# Course-provider application startup qualification

Status: source-level application initialization, backend tests and exact deployed-image startup checks passed; complete production integration qualification remains open. Moodle stays planned / not deployed.

Admin source: `mul-cps/e2x-course-hub`, commit `d9f33922b6d1c786c087fc7046ac527aa33a75b0`. See the [canonical application documentation](https://github.com/mul-cps/e2x-course-hub/blob/d9f33922b6d1c786c087fc7046ac527aa33a75b0/docs/cps-platform.md) and [startup tests](https://github.com/mul-cps/e2x-course-hub/blob/d9f33922b6d1c786c087fc7046ac527aa33a75b0/tests/test_provider_startup.py).

Both CPS and CIT console owners initialize the actual `CourseServiceApp` with isolated SQLite files, synthetic Hub configuration and disabled Moodle values that deliberately contain a nonfunctional base URL, nonexistent secret reference and short sync interval. Guards forbid socket connections, started Tornado periodic callbacks and Moodle provider construction. The configured Moodle secret-file path is not opened. The resulting active provider is local and has the correct console owner.

Explicitly enabling Moodle invokes its existing rejecting constructor and fails with the planned/not-deployed configuration error before persistent console files are created; network and periodic-work guards remain active. Tests do not require a working Moodle server, credential or integration package.

The complete 57-test backend suite passed at the recorded source commit. Existing tests separately exercise local CRUD/audit/provenance, source-migration reference preservation and fake-provider snapshots through the existing workspace reconciler. Their external lifecycle sinks are mocked; those tests do not qualify live Hub/compute/NFS reconciliation for an external provider.

Private evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/admin-provider-startup/report.json` and mode-0600 `backend-suite.log`. No production course records, identity links or console settings changed. Tests cover initialization, not a continuously running deployed process, production OAuth or rendered Integrations UI. Release-image/deployment qualification and complete platform acceptance remain open; do not enable Moodle or mark the overall policy qualified from this evidence.

## Exact deployed artifact

Both console Deployments currently use `ghcr.io/mul-cps/e2x-course-hub:qualification-combined-sdk-0ef266b@sha256:03634029cbe382c4a5c520f9e19a32fc047a676afbe51de47639c62e0aa1b12e`. A Git comparison confirms the newer `d9f3392` commit changes tests/documentation only, with no application, frontend, dependency, image-build or packaged-share changes from `0ef266b`.

A bounded restricted Pod ran the new startup tests against the installed packages in that exact image. Both tests passed, all 42 application Python files matched the current source checksums, and package metadata confirmed `e2x-course-hub 0.1.1` and `cps-compute 0.1.0`. Runtime imageID matched the expected immutable digest. The Pod had no service-account token or Secret/projected volumes, a read-only root filesystem, UID 10001, bounded resources/deadline and only ConfigMap/test-temporary mounts. NetworkPolicy inspection confirmed its only selected egress policy allowed no traffic. The namespace-local pull credential was used solely for image pulling.

Evidence is under `/home/bjoern/cps-platform-evidence/2026-10-06/admin-provider-image/`, including image/source inputs, fixture manifests, private test log and sanitized `report.json`. The owned Pod, ConfigMap and NetworkPolicy were deleted after success. Production console Deployments were unchanged. This proves image-level initialization under guarded, isolated conditions; it does not qualify continuous production behavior, authenticated course CRUD, live external-provider reconciliation, OAuth or rendered Integrations UI. No Moodle credentials or service were installed.

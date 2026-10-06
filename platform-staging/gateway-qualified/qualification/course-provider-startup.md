# Course-provider application startup qualification

Status: source-level application initialization and backend tests passed; deployed image qualification remains open. Moodle stays planned / not deployed.

Admin source: `mul-cps/e2x-course-hub`, commit `d9f33922b6d1c786c087fc7046ac527aa33a75b0`. See the [canonical application documentation](https://github.com/mul-cps/e2x-course-hub/blob/d9f33922b6d1c786c087fc7046ac527aa33a75b0/docs/cps-platform.md) and [startup tests](https://github.com/mul-cps/e2x-course-hub/blob/d9f33922b6d1c786c087fc7046ac527aa33a75b0/tests/test_provider_startup.py).

Both CPS and CIT console owners initialize the actual `CourseServiceApp` with isolated SQLite files, synthetic Hub configuration and disabled Moodle values that deliberately contain a nonfunctional base URL, nonexistent secret reference and short sync interval. Guards forbid socket connections, started Tornado periodic callbacks and Moodle provider construction. The configured Moodle secret-file path is not opened. The resulting active provider is local and has the correct console owner.

Explicitly enabling Moodle invokes its existing rejecting constructor and fails with the planned/not-deployed configuration error before persistent console files are created; network and periodic-work guards remain active. Tests do not require a working Moodle server, credential or integration package.

The complete 57-test backend suite passed at the recorded source commit. Existing tests separately exercise local CRUD/audit/provenance, source-migration reference preservation and fake-provider snapshots through the existing workspace reconciler. Their external lifecycle sinks are mocked; those tests do not qualify live Hub/compute/NFS reconciliation for an external provider.

Private evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/admin-provider-startup/report.json` and mode-0600 `backend-suite.log`. No production course records, identity links or console settings changed. Tests cover initialization, not a continuously running deployed process, production OAuth or rendered Integrations UI. Release-image/deployment qualification and complete platform acceptance remain open; do not enable Moodle or mark the overall policy qualified from this evidence.

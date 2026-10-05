# Qualification and releases

**The full platform is not production qualified.** Successful local tests and
configuration renders are necessary checks, not acceptance evidence for hardware,
real authentication, shared kernels or data recovery.

Run configuration checks with `scripts/compute-platform/verify-config.sh`.
It verifies pinned chart checksums, catalog/generated artifacts, disabled staging,
console/store isolation, effective Loki retention, Alloy node discovery and narrow
Descheduler scope. It runs existing storage/Jupyter manifest checks. Public PRs
use GitHub-hosted runners; GPU qualification must be a trusted operator job.

| Acceptance scenario | Required evidence before a release |
| --- | --- |
| Identity/storage | Reviewed email/person aliases; unchanged homes, named-server slugs/PVCs/NFS; one allowance per person |
| Authorization | Crafted gateway, admin and direct workload requests denied for resources, image, mount, queue, priority and entitlement bypasses |
| Permissions | Imported local grants survive login; expired grants stop being effective; instructor operations remain course-scoped |
| Collaboration | Two browser visitors retain their own identity while sharing RTC state; removed members lose existing access |
| Pooling | Cross-Hub simultaneous starts conflict atomically; rollback; shutdown-confirmed release; CPU/batch independent |
| Notebook jobs | Immutable saved notebook/files; typed tagged parameters; fresh kernel; authorized successful and failed executed notebook retrieval |
| Isolation | Intentional OOM respects the measured cap and its peer continues |
| Scheduling | Idle batch fill, teaching reclaim, protected sessions, bounded checkpoint retry and no distributed orphans |
| Startup | Representative pre-pulled CPS/CIT bursts: p95 ≤180s and maximum ≤300s |
| Defragmentation | KAI with/without fallback: free GPU availability ≥95% baseline; wait/start ≤110%; protected sessions unaffected |
| Recovery | Matching Hub/console/database/application restore, NFS archives, artifact ownership/retention |
| Moodle scaffold | Local CRUD and provenance references; no disabled side effects; enable fails; fake provider reconciles |

`compile_compute_policy.py --qualification-evidence FILE --check` binds evidence
to the exact policy hash and verifies artifact SHA256 bytes. All scenario names
are required. It is an integrity check; an operator still reviews the validity
of the results. It does not enable profiles, deploy applications or issue releases.

| Stage | Compute | Admin fork | Cluster / CIT | Notebook |
| --- | --- | --- | --- | --- |
| Pilot target | 0.1.0 | cps-v0.1.0 | v1.1.0 | 0.1.0 |
| Candidate target | 1.0.0-rc.1 | cps-v1.0.0-rc.1 | v2.0.0-rc.1 | 1.0.0-rc.1 |
| Production target | 1.0.0 | cps-v1.0.0 | v2.0.0 | 1.0.0 |

Python prereleases use PEP 440 equivalents. Preserve upstream admin tags and use
CPS-prefixed fork tags. Each release needs wheels, immutable image digests,
deployment artifacts, checksums/SBOMs, compatible Hub/chart/policy/upstream versions,
migration/rollback procedures and qualification artifacts. Build all notebook
variants from the same clean tagged source and promote the same tested bytes.
Never fabricate image digests or publish a production tag to unblock staging.

Release blocks still include measured GPU isolation/packing and Hub GPU lifecycle,
JobSet launcher qualification, complete legacy grant migration, real browser/RTC
and Shares/NFS provisioning, expired-session/idle lifetime enforcement, actual
artifact retention and matching-version restore exercises. The referenced
application docs track the exact implementation boundary.

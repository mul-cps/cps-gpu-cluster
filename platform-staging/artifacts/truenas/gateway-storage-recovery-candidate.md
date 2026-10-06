# Storage recovery candidate

Status: published source/wheel/container candidate; live recovery qualification pending.

Application commit `111dc2d41346027fae1b747646b47e982d0be628` adds per-source/group Linux process locks beside the control database and same-operation replay with a new durable generation. A failed operation retains its provisioning/archiving fence. A live peer cannot resume it; process death releases only the process lock. Archived/archiving groups cannot be provisioned. Stale completions cannot overwrite recovery. Provisioning refreshes group/owner metadata under the lock. Archive replay refreshes every group workspace and rechecks policy, ownership and confirmed shutdown before the backend writer barrier and immutable NAS/read-only mount proof.

HTTP request cancellation leaves the backend task alive and locked until completion or failure. Lifecycle start/resume/completion mutations and backend failures are audited. Deployment requires one gateway replica and its existing local Longhorn filesystem; no database copying, lock-file deletion, mixed-version concurrency or distributed SQLite/NFS is supported.

Regression tests first reproduced permanently fenced provision/archive requests, missing process-lock recovery and cancelled backend work. The final suite and installed wheel each passed 261 tests with 22 existing warnings. New tests cover failed provision replay, competing/cross-source requests, stale generation, failed archive replay, changed shutdown, actual spawned-process death, cancelled HTTP requests, audit transitions and group-binding races. These are source/Linux fixture tests, not live NAS/Kubernetes recovery evidence.

The candidate image contains all 20 matching committed Python source files, runs as UID 10001 and passes pip dependency checking. Its OCI index and referenced attestation manifest were checked against GHCR after publishing with preserved digests; SBOM and provenance were requested at build time. Exact image/wheel/attestation hashes are in `gateway-storage-recovery-candidate.json`.

The previously qualified `3d6de75` image remains separate, and production has not been changed. Next qualify forced SSH interruption, authenticated replay without database reset and gateway restart against the same fixture state. Keep legacy handover, future parent-mount prevention, privacy and full restore gates open.

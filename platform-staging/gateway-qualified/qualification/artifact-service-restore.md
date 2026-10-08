# Artifact-service snapshot restore qualification

Status: bounded same-host SeaweedFS snapshot restore passed; off-host disaster recovery and application-level ownership reconciliation remain open.

Authenticated TrueNAS API inventory found the running `cps-compute-artifacts` app storing configuration and data in `persistent1/cps_compute_artifacts`. A daily 07:00 recursive snapshot task for `persistent1`, with two-week retention, covers the dataset. Snapshot `persistent1/cps_compute_artifacts@auto-2026-10-06_07-00` actually existed. No TrueNAS replication tasks were configured. Snapshot retention is distinct from the planned 14/90-day object retention policy.

The snapshot was cloned to the dedicated `persistent1/cps_compute_artifacts_restore_qualification_20261006` dataset. Its origin and initial read-only property were verified. Inventory confirmed filer configuration, S3 credential configuration, TLS certificates/key, filer metadata, master state and volume/index files without capturing credential contents. Only this disposable clone was made writable for the restore service.

The clone started with the same pinned production image: `chrislusf/seaweedfs:4.48@sha256:aba492e2a4e4c90bff795745e8e660affa1f09e7650f5981bd7bccd1a06cd931`. The custom restore app used an internal Docker network, no published ports and clone-only mounts. Production remained running. The configured healthcheck validates TLS with the restored CA, but lacks fail-on-HTTP-error; startup alone is not counted as artifact recovery.

A pinned Python probe in the internal restore network read cloned credentials in-container and sent AWS Signature V4 GET requests over CA-validated TLS. It recovered the bucket inventory and read five restored objects (10,240 bytes each), recording SHA-256 fingerprints and hashed keys only. Unsigned root access returned HTTP 403. No production S3 requests, object writes or credential values were involved. These fingerprints are recovered-object observations, not comparisons with independently recorded pre-backup checksums.

Private evidence under `/home/bjoern/cps-platform-evidence/2026-10-06/truenas-artifact-recovery`: `inventory.json`, `clone-inventory.json`, `restore-startup-report.json`, `s3-restore-report.json`, the probe source and restore Compose manifests. The private original app config is excluded from Git. The restore app is stopped after evidence collection; retained clone/evidence permit review.

Remaining gates: off-host backup and restore destination, authenticated per-person/workspace artifact ownership through matching gateway state, independent pre-backup object checksums, retained-input/output lifecycle guarantees and the complete disaster-recovery exercise. This bounded test does not authorize enabling retention deletion or promoting the release.

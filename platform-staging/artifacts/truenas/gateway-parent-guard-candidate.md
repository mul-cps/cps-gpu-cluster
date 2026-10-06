# Parent mount guard gateway candidate

Status: built, tested and published; production deployment pending.

The candidate contains compute commit 9e5682a and matching constrained runtime
dependencies. All 243 tests passed against the installed wheel. All 20 container
application files matched source, UID 10001 was verified, and pip check found
no broken requirements. SBOM and provenance attestations were published with
preserved OCI digests and their image reference verified from GHCR.

See gateway-parent-guard-candidate.json for immutable references and checksums.
This supersedes qualification-permissions-a8426ed for further storage testing.
It does not qualify full lifecycle or permanent isolation and has not been
promoted to production.

A read-only live mount inventory found no active ancestor mounts for the
possible sibling root `/mnt/persistent1/cps_compute_workspaces`. The old compute
root is inside an actively mounted writable parent. See storage-root-options.json.
The sibling placement is an option, not a completed migration. Qualification
must verify NAS dataset/export policy, all PV/PVC and registry references,
backups, versioned root compatibility, and absence of future broad mounts.
Existing homes, storage paths and retained datasets must remain preserved.

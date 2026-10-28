# Archive compatibility rollout — 28 October 2026

Gateway and both admin consoles now run the bounded archive compatibility
packages. This is a narrow deployed remediation, not complete assignment
closure, cross-Hub or production acceptance.

## Exact artifacts and ownership

- Gateway: `ghcr.io/mul-cps/cps-compute@sha256:d9053551c63f6844b043cea3cdb7df67a2a8f2091d93b9c6f560818df07ed711`, source `ad451f574d7629dcc0e97ae1e73f490e8e3ddfb5`, SDK 0.1.1. The 83 installed module paths are retained; only storage grouping, archived-state retry verification and package version change.
- Both consoles: `ghcr.io/mul-cps/e2x-course-hub@sha256:b6856fa9c0ac1ddd42541c5bb629ee31ff8a5fd7420cd152548d6fdc8edde7b7`, source `a1c554a84358d2ad7e0d5952900b42b1f6e4c348`, admin 0.1.2. The 51 installed modules and two pre-existing overlays are preserved except the version; one provider module is added. The console SDK remains 0.1.0 and six served UI assets are unchanged.
- Wheels install system-wide as root, then restore the original runtime user (Gateway 10001, console 1000). Installation is offline, without dependency resolution. Distribution inventories and `pip check` passed before publication. No Lab files change ownership.

The manifests beside this receipt record wheel SHA-256 and verified RECORD
entries. Both remote immutable image references and OCI source revisions were
read back before deployment. No database schema migration is introduced.

## Guarded deployment and checks

The Gateway image and its paired runtime/publisher process-image declarations
were updated together using Deployment UID, resourceVersion, old-image and
old-volume-reference JSON-patch tests. CPS and CIT consoles were then updated
one at a time, pairing the image with an immutable configuration selecting
`e2x_course_hub.cps.filesystem.CourseServiceFilesystemAdapter`.

Both consoles import that provider and their mounted configuration selects it.
The authenticated Gateway approval API reports `ready: true`, unchanged policy
`sha256:9d86546fd3b9cc52eb92f030932c64600d352884f949c7d06b8b86a0f1f42620`
and approval revision
`sha256:992ae99b027bccef76a537ce91fd6f249f48df6f6263523652ae54fc8985b863`.
Qualified profile scope remains 5/10 GiB on the previously qualified device;
this rollout does not approve additional workspaces or devices.

Four focused provider tests pass, including two-group partitioning, rejection
of incomplete targets, pending state on a later group failure, and sanitized
503 handling at the assignment-close route. Gateway storage/recovery tests
were run before publication. These tests do not prove actual NAS archive
closure or permission revocation; controlled live acceptance remains open.

## Rollback and retained data

Private online SQLite backups for Gateway control/reservations and both console
databases passed integrity checks before deployment. This is a local rollback
preparation, not the required coordinated off-host restore exercise.

Restore the console image and filesystem-provider configuration reference
together: the preceding image lacks the new provider. Restore Gateway image,
runtime Secret and publisher ConfigMap references together. Original Gateway
image is `sha256:bff495fb011f10274022a9f848b27daccea69c8a7c2b24fd897c1b3e096a1524`;
original console image is `sha256:d475f8ff0d9c3075e3c995020c95ff16217eed5851b667a371a7510b7645daa2`.
Re-read current Deployment UID/spec and use guarded inverse patches, rather
than replaying a stale resourceVersion. Never re-provision an archived group
or overwrite history to perform rollback. Archive preserves files read-only.
No watched Fleet main branch was merged. Runtime-preserving GitOps promotion
remains open.

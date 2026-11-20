# Combined admin qualification

Application revision: `0ef266ba721f07a7b19b841d1dbbbd06818cb620`
(`mul-cps/e2x-course-hub`, `feat/admin-release-qualification`).
Compute SDK revision: `25e219011d761dd9a7105bd4cc2bf3996005463e`.
The SDK wheel is supplied by explicit filename and SHA256 build arguments.

The installed image passes 55 backend tests with networking disabled and
`pip check`. Copies of both live SQLite databases open at schema version 5,
preserve all rows and pass integrity checks. Their local record tables are
empty; populated migration is demonstrated only by integration fixtures.
The frontend is the previously tested five-pass refinement source.

Use `values.yaml` only as an image overlay on the reviewed runtime values.
Keep one replica and the existing Recreate strategy for each SQLite console.
Roll out consoles sequentially after consistent database backups, and verify
readiness, database integrity and static asset hashes after each rollout.

Rollback image:
`ghcr.io/mul-cps/e2x-course-hub:qualification-ui-240350a@sha256:3c9a6241fd53263c6a7037c205adc7662cfd95d56672deed535eb811c7369d1f`.
The schema remains version 5. Restore a matching database/application pair if
a later migration changes it; do not downgrade a newer database in place.

This qualification does not complete live visitor/RTC revocation, identity and
grant migration, GPU isolation or the full platform production release gates.

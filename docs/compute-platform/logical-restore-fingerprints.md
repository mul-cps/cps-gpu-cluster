# Optional Hub logical fingerprints

`scripts/compute-platform/restore-hub-backups.py` keeps its existing validation
and isolated restore default. Its optional `fingerprint_probe(namespace,
bootstrap_role, read_only_sql)` callback runs once for each separate CPS/CIT
fixture, immediately after selecting the one restored database and before
fixture cleanup. The SQL transport uses that exact database and bootstrap role,
`psql -X -qAt`, `ON_ERROR_STOP=1`, and
`PGOPTIONS=-c default_transaction_read_only=on`. The trusted callback supplies
the reviewed read-only fingerprint query; this is not a general SQL sandbox.

The CLI composes the existing `LogicalRestoreProbe` from the reviewed admin
recovery commit `e442f43577c44be9fab60d5aa9a29e98f491eec5`. This includes the
corrected role-configuration and membership queries; the earlier `a0d1bd1`
revision is insufficient. That module must be
installed or explicitly available on `PYTHONPATH`; the restore tool installs
nothing and fails before container startup if the optional dependency is absent.
The example uses the frozen admin worktree and its existing dependency
environment. Verify the checkout remains at that commit before execution.

New `backup-hubs.py` bundles include a private, manifest-hashed
`<namespace>-bootstrap.json` for each Hub. Its closed version 1 schema is
`{"version":1,"builtin_membership_grantors":["observed_role"]}`. A read-only
catalog query examines all memberships whose role and member names both start
with the literal `pg_` prefix. Exactly one distinct, safe grantor is required;
zero, multiple, duplicate-key, or unsupported identities fail closed. Neither
the current login nor configured usernames determine this value. The metadata
contains no password columns and does not make the sequential backup atomic.

The official PostgreSQL fixture initializes using that captured grantor.
The supported Bitnami fixture requires the observed grantor to be `postgres`;
other initial-role layouts need separate qualification. Only the exact matching
`CREATE ROLE` line (quoted or unquoted safe identifier) is suppressed because
initdb already created it; a missing or duplicate line fails. Before source
roles are replayed, the fixture creates a separate random, collision-checked
superuser login. Restore and fingerprint calls use that login, so source role
passwords and privileges can be replayed intact without breaking the fixture
connection. Every other CREATE, ALTER, and membership statement is preserved.

Bundles without bootstrap metadata retain the legacy logical-only exercise.
Fingerprint mode requires fresh metadata for both Hubs before starting any
fixture. Source role statements and fingerprint grantors are never normalized
or filtered to hide differences. Complete, contemporaneous source comparison
remains required, including for explicit source membership GRANT statements.
Mocked tests do not establish actual PostgreSQL15 or Bitnami PostgreSQL18 startup
or fingerprint equality.

After source review, Root can run:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/tmp/e2x-coordinated-restore-20261011:/tmp/cps-compute-native-integrated-20261009/src \
/home/bjoern/git/e2x-course-hub/.venv/bin/python \
scripts/compute-platform/restore-hub-backups.py \
/PRIVATE/current-hub-backup-bundle \
--execute --output /PRIVATE/new-logical-restore \
--fingerprint-output /PRIVATE/new-logical-fingerprints
```

Inputs remain operator-owned private files outside Git. Both output directories
must be new; the fingerprint directory's parent must already be private mode
0700. No ports, host mounts, or network are attached to the restore fixtures.
Only the locally cached exact database images recorded in the bundle are used.
Callback/SQL failures stop the exercise and remove only its unique fixture and
bootstrap environment file. If container removal itself fails, cleanup reports
the failure and still removes that environment file. Existing private diagnostics
and any captured fingerprints remain available for review.

Without contemporaneous source fingerprints, the separate fingerprint
`report.json` records observations with `source_comparison_passed: false`.
For a real comparison, supply both `--cps-source-fingerprint /PRIVATE/cps.json`
and `--cit-source-fingerprint /PRIVATE/cit.json` alongside
`--fingerprint-output`. The admin callback compares all captured table rows,
sequences, structural schema, roles, memberships, and ACL fingerprints against
their matching source scope. A mismatch prevents a completed fingerprint
receipt. A historical dump alone does not establish contemporaneous source
equality.

The callback's completed receipt requires both sources. Logical restoration and
fingerprint equality leave `coordinated_capture`, `connected_restore_passed`,
and `productionQualified` false. Actual OAuth/login, normal Start, store mounts,
coordinated capture, and off-host recovery have separate acceptance gates.

CPU-only tests replace the Podman boundary and run no PostgreSQL processes:

```bash
TMPDIR=/var/tmp PYTHONDONTWRITEBYTECODE=1 \
python -m unittest discover -s tests/compute_platform -p test_hub_restore.py -v
```

Use a temporary directory outside Git. On this workstation `/tmp/.git` exists,
so `/var/tmp` is used for the test fixtures without relaxing the input guard.

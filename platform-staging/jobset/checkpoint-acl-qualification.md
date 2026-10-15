# Qualification checkpoint ACL correction

The private-file creation failure documented in
[checkpoint-qualification.md](checkpoint-qualification.md) was reproduced with
plain Python `os.open`, without PyTorch: requested modes 0600/0666/0700 and umask
0077 all produced files reported as 0777. TrueNAS `filesystem.getacl` showed
inherited NFSv4 owner/group/everyone permissions and named USER entries, including
an inherited broad grant to UID 950. Mode 0600 alone did not remove those entries.

The operator backed up the ACL and changed only the dedicated qualification
checkpoint directory, non-recursively. The tested directory recipe is recorded
exactly in [checkpoint-acl-report.json](checkpoint-acl-report.json):

- Owner full control applies to this directory and descendant directories.
- An inherit-only owner file ACE grants data read/write and necessary metadata
  permissions, with execution disabled. It propagates to files through directories.
- Everyone may read this directory's metadata/listing through a non-inheriting
  READ ACE; no broad or named-user data grant propagates to files.

Four known synthetic checkpoint/result files retained old ACLs despite earlier
chmod corrections. Each received a separate non-recursive owner-only data ACL;
per-file ACL backups are retained privately. No artifact bytes were changed.
Production exports, dataset properties, other directories and human files were
not modified. The NFS address remains **193.170.30.58**.

The repeated creation probe now reports 0600 for all three requested modes.
Actual NFS-mounted probes, with caps dropped and no token, verify:

| Runtime UID / GID | Read | Write | Metadata |
|---|---|---|---|
| 1000 / 100 | Allowed | Allowed | Available |
| 1001 / 100 | Denied | Denied | Denied |
| 950 / 100 | Denied | Denied | Available |

The UID 950 probe can obtain metadata but cannot open data for read or write,
so its data denial is not merely an inaccessible filename. These checks concern
Unix credentials on this synthetic fixture. They do not establish isolation
between different Hub people who run with the same Unix UID, prevent forged
NFS RPC credentials, or replace Kubernetes mount authorization/network policy.
Those remain part of real project provisioning qualification.

TrueNAS readback reports the requested NFS4 `protected` flag as false. The
observed ACL/creation/access results passed, but this flag is not qualified as a
persistent safeguard against later inheritance changes. Retain ACL snapshots
and revalidate after storage administration or parent ACL changes.

All probe Pods were removed. The corrected ACL is intentionally retained on the
qualification directory; its parent remains mode 2770. Private evidence/scripts
are in `cps-platform-evidence/2026-10-06/nfs-checkpoint-acl/`, with ACL backups
available for a reviewed rollback. Do not restore inherited broad data access
as routine cleanup.

## Packaged compute artifact

The checkpoint-enabled source at `1a71bc713aac8b9ea263860b8b7ca0c878892619` was
built into a qualification wheel. All 234 tests passed against that installed
wheel using Python 3.12.13 in the existing qualification dependency environment.
Every packaged application Python file matches the source bytes; see
[checkpoint-wheel-report.json](checkpoint-wheel-report.json) for hashes.

This untagged wheel is private qualification evidence. It is not a published
0.1.0 release, a pristine dependency installation qualification, an updated
production gateway image, or approval to enable distributed/GPU access. Next
work must integrate this ACL behavior with canonical project provisioning and
qualify matching immutable gateway/SDK deployment artifacts.

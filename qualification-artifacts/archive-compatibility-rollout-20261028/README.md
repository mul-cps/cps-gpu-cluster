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

## Reproducible offline fixture

# Offline assignment archive acceptance fixture

Run the credential-free plan (default mode):

```sh
python qualification-artifacts/archive-compatibility-rollout-20261028/qualify_assignment_archive.py
```

Run the in-process Source and gateway fixture with the private, previously
qualified wheel directory:

```sh
python qualification-artifacts/archive-compatibility-rollout-20261028/qualify_assignment_archive.py \
  --in-process --wheel-dir /path/to/private-artifact-wheels
```

The wheel directory must contain `e2x_course_hub-0.1.2-py3-none-any.whl` with
SHA-256 `a582d48a333d2aaf1eeb8edf5d9fa5041799b8a992baa954a1336c6b389093a5` and
`cps_compute-0.1.1-py3-none-any.whl` with SHA-256
`ac7ccb12aed2832a79e93df7968a236ce77fc050ef54c2848d026dd5f14befff`. The
script checks both full-file digests before extracting either wheel. No wheels
or credentials belong in this artifact directory.

The fixture posts the course, term, synthetic reviewed identity mappings,
memberships, manual assignment, and two CPU workspace requests through the
pinned Source Tornado handlers. It then exercises the pinned Source archive
adapter against the pinned gateway FastAPI archive endpoint using a temporary
SQLite control store. The first attempt deliberately fails the second group;
the retry verifies the first group's archived state again and completes the
second group.

This is offline software-contract evidence only. The Hub identity lookup and
neutral accounts, compute policy and reservation calls, Hub stop/share calls,
and storage controller's read-only evidence are fixture doubles. Gateway
registrations and active storage records are seeded into the temporary control
store. The fixture does not start Hub servers, call a live Hub or gateway,
touch a live Source database, exercise Kubernetes or NAS snapshot operations,
or prove a physical read-only mount. It has no live execution mode and accepts
no credentials.

## Post-upgrade spawn check: placement gap retained

The controlled repeat start reached Pod creation, but did not reach CUDA: KAI
selected a fresh reservation on the other GPU2 A100, UUID
`GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6`, while the qualification contract
allows only `GPU-16128952-b438-556a-00bb-93039ee24e56`. The native guard held
with `reserved-gpu` before prepare. This was a newly created reservation, not
an orphan from the preceding successful run. Node-level eligibility currently
does not constrain KAI's physical-device choice. The earlier successful run
therefore does not establish reliable repeated group spawning.

The exact new Pod UID `3e9dad5c-2aa3-4ab8-83a8-562f04bddf6b` was checked before
Hub REST shutdown (204). A fresh read confirmed that Pod and its KAI reservation
Pod were absent, and the global reservation was inactive. No UUID check,
qualification record or real user workload was changed. The placement/eligible
device mismatch must be resolved through trusted qualification or supported
physical-device selection; readiness alone does not close this acceptance gate.

## Live CIT two-group acceptance

A fresh controlled course and manual assignment were created through the
running authenticated CIT console API, using the two existing reviewed test
identities without remapping them. Temporary grants permitted only the CPU
profile. Both neutral workspaces started through the actual account adapter,
Hub, gateway and NAS path; their Pods became Ready. A distinct marker file was
written in each workspace before closure.

`POST /api/assignments/archive-qa-20261028-assignment/close` returned HTTP 200,
`state: closed`, `archived: true`, `archive_pending: false`. Both groups returned
NAS `readonly: true`, mechanism `zfs-readonly`, and successful mounted read-only
verification. Repeating the same close operation also returned HTTP 200 with
fresh mount verification evidence for both groups. No live failure was injected.
The deliberate partial-failure/retry case remains the separate in-process
fixture described above.

An independent unprivileged, tokenless Pod mounted the two retained PVCs and
verified the exact marker hashes in `live-marker-verification.json`; both write
attempts failed with errno 30 (`EROFS`). The probe completed and was deleted.
Fresh Source readback showed both workspaces stopped and archived with pending
flags clear. Hub readback found no active servers and empty native Share lists
for both neutral accounts. This proves the controlled assignment closure and
retained read-only data path, not arbitrary membership revocation during an
active GPU kernel or browser RTC visitor behavior.

The two temporary grants were withdrawn (empty profiles, allowance zero);
the one-hour operator token was revoked through Hub REST (204) and its private
file removed. Course, audit history and read-only research-data fixtures remain
retained. Existing Aditya, Gottam, Muslim and Rino Pod UIDs/restart counts were
unchanged during the rollout and tests.

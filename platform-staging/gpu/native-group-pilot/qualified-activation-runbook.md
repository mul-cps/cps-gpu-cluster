# Root-reviewed activation of the two qualified group scopes

This runbook is limited to `cps:native-group-b` and `cit:native-group-a`, canonical
`interactive-shared-5`, and the selected A100 on GPU2. Use the full private
Root-reviewed artifacts whose hashes appear in the
[qualification summary](../../../compute-policy/qualification/native-groups-v1.json).
The committed disabled manifests do not activate this target. Root owns every
live source, Kubernetes and driver operation.

## Verify the frozen target

Check the protected artifact bytes and their source closure before using them.
The full private proof has raw SHA256
`ea27b779fb564ca0f98b3973b13368faada720cdc5ebbc835e7699d98bea01c3`
and canonical SHA256
`0bbef2a13f4f1eb6a376f8576498563c39fc9fe14e51b550499d1c0f93ccdaf7`.
The compiler must validate the six local reports, rather than accept the
sanitized summary as evidence:

```sh
python3 scripts/compile_compute_policy.py \
  --catalog /REVIEWED/catalog-candidate.json \
  --native-group-evidence /REVIEWED/native-group-proof.json \
  --native-group-artifacts /REVIEWED/gate-artifacts.json \
  --output /REVIEWED/new-compiled-policy
```

The resulting policy hash must be
`sha256:78fb2d7ca42585a000e58b52c297d072a11dfbc466b19f50aa9d276d567a413f`.
Its only qualified GPU profile is the canonical 5 GiB profile. The compiler's
general release lock remains `unqualified`; this bounded evidence does not
qualify other profiles or the whole GPU fleet.

Validate the exact two-scope deployment with the genuine released SDK
`Policy` and `NativeGroupDeployment`, then authorize it against complete fresh
registered records. Preserve their existing server, principal, course, term,
members, ceilings and storage version, including every registered storage
field. The deployment approval contains only the SDK's seven storage fields:
`namespace`, `pvc`, `pv`, `path`, `group_hash`, `storage_version`,
`readonly_mounts`. Server remains in the complete central record. Compare the
reviewed runtime render with fresh source, gateway and authority observations;
retain terminal history and unrelated policy/runtime fields.

## Perform the normal source handovers

Keep admin writers at zero, exclude fixture starts and retain Root-exclusive
source-token custody throughout fresh capture, review, updates and readback.
Use the reviewed UID10001 operator and source-owned APIs. Do not extend expired
grants or change identities, allowances, project fields or membership.

First migrate the six reviewed fixture grant records through their normal
source GET/PUT/readback paths, while all fixtures are stopped and their local
profiles are still unchanged. The grant helper's fixed review actor is
`operator:native-group-qualification-20261009:canonical-grant-handover`.
Its closed review contains version, source, actor, the canonical hash of the
whole fresh capture, and the actual writer-exclusion observation. The latter
requires `passed`, `source_writers_stopped` and `fixture_starts_excluded` true,
`source_token_custody: "Root-exclusive"`, the same operator and a timezone-aware
observation no more than 600 seconds old. Each PUT rechecks that exclusion.
CLI source/config/before/review pins use bare 64-character raw SHA256 values;
the review's `before_sha256` is the canonical capture hash, including its time.

After complete normal grant readback, hand over the local and registered
profiles for only the two approved scopes through the normal reviewed source
flow. Preserve all other record fields and storage bytes. A grant profile
update for the dormant unapproved fixture does not authorize its workspace.
Review partial/unknown mutation receipts and fresh GETs before any retry;
there is no automatic retry, rollback or start.

The gateway registration readback uses the separately reviewed projected-Secret
reader SHA256
`bc16a76773fefb1d6c1b97385a08d815222064b2a888bb250313949b07466fe4`.
It permits only `/config/runtime.json` through the exact Kubernetes projection
chain on a descriptor-verified read-only filesystem, with stable identities
and the pinned byte hash. Module reads and the released ControlStore remain
read-only. Retain the original reader and explicitly pin the reviewed
compatibility reader in protected metadata; do not silently replace sources.

## Activate and record the actual result

Root reviews the complete live delta, fresh healthy driver/node/boot epoch,
two-workspace allowlist, physical GPU identity, storage identities, source
readbacks, runtime render and image pins before enabling the reviewed target.
Keep the notebook `91678610…`, cap-gate `bc5b128f…` and gateway `85f2fbd3…`
digests distinct. A changed driver epoch, source closure, image or storage
identity requires fresh review of its evidence before another approved start.

Use normal source starts for the two approved scopes and capture actual
cap/device gate success and real kernel execution. Inspect the exact private
receipts, storage preservation and retained historical records. For stop or
revocation, use the normal lifecycle API; a first conflict remains a conflict
until the explicit reviewed resume completes. Reservations release only after
the gateway validates the real cleanup evidence. Retired caps retain their
original finite limits and exact UID/cgroup tombstones; do not reset them or
delete enrollment/history to simplify a receipt.

Record each subsequent activation in the
[dated runtime record](qualification/qualified-runtime-20261009.md) and its
`runtimeActivation` summary fields only after Root reviews actual poststart
captures. Commit a sanitized status and receipt hash. Keep raw source, Secret,
Pod, member, token and ledger captures private. Human CIT OAuth, browser
collaboration, larger profiles, additional workspaces and fleet-wide GPU
qualification remain outside this evidence.

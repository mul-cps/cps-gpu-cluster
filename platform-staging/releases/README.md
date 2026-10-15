# Recorded release candidates and compatibility checks

The [2026-10-09 inventory](qualification-20261009.json) records the actual
restricted no-MIG pilot: CPS `native-group-b` and CIT `native-group-a`, canonical
5 GiB, selected A100 and at most two workspaces. It supersedes the older
[2026-10-08 checkpoint](qualification-20261008.json) only for that scope.
Whole-platform production qualification, Fleet promotion and release publication
remain false. These records describe the observed 2026-10-09 result, rather than
current operational health.

The inventory pins the compiled policy and existing `release-lock.json`, full
native proof and six report hashes, committed runtime receipt, actual build
receipts, immutable image digests, source commits, wheels and Python module
bytes. Source and build receipts remain private. No raw runtime Secret, Pod,
member, token or ledger captures are copied here.

The SDK package version is `0.1.0` in three different measured builds:

| Role | SDK source | SDK wheel SHA256 prefix |
| --- | --- | --- |
| Gateway, both Hubs and admin | `a5a75b720c66af5c54b056efa6c306214d5418ca` | `3381788cf43c8b08` |
| Cap gate | `abeb5589235c17cf0945e12078a747e9ebac3b00` | `f4061c29c59305af` |
| Notebook | `980408ae6fd4396951d46b7bad00f90d03481034` | `a9f80de18f324319` |

The admin separately pins backend `5714bed…`, UI `9223264…`, all 45 backend
modules and three static assets. Full commits and hashes are in the inventory.
The notebook retains its measured image. It does not establish a twelve-image
matrix rebuilt against the current SDK. Registry qualification-image publication
is distinct from issuing a pilot, candidate or production release.

## Verify the recorded bytes

Run from the repository root with the protected evidence root containing the
inventory's relative `images/` and `group-probes/` paths:

```sh
python3 scripts/compute-platform/verify-release-candidate.py \
  --artifact-root /PRIVATE/native-evidence-root
python3 -m unittest discover -s tests/compute_policy -p 'test_*.py' -v
```

The verifier imports the existing policy compiler and its strict six-gate
validator. It checks source commits and wheel/module bytes against recorded
image verification, registry manifest digests, admin backend archive and actual
final JavaScript/CSS/icon bytes against the source/build static maps,
Hub/chart versions, compiled policy, full-platform release lock and the exact
two-scope runtime receipt. Missing or inconsistent inputs return exit 1 with
`status: "unverified"`. Success returns `compatibility-integrity-verified`, the
verified artifact/module counts and `productionQualified: false`.

The current retained artifacts verify 39 files, 31 current SDK modules, 30 cap
gate SDK modules, 30 notebook SDK modules, 45 admin modules and three static
assets. The admin image's recorded installed-byte verification counters must
match the verified backend/static counts; a fresh running-image check remains
separate. Checks use local
bytes only; they run no image, workload, registry request or live API. Root's
independent hardware and activation review remains the qualification authority.
The verifier catches stale same-version wheels, policy/lock drift, image/source
mismatches, failed receipts and broadened pool/scope claims. It never issues
release tags or changes a deployment.

This replay pins the existing compiler's raw source hash. Integrating a later
compiler extension must explicitly replay this v1 catalog and proof under the
new compiler, confirm identical compiled policy bytes, and update only the
verifier/compiler provenance pin after review. The measured hardware and
activation observation remains dated 2026-10-09.

The broader pending gates remain in
[the qualification record](../../docs/compute-platform/qualification.md#2026-10-09-qualified-no-mig-group-pilot).
The existing compiler's general release lock stays `unqualified` until the full
production acceptance evidence and compatible release artifacts are reviewed.

# Controlled 14/90 day retention qualification

Status: passed for ten controlled operator cases against real SeaweedFS S3, Argo HTTPS and Kubernetes resource-version CAS. Production lifecycle remains unqualified, and the production CronJob remains suspended.

The actual current retention template/image, CA references and projected-token volume were reused in a fresh CPU Pod on `k3s-wk-gpu1`. A unique service account received only `get` and `patch` on the ten explicitly named QA workflows. Its authenticated request for an unrelated workflow was denied. S3 calls were additionally restricted to this run's exact artifact and immutable-provenance keys. Initial writes required empty owned prefixes and `IfNoneMatch: *`; deletion required the observed ETag.

| Controlled case | Actual result |
| --- | --- |
| Temporary input before/at 14 days | Preserved before the boundary; conditionally deleted at the boundary |
| Run artifact before/at 90 days | Preserved before the boundary; conditionally deleted at the boundary |
| Active inputs and run artifacts | Preserved |
| Retained-tag inputs and run artifacts | Preserved |
| Durable retained output claim with stale tags | Preserved |
| ETag changed at the final deletion boundary | SeaweedFS rejected stale `IfMatch` with HTTP 412; changed data survived |
| Lost response before conditional delete | Data and permanent deletion claim survived |
| Lost acknowledgement after actual conditional delete | Object absence and permanent deletion claim survived |
| Fresh-process recovery for every case | No deletion retry, claim expiry, or data change |

The fixed 90-day artifact path carried the actual workflow UID, hashed owner, policy/submission hashes, metadata and immutable first-UID binding. Both retention ages used actual S3 LastModified and authenticated workflow finish time with a per-call test clock. No global clock, existing data, production settings, native GPU state or gateway database was changed.

The ten workflows used suspended templates and explicitly synthetic terminal status; no execution Pods or real notebook execution are claimed. Transport ambiguity was injected immediately before/after the real deletion operation. This evidence does not qualify the gateway's full snapshot/executed-notebook/user-retain lifecycle, off-host restoration, arbitrary crash boundaries, automatic claim resumption, or production scheduled deletion.

All 15 owned Kubernetes resources were removed using exact UID deletion preconditions. Surviving unique-prefix S3 objects and immutable provenance remain as evidence. The original production CronJob UID and complete spec were unchanged and suspended.

See [qualification.json](qualification.json) and [report.json](report.json) for source checksums, actual image identity, individual measurements, owner/UID bindings, recovery results and cleanup. The exact executed [run.py](run.py) and [fixture.py](fixture.py) are checked in beside the receipt. CPU validation: four scope/RBAC guard tests and twenty existing retention tests pass; Ruff passes.

Only a trusted operator should run this bounded fixture. Public PRs must not execute it on cluster runners. Preparation performs read-only capture and server dry runs, creates fresh identifiers, and writes a private reviewed plan. Execution checks its exact hash and captured suspended configuration before creating any QA resources. It never unsuspends the CronJob.

```bash
python run.py --prepare /absolute/new/private/evidence-directory
python run.py --execute /absolute/new/private/evidence-directory/plan.json \
  --reviewed-plan-sha256 <reviewed-exact-plan-hash>
```

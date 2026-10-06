# Notebook and artifact data-path qualification

Status: operator data path passed; full platform qualification remains incomplete.

On 2026-10-06 the deployed `cps-compute` application revision
`25e219011d761dd9a7105bd4cc2bf3996005463e` executed controlled CPU notebooks
through its `/v1` handlers, the real Argo controller, workload admission and
SeaweedFS over the existing relay. The pinned compute image was used as the
runner, with synthetic workspace identities and a candidate CPU image policy.
No human login, identity mapping, grants or Hub storage paths were changed.

| Check | Evidence |
|---|---|
| Successful and deliberately failed notebook runs | Both retain executed notebooks with the expected result/error |
| Snapshot outputs and supporting import | Old outputs stripped; selected `files/helper.py` imported |
| Typed parameters | Integer, boolean and list reach the fresh kernel |
| Immutable/idempotent submission | Snapshot hash unchanged; retry keeps UID; altered request rejected |
| Ownership of inspect/logs/artifacts/termination/retain | Other synthetic principal receives 403 for every operation |
| Runtime credentials | Main notebook has neither S3 secret environment nor Hub API token |
| Retention metadata | Both artifacts bound to the real workflow UID; retained and inactive tags verified |
| Conditional S3 deletion | Wrong ETag returns 412 and preserves body; correct ETag deletes own probe |
| Cleanup coordination | Exact disposable prefixes require UID/resourceVersion CAS before deletion |
| Retain/deletion fencing | Retain after deletion claim receives 409; permanent binding preserved |
| Retained data | Four retained fixture artifacts survive the same cleanup sweep |

The cleanup probe simulated an age of 100 days for its own exact prefixes. It
performed real S3 deletions and Kubernetes annotation CAS. It did not scan or
delete unrelated data. Temporary admission image allowances were removed after
each fixture. The operator archive contains the full reports and scripts; its
immutable report hashes are:

- `2026-10-06/argo-notebook-live/report.json`: `e3bf0aade3442c8ceea9ab4d6155f3152357d2df5a1ecac42ec013991ceec811`
- `2026-10-06/argo-notebook-live/conditional-delete.json`: `ef65587045c25eba3736c82235122721c8ddb698c5f62fcdd8e3c9a4932f72fb`
- `2026-10-06/argo-notebook-live/lifecycle-report.json`: `e554376ac15d96c4da60a236b28258220525edf3052ae75445b1c1e248a4567c`

The runtime now enables `artifacts.lifecycle.enabled: true`, which configures
the ownership-checked retain API. This creates no cleanup timer or deletion
work. Its rollback is to restore that field from the private runtime backup and
restart the gateway, preserving every other field and its policy hash.

A one-off job using the scheduled retention service account passed verified
Argo reads, Kubernetes UID/resourceVersion metadata CAS and retained-object
dry runs with the current script and its bounded refused-read retry. This
required granting that dedicated account the chart-defined Workflow `patch`
permission. Its report SHA-256 is `b91a58c79164e7116126152027b64a27782a03ee3fe8e3d3dcd8c67059d89db2`.
Authentication failures and ambiguous metadata PATCH failures are never
transport-retried.

Scheduled cleanup remains suspended: its persistent ConfigMap/template still
needs the current image/settings, and permanent provenance write restrictions
and activation qualification remain open. The final notebook-image matrix,
canonical human identities, Hub grant migration and real browser/RTC scenarios
remain open. These reports do not satisfy the catalog's all-scenario release
gate. See [canonical compute application documentation](https://github.com/mul-cps/cps-compute)
for application/API contracts; keep deployment activation and rollback here.

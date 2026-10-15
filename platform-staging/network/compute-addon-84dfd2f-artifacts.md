# Current compute addon and CPU artifact qualification

Status: verified candidate artifacts and initial fixture preparation; captured before the controlled runtime attempt.

The later [CPU Argo attempt and observed cleanup](notebook-argo-84dfd2f-run-19dd7c214a8e.md) record one successful notebook and an incomplete full CPU gate. These remain qualification candidates, without production deployment or release.

The batch-profile selection and resource-correct plain Hera snippets from compute
`84dfd2fa09b68e77a46f62d1a0fd6da0a42b359b` are packaged in wheel
`f4390d13cd158700904091bffe8607534230a06dd46e16fdc77a0317a3882821`.
The ten addon tests passed, including generated Hera serialization and current
central-policy validation. This records packaged source, not human UI qualification.

The gateway candidate is
`ghcr.io/mul-cps/cps-compute@sha256:2cc3b7924ea3a051ea871aac35e833e9dff020932e381f04d2b557e06aa99cc9`.
Remote digest/source/wheel bindings, all 21 Python modules, all 5 addon assets,
79 locked package versions, UID/GID 10001 and `pip check` passed.

The standard CPU notebook candidate is
`ghcr.io/mul-cps/cps-jupyter-notebook@sha256:eac3085e567e85de3df63b84f985ef3f20dffcc75a55ccccbc4be66026384f1d`.
It installs only that wheel offline onto exact locked base `1fab0663…`, without
dependency resolution. All21 modules, all 5 addon files, all 315 package versions,
30 Jupyter configuration hashes and `pip check` passed. It retains JupyterLab 4.5.7,
RTC 4.4.1 with the ydoc server extension enabled, and UID 1000/GID 100.
All five startup fields match the locked base in both raw registry configuration
and runtime inspection. Docker schema 2 is required here to retain the health
check; the intermediate OCI digest is superseded. This thin CPU distribution has
no attached provenance/SBOM. The canonical release exporter retains OCI
attestations: changing its media-type flag would conflict with the pinned
BuildKit provenance contract, so that exporter was left unchanged. A matching
runtime distribution and release provenance still need qualification.

An isolated two-notebook Argo fixture is prepared for these exact current images.
Seven preparation tests pass, scripts compile, default execution is a network-free
dry run, and its 21 sanitized objects are not installed. The test is intended to
check success/failure executed notebooks, immutable snapshots, selected imports,
typed parameters, idempotent UID, artifact provenance, archived logs, ownership
denials and credential-free kernels. Those live outcomes have not been measured.

The authenticated SeaweedFS endpoint accepted creation of one empty test bucket
but rejected IAM `CreateUser` with `AccessDenied`. No test identity/key or cluster
credential was created. The exact empty bucket was deleted; its absence, the
original two identities and the production bucket were verified. Embedded IAM
read-only behavior in [pinned 4.48](https://github.com/seaweedfs/seaweedfs/blob/4.48/weed/s3api/s3api_embedded_iam.go#L2596) is a source-backed explanation for the denied
write; its exact live runtime flag has not been independently confirmed. A reviewed
administrative provisioning route is required before this fixture runs. No service
restart or IAM configuration change was made.

The adjacent [canonical 12 build report](notebook-canonical-build-70471b9-completion.md)
qualifies the historical 704 build artifacts. It excludes these later addon fixes
and does not establish runtime qualification of all variants. Admin c91 remains a
separate candidate bundled with compute 34; no final complete release tuple is
claimed. Production GPU isolation/scheduling, human collaboration/identity, complete
recovery and release gates remain open.

The [machine-readable record](compute-addon-84dfd2f-artifacts.json) binds private
receipts by SHA256. No new SBOM scan, GPU workload, queue change, Fleet/main
promotion or formal release was performed.

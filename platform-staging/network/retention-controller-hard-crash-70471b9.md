# Controlled retention-worker hard-crash evidence

Status: passed for the bounded process-crash fixture; production lifecycle remains unqualified.

The current controller committed a permanent deletion claim through real Kubernetes resource-version CAS and completed its final live identity/provenance checks. The fixture worker then received SIGKILL immediately before calling conditional S3 deletion. The killed worker returned no sweep report.

A separate, freshly started recovery process ran the unchanged controller against the same real Argo HTTPS, Kubernetes and SeaweedFS APIs, with a clock advanced another 100 days. It preserved the deletion claim, skipped the snapshot, reported zero deletions/errors and made no deletion retry. The snapshot body hash remained unchanged.

One suspended synthetic terminal workflow was used; no execution Pods were created. The workflow, fixture Pod and temporary ingress policy were removed with UID preconditions. The synthetic snapshot and immutable provenance records remain as evidence. Production admission, scheduled deletion and live configuration were unchanged.

See [the receipt](retention-controller-hard-crash-70471b9-report.json), [executed fixture source](retention-controller-hard-crash-70471b9-fixture.py.txt) and [launcher source](retention-controller-hard-crash-70471b9-launcher.py.txt). Source hashes match the executed bytes.

Synthetic terminal status and time limit this result. It proves preservation after an actual worker-process kill at this barrier. Real executed-notebook lifecycle, crashes at other mutation boundaries, automatic deletion resumption, network failures and off-host restores remain open. Keep automatic cleanup suspended; public PRs must not execute this fixture on cluster runners.

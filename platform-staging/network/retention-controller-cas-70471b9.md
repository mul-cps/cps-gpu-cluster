# Controlled artifact-controller CAS and ambiguity evidence

Status: passed for the bounded operator fixture; production lifecycle remains unqualified.

The current controller ran against real authenticated Argo HTTPS, Kubernetes resource-version CAS and the SeaweedFS S3 API. Four suspended workflows used synthetic terminal status and a clock advanced by 16 days. They contained no execution templates or Pods.

- An eligible snapshot was conditionally deleted using its observed ETag.
- A durable retained claim protected a snapshot despite stale `retained=false` tags.
- Injected ambiguity after successful conditional deletion preserved the permanent deletion claim and authenticated object absence.
- Injected ambiguity before the delete preserved both the object and deletion claim. A later sweep did not retry deletion or expire the claim.

All four workflows, the fixture Pod and temporary ingress policy were removed using UID preconditions. Two surviving synthetic snapshots and immutable provenance records remain as private fixture evidence. No scheduled cleanup, production configuration or approved image catalog changed.

The initial attempt targeted a status subresource absent from the live Argo CRD. It failed before S3 writes and its sole workflow was removed. The corrected fixture used ordinary workflow status updates; the initial failure report is preserved privately.

See [the checksummed execution receipt](retention-controller-cas-70471b9-report.json). This does not qualify real executed-notebook lifecycle, actual controller process crashes, automatic resumption, network-failure recovery or off-host restores. Those gates remain open.

## Executed fixture sources

The receipt includes SHA-256 hashes of the exact [fixture source](retention-controller-cas-70471b9-fixture.py.txt) and [launcher source](retention-controller-cas-70471b9-launcher.py.txt). The archived bytes match the privately executed scripts. These files contain configuration/credential references, with credential values read only inside the controlled Pod.

The launcher consumed privately prepared, fresh workflow identifiers and the checked-in controller source. Its four records passed server-side dry runs before execution. Reproduction requires fresh identifiers, an external private evidence directory, the matching controller bytes, trusted operator access and the configured gateway service identity. Keep automatic cleanup suspended. The archived launcher creates suspended synthetic terminal workflows and removes its Kubernetes resources with UID preconditions; it preserves surviving synthetic S3 objects and provenance. Public pull requests must not run this fixture on cluster runners.

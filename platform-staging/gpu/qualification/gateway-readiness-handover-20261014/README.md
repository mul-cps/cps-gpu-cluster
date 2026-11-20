# Gateway readiness package handover

The controlled Gateway-only handover to immutable image `440711b2…` passed on
2026-10-14. It packages readiness fix `8ecb7e38`, which removes repeated full
approval observations from immutable configuration getters while retaining
fresh workspace, authorization, node-reference and revocation checks.

[receipt.json](receipt.json) records the actual Pod identity, image, approval
revision, completed replacement delivery journal, retained original seed/PVC
custody and exact hashes of private proof files. It contains no credentials,
runtime Secret data, unrestricted logs or database archives. The final protected
native inventory was zero active caps and zero charged bytes at cutover.

Only the Gateway image, its immutable publisher binding and its one image trust
pin changed. Both Hub images/configs and Source remained unchanged. The old
Gateway process was absent, its replacement mounted the exact approved runtime
data, and all four processes acknowledged the same fresh approval revision.
The retained delivery controller completed the new seed/journal using its
existing Role UID/full-rule guards and narrow replacement-process GET names.

Validation: 1863 core tests, exact installed wheel files (43), UID10001 and
`pip check`; six private operator CPU guards and Ruff. Root also independently
verified the published OCI manifest/config against the built image and reviewed
the concrete CAS plan before execution.

This is package handover evidence. It does not establish MPS isolation,
scheduling qualification or production readiness; later native state may change
when separately authorized workloads start. The full private receipt is pinned
by SHA256 `057fef84b6d2e036c229ce7dc890d47d29365f15c590c3e7db0408c416176191`.

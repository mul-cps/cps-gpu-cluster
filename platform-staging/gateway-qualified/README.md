# Gateway application/policy qualification pair

Application revision: `25e219011d761dd9a7105bd4cc2bf3996005463e`.
The image passes 203 installed-package tests with networking disabled, plus
`pip check`. Use the image digest in `values.yaml` together with the exact
`compute-policy/generated/policy.json` artifact and its recorded hash.
Set `policyJson` from that file when rendering the chart; the overlay alone
does not configure a deployable installation.
The runtime JSON `policy_hash` must match this artifact too; changing only the
ConfigMap causes startup to fail with `Deployment policy hash mismatch`.

The former deployed catalog differed only by lacking `workloadScheduling`.
Current code deliberately rejects it at startup. Interactive work uses
`cps-interactive` / `cps-homework`, and batch work uses `cps-batch` / `cps-batch`.
These settings are policy-owned, not submission overrides.

GPU profiles remain disabled. Identity aliases, grant migration, lifecycle
cleanup and distributed GPU qualification are separate unresolved gates.
The university federation hook remains disabled pending ICT registration.

The ownership-checked artifact retain API is enabled in the runtime JSON with
`artifacts.lifecycle.enabled: true`; scheduled deletion remains suspended.
See [notebook/artifact operator qualification](qualification/notebook-artifacts.md)
for evidence and its identity/image-matrix limitations.

For rollback, restore the former policy ConfigMap, runtime `policy_hash`,
and previous image:
`ghcr.io/mul-cps/cps-compute:qualification-fa48334@sha256:409231d125fb9e2ace3b4356ea4ff5d142dd351bdde7d6ac5be8ad80c56caafe`.
Former policy hash:
`sha256:bd2269a93fef4de1e6fc0124d6a6b07d11ac9708eb4b3fb56dd4f3d790ada2ce`.
Keep private runtime credentials and state databases unchanged.

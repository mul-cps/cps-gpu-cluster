# Storage HTTP authorization and matching gateway candidate

Status: six bounded live rejection checks passed; positive lifecycle remains open.

The production TLS service was probed through its certificate DNS name with
CA and hostname verification enabled. Missing and invalid service credentials
returned 401. CPS and CIT service credentials targeting an unknown workspace
returned 409. Each monitoring credential returned 403. These requests did not
register a workspace, acquire a storage fence or call the NAS.

See storage-http-authorization-report.json. This qualifies rejection behavior
on qualification-5771df5, not positive provisioning on the new candidate.

The matching permission-check candidate was published as
`ghcr.io/mul-cps/cps-compute:qualification-permissions-a8426ed`.
See gateway-permissions-candidate.json for exact application and build recipe
revisions. OCI index, platform image and attestation digests were preserved
and read back from GHCR; the attestation references the original image digest.
Production deployment and Fleet promotion remain unchanged.

Next gates are a controlled positive workspace registration with qualified
neutral Hub ownership, authenticated provision and verified PV/PVC binding,
writer reconciliation, archive and mounted read-only proof using this candidate.
Identity aliases, production GPU qualification and release promotion remain
separate open gates.

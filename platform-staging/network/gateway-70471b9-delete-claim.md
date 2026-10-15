# Committed deletion claim precedes owner retention

Status: live committed-claim refusal passed; actual object deletion/recovery and concurrent controller race remain incomplete.

The installed 70471b9 gateway submitted a suspended operator fixture in the fixed `cps-workflows` namespace and bound its real UID to an immutable S3 snapshot. Using its actual Kubernetes CAS adapter, the operator committed a snapshot lifecycle state of `deleting`. The authenticated owner then requested retention over certificate-verified HTTPS. Both the first request and retry returned 409. A fresh workflow read verified that the deletion claim stayed identical; the S3 object still existed and had not acquired a retained tag. Another identity was denied, and no execution Pods were created.

The deletion claim was an operator fixture, not the production retention/deletion controller. No S3 delete was called. This tests refusal after a committed claim rather than a simultaneous controller race or crash-recovery scenario. The fixed namespace, image permission restrictions and installed gateway code were preserved.

The fixture workflow was deleted with its exact UID precondition and NotFound verified. Its gateway Pod and temporary Pod-scoped Argo ingress rule were removed. Synthetic S3 input/provenance evidence remains preserved. Exact results are in `gateway-70471b9-delete-claim-report.json`. Real identities, completed-output retention, production Service routing and full release qualification remain open.

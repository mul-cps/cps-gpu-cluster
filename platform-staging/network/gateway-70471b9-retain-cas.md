# Retention stale-write protection

Status: live stale resource-version rejection passed; deletion-controller race and completed-output retention remain open.

The packaged gateway retained an actual S3 snapshot via verified HTTPS and the real Kubernetes API in `cps-workflows`, using a suspended operator fixture with synthetic identities. After retention, its installed `KubernetesClaims.patch` method attempted to restore the earlier lifecycle value using the workflow's stale resource version. The API rejected it as a conflict. A fresh read verified that both the retained state and original audit entry survived, and S3 reconciliation preserved the retained tag. No fake Kubernetes adapter or namespace override was used.

The owner retry, other-owner denial and zero execution-Pod assertions also passed. Cleanup deleted only the fixture workflow with its exact UID precondition and verified absence; the gateway Pod and temporary Pod-scoped ingress allowance were removed. Retained synthetic S3 evidence remains. Exact results are in `gateway-70471b9-retain-cas-report.json`.

This validates stale-write protection, not a live retention-versus-deletion race, an artifact deletion recovery exercise or owner retention of a completed executed notebook. Production deployment, image permissions, human accounts and storage paths were not promoted or migrated.

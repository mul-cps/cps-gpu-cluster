# Gateway owner snapshot retention qualification

Status: controlled owner snapshot retention passed in the real fixed lifecycle namespace. Real human identities and full executed-output retention remain incomplete.

The packaged 70471b9 gateway served certificate-verified HTTPS with synthetic owner/other identities. Its installed submission, immutable S3 provenance and retention code operated on a real workflow UID in `cps-workflows`. An operator-only policy wrapper added suspension before submission digest calculation; the lifecycle namespace restriction and application code were unchanged. The workflow remained suspended and no execution Pods were created. Production image approval was not expanded.

The owner retained the real snapshot through the HTTP endpoint. Kubernetes saved the UID/resourceVersion-bound retention annotation; a repeated request returned the same audit entry. Another identity received 403. The installed S3 reconciliation code marked the actual snapshot retained. Exact assertions are in `gateway-70471b9-retain-report.json`.

Cleanup deleted only the fixture workflow using its exact UID precondition and verified NotFound. The gateway Pod and temporary Pod-scoped Argo ingress policy were removed. Retained synthetic S3 input/provenance evidence remains preserved; no broad data deletion occurred.

This proves snapshot retention on an operator-controlled suspended workflow. It does not prove owner retention of a completed executed notebook, deletion-race recovery, real Hub identities, browser authorization, production Service routing or release readiness. Those gates remain open; production deployment and image permissions were not promoted.

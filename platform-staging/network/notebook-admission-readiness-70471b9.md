# Notebook candidate admission prerequisite

Status: incomplete. Read-only live comparison found zero of the twelve notebook candidate references in the workload boundary's `approved-images` parameter. The parameter contained only the pinned Argo executor image. See [the observation receipt](notebook-admission-readiness-70471b9.json).

Published images, matching compute wheels and verified SBOM attachments do not establish workload admission readiness. No production image parameter, policy, binding or deployment was changed by this check. Thirteen server-side dry-run Pod requests now verify the image boundary: the approved executor baseline passes, while all twelve candidate notebook references are denied for lacking explicit image approval. The requests share the same credential-free CPU Pod shape, isolating image approval from hardware/runtime behavior. Policy, binding and parameter contents were checked unchanged afterward. No Pods were created; this is not runtime qualification.

The artifact controller requires the fixed `cps-workflows` namespace and immutable provenance for that namespace. Earlier isolated-namespace notebook execution and synthetic fixed-namespace controller fixtures therefore do not jointly prove real executed-notebook lifecycle in production. That integration gate remains open.

Qualification must establish a reviewed runner image, compatible resource and credential injection, admission behavior, successful and failed executed notebook retention, controller process-crash recovery and rollback before production cleanup activation. Keep automatic deletion suspended. GPU isolation, identity, human collaboration and off-host recovery gates remain independent requirements.

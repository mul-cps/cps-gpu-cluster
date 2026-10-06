# Candidate workload admission boundary

Status: 16 isolated server-side admission requests passed; live Argo/executor/runtime enforcement remains separately qualified.

`scripts/compute-platform/qualify-admission.py` clones the candidate policy and parameter CRD into a unique namespace and API group. It waits for successful CEL type checking and establishes a rejected automatic-token request before testing, avoiding a false pass while the binding propagates. Only server-side dry-run requests are submitted; no workload images execute.

Approved credential-free workload and pinned executor/secret shapes are accepted. Rejected cases cover automatic service-account credentials, overridden executor commands, loader environment, executor binary-shadow mounts, user Secret environment/envFrom, projected service-account tokens, an untrusted wait image, shared process namespaces, scheduler/service-account overrides, unapproved image digests, mutable tags and mounting the executor's approved Secret in a user container. Negative cases must identify the isolated policy in the rejection, so unrelated failures do not count as boundary enforcement.

Evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/admission-expanded/report.json` and `manifest.json`, binding the report to checksums of the qualification script, candidate policy and parameter CRD. Namespace deletion and removal of the isolated policy/binding were confirmed. Existing production admission bindings were unchanged.

This is request-time qualification of the candidate policy, with fake image digests and trusted-executor shapes. It does not prove production parameter alignment, live controller-generated Pod compatibility, runtime credential isolation, profile resource enforcement, GPU isolation or protection against all possible workflow attacks. The gateway, deployed admission bindings, Pod Security, quotas and scoped RBAC must still be qualified together before a release.

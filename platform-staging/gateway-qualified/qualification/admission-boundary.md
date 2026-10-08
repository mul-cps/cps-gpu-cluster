# Candidate workload admission boundary

Status: 16 isolated server-side admission requests passed; live Argo/executor/runtime enforcement remains separately qualified.

`scripts/compute-platform/qualify-admission.py` clones the candidate policy and parameter CRD into a unique namespace and API group. It waits for successful CEL type checking and establishes a rejected automatic-token request before testing, avoiding a false pass while the binding propagates. Only server-side dry-run requests are submitted; no workload images execute.

Approved credential-free workload and pinned executor/secret shapes are accepted. Rejected cases cover automatic service-account credentials, overridden executor commands, loader environment, executor binary-shadow mounts, user Secret environment/envFrom, projected service-account tokens, an untrusted wait image, shared process namespaces, scheduler/service-account overrides, unapproved image digests, mutable tags and mounting the executor's approved Secret in a user container. Negative cases must identify the isolated policy in the rejection, so unrelated failures do not count as boundary enforcement.

Evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/admission-expanded/report.json` and `manifest.json`, binding the report to checksums of the qualification script, candidate policy and parameter CRD. Namespace deletion and removal of the isolated policy/binding were confirmed. Existing production admission bindings were unchanged.

This is request-time qualification of the candidate policy, with fake image digests and trusted-executor shapes. It does not prove production parameter alignment, live controller-generated Pod compatibility, runtime credential isolation, profile resource enforcement, GPU isolation or protection against all possible workflow attacks. The gateway, deployed admission bindings, Pod Security, quotas and scoped RBAC must still be qualified together before a release.

## Live binding and quota qualification

`qualify-live-admission.py` now audits the existing workload policy and binding against the candidate, accounting only for Kubernetes defaults (`matchPolicy: Equivalent`, empty object selectors and wildcard rule scope). Validations, fail-closed parameter lookup, namespace restrictions and Deny actions match. CEL type checking is current with no warnings. The audit checks policy/binding identity and specs again afterward and rejects parameter changes during its requests.

Eleven fresh server-side dry-run requests passed against the actual `cps-workflows` binding. An approved credential-free Pod shape with explicit bounded CPU/memory requests and limits was accepted. Omitting those resources was rejected by `cps-workflow-ceiling`; scheduler, service account, automatic/projected token, shared-process, unapproved digest, mutable tag and Secret env/envFrom overrides were rejected by the live workload-boundary policy. Each negative result must identify its expected enforcement source. Three unit tests ensure normalization cannot erase namespace, scope, validation or binding-action changes.

The current live parameters approve only the pinned executor image. The positive shape uses that already-approved image; it does not approve notebook/runner images or prove an executable user workload. No parameters, bindings, quotas or catalog state changed, and no Pods were created. Earlier controlled notebook runs demonstrated real Argo execution under temporary image allowances (see [notebook data path](notebook-artifacts.md)); those earlier runs do not replace current gateway/runtime qualification.

Evidence is `admission-expanded/live-stable-report.json` and `live-manifest.json` in the private operator archive. Reproduce without changing cluster state:

```sh
python scripts/compute-platform/qualify-live-admission.py \
  --context '<reviewed cluster context>' --evidence /path/to/new-live-report.json
```

Controller-generated Pod compatibility, runtime executor credentials, profile/image alignment and GPU isolation remain release gates. This evidence does not authorize adding image allowances or activating GPU access.

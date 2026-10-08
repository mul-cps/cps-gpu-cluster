The bounded Kubernetes API-server admission gate passed for Pod and quota-map
CREATE requests on 2026-10-08. This qualifies the candidate schemas and literal
CEL against Kubernetes v1.34.9+k3s1, with authenticated, in-cluster requests. It
does not qualify actual Argo materialization, KAI scheduling/binding, HAMi/MPS
isolation, GPU execution, or production activation.

The candidate starts at source commit
`d4530d0d47be76b472c8232b716cc08f4385f8ef`. Fixtures came from the pinned
40b9525 SDK wheel and the existing
`qualification-artifacts/dynamic-runtime-admission-20261007/offline-evidence`
capture. The executor digest was read from the live Argo controller's
`--executor-image` argument:
`quay.io/argoproj/argoexec:v3.7.18@sha256:8651f0d1a1050be46ef28a7362cbb7387b5f5c29ce691ebddd5d99a0bb7281a9`.
Workflow owner UIDs, Pod UIDs, physical GPU assignments, quota-map generations
and the reviewed Binding target remain explicitly synthetic fixture inputs.

| Gate | Result | Evidence |
| --- | --- | --- |
| Three CRDs, three registries, three VAPs, three bindings | Server dry-run accepted; installed in isolated scope | `live-evidence-20261008/installation.json` |
| CEL type checking | All three VAPs have current observed generation and zero warnings | `live-evidence-20261008/resources-preserved.json` |
| Empty registries | Pod, ConfigMap, Binding denied: 3/3 | `live-evidence-20261008/incluster-probe.jsonl`, phase `empty` |
| Crafted Pod creates | 5/10/20 GiB, main index 0/1 accepted: 6/6 | `live-evidence-20261008/incluster-final.jsonl` |
| Crafted quota-map creates | Empty capabilities/evar accepted: 2/2 | `live-evidence-20261008/incluster-final.jsonl` |
| Bypass mutations | Wrong owner, extra hostPath, loader override, wrong indexed quota, forged/unregistered maps and extra toleration denied: 12/12 | `live-evidence-20261008/incluster-final.jsonl` |
| Registry schema and CEL | Valid reviewed quota accepted; mismatched aliases, forged quota, oversized selector and malformed UID denied: 5/5 | `live-evidence-20261008/registry-schema-probes.json` |
| Reviewed Binding negatives | Wrong target node and wrong Pod UID denied: 2/2 | `live-evidence-20261008/incluster-binding.jsonl` |
| Reviewed Binding positive | Not completed: API returns 404 because the fixture Pod does not exist | `live-evidence-20261008/incluster-binding.jsonl` |

Every GPU-shaped Pod request used `dryRun=All`; the target namespace contains
zero Pods and no fixture quota ConfigMaps. The valid Binding reached storage
and returned `NotFound`, which is evidence of the bounded request path, not a
successful Binding or scheduler integration. Live ConfigMap UPDATE/DELETE,
Pod UPDATE/resize/ephemeral-container requests, registry races/rollback and
generation coordination remain separate gates.

The live gate exposed and fixed five source defects:

1. A loop variable replaced the Pod binding's policy name with `cps-mps-shm`,
   leaving Pod admission unenforced. The policy name now has its own variable;
   a regression checks the binding references the emitted namespace policy.
2. Mixed dynamic/string secret-name list literals failed the Kubernetes CEL
   homogeneous-literal check. Equivalent equality comparisons compile.
3. Unbounded quota strings and `string(int(...))` exceeded CRD CEL estimated
   cost. Explicit wire-format bounds and bounded numeric quota comparison pass
   the server estimator and reject a one-MiB forged quota.
4. Kubernetes's Quantity OpenAPI schema caused static field warnings for
   resource maps and `emptyDir.sizeLimit`. Narrow `dyn` access retains exact
   runtime values, resource-map cardinality and cache-size validation.
5. The server adds not-ready/unreachable NoExecute tolerations with exactly
   300 seconds. Only those two unique defaults are allowed; other tolerations
   remain denied. The exact defaulting was recorded before changing the rule.

Kubernetes documents the [CEL string library and cost limits](https://kubernetes.io/docs/reference/using-api/cel/).
The local CEL test interpreter lacks `substring`, so the quota schema test
provides only that documented string operation; literal numeric conversion
and arithmetic still execute in CEL. Actual server schema tests independently
check the quota calculation and rejection paths.

The workstation reaches the API through Rancher. Its proxy submitted requests
as the Rancher user even when `kubectl --as` requested a service-account actor;
those attempts are diagnostic evidence, not actor-qualified positives. Direct
control-plane TLS connections reset. Narrow qualification SAs and 10-minute
tokens were attempted, with tokens kept only in 0600 temporary kubeconfigs.
No token or kubeconfig is in this evidence directory.

The authorized alternative used four CPU-only Jobs in
`cps-admission-runner-20261008`, pinned to
`ghcr.io/mul-cps/cps-compute@sha256:627f093c3c96038c7ecd9e9b99f0138198c23c9460cabb7bd11b19e94f465096`.
Each used requests 100m/128Mi, limits 1 CPU/512Mi, `backoffLimit: 0` and a
300-second deadline. The runner authenticated itself through SelfSubjectReview
as `system:serviceaccount:cps-admission-runner-20261008:probe`. Its role grants
only CREATE Pods, ConfigMaps and pods/binding in the target namespace. Its
script hardcodes the target namespace, allows only these resource types and
always sends `dryRun=All`.

All qualification resources are preserved. The target contains the three
empty parameter registries, three namespaced Roles/RoleBindings, four service
accounts including `default`, and only the automatically created root-CA
ConfigMap. The runner namespace contains four CPU Job Pods, four Jobs, two
service accounts including `default`, its script ConfigMap and the automatic
root-CA ConfigMap. There are three uniquely grouped CRDs and three uniquely
named policy/binding pairs. The first render also created the inactive orphan
binding `cps-mps-shm`, which matches only the target namespace and references a
nonexistent policy. It is preserved as evidence; the corrected active binding
is `cps-dynamic-admission-live-20261008-boundary`. No preexisting resource was
deleted or modified. See `resources-preserved.json` and
`final-empty-registry-reset.json` for exact names, UIDs and final contents.

The final source suite passed 89 tests in 33.728 seconds; the full command
output is `live-evidence-20261008/unit-tests-final.txt`.

The reproducible local test command is:

```sh
PYTHONPATH=/tmp/cps-cel-qualification-20261008 \
  /home/bjoern/git/cps-compute-worktrees/end-to-end/.venv/bin/python -B \
  -m unittest discover \
  -s platform-staging/scheduler/qualification/dynamic-admission -p 'test_*.py'
```

`server_validation.py install-empty` renders and checks the isolated resource
set, refusing undeclared drift. Its workstation probe modes verify the actual
authenticated username and fail if proxy impersonation does not work.
`incluster_probe.py` is the trusted CPU runner; the exact phase inputs, observed
identity, server responses and sanitized bootstrap resources are committed
under `live-evidence-20261008`. These are qualification artifacts, not a
production registry coordination protocol.

# Cold native-authority retirement proposal

Use only reviewed, redacted object captures. No API/executor, Secret values,
credential minting, host changes, normal-history exceptions or initial heads.
New files: cold_retirement_plan.py, test_cold_retirement_plan.py, this document.

Input closed {version, scope, old_namespace, new_namespace, node, namespaced,
cluster, secret_metadata, fleet_metadata}. Scope {node,node_uid,gpu_uuid} is the
actual GPU2 identity; only k3s-wk-gpu2 is supported. Namespaced captures cover
cps-native-system,cps-compute,jupyterhub,cit-jhub,kai-scheduler. Raw spec/object
SHA provenance is retained because redacted objects are NOT API preimages.

Output is a DRAFT, never an execution authorization:
* exact UID/RV/original spec SHA scale-zero intents for dedicated Node,
  Observer, head writer and old writer ONLY; Root must materialize full-spec
  JSON test from a fresh actual object matching the pinned raw spec SHA;
* exact UID/RV/full-subjects CAS -> [] for every mutating native-prefixed
  RoleBinding/ClusterRoleBinding with the reviewed nine native principals;
  all rules/non-native bindings and shared Gateway/Hub/Binder specs preserved;
* exact dedicated SA UID/RV automount=false intents (no shared SA mutation);
* old Namespace UID/RV/labels/annotations CAS: restricted PSA and retirement
  scope annotations. Existing proof objects stay readable, not deleted;
* fail-closed VAP+binding candidates freezing old native ConfigMap writes,
  old dedicated-SA/controller/token resurrection, native grant recreation and
  namespace removal. No path-string claim of complete hardware exclusion.

Create the inactive policy only after exact old workloads/writers are stopped
and old scope archived. Do not create its binding yet: first require server CEL
compilation/typechecking and a separately scoped admission negative matrix,
including real TokenRequest, Scale, direct User and omitted/empty-namespace
ServiceAccount grants. Binding promotion is a separate Root-reviewed step:
a CEL error can fail closed across matched API writes. No renderer test
qualifies CEL. Kubernetes explicitly excludes ValidatingAdmissionPolicy and
ValidatingAdmissionPolicyBinding APIs from VAP matching; neither candidate can
protect itself or the other policy/binding. Exact admission-policy/binding RBAC
denial, admin privilege closure and explicit identity/group SAR proof are a HARD
external gate. No self-locking or frozen-admin claim is made. A protected expected
UID/reference is only an external Root-reviewed boundary, not fabricated CAS.
Qualification must also show explicit
SubjectAccessReview(user,groups,resourceAttributes) denials. Rancher --as / self
SAR can report the administrator rather than requested identity and are NOT
proof. System root-CA CM updating is intentionally denied in archived namespace.

Required external gates remain hard/incomplete: complete privileged GPU2 runtime
and process exclusion (including any host mount alias), credential audience and
existing-token incapability, GitOps source retirement and observed no-resurrection,
API admission negative matrix, unchanged CPU/batch/NFS/entitlement/homes/personal
workloads. A fenced namespace is not automatically a global physical GPU lease.
New namespace/ledger/qualification/heads/driver activation is a separate approved
operation; no old journal or history is interpreted as recovered by this plan.

TDD: missing-module RED; synthetic captured full shape + wrong controller UID,
extra SA, wildcard/broad native RBAC, GPU1 targeting, redacted spec misuse,
non-native mutation, missing capture closure. Then actual capture rendering and
independent source review. No live invocation or application by author.

Direct retired SA/User regrant denial resolves omitted or empty RoleBinding
subject namespaces to the request namespace. This candidate deliberately does
not freeze all authenticated/service-account Group bindings: that would block
unrelated infrastructure and read-only grants. Broad Group, aggregated-role and
other indirect capabilities remain an external HARD gate. The binding cannot
be promoted until complete actual retired-credential denial is independently
verified, using explicit SubjectAccessReview identities/groups and relevant
admission requests. Rendering or a warning-free CEL compilation does not prove
that capability closure or unchanged CPU/batch availability.

## Root verification, 2026-10-22

17 renderer tests pass. The API server compiled generation 3 of a temporary
unbound candidate with no expression warnings. A temporary binding was then
qualified using an exact-operator AND dryRun-only match condition, read back
before requests. Admission-cache readiness was established by an actual denied
Scale request before evaluating the matrix. All nine corrected cases passed;
see `platform-staging/native-approval-delivery/cold-retirement-admission-evidence-20261022.json`.
The temporary binding and policy were removed and their absence verified.

An initial matrix issued immediately after binding creation was affected by
admission-cache propagation and is not qualification evidence for early allowed
requests. The corrected matrix waited for the denial readiness control.
No fixture requests persisted. This does not qualify TokenRequest, all resource
kinds/subresources, credential revocation, physical exclusion or recovery.
The proposal remains incomplete and must not be executed as an approval.

## Dedicated writer-identity candidate

`retired_writer_admission_candidates` is a separate VAP/binding pair. It denies
CREATE/UPDATE/DELETE/CONNECT for exactly the five dedicated retired SA usernames
(Node, Observer, current/old delivery and handover operator), across all resource
groups and subresources regardless of inherited RBAC. GET/LIST/WATCH are not
matched. Shared Gateway/Hub/Binder identities and ordinary users are not selected.
No blanket Group binding freeze is added. Both candidates remain nonexecutable.

Reads (including Secret exfiltration), cached RPC credentials, host processes,
already established connections and existing credentials still need separate
proof. This candidate cannot establish physical/global GPU exclusion or revoke
old processes. All existing external gates remain. Server typechecking and
actual negative admission/SAR qualification are mandatory before promotion.
Review both inactive policies before separately approved binding promotion.
There is no policy-enforced writer-before-archival ordering dependency: VAPs
cannot match either admission-policy API. External policy protection and an
independent admission recovery procedure remain required. The writer resource
selector is the sole `*/*`, which covers all resources and subresources; mixing
`*` with `*/*` is invalid Kubernetes schema. API exclusions remain exceptions to
the broad resource selector, not a guarantee of universal mutation interception.

## Root writer qualification, 2026-10-22

The corrected writer candidate compiled on the API server with no expression
warnings. Using a short-lived token bound to the actual running Observer Pod,
a TLS-verified direct Kubernetes API request identified the expected SA (not
Rancher impersonation). Its unchanged-role annotation PATCH with dryRun=All
returned 200 before the dry-run-only fence and 422 with the intended policy
message after it. GET still returned 200 and the Root dry-run PATCH succeeded.
Temporary policy and binding were removed. No role or controller was changed.
The broad CREATE/DELETE/CONNECT matrix is not proved by this PATCH result.

50 explicit identity/group SubjectAccessReviews denied all five retired SAs
create/update/patch/delete/deletecollection on both admission-policy APIs with
zero evaluation errors. Current effective Role/ClusterRole rule inventory found
no Secret-read grants for those SAs. All 1702 resources in 47 current Fleet
bundles were decoded, including gzip/binary resources, with zero errors and no
literal retired-controller names. This bounded search does not prove arbitrary
template expansion, future grants or no resurrection. Those gates remain open.

See `platform-staging/native-approval-delivery/cold-retirement-writer-evidence-20261022.json`
for the bounded receipt. Kubernetes API exclusion reference:
https://kubernetes.io/docs/reference/kubernetes-api/admissionregistration/validating-admission-policy-v1/

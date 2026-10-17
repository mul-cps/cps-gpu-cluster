# Isolated admission qualification

`qualify_admission.py` is inert without `--execute`: no API, credential, or file
access. Root must review the source before running the explicit command with an
administrative kubeconfig identity allowed to impersonate the fresh test SA:

```text
python -I -B qualify_admission.py --execute \
  --private-dir /absolute/new/owned-private-directory [--context reviewed-context]
```

The destination must be empty, owned `0700`, and outside Git. Receipts and the
created-resource UID journal are written `0600`. Output contains only status
and counts. Raw credentials, Secret contents, API response messages and request
bodies are not logged. This source alone is not an actual K3s admission pass.

The qualifier creates four fresh random QA namespaces and the real test SA
`cps-native-head-delivery` in the first. Its temporary Roles allow only bounded
ConfigMap operations and GET/PATCH/escalate on two exact QA Role names. A second
pointer/Role fixture allows wrong-target and unrelated-operator requests to
reach admission. All fixtures and rights remain inside the four namespaces.
No Pods, Secrets, images, workload jobs, production namespaces or production
policies are created or changed.

The three policy/binding pairs come directly from production `render._policies`
using actual isolated pointer/observer Role UIDs. Only unique names and explicit
four-namespace policy/binding selectors plus a namespace match condition are
added. Production validation expressions stay byte-identical. These guards
retain foreign-actor enforcement on protected QA targets while excluding every
production namespace. Real denied-request barriers precede the matrix.

Every matrix request uses `dryRun=All`, including positive approval CREATE,
pointer PATCH and named Role GET growth in all four namespaces. Negative cases
cover extra data, name/namespace targets, mutability, owners/labels, unsafe Role
verbs/static rows/wildcards/removal/foreign names, and foreign operator writes.
Unrelated foreign operator operations must succeed. A denial counts only when
HTTP403/Forbidden names the exact temporary ValidatingAdmissionPolicy and says
it denied the request; RBAC refusal, API422, or another policy cannot pass.

UID cases run last: the qualifier deletes and recreates isolated same-name
fixtures, then patches their genuine replacement UIDs against the old pins.
This avoids counting an API-invalid fabricated metadata UID/name as admission
enforcement. API byte-size/immutable-field validation is not attributed to the
VAP. Writer CREATE outside the four QA namespaces is omitted; no outside
permission is granted. Wire fixtures exercise admission shape only, not SDK
approval authentication, Source authority, GPU behavior, or production rollout.

Available policy type-check warnings are recorded and fail qualification;
policy/binding UID/specs are reread before and after the matrix. Cleanup always
runs in `finally`, using each original UID and freshly read resourceVersion,
refusing replacement identities and retrying bounded conflicts. All created
objects must subsequently return404; residue makes the receipt fail. Namespace
cleanup also removes Kubernetes-generated namespace defaults. Interrupted
processes that cannot run `finally` require Root to inspect the retained exact
UID journal and QA namespace names; there is no name-only cleanup fallback.

Offline tests include the complete setup/matrix/UID-replacement/cleanup flow
against the qualified official Go CEL evaluator and a local API fixture. Set
`CPS_NATIVE_PENDING_CEL_EVALUATOR` to that executable for the complete CPU
matrix; otherwise this integration test skips. Root still owns actual execution
and must require a passing receipt with zero residual resources before binding
production policies or starting the adoption Job.

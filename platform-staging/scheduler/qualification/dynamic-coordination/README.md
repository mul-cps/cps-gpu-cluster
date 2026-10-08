# QA dynamic quota generation fence

This is an **inactive QA candidate**, with no cluster changes, workload submission,
GPU/device changes, publishing, registry enrollment, or production activation.
The renderer emits zero webhook Deployment replicas and an empty manual registry
by default. It grants no Node access or sealer PATCH permission by default.

The adjacent `dynamic-admission/{render_runtime,injected_policy,quota_policy,binding_policy}.py`
contracts remain unchanged. Their protected registries are still manually managed.
Their prior CEL/live evidence does not qualify this service or its coordination protocol.

## What the fence decides

`fence.authorize(review, registry, read)` is a pure AdmissionReview v1 core. The
injected reader returns a current API object, or `None` only for a confirmed 404.
Every missing, partial, stale, deleting, recreated or conflicting generation and
every API error denies. There is no enrollment or seal HTTP endpoint.

A binding must carry the actual Pod UID **and current Pod resourceVersion** in
`Binding.metadata`, and name the reviewed Node. Nonempty Binding annotations and
labels are denied: the binding subresource otherwise merges them directly into
the Pod. Kubernetes v1.34 source passes Binding UID/resourceVersion into native
storage preconditions, which stop a named replacement or concurrent Pod update:
[BindingREST source](https://github.com/kubernetes/kubernetes/blob/v1.34.0/pkg/registry/core/pod/storage/storage.go#L180-L208).
This is source evidence, not a live API-server qualification of this candidate.

The service GETs the persisted **final KAI-injected Pod**, original Workflow UID
and spec, exact Node UID/resourceVersion/inventory, and both complete quota maps.
It derives the random prefix from all four actual main-container configMapKeyRefs,
then checks the evar reference, volume and pinned KAI owner/index naming rule.
The Pod annotation only corroborates those references; a Workflow/user annotation
cannot select maps or authorize a binding. The complete reviewed Pod executable
spec, annotations, labels and parent references must match the observed final Pod.

The Node receipt includes every advertised GPU index/UUID with a reviewed evidence
digest. Numeric CDI selection must match the explicit inventory entry, never a
UUID guessed from syntax. Node inventory is operator-reviewed evidence tied to
that Node generation; its digest alone is not authentication or a hardware probe.

Both maps must retain their independently pinned UIDs/resourceVersions, exact
Pod owner, complete quota/evar data and native `immutable: true`. This permanently
prevents data changes even if an earlier admitted writer commits after review.
The webhook also denies owner/metadata changes, re-creation and deletion while
the **original Pod UID exists**, including terminating, completed or failed Pods.
Cleanup requires an independently reviewed cleanup actor, exact map UID and RV
DeleteOptions preconditions, and confirmed original Pod absence. A replacement
Pod with a different UID does not resurrect the old UID; its generation cannot
use old binding approval or old maps. API errors never establish absence.

## Bounded sealing hook and explicit transition

KAI creates mutable maps and populates them in stages. `sealer.seal` is a callable
QA hook for a separately trusted coordinator. It first GETs and validates the
complete actual generation pair, then makes at most two JSON PATCH requests.
Each PATCH tests **both UID and resourceVersion** before adding `immutable: true`.
It rereads both persisted sealed receipts and the Pod/Workflow/Node before return.
It has a total deadline of at most three seconds, with no overwrite/retry loop.

The two PATCHes are **not a transaction**. `SealAborted.partial_record` reports
only proved returned receipts. The first seal may remain after a second conflict.
No rollback or binding approval is published. Retry requires explicit review of
partial receipts; the original stale receipt is rejected. An already sealed exact
receipt is a no-op. A timeout after a successful PATCH has an uncertain outcome:
read and review the exact objects before retry; do not infer success or undo a seal.

The current quota policy explicitly forbids immutable maps. `quota_transition.py`
therefore renders a **new, separate QA replacement candidate** preserving the
existing staged shape, owner and UID checks and adding only the reviewed coordinator
false/absent-to-true seal transition for complete, pinned maps. It does not edit
the existing policy. An additional Allow cannot override the old Deny: the old
QA quota-policy binding must be deliberately replaced as part of a reviewed
qualification transition. Keep the existing full injected-Pod admission contract
and binding boundary in place. Do not combine both incompatible quota bindings.

The coordinator may not populate/rewrite maps. Explicit cleanup remains subject
to both the replacement quota policy and the generation-fence webhook. Optional
sealer RBAC grants GET/PATCH only the currently reviewed map names, and GET the
exact Pod/Workflow names. It grants no delete, broad update or Node edit rights.
Cleanup writer authorization/RBAC and protected registry management are separate
operator responsibilities, not automatically granted by a review record.

## Manual qualification sequence

1. Keep binding denied by the existing empty/manual binding registry. Pause the
   binder at the independently observed complete-map stage. Review the actual
   persisted final Pod, owning Workflow, complete mutable map UIDs/data/RVs,
   full Node/device evidence and exact authenticated writers.
2. Prepare a protected pre-seal registry and reviewed quota replacement. Install
   neither from this script automatically. Configure/test TLS, actual API-server
   admission/defaulting, correct webhook ordering and fail-closed availability
   before a supervised QA transition. The webhook is installed only after its
   service is ready; zero default replicas are an inactive artifact, not readiness.
3. Invoke the trusted sealing hook immediately before the modified binder's bind
   attempt. Abort partial/conflicting seals; cancel rather than silently roll back.
4. Independently review both final sealed UID/data/RV receipts, publish a **new
   protected registry generation**, and update the adjacent reviewed binding
   records to those same generations. A mutable/pre-seal record cannot bind.
   The immutable mounted registry loads once at service startup; changing it
   requires a deliberate new ConfigMap name and service rollout. No registry
   writer/controller, signing mechanism or automatic enrollment is implemented.
5. The binder sends the exact UID/current Pod RV preconditions. After confirmed
   Pod deletion, the reviewed cleanup actor may issue UID/RV-preconditioned map
   deletes. An errored absence check must retry conservatively; never detach
   owners, erase data or delete maps to recover a still-existing Pod.

KAI rollback currently deletes quota/evar maps while the Pod can still exist.
That rollback is intentionally incompatible with this fence. A binder integration
must support cancellation, confirmed old Pod removal, cleanup and a freshly
reviewed Pod/map generation. Current KAI has no qualified sealing hook or bounded
retry/cancellation handshake here. This package does not claim that integration.

## Service/manifests and remaining races

`service.py` serves TLS AdmissionReview v1 at `/validate` and readiness at
`/healthz`. It has at most eight configured request workers (four by default), a
2-second API decision deadline, per-API network timeout at most 0.5 seconds,
1 MiB body/API-response bounds, a 2-second TLS handshake/socket timeout and an
absolute 4-second post-handshake connection lifetime. FailurePolicy is Fail, webhook timeout is 5 seconds,
and sideEffects is None. Only the sealer function's explicit trusted API adapter
can PATCH; the admission path only reads. A remote API read overrun is denied.
No callers' Authorization header is forwarded to Kubernetes.

`render.py` emits review artifacts only, never applies them. Provide a separately
built/reviewed immutable image and the actual reviewed TLS CA. The TLS Secret is
not fabricated. It renders a separate QA service namespace and reads only the
target QA namespace. The target namespace must already be deliberately prepared.
`Dockerfile` requires a reviewed Python BASE_IMAGE digest supplied by the builder;
no image was built or published during this task.

Explicit `--node-name` opts into GET of only reviewed exact Node names plus a
whole-window webhook denying their deletion and changes to spec, labels,
annotations or GPU allocatable inventory. It grants no Node writes. Other status
updates may proceed, but their RV change makes binding stale until independently
reviewed. Without this opt-in the default read RBAC cannot read Nodes, so binding
fails closed. Do not widen Node permissions to make errors disappear.

**Production atomicity is not established.** Separate Pod/Workflow/Node/map GETs
are not a cross-object transaction. Final rechecks narrow a window; the native
Pod UID/RV fence and immutable maps address specific races, not all state changes.
Parent Workflow deletion/mutation can race the last read; optional Node protection
must already be effective, and a Node RV can change after the read. Physical GPU
hotplug/device-plugin remapping outside Kubernetes inventory is not fenced.
Admission requests already in flight when this candidate or manual registry is
installed, webhook configuration/RBAC changes, registry rollouts and server cache
consistency require separate live qualification. There is no durable per-Pod
coordination controller, parent freeze, transactional registry publication,
automatic cleanup, controller reconciliation or production availability proof.
Unreviewed ConfigMap finalizers/metadata operations are conservatively denied and
may need operator recovery after Pod absence. Do not deploy on a production node
or claim full dynamic packing/quota enforcement from these offline tests.

## Verification

Only local Python fixtures, local TLS HTTP traffic and the actual cached literal
CEL interpreter are used. No GPU jobs or cluster API requests are made.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/cps-cel-qualification-20261008 \
  /home/bjoern/git/cps-compute-worktrees/release-qualification/.venv/bin/python \
  -m unittest discover -s platform-staging/scheduler/qualification/dynamic-coordination -v
```

The NEW transition CEL expressions are executed; they are not checked by a Python
policy mirror. These tests do not rerun or replace the adjacent 89-test/live-CEL
evidence. Live Kubernetes CEL type/defaulting checks for the new transition, real
TLS/API authentication, service image digest, binder hook, cancellation/rollback,
concurrent admission stress, registry rollout and failure/recovery remain gates.

All **43 new tests passed**. `evidence.json` records the command, suite counts,
source hashes and explicit unqualified gates.

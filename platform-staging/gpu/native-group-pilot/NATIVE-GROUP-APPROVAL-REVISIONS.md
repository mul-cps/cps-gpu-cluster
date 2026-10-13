# Source approval revision projection

This packet is offline preparation. It does not apply resources, read Secrets,
start workspaces, or qualify broader GPU access. It preserves the reviewed
policy, driver epoch, node pool, static custody configuration, service images,
credentials and existing workload identities. Only Source-owned approvals for
the qualified 5/10 GiB profiles may change through the registry.

The canonical immutable document is shared by `gateway`, `hub:cps`, `hub:cit`
and `node`. ConfigMap data contains only `approval.json`; each component has an
actual API-created document UID and full-data hash. The revision hashes the
registry projection, not its individual namespace copies. Prior references are
retained for terminal custody and authorize no active workload.

## Operator inputs and preparation

Use the reviewed compute package containing `native_group_revision.py` and the
public `ApprovalSnapshot.from_document` API. The renderer is
`platform-staging/gpu/native-group-pilot/native_group_approval_renderer.py`.
Its default invocation is inert:

```sh
python native_group_approval_renderer.py
python native_group_approval_renderer.py --render --input /private/request.json --output /private/new-packet
```

The input is a new regular file, owned by the operator, mode `0600`. Output must
not exist; the renderer creates a `0700` directory and `0600` `intent.json`.
Console output contains only revision/count/digest metadata.

The render request has exactly these keys:

```text
version: 1
source_raw: exact UTF-8 authenticated server export of {version,generation,deployment}
source_sha256: independently pinned sha256:<raw export hash>
trusted_revision: independently captured Source registry revision
policy: current complete catalog
qualification: reviewed unchanged NativeGroupDeployment config
baselines: all four actual component Deployment records
captured_at: aware timestamp of the authenticated capture, no older than 120 seconds
documents: null for document creation; actual four ConfigMaps for projection binding
```

Do not take Source provenance pins, component declarations or acknowledgments
from browser requests. Content validation verifies a trusted captured export;
its hash alone does not establish its origin. Each baseline entry has exactly
`deployment`, `container`, `previous_document`, `previous_reference`. The
Deployment is the full actual API object with UID, resourceVersion and spec.
Previous projection entries are both null initially, or both complete actual
immutable ConfigMaps after a completed prior rollout. A partial prior rollout
requires operator repair. No fabricated UID is accepted as readback evidence.

## Apply and verify

1. Capture the authenticated Source export and all four full Deployments.
   Render `documents` with null readbacks and review the full guarded packet.
   Check the captured Deployment UID/resourceVersion/spec before initial
   ConfigMap creation. Create the four identical immutable document copies.
2. Capture all four complete actual ConfigMaps. Re-render with those readbacks
   and a fresh capture of the same Source revision. The packet binds each actual
   UID/full-data hash, creates immutable `reference.json` descriptor ConfigMaps,
   and returns exact full-spec JSON patches. Apply each patch with its three
   tests: Deployment UID, resourceVersion and complete previous spec. Stale
   objects, conflicting mounts/arguments and substituted document data fail.
3. Each trusted process mounts both files under
   `/var/run/cps-native-approvals/`. Non-root Hub/gateway projections use `0444`;
   the root node process uses `0400`. The node also mounts `template.json` and
   `process.json` from a node-only immutable bootstrap ConfigMap. The first is
   the unchanged reviewed typed qualification; the second contains exactly the
   actual Deployment's namespace, kind, name, UID, container, immutable image and
   service account. These seven fields bind the current controller; the running
   Pod's identity comes separately from the downward API and fresh API reads.
   It receives all three `--approval-reference`, `--approval-template` and
   `--approval-process` paths separately from its unchanged static config. Create
   the reviewed bootstrap ConfigMap before applying the node patch. SDK consumers receive
   `CPS_NATIVE_GROUP_APPROVALS_PATH`, `CPS_NATIVE_GROUP_APPROVAL_REFERENCE` and
   component/process downward fields. These are service mounts, not user Pod
   mounts. Preserve all old immutable documents and active enrollment refs.
4. Collect actual current Deployment, ReplicaSet, Ready Pod and successful
   process acknowledgments; call `readiness_intent` with those observations,
   reviewed process declarations and the freshly observed qualified DriverEpoch.
   No desired annotation counts as a loaded-document acknowledgment. The helper
   verifies the Deployment→ReplicaSet→Pod chain, both projections, image digest,
   service account, all four document copies and 30-second acknowledgments
   (allowed TTL range 15–120 seconds). An arbitrary same-image Pod, stale epoch,
   old reference or partially ready revision cannot authorize Start.
5. The resulting `enrollment_approval_reference` is the verified **node** copy.
   Gateway/Hub local-copy references must not be frozen into node enrollment.

## Named acknowledgment publication

The Root operator pre-creates one mutable ConfigMap per component with exactly
`data: {ack.json: "{}"}`. Capture all four full actual objects, including UID and
resourceVersion. The empty value acknowledges nothing. Names are operator
selected; the renderer accepts the actual names rather than guessing them from
a revision. Preserve these UIDs in runtime reader settings and publisher inputs.

### Advancing an installed publication

Use `revision_projection_intent` for the second and later Source revisions.
`projection_intent` and `publisher_intent` remain the initial-install path;
reinstalling the publishers would replace their immutable prerequisites.
The canonical Source snapshot is available through the trusted in-process
`NativeGroupApprovalRegistry.snapshot().document` API. No browser export or
additional HTTP endpoint is required.

Capture the authenticated new snapshot, all four current full Deployments,
their previous immutable documents/references, all four actual immutable
publisher bootstrap maps, and the four existing mutable acknowledgment CMs.
Retain the complete reviewed prior publication packet with an independently
pinned canonical SHA. Capture the old actual Deployment/ReplicaSet/Ready-Pod
records and all seven full named Roles before changing projections. Keep these
records unchanged for the second access step; they describe the prior process
identity, not a claim that the old Pods still exist after rollout.

After `document_intent` creates the next document candidates and the operator
captures their actual created UIDs, call the new path with the same document
request arguments:

```python
publication = revision_projection_intent(
    **request, documents=actual_new_documents,
    previous_publication=reviewed_prior_publication,
    previous_publication_sha256=independently_pinned_prior_packet_sha,
    previous_bootstrap_maps=actual_existing_bootstraps,
    acknowledgments=actual_existing_acknowledgment_configmaps,
    driver_epoch=unchanged_actual_epoch, ttl_seconds=30)
```

The helper checks the complete old Deployment spec and exact installed inputs,
the prior document/reference data and identities, actual immutable bootstrap
readbacks, existing acknowledgment UIDs, controller declarations, epoch and
TTL. Unknown fields, conflicting projections, partial rollout or changed prior
custody fail closed. It preserves all bootstrap maps, publisher arguments/env,
acknowledgment identities, process declarations and runtime settings. Each
Deployment patch changes only the two document/reference ConfigMap names and
tests the captured UID, resourceVersion and complete old spec. Create only the
new document and reference maps; **do not recreate the returned bootstrap maps
or acknowledgment maps**. Their existing objects remain prerequisites.

Before applying the Deployment patches, call `revision_access_intent` with
`projection=publication`, `previous_publication`, the retained old
`deployments`, `replicasets`, `pods`, and actual `roles` keyed by namespace/name.
It validates the old owner chains and exact prior named rules, then replaces
only the document GET name. The actual old Pod/ReplicaSet GET targets and own
acknowledgment PATCH names stay unchanged. Apply the seven Role patches under
their UID, resourceVersion and full-rules tests; existing RoleBindings remain
unchanged.

After the new processes exist, capture their actual full Deployment,
ReplicaSet and Ready-Pod objects and fresh Role readbacks. Call
`revision_process_access_intent` with the same two publication packets,
`previous_process_records` (exact keys `deployments`, `replicasets`, `pods`),
the new `deployments`, `replicasets`, `pods`, and the fresh `roles`. This second
guarded step changes only actual Pod/ReplicaSet GET names. No future name or
acknowledgment is invented. Preserve any separately managed historical custody
permissions; these helpers own only their seven named approval Roles.

Finally, use the unchanged `readiness_intent` with genuine fresh acknowledgments
and current processes. A rendered revision remains pending until all four
loaded-process proofs pass. Old document history is retained in every new
envelope; neither rendering nor Role delivery qualifies a new hardware path,
broader GPU access, or production readiness.

After `projection_intent`, call:

```python
publication = publisher_intent(
    projection=projection, documents=actual_documents, baselines=baselines,
    acknowledgments=actual_acknowledgment_configmaps, policy=policy,
    qualification=qualification, driver_epoch=actual_epoch, ttl_seconds=30)
initial_access = access_intent(projection=publication)
```

`publisher_intent` preserves the complete original static Deployment spec. It
adds the node's root `0400` `acknowledgment.json` descriptor and
`--approval-acknowledgment` argument. The descriptor has exactly namespace,
name and the actual acknowledgment ConfigMap UID. It does not contain an ack.
Gateway and Hub bootstrap maps contain `publisher.json`, selected by
`CPS_NATIVE_APPROVAL_PUBLISHER_PATH`. Each bootstrap has exactly version,
component, acknowledgment, process, driver_epoch and ttlSeconds. The process
has the seven trusted controller fields. Create the returned immutable
`bootstrap_maps` and `reference_maps` before applying the guarded Deployment
patches. All image digests, credentials and static custody remain preserved.

The same preparation is available through the inert-by-default CLI. The extra
private publisher request has exactly `version: 1`, `acknowledgments` (all four
full actual mutable ConfigMaps), `driver_epoch` (node_uid, boot_id,
driver_generation, gpu_uuid) and `ttlSeconds`:

```sh
python native_group_approval_renderer.py --render --input /private/projection-request.json --publisher-input /private/publisher-request.json --output /private/publication-packet
```

The returned `initial_access.objects` contain seven namespaced Roles and their
RoleBindings. Every rule has exact resourceNames. Each component gets GET for
its immutable document, own acknowledgment and reviewed Deployment, and PATCH
only for its own pre-created acknowledgment. Gateway additionally gets named
GET for its three peers' document, acknowledgment and Deployment; it gets no
peer PATCH permission. These are new named objects, so the operator must
confirm absence before creation; an existing conflicting object needs explicit
review rather than an unguarded apply. There is no create, update, delete, list,
wildcard or Secret permission in this packet.

New Pod and ReplicaSet names are unknown before rollout. Publishers retry a
transient denied GET without refreshing an acknowledgment. After the actual
new Pods exist, capture all four full Deployments, ReplicaSets and Ready Pods,
plus the seven actual initial Roles. Use:

```python
process_access = process_access_intent(
    projection=publication, deployments=actual_deployments,
    replicasets=actual_replicasets, pods=actual_pods,
    roles=actual_roles_by_namespace_slash_name)
```

This validates the real Deployment→ReplicaSet→Pod owner chain and exact current
executable/security template through the shared process observer. It adds only
the actual Pod/ReplicaSet names to GET rules. Every Role change tests its actual
UID, resourceVersion and full previous rules before replacement. No future Pod
UID or name is invented. A private CLI request for this phase has exactly
version, projection, deployments, replicasets, pods and roles; roles are keyed
by `namespace/name`:

```sh
python native_group_approval_renderer.py --render --process-access --input /private/actual-process-request.json --output /private/process-access-packet
```

The `runtime_settings` fragment uses all four UID-pinned acknowledgment refs,
seven-field controller declarations, the observed DriverEpoch and bounded TTL.
Only the gateway consumes all-four API readback. Hubs publish their own proof
and use the private gateway interface for the current registry head. Node
publishes its proof after a successful full custody iteration. Each writer
GETs and PATCHes its existing own acknowledgment with UID/resourceVersion/full
data CAS. No writer can create an acknowledgment or replace another copy.

The existing cleanup-only node and create-only gateway admission policies in
`render.py` match ConfigMap **CREATE** only. Named PATCH of an existing
acknowledgment does not match those policies; this packet changes neither.
The operator verifies actual deployed admission rules before rollout.

The richer acknowledgment schema is supplied by the compute package:
`version`, `component`, `revision`, `policy_hash`, `document`, `process`,
`driver_epoch`, `observed_at`. `process` contains exactly namespace, name, UID,
container, immutable image and service account. These six fields identify the
running process, while the seven-field bootstrap identifies its controller.
The node also keeps its atomic private `state/approval-loaded.json`. Preparation
never generates successful receipts or claims loaded-process readiness.

Rollback uses guarded actual Deployment preimages and retains every immutable
document still referenced by an active or terminal custody record. Do not
delete documents or rewrite the static ledger/history to make a revision fit.
Fresh live all-four convergence, Source add/remove, active-old-revision cleanup
and reservation behavior remain acceptance work until measured by the operator.

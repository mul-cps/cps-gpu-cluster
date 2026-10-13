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
   actual Deployment's namespace, container, immutable image and service account.
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

The richer acknowledgment schema is supplied by the compute package:
`version`, `component`, `revision`, `policy_hash`, `document`, `process`,
`driver_epoch`, `observed_at`. `process` contains exactly namespace, name, UID,
container, immutable image and service account. Process acknowledgment transport
and its RBAC/admission must be reviewed separately; the current node adapter
writes its actual acknowledgment atomically to private `state/approval-loaded.json`.
This packet adds no RBAC or cleanup admission exception and never synthesizes
acknowledgments or transports them as an unauthorized ConfigMap.

Rollback uses guarded actual Deployment preimages and retains every immutable
document still referenced by an active or terminal custody record. Do not
delete documents or rewrite the static ledger/history to make a revision fit.
Fresh live all-four convergence, Source add/remove, active-old-revision cleanup
and reservation behavior remain acceptance work until measured by the operator.

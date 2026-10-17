# Protected current-group Coordinator configuration (not activated)

The actual existing Gateway is already HTTPS on port8000: its single uvicorn
process has `--ssl-keyfile /tls/tls.key --ssl-certfile /tls/tls.crt`. The Service
port name `http` is misleading; it does not select the transport protocol.
Reuse `https://compute-gateway.cps-compute.svc.cluster.local:8000`, existing
`cps-compute-gateway-tls` and public `cps-compute-gateway-ca`. No TLS proxy,
second Gateway process, database owner, Certificate or auth change is needed.
Public CA GET shows CPS Compute Artifact Service CA, valid2026–2036; the CA
alone does not prove the serving certificate hostname/SAN. Root must verify
actual TLS peer identity with that CA before activation (no insecure fallback).

`endpoint.render` accepts an actual qualified SDK551 `GroupPendingContext` (loaded
from protected exact6-key NodeConfig ref and actual immutable API objects),
actual undeleted ServiceAccount objects including a separately created dedicated
binder SA, current Hub settings/readiness, exact reservation template/digest,
explicit accepted Kubernetes API audience, exact binder Pod labels and captured Gateway Pod security context with integer fsGroup10001. Readiness node process must exactly match the typed NodeConfig declaration (service_account_uid is excluded from the process declaration).
It emits a proposal only; calling the file without importing application code
prints disabled/API-false/GPU-false. No API client or executor is provided.

`snapshot_inputs` can load the Root-private captured bundle in memory with an
explicit protected NodeConfig reference. It authenticates the full typed chain
and rejects active ledger rows, returning only the public configuration subset;
no service bearer or export token is returned. Do not copy that original bundle
to Git or pass an untrusted reference from browser/submission input. Capture
fresh policy, runtime readiness2, both Hub settings, released ledger, actual
ServiceAccounts, and the exact Node4 ConfigMap plus its qualification, anchor,
pointer, current and retained approval documents. Refresh the four complete
controller templates, seven independently pinned Roles and ObserverRelease2
before building a rollout proposal; an earlier endpoint snapshot is historical.

For Node4, the protected NodeConfig supplies the namespace-local head binding.
The unchanged coordinator configuration version2 lets SDK551 select
`HeadNodeEpochObserver` automatically and follow current heads without replacing
the NodeConfig. Gateway/Hub template changes still require reviewed prospective
and actual observer captures and fresh process proofs. Keep the held Node
template digest unchanged only when the complete Node template is unchanged.

Open limitation: this renderer requires a nonempty current deployment. A global
empty head has `context.deployment is None` and is not supported here, although
SDK551 can install an inert consumer. Do not synthesize scopes to bypass it;
empty-head rendering remains separate future work.

The seed ConfigMap is immutable/public configuration; the generated init copies
only3named documents into fresh emptyDir/config0700 and files0600 owned10001.
Main Gateway reads that private volume read-only, matching SDK private_bytes
without relaxing symlink/ownership checks. Retain existing data PVC and single
Gateway Recreate strategy; new custody DB is /data/native-kai-private/custody.sqlite and the shared writer lock is /data/native-kai-private/writer.lock. Merge
fragments with fresh UID/RV/full-preimage CAS; this file does not generate a
blind Deployment overwrite. The init image is the exact authenticated Gateway
component image and must follow coordinated declaration updates.

Binder fragments contain all5native flags plus the exact reservation image flag with native-pending-coordinator-enabled=false by default and a separate explicit opt-in flag set. The binder gets its own cps-native-kai projected token and a read-only namespace-local public Gateway CA mount; existing service-account identity is caller-supplied, not a fixed replacement identity. Root may preserve the actual existing binder SA UID through reviewed operator handover.

Hub proposal preserves all groupHub settings and existing Source bearer env.
A distinct projected signed token uses `cps-native-kai` audience; Hub route
permissions are exactly v2 lease/compile/created; binder's8terminal operations
remain v1. Gateway TokenReview/SAR create and named current SA GET permissions
are additive and separate from its existing resource permissions. Never grant
Hub/binder protected-authority ConfigMap creation as part of these role grants.
Root must mount a namespace-local public CA ConfigMap at each emitted
ca_requirement.path (copy existing public CA only; no private TLS key).

NetworkPolicy intent permits only the exact dedicated binder selector in its
namespace to Gateway TCP8000. Existing compute-private-ingress does not allow
kai-scheduler. Preserve all existing Hub/admin ingress union; also check binder
egress policy. No policy here activates scheduling or opens the general public.

Remaining activation gates: accepted API token audience (not assumed), current
reservation image's immutable digest and exact security/resources template,
actual scoped resource RBAC, private-input mounts, image/process bindings,
source/grants/current approvals, live auth/TLS checks, and Root's explicit
rollout. The coordinator currently performs a cluster Pod LIST census and
source namespace Pod dry-run CREATE, ConfigMap GET/PATCH/DELETE/CREATE and
BindRequest GET. Existing Gateway privileges must be checked against those
actual operations; the small authentication grants do not implicitly provide
or claim them. Do not broaden unrelated permissions to mask failures.

GPU2 is cordoned. Stock KAI's CheckNodeConditionPredicate rejects
node.Spec.Unschedulable. True automatic placement cannot pass until separately
reviewed maintenance changes; no scheduler workaround or live qualification
is claimed. Fixed measured GPU2 5/10GiB pilot only, no MIG/driver/reset actions.

CPU verification (qualified SDK source `551379c6902791d0dd192596046669f1fe274562`):
set PYTHONPATH to this directory plus that SDK's src, packages/hub/src and tests
and the qualified test dependencies; run `pytest -q test_endpoint.py`.
Twelve tests use actual central-authority/current-context fixtures, execute both source Hub pending settings parsers (infrastructure construction substituted; actual closed groupHub structural parser and typed pending adapter execute), validate the v2
installer configuration and independent epoch parser, closed path grants,
separate projected audiences, staged-off binder flags, explicit fsGroup/process mismatch negatives and actual private materializer.
The v4 regression advances real fixture registry/head generations 1 through 7
with the same NodeConfig reference. It runs the actual SDK configuration parser,
installer, `HeadNodeEpochObserver` constructor and authenticated head loader;
external transport and receipt/process I/O are substituted. Replacing that
observer with its legacy parent is rejected. The SDK's separate
`tests/test_native_head_epoch.py` tests cover actual fixture ACK2 consumption.

Root-verified operator inputs: accepted API audience https://kubernetes.default.svc.cluster.local; preserved binder SA UID0ed4f47d-dc7f-4136-9174-6744f03f3d35; reservation v0.18.1 registry manifest digest sha256:f476965d65e49059da53b3999494a33814a45408111d12010086acfadc0131d3. These are recorded evidence, not defaults or authority injected by this renderer. No live calls were made for these follow-up checks.

The binder fragments include `podSecurityContext.fsGroup: 10000` so its added
0440 projected token/CA files are readable by the unchanged nonroot binder. Merge
this with the actual Pod security context during activation; both current Hubs
already have fsGroup1000, and the Gateway has the required fsGroup10001.

The emitted binder flags also pin `--resource-reservation-pod-image` to the exact Coordinator reservation-template digest in both disabled and opt-in modes. Replace the existing tag-valued flag when merging; do not append a duplicate flag. Actual live tag remains unchanged until explicit activation.

Private-state activation correction: the captured PVC root was UID0/mode02775, so the old sibling-of-control.sqlite lock and root-level custody path cannot satisfy the SDK private-state contract. The proposal requires the actual Gateway data PVC volume name (authenticated from its complete writable `/data` mount), mounts that same PVC in the nonroot initializer, and creates only `native-kai-private` owned by UID10001. It opens the child with `O_DIRECTORY|O_NOFOLLOW`, verifies ownership, and applies0700, clearing inherited SGID. Existing databases and the PVC root retain their bytes and permissions. All guards and execution fences must consume the explicit `writerLockPath`, supported by qualified SDK551. Do not apply an earlier dry-run patch as an activation artifact.

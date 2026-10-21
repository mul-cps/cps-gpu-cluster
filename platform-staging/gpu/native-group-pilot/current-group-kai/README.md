## Coordinated image adoption renderer

`image_adoption.py` is a pure, two-phase renderer for the four existing protected
processes: Gateway, CPS Hub, CIT Hub and the packaged Node service. It has no
capture or apply CLI. Importing it performs no file, API, process or GPU access.
Inputs and returned plans contain private Secret data and CAS preimages; retain
them in private operator storage and never print them or commit generated plans.

Call `render(snapshot, images, expected_snapshot_sha256=..., expected_revision=...)`
with a complete, explicitly pinned capture and exactly four digest image entries
(`gateway`, `hub:cps`, `hub:cit`, `node`). Gateway/Hub images must use the reviewed
`ghcr.io/mul-cps/cps-compute` repository, and Node must use
`ghcr.io/mul-cps/cps-native-node`. Digest syntax is checked; publication, package
qualification and operator review remain separate prerequisites.

The renderer validates the captured packaged Node configuration and all four
approval projections through the SDK, then checks actual controller and signed
ServiceAccount identities, current process declarations, publishers and the
capture seed. It requires a released-only captured ledger. Publisher cadence and
reader TTL are independently bounded and preserved; differing valid Hub and
Gateway TTLs are not rewritten. The terminal index and ledger are retained
separately: the current capture has 82 archived records and 117 released ledger
lifetimes, including records outside that older archive index.

The result contains `creates`, `reuses`, `patches` and `preservation`. Each patch
records its resource kind/namespace/name and tests UID, resourceVersion and the
complete changed field preimage before replacement. Only these fields advance:

- All four images in Node `component_declarations` and runtime
  `nativeGroupApprovals.processes`.
- Each existing Gateway/Hub publisher's `process.image` and its mounted
  content-addressed ConfigMap reference.
- Gateway main/capture/init images and the capture-seed reference. A new
  immutable Secret preserves all original data except `config.json`'s
  `node_process.image`; the existing Secret is never patched.
- Named ConfigMap GET rules for the new publishers and Node configuration.

Existing immutable candidates are reused only with actual captured identity and
identical contents. No permission verbs/resources are added. Approval revision,
all approval documents/references/history, qualification, policy, driver epoch,
CDI pins, archive/index/ledger, database/auth/token/CA data, storage and unrelated
controller fields remain unchanged.

`render` does not emit a Node Deployment patch. After Root creates or reuses the
new immutable NodeConfig, call
`bind_node(snapshot, plan, actual_node_config, stopped=None)`. It revalidates the
exact plan and actual config contents/name/UID/resourceVersion/data hash, then
returns a new bootstrap ConfigMap and guarded Node Deployment patch. The existing
bootstrap reference schema and `python -m cps_compute.native_node.service`
command remain unchanged. The reference value binds the actual new immutable
config; the new bootstrap starts with `release=false`. Node main and bootstrap
initializer images and the initializer's exact `NODE_IMAGE` literal advance
together, so generated process declarations name the installed image. Missing,
duplicate, indirect or foreign `NODE_IMAGE` values fail closed. An optional actual stopped Node Deployment
is accepted only when its full spec differs solely by `replicas=0`.

Root owns fresh writer fencing/quiescence, maintenance, observer coordination,
actual creates/readbacks, held Node release, named actual Pod/ReplicaSet reads and
fresh genuine four-component acknowledgments. A pinned historical capture does
not prove those live preconditions. Compose the endpoint renderer against the
appropriate fresh state; two independent stale full-preimage patches cannot be
applied as though they were a combined plan. Neither rendering phase activates
the KAI endpoint, creates GPU work, proves production readiness or qualifies a
KAI lifecycle.

CPU tests use synthetic credentials and the SDK's existing typed configuration
fixture. With the qualified SDK source, Hub source and SDK tests on `PYTHONPATH`:

```bash
PYTHONDONTWRITEBYTECODE=1 "$CPS_COMPUTE_PYTHON" -B -m unittest discover \
  -s platform-staging/gpu/native-group-pilot/current-group-kai \
  -p test_image_adoption.py -v
```

## Observer successor for image adoption

`observer_adoption.compose` composes a successor from an independently hashed
previous observer release, catalog, exact image snapshot/plan, actual immutable
NodeConfig and all three publisher readbacks, an actual `release=false` bootstrap,
and a fresh four-Deployment/seven-Role/ConfigMap capture. `actual_configmaps`
accepts the three publisher objects as a list or a closed labelled dictionary;
the actual NodeConfig/bootstrap may also be included consistently.

The previous seven Role identities and baseline rules remain independent of live
permissions. Only the unique existing static ConfigMap GET rows receive the new
NodeConfig and **all three** Gateway/CPS Hub/CIT Hub publisher names. Other static
names, rows, verbs and writes are rejected, even when present in the live API.
Mutable Pod/ReplicaSet GET names may differ without becoming trusted baseline
permissions. Returned static patches test the actual Role UID/resourceVersion
and complete rules preimage.

The successor pins the actual new NodeConfig six-field reference and exact held
Node template digest. The prospective capture carries actual controller and
ConfigMap identities with only reviewed future controller/static-rule values;
it never invents a new API UID/resourceVersion. Both the old and prospective
states pass the existing pure observer renderer. Outputs explicitly retain
`prospective=true`, `live_applied=false`, `process_readiness_verified=false` and
`actual_only_render_required=true`. Root must obtain and validate actual fresh
post-apply captures with the existing renderer before activating this release.
This helper performs no apply, observer activation, process or GPU operation.

The pure `head_hub_rotation.prepare` helper also accepts optional closed
`component_images` and `operator_images` maps. Existing calls retain the paired
Hub successor behavior. For a complete same-policy SDK refresh, prepare and
complete the paired Hub journal rotation first; then take a fresh pinned snapshot
and prepare the Gateway/Node rotation with `hub_image` equal to the unchanged
current shared Hub image and `component_images={"gateway": "<digest image>",
"node": "<digest image>"}`. Only actual image change sets already supported by
SDK delivery are accepted: Gateway, Node, Gateway plus Node, or both Hubs.
A simultaneous four-component change is rejected before any CREATE intent.
Each stage requires its own actual immutable readbacks and ordinary journal
rotation. Maintenance fencing and process readiness remain operator gates.

Optional `operator_images={"observer": "<digest image>", "writer": "<digest image>"}`
can select either or both fixed operator Deployments captured in the pinned
snapshot objects. It changes only the fixed main image and Writer private-input
initializer image, using UID/resourceVersion/full-spec CAS; all settings,
checkpoint references, journal PVCs, replicas and private mounts remain exact.
These patches share the supplemental permission readback gate. They are image
refresh intents: use the existing observer/delivery renderers for the separately
reviewed release/configuration binding, and coordinate Writer/Observer maintenance
before applying them. Synthetic tests establish intent preservation and rejection
behavior; they do not establish rollout or hardware qualification.

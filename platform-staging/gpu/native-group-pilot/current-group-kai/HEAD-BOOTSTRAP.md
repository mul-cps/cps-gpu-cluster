# One-time dynamic head bootstrap

`head_bootstrap.py` is a pure renderer, not an automatic rollout. It has no API
client and does not enable the Coordinator or release the Node. Use it only
after the compatible image adoption has been qualified and current workloads
have reached the separately reviewed migration boundary.

1. Load the actual immutable v3 `NodeConfiguration` with the released SDK and
   capture the four current immutable approval ConfigMaps. Their complete v3
   envelopes, including retained history, must agree. The Node's initial
   reference must exactly match its existing protected configuration.
2. `pointer_candidates(configuration, approvals, policy)` returns four
   namespace-local mutable pointer CREATE candidates. Apply CREATE and read
   back their actual UID and resourceVersion. Do not invent metadata, replace
   a pointer, or retry an AlreadyExists conflict with an overwrite.
3. `anchor_candidates(configuration, approvals, policy, actual_pointers)` binds
   those actual fixed pointer UIDs into four immutable anchor CREATE
   candidates. Apply CREATE and obtain actual immutable readbacks.
4. `bind(configuration, approvals, policy, actual_pointers, actual_anchors)`
   returns four validated `HeadBinding2` values and a v4 Node configuration
   CREATE candidate. Qualification, CDI, terminal index, component declarations
   and acknowledgment targets are preserved. The new configuration must be
   created/read back and then incorporated into the coordinated, held
   bootstrap/observer/publisher adoption. It is not applied by this helper.

Actual reader permissions, immutable anchor mounts, publisher binding files,
Source/epoch checks, the observer release, legacy journal migration and all
four fresh ACK v2 receipts remain separate required steps. A binding JSON file
and the mounted `anchor.json` payload are different objects. Never use these
staging results alone to declare ready or activate GPU starts.

Routine approval delivery uses the fixed pointers. It must not rerun this
migration or patch Deployments, Node configuration, anchor mounts or images.
The helper rejects divergent initial v3 history; later authenticated v2 heads
may legitimately retain namespace-specific histories without changing the
shared current registry.

The CPU tests use actual SDK validators, actual-shaped fixture readbacks and
no cluster/GPU access. They exercise successful v4 typed reconstruction,
missing/foreign components, mixed registries/history, pointer UID/RV/data
changes, garbage-collection/deletion metadata, and altered immutable anchors.

`runtime_candidates(...)` then creates three immutable binding-file candidates.
After actual readback, `bind_runtime(..., bindings, controllers)` emits guarded
four-Deployment mount intents. Every target must match its declared UID,
namespace, name, selected image and service account; UID, resourceVersion and
full original spec are tested before replacement. Existing images, commands,
resources and other containers stay unchanged. These intents must be composed
with the held Node/bootstrap/observer/Gateway adoption before release.

The binding file mounts at `/etc/cps-native-head-binding.json`, with
`CPS_NATIVE_GROUP_APPROVAL_HEAD` pointing to that direct path. The actual
reviewed Gateway and Hub filesystems have `/var/run -> /run`; the protected
binding reader rejects symlinked parents. CPU probes at both actual runtime
UIDs confirmed rejection of the old path and successful protected reads from
`/etc`. The separate ACK-attested anchor mount remains
`/var/run/cps-native-approvals/head-anchor.json`.

`readiness_settings(...)` validates the exact enabled legacy Gateway readiness
settings against the reviewed Node configuration before adding `version: 2`
and the four actual head bindings. It preserves ACK/process identities, driver
epoch and TTL; mismatched authority and repeat migration fail. This returns
settings only. Compose it with the capture server's explicit v2 configuration,
held Node bootstrap, runtime mounts and observer release before changing the
Gateway Secret. Component publisher settings remain schema v1: their protected
head-binding environment selects genuine v2 ACK publication. Changing publisher
settings to an invented schema v2 is invalid.

`head_runtime_adoption.prepare(...)` composes the four head mount specs with
Gateway readiness v2, capture server v2 and an actual v4 Node reference in a
held bootstrap. It requires a separately pinned complete preimage snapshot,
matching duplicate controller captures and a fully released claim ledger. The
capture configuration must be the closed legacy schema and match the exact
existing Node process and ACK authority; all other Secret keys stay byte-exact.
It returns two CREATE candidates, four future specs and one guarded runtime
Secret patch. Keep all inputs and outputs private.

After actual CREATE readbacks, `bind(...)` recomputes the complete plan and
validates the held mutable bootstrap and immutable capture Secret before
emitting four UID/RV/full-spec CAS patches. The independently reviewed observer
v2 release and exact reader permissions must be composed before applying those
patches. Root separately verifies SQL quiescence, backups, actual Pod shutdown,
protected personal servers, API dry-run and fresh actual four-component ACKs.
This renderer does not perform any of those live operations or journal migration.

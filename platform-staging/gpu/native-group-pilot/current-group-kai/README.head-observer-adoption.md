# Held v3-to-v4 observer release composition

`head_observer_adoption.py` is a pure, one-time ObserverRelease1-to-2 composer.
It changes no process, image, file, API object, or permission by itself.

```python
proposal = compose(
    previous_release, reviewed_sha256, catalog,
    old_configuration, new_configuration, held_bootstrap,
    heads, capture, runtime_specs,
    reviewed_runtime_specs_sha256=reviewed_specs_hash,
    actual_gateway_capture_seed=actual_immutable_capture_seed)
```

Supply independently pinned previous release and exact proposed full four
Deployment specs; actual typed NodeConfiguration3 and NodeConfiguration4; actual
held bootstrap; four local HeadBinding2 values; and a version1 capture containing
actual old four Deployments, all seven Roles, and required ConfigMap readbacks.
The capture may include the additive staged authorities and retained history
(up to the existing v2 544-ConfigMap bound). No API identity is invented.

The helper reauthenticates both configurations against captured objects. The
v4 document and four bindings must equal `head_bootstrap.bind` from the v3
cohort. It regenerates `head_bootstrap.bind_runtime` against the actual old
controllers and three actual immutable binding files. Proposed full specs must
match exactly, with only the Node bootstrap ConfigMap name and Gateway
capture-seed Secret name additionally substituted. Commands, images, other
mounts, environment, resources and controller identities cannot change even if
a caller repins a modified proposal. The held bootstrap must contain the exact
new config reference, identical policy and `release: false`.

The capture-seed argument authenticates actual local immutable Secret metadata
only. Its protected contents are neither read by this helper nor included in
its result. Root must independently validate its bytes using the coordinated
runtime prepare/bind helper. The expected specs hash is a review pin, not a
replacement for that protected-content validation.

All seven Role UIDs and all original rules remain independently pinned.
Existing Pod/ReplicaSet row handling is retained. Each head row receives only
SDK-authenticated namespace-local anchor, pointer, current and retained approval
GET names. A new NodeConfig GET is added only to an existing same-namespace GET
row that already read the old NodeConfig. No name is inferred from live rules.
A default head row is selected uniquely from the old initial-approval read row,
or from a sole eligible baseline ConfigMap GET row. If ambiguous, supply exact
seven `head_get_rows` entries (`namespace`, `name`, `index`); the SDK validates
them against the pinned release rules. All unrelated static drift is refused.

The result contains the successor release/hash, prospective capture, exact
UID/resourceVersion/whole-rules CAS intents, old release/spec pins, and explicit
`prospective: true`, `live_applied: false`, `process_readiness_verified: false`,
`actual_only_render_required: true` flags. It pins the full proposed held Node
template and checks both old and future captures through the existing observer
renderer. Root must capture actual controllers/Roles after rollout and re-render
before observer activation. This proposal is neither live readiness evidence
nor permission to skip the existing maintenance, backup, ledger, SQL or ACK2
gates. Future per-head operator-own named GET pregrants remain a separate
producer prerequisite; no broad GET/LIST grant or restart-per-head is added.

### Node image successors after v4 adoption

`head_gateway_rotation.prepare(..., node_image=<reviewed digest>)` also supports
node-only successors: pass the existing Gateway digest as `gateway_image`.
The explicit node image must be a distinct immutable `mul-cps/cps-native-node`
reference. The proposal updates the node service/bootstrap, NodeConfiguration,
Gateway runtime, Coordinator epoch and a new immutable capture Secret together.
Other capture data and both Hub specifications remain unchanged. An unchanged
publisher ConfigMap may be reused only after matching its captured UID and full
immutable data; never overwrite an existing object. Supplemental reads, the
five guarded runtime intents, held-node observer validation and same-journal
rotation still apply. Rendering and image publication do not qualify hardware.

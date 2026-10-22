# Cold-domain runtime head composition

Add a separately named pure `bind_domain_runtime` stage to head_bootstrap.py.
Ordinary bind_runtime and normal image rotations remain unchanged. Existing
image/runtime/publisher composers retain responsibility for qualifying their
adoption intents; this stage never reconstructs those changes.

Inputs: actual typed new-domain v3 NodeConfiguration, four namespace-local
initial approvals, new pointer/anchor/three binding actual readbacks, three
actual Gateway/Hub Deployments, their existing qualified full-spec CAS adoption
intents, four independently captured old head bindings, three old immutable
anchor/binding ConfigMaps, canonical nonzero domain_uid, closed external
retirement descriptor, and independently reviewed SHA over all these inputs.
The token/descriptor/hash are review pins, not retirement authentication.

Validate new staged heads through existing bind/runtime_candidates; require a
fresh root qualification, distinct old/new Node authority namespaces and new
pointer identities. Validate old mounted immutable refs and exact head fragment
values, unique names/paths/env. Verify adoption UID/RV/full-old-spec preimage
matches actual Deployment. On its desired spec only, replace the two old head
ConfigMap names in place; require all mount/env fragments remain exact. Require
new main image and same controller/SA identity match new declaration. Return
original UID/RV/full-spec test operations plus the final desired full spec.
No Secret construction, publisher reconstruction, SA/role changes, APIs or live
intermediate image adoption. All unrelated adoption changes remain byte-exact.

TDD: real typed old/new domains, initial heads and actual-style readbacks;
ordinary mounted bind_runtime remains denied; atomic image/runtime/publisher +
heads desired composition succeeds, original preimages and list order preserved.
Negative input pin, old ref/data/UID, duplicate/missing fragment/env, altered
adoption preimage, wrong target declaration/image, same domain/pointers and
missing/noncanonical retirement token refuse. Existing head tests stay green.

## Callable procedure and proof boundary

1. Independently qualify the fresh-root target v3 `NodeConfiguration`, its four
   identical initial approval registries, and the upstream atomic adoption
   desired specs. Use `pointer_candidates`, `anchor_candidates` and
   `runtime_candidates` with the same nonzero `domain_uid`, passing genuine API
   readbacks between stages. Those unchanged functions authenticate new heads.
2. Capture all four previous typed head bindings, and the actual immutable old
   anchor/binding ConfigMaps for Gateway and both Hubs. Supply exactly those
   three actual Deployments and upstream adoption intents. Each adoption intent
   must be the exact four-operation UID/RV/full-spec CAS used by existing tools.
3. Independently review the complete input set and obtain
   `domain_runtime_review_sha256(**inputs)`. Keep that pin separate from the
   later call; recomputing it on unreviewed inputs provides no approval.
4. Call `bind_domain_runtime(**inputs, reviewed_sha256=reviewed_pin)`. Apply each
   returned full-spec CAS only in the externally established retirement fence.
   Root owns API apply/readback and the separately composed Node/Observer/Writer
   activation and four fresh ACK requirements. The three controller patches are
   individually atomic; this does not claim a multi-controller transaction.

This stage checks no signature or live credentials and proves no physical GPU
quiescence. The descriptor is an externally authenticated review reference, not
an authorization token. Upstream adoption is trusted as reviewed: arbitrary
runtime/publisher edits are not independently requalified by this stage. It
preserves their exact desired bytes and changes only the two canonical head
volume ConfigMap names; all original CAS tests remain intact. It does not load
old missing custody or reconstruct its evidence.

Source-domain append is a separate gate. Its same-policy, workload/gate images,
roster, capacities and physical identity constraints must pass independently.
The existing compiler's old qualification literals are not changed here. A
policy/image change required to obtain fresh qualification cannot be disguised
as the same-policy append. Typed policy body/hash is authoritative; a stale
ConfigMap annotation cannot establish policy compatibility.

Tests use a real typed fresh-root configuration and actual-style staged head
readbacks; old Node namespace is independently pinned as forensic input, not
reloaded as current qualification. The positive case composes an image change,
new runtime Secret reference and publisher volume in one desired spec. Existing
ordinary mounted-runtime rejection remains covered. No activation or hardware
qualification is claimed by these offline tests.

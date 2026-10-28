# Inert placement binder candidate

This patch is based on the exact deployed binder source, not the unpublished
composed inventory/deletion branch. `source.json` pins the base, reviewed
candidate, patch bytes and actual Python compiler fixture.

The new protocol independently reads the protected immutable registry and its
pinned compiler seed before stock reservation or map writes. It verifies raw
pending spec hashes, the full future Node-bound spec hash, typed actual Pod
spec equality and original compiler metadata. Only existing named controller
metadata additions are accepted. The actual reserved KAI UUID, Node UID and
boot must match a qualified candidate. The coordinator retains qualification,
current Source/member custody, capacity, fencing and final Binding authority.

Primary-agent independent verification passed the owning binder package in
16.282 seconds with Go 1.26.8. The focused fixtures cover second-card selection,
wrong seed identity/data, changed metadata/resources/caps, unknown fields,
foreign UUID/Node/epoch, mixed protocols and unbound-as-bound hash substitution.

This is a source candidate, not a built or installed image. Connected selected
claim, cap enrollment, immutable allocation ACK, Node consumption and lifecycle
acceptance remain open. No live KAI, driver, GPU mode or user Pod changed.

# Observed reservation-Pod deletion

This source patch adds UID and resourceVersion preconditions to reservation
cleanup. A stale observation conflicts instead of deleting a replacement Pod
with the same name. Grace period zero and already-absent handling are unchanged.

The patch targets exact upstream KAI revision
`bdf434e5e9201cccf4e05fad04d814363653f692` (0.18.1). It includes six behavioral
identity cases and passed the upstream non-E2E Go package boundary with Go1.26.8
and isolated Kubernetes1.35.0 envtest servers. Existing reservation tests passed.
The fake client omits UID enforcement, so the regression models that external
API contract explicitly while retaining its resourceVersion checks. Initial
missing-envtest setup failures were preserved before the complete successful run.

Apply with `git apply observed-delete.patch` in the pinned source checkout.
Compose it with the current qualified native binder overlay and the scheduler
inventory/budget patches before building an image; that composition has not yet
been qualified. `verification.json` records the exact patch/source/log hashes.
No image or deployment is changed by this directory.

This is identity protection, not a native retirement permit. The binder must
still fence new native enrollment and confirm native-zero cleanup before
deleting the reservation. Expiry or terminal Pod status alone is insufficient.

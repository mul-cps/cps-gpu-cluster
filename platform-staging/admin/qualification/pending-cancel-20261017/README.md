# Pending workspace Start cancellation

Merge `values.yaml` into the complete qualified platform values. This image-only
overlay is not a standalone deployment; do not replace live policy or unrelated
settings with chart defaults.

Both console images contain admin source
`1bb4f9b4f9114f3edf32760372caf870b30e9c13`. The chart derives each console's
`BACKUP_IMAGE` from its deployment image. Installed-package tests: 346 passed;
UI bundle remains unchanged from the tested cancellation UI revision.

The change signals cancellation before waiting for the workspace lifecycle lock,
observes confirmed Hub shutdown before releasing reservations, and returns the
intentional cancellation as JSON HTTP 409 for the UI. Ambiguous Hub DELETE errors
require authoritative absence observation; they do not authorize early release.

See `qualification-artifacts/native-head-delivery-release-20261017/` for live
adoption and bounded cancellation evidence. This does not qualify GPU placement,
CUDA execution, or a live browser session. GPU qualification remains a separate
production gate.

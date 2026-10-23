# Workspace startup confirmation — 23 October 2026

Both consoles run the packaged startup confirmation fix. The source retains the
previously deployed HTTP error mapping and all frontend assets. Only the workspace
module changes; 105 other distributions are byte-identical apart from excluded
Python bytecode. No database migration is introduced.

The final readiness publication requires the GPU reservation to remain active and
checks pending cancellation after sharing operations. A normal deployed start and
stop passed. A pending start cancelled through the normal close operation raised
`_WorkspaceStartCancelled`, ended stopped, and retained no member reservation.
See verification.json for measured results. Focused tests cover reservation loss
at final publication; the live cancellation test exercises cancellation during
pending startup, not the exact final-publication race window.

The image is deployed live. GitOps integration and production promotion remain
separate unfinished gates. This does not prove actual wall-clock lifetime expiry.

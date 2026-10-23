# Actual Gateway artifact lifecycle — 23 October 2026

The deployed unchanged retention controller was run in bounded owned Jobs.
Wrappers restricted artifact reads/mutations to the exact two QA keys and
immutable provenance, and workflow reads/claims to the exact name and UID.
Production retention settings, clocks and unrelated objects were unchanged.

For the successful cross-Hub QA notebook, real-clock reconciliation bound both
objects to the terminal workflow and preserved both. An isolated per-call 91-day
test clock then conditionally expired both objects, reporting two deletions and
zero errors. The Job output was observed directly but its TTL removed the Job
before local log export. A separate read-only Job verified durable deleting
claims for both artifacts and S3 404 for both exact keys; deletion was not repeated.
This intentionally removes only those two disposable QA artifacts. Earlier
execution receipts remain historical evidence, not current download claims.

A new actual Gateway notebook performed a controlled 90-second computation.
While its workflow was Running before and after the sweep, the aged-clock apply
path examined its input and performed zero reconciliation/deletion, with zero
errors and unchanged snapshot ETag/tags. No synthetic workflow status or altered
object timestamp was used. The active-input report was saved directly.

These checks close real Gateway-created conditional expiry and active-input
protection within the owned scope. Existing owner-retain/foreign-denial evidence
remains separate. Current image alignment, full scheduled mutation qualification,
orphan proof disposition and release integration remain open. Automatic cleanup
is still suspended.

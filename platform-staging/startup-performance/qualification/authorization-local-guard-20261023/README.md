# Final local permission guard — 23 October 2026

The full suite at `e837d76` finished with 5180 passed and one failure: the
authenticated lease callback-budget regression correctly detected that the
first grant-race fix replayed the full Source callback. No candidate was deployed.

Source `bca0123` preserves that test's original thresholds: one Source callback
and one four-component observation per claim. It brackets the external proof
with read-only local observations of the workspace, storage lifecycle and each
member's effective grants. The effective-grant comparison includes expiry; it
adds no external readiness observation or full Source-policy callback.

All 32 acquisition and callback-budget tests pass. Deterministic checks deny
revocation during approval observation, revocation during the final ledger
read, and expiry without a grant-row mutation. An unrelated person's grant
change remains allowed. Denial retains the reservation and non-executing claim.
The complete repository suite is running against this source; its outcome is
not yet known. No polling change or startup gain is active yet.

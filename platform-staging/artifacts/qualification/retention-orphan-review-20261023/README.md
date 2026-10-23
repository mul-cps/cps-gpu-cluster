# Legacy artifact preservation — 23 October 2026

Read-only inventory identified 28 fixed-format artifacts without a live workflow:
seven are matched to the exact controlled retention fixture plan, nine retain
metadata naming removed qualification namespaces, and twelve lack enough current
provenance to attribute safely. The decision is preservation, not inferred
ownership, repair of workflow history, or deletion authorization.

`review.json` records each exact key and observed ETag, an explicit reason and
review reference. The retention exclusion applies only while that exact key has
the same ETag. It performs no storage mutation. A changed object or a new unknown
key returns to normal proof verification; missing proof continues to fail visibly.
No prefix or wildcard exclusion is accepted. This is an operator-owned deletion
exclusion; owners may later review the data through a separate audited process.

All 28 objects remain in place with their existing bytes and tags. Unmanaged key
formats remain preserved independently. Normal 14/90-day eligibility, active-input
protection, retained output protection, permanent workflow UID provenance, CAS
claims and conditional deletion remain mandatory for other objects.

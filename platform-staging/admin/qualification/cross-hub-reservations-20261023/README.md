# Cross-Hub reservations — 23 October 2026

Normal Source lifecycle starts raced within 1.67 ms for two workspaces sharing
Armin's reviewed canonical identity. CIT won; CPS was denied with a recorded
reservation conflict and zero partial member holds. After normal shutdown and
zero-row verification, CPS started successfully and CIT was denied in reverse.
Both winners completed a CUDA allocation. No manual reservation release was used.

During the CPS hold, Armin launched a normal CIT CPU server and completed both
successful and intentionally failing CPU notebook batch jobs. Timestamp receipts
place those executions inside the same active GPU reservation interval. Typed
parameters, selected imports, executed artifacts, foreign-owner denial and
idempotency passed. Temporary API tokens were revoked.

CIT's temporary GPU approval was then revoked, the original CPU ceiling/profile
restored, and its fixture left stopped with files preserved. All four approval
components acknowledged the resulting revision. CPS retained its original
three-member 5 GiB configuration and was stopped normally.

## Scope and unresolved observation

This qualifies global member exclusion and CPU/batch independence for the bounded
5 GiB pilot on one GPU, not full-pool packing or startup-burst performance.
The first race failed before reservation acquisition with a storage-provisioning
409 on both sides. Concurrent provisioning subsequently passed on both sides
(27.028/26.978 seconds), followed by the successful lifecycle race. The initial
transient remains unexplained; these receipts do not claim its cause was fixed.

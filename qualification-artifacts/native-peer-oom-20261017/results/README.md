# Scoped peer-OOM results — 17 October 2026

Two approved CPS workspace Pods, each capped at **5 GiB**, passed the frozen
held-OOM test in both directions. Starts and Stops used the normal console API,
sequentially. This is a memory-pressure isolation result, not production approval.

| Pressure direction | Held before typed OOM | Hold | Peer ticks inside hold | Maximum peer gap |
| --- | --- | --- | --- | --- |
| A → B | 4,608 MiB | 8.00053 s | 16 | 0.50306 s |
| B → A | 4,608 MiB | 8.00038 s | 16 | 0.50260 s |

A → B means A ran the peer kernel while B ran the OOM pressure test.
Each direction produced `torch.OutOfMemoryError`, recovered a kernel result of
37, and preserved Pod/process/seal/journal identities. Both parents' charged
bytes returned to zero. Each hold contains four independent host NVML samples:
physical free 36,491,493,376 bytes; total 42,949,672,960 bytes.
The host measurements avoid capped notebook memory reporting.

[Summary](summary.json) includes exact source pins, private raw-evidence hashes,
manifest hash, metrics and cleanup. Each direction has its exact bounded
assessment and physical samples. [Post-cleanup readiness](final-readiness.json)
records the four installed consumers, policy hash and approval revision.
Raw event streams and full custody observations remain in operator-private
storage; their hashes are recorded rather than publishing full inventories.
Both assessments were replayed offline against the raw streams before publication.

Normal Stops returned 200, all 114 native claims were released and the original
112 records preserved. SQL reservations/bindings were empty; temporary grants
and memberships were restored, test credentials revoked/removed, and all four
personal notebook Pod UIDs preserved. No MIG, reset, reboot or driver change.

The unchanged Node image is `47d8e532…a670c7f`; notebook runtime is
`91678610…4ca4dc0`. Exact process images are in the readiness receipt.
Gateway/Hub deployment is recorded in the
[adoption receipt](../../../platform-staging/jupyter-extensions-20261013/gpu-lifecycle-recovery-adoption-20261017.json).

**Not covered:** unequal or larger caps, MPS, other memory routes, concurrent
startup, cross-Hub pooling, scheduling/reclaim, burst SLOs, whole-fleet isolation,
or production release. Existing approvals are unchanged; this result does not
create a 20 GiB approval or enable broader access.

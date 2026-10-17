# Concurrent CPS5/CPS5 normal startup — failed, 17 October 2026

[Attempt 8](result-08.json) sent the two normal console Start requests only
0.058269 milliseconds apart, after independent current grants, roster, exact
approval, stopped-state and server/Pod absence checks. No GPU probe ran.

The secondary workspace reached Running (HTTP 200). The lab returned HTTP 503:
its Hub reservation-acquire POST raised `httpx.RemoteProtocolError` because the
server disconnected without a response. The Gateway Pod did not restart.
This establishes a transport failure, **not its root cause**. Absence of an
access log does not establish whether a request was processed or committed.
No ambiguous POST was automatically replayed.

Both normal Stops returned 200. All 115 native claims are released, the old
114 records and ledger UID preserved, reservation/binding tables empty, and
controlled Pods/Hub servers absent. Two temporary grant expiry changes and two
membership expiry changes were restored exactly. The temporary token was revoked
(204, subsequent authentication 403) and its plaintext removed. All four
personal notebook Pod UIDs were preserved; installed four-consumer readiness
passed after cleanup. No MIG, reset, reboot or driver change occurred.

Raw receipts and logs stay operator-private, with hashes in the result.
The prior bidirectional 5/5 GiB peer-OOM result remains valid for its scope.
Concurrent startup, deliberate cancellation and production qualification remain
open. A controlled real-TCP/TLS CPU reproduction is the next diagnostic step;
a passing synthetic transport test alone cannot qualify the live startup gate.

## Attempt 9 — synchronized normal startup passed

After the reviewed Hub fresh-connection image was deployed, requests sent
0.053341 ms apart both returned HTTP 200 and reached Ready with zero restarts.
All four init gates exited zero; distinct 5 GiB allocations occupied the same
qualified GPU. Normal start latency was 97.82 s and 115.96 s. Both normal Stops
returned HTTP 200; all 117 claims were released, the original 115 history
records were unchanged, SQL reservations/bindings were zero, and the exact
temporary grant and membership expiry changes were restored. The test token
was revoked and its plaintext removed; all four personal Pod UIDs survived.
Final installed four-component readiness passed.

This proves one controlled CPS5/CPS5 concurrent lifecycle, not cross-Hub or
representative burst/p95 qualification, cancellation, scheduler integration,
20 GiB access, or production readiness. [Bounded receipt](result-09.json).

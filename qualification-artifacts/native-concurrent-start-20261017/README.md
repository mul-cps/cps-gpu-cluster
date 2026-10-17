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

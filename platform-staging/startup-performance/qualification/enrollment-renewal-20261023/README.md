# Enrollment ACK renewal correction candidate

Source `063d85e242cf3ec4d7db0585c9987b243e704e2f` corrects the reproduced
live enrollment race: a valid same-generation Node heartbeat published during
a slow all-peer proof was incorrectly required to be an empty withdrawal.
The retry now authenticates the exact renewal or withdrawal and restarts the
outer fenced observation. No intermediate observation completes enrollment.

The positive regression first failed at the exact live denial. A future-dated
receipt with recomputed witness hashes remains rejected. All 96 focused final
publication, read-amplification, fence-budget, readiness and terminal tests pass.
Existing negative tests, callback counts and deadlines are unchanged.

Both candidate images are published with registry digests read back. Offline
preflight checks match the live manifest/kernel/policy and installed source
checksums for the service, grant-control, changed coordinator and history reader.
No GPU calls were made. The full suite is running; nothing is deployed from
this candidate yet. See `candidate.json` for artifact identities.

The next live run must verify actual Pod readiness and CUDA. The prior Source
success coincided with cleanup from a second diagnostic process and must not
be treated as proof of a normal UI readiness failure or startup success.

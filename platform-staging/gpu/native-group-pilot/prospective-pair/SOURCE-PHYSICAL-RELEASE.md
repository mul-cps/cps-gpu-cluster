# Complete physical custody for Source restoration

`source_physical_release.physical_release_verifier` connects an asynchronous Root
collector to `source_restoration.restore(..., verify_physical_release=callback)`.
The collector must obtain the complete current authority, ledger, immutable
history, physical observation and unpaginated PodList using the reviewed live
capture/observer path. The adapter does not execute shell commands or mutate the
cluster and cannot turn a cached file into a live observation.

Original/current immutable configurations, full baseline, independent Root pair
contract, independent restoration approval and frozen Node/epoch source bytes
are copied into the callback. On every call it recollects final custody and runs
the actual bounded Node inverse validator for the explicitly selected phase:
zero new lifetimes, one completed lifetime, or both completed lifetimes. Every
original allocation/journal/immutable reference must survive. Physical inventory
must show finite zero-charge retirement for the exact new lifetimes, no active
targets, the original driver/device epoch and no pair or replacement Pods.

Only after full replay does it summarize the original observation timestamp,
ledger UID, exact epoch and zero charge for Source. It checks Source's stricter
30-second freshness window after replay; it never resets observation age. No
inverse patches returned by the validator are applied.

14 focused tests exercise all three phases, repeated fresh collection, charged
and stale physical observations, missing journals/cleanup, active claims,
changed ledger, live Pods, pagination, phase mismatch, changed approval and
collector failure. Combined with Source tests, 41 tests pass. Two Source tests
also preserve the positive 5/20 GiB course ceilings found in the actual saved
operator target capture; CPU selection must not erase a course's GPU ceiling.

The API boundary is implemented and tested. The coordinated live executor still
has to invoke the trusted actual collector, enforce the external freeze, apply
Node/Gateway/Hub transitions and perform the current-image hardware run. No live
restoration, memory isolation or production qualification is claimed here.

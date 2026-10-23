# Bounded fresh history-read candidate

Source `0d0b046e6c3eec59f9a7950856178b299912360a` overlaps retained approval
ConfigMap GETs with four workers, then validates the fetched observations in
original history order inside the existing pointer bracket. Every scan reads
every object afresh; there is no cross-request authorization cache. Outstanding
reads are drained on failure. Existing schema, identity, policy, cohort-prefix
and transition validation remains unchanged.

The regression first failed because serial GETs could not reach a four-reader
barrier. It now passes and verifies that deleting a retained object is observed
by the next scan. All 33 focused head/history tests pass. The full suite is still
running; this receipt does not claim its result.

Both released-wheel candidate images built and passed offline checks against
the live driver-load manifest, kernel and policy graph, with no GPU calls.
Registry digests were read back and matched publication output. These artifacts
are candidates only: no deployment or measured startup benefit is claimed.

See `candidate.json` for source, wheel checksum and image digests.

## Subsequent deployment verification

The full suite completed with 5184 passed, 6 skipped and 68 subtests passed.
Supported delivery rotation 8 activated the pair, preserved all prior history
and restored the normal writer. Both maintenance Pods were deleted with UID
preconditions. See `deployed.json`; this supersedes the pending statements above.
Live startup performance remains to be measured.

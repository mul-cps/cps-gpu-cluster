# Pre-CAS readiness and empty-capture correction candidate

Source `2fa6315cb620ed71baeac2bc4910f997d2c5b3d0` includes the bounded full
read-only pre-CAS authority retry and exact empty-receipt classification.
A real Node withdrawal between capture and claim reproduced the live failure.
An adjacent empty-capture-then-recovery regression was caught before rollout,
so the superseded `cc80800` full run was deliberately interrupted and its
locally built images were never published or staged.

Only an exact target with canonical empty data and absent custody/pending
witness annotations enters the bounded retry. Wrong UID, stale annotations,
noncanonical data, expired grants and changed custody still deny. Existing
request deadlines, callback budgets and post-fence behavior are retained.
All **104 focused tests pass**, including expiry of the actual server deadline
without an enrollment or GPU write. The complete suite is running.

Both images are published and their registry digests read back. Offline
preflight matches the live driver manifest, kernel and policy graph, plus
installed service/grant/coordinator/history-module source checksums. No GPU
calls or controller changes occurred. This candidate is **not deployed**;
live rotation 9 remains active. See `candidate.json` for artifact identities.

The next controlled run uses normal console HTTP authentication and CSRF,
requires a same-UID Ready Pod and actual CUDA proof, and uses normal Stop and
fixture restoration. The narrowly scoped QA credential has a short expiry
and an exact-ID/user/note/scope revocation helper; no credential is in Git.

## Subsequent deployment and live outcome

The full suite passed (5194 tests and 68 subtests); rotation 10 deployed the
images. Two HTTP attempts failed at initial workspace authorization before Pod
creation. Idle read-only checks pass, so the original wrapped reason remains
unproven. No hardware or startup gain is claimed. Full cleanup passed. See
`deployed.json` and `lease-entry-live-result.json`.

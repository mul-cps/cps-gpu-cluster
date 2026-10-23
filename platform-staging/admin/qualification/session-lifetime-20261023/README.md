# Session lifetime qualification — 23 October 2026

The ordinary shared test workspace is running under its unchanged 4-hour maximum
and 30-minute idle policy. An active local watcher observes Pod identity and
absence, then reads the console reservation and lifetime state. No notebook
browser/kernel connection is opened. Hub API reads do not count as notebook user
activity. Baseline deadlines are preserved in verification.json.

112 Hub lifetime tests and 96 addon tests pass. Deployed notebook distribution
cps-compute-jupyterlab owns the static extension, containing the countdown and red
maximum/idle warning messages. Warning tests exercise 15/5-minute thresholds,
dismissal, stale authority and deadline extension. This is not visual browser QA.

The live idle expiry passed. Without a manual Stop, the Hub removed the proxy
route at 02:12:55.574Z and requested exact Pod deletion at 02:12:55.586Z,
2.227 seconds after the recorded idle deadline. The watcher observed absence
at 02:13:18Z and the member reservation was already inactive. KAI reservations
and online kernel caps were zero on final readback. Hard maximum wall-clock
expiry is not yet demonstrated.

The Source console record still says running after this automatic Hub stop. This
is a confirmed status/reconciliation followup, not an unreleased GPU allowance.
Keep this stale record available for reproduction; do not claim full UI expiry
acceptance from the successful Hub/native lifecycle alone.

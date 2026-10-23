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

Live idle expiry is still pending. Do not infer it from correct deadline telemetry
or software tests. Hard maximum wall-clock expiry is also not yet demonstrated.

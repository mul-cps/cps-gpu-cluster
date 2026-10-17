# Dynamic head delivery release candidate — 17 October 2026

Source `551379c6902791d0dd192596046669f1fe274562` implements the automatic
approval producer and explicit legacy-journal adoption. The full SDK/Hub matrix
passed 3,282 tests and 49 subtests (three environment-specific skips); the addon
scope passed seven tests and 19 subtests (three skips). All six skipped cases
were subsequently run in their required environments. All four exact-source CI
jobs succeeded in run `39019600947`.

SDK wheel SHA-256: `7b38c882b8c76ed4faccaa20fb8aea0c05af036d61a6149ce8d935762d6c2c05`.
Hub wheel SHA-256: `2ee2475c06e33731b3e7ed132911ca53198af4ccb4954133279e3e71f5932fc2`.
The actual installed Node image passed six CPU-only functional cases; all 72 SDK
modules matched the qualified wheel. These are not GPU hardware tests.

The four image receipts record published registry manifests and config digests,
independently read back from GHCR. These receipts describe publication time. The subsequent [live adoption](live-adoption-result.json) now verifies all four component consumers and the observer on those successor images.

The actual staging receipt proves five immutable objects and a held bootstrap
were created and bound using actual Kubernetes identities. Five immutable
candidates first passed API-server dry-run. Staging changed no process, activated
no GPU, preserved the four personal notebook Pods and retained GPU2's cordon.
Private configuration/Secrets, snapshots and original migration journals remain
outside Git. These receipts intentionally contain no raw authority documents.

Next: matching database backups and writer quiescence; coordinated image adoption;
actual four-component ACK checks; one-time v4 head adoption and original-journal
migration; continuous delivery and no-MIG GPU lifecycle qualification. The Job
renderer and dynamic delivery renderer passed 74 source checks together. Runtime
migration, production admission, wider GPU caps/routes/MPS, cross-Hub bursts,
recovery and full production release remain open.

The coordinated v3-compatible rollout completed at 2026-10-17T09:30:17.418103+00:00. Both public installed Gateway readiness calls verified all four actual fresh ACKs. All seven observer permission bindings verified before Node release. Three pre-upgrade database backup Jobs succeeded. Four personal Pods and all 117 released claims were preserved, with empty SQL reservation/binding tables. The old delivery writer remains paused for the explicit v4 migration; no dynamic-head or new GPU hardware qualification follows from this rollout.

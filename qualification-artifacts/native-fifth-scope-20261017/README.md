# Fifth isolated workspace adoption — 17 October 2026

Normal admin APIs created six fresh records and approved `cps:native-isolated-b-20261017` on separate v2 storage, preserving old workspaces. Actual new registry revision is `sha256:1e2b09e4f7a30389a78ac82eb9243ba8466a0e5e396dc312b7d76672501d88a1`. Existing four scopes, policy, pool, qualification, images and history were preserved. Authenticated capture used verified TLS with the existing public CA; the token remained inside the sidecar.

Four immutable documents, actual API-created references, three peer reference ConfigMaps and an approval-reference-only NodeConfig were adopted through guarded patches. The old node writer stopped first. The replacement was held in init until its actual Pod/ReplicaSet Role binding was established. The ledger metadata fence preserved existing allocation bytes. The installed Gateway consumer then verified all four current processes on the new revision, with unchanged policy/epoch. All four personal notebook Pod UIDs were unchanged.

An operator ACK withdrawal used empty outer data and caused a node startup failure. Correcting it to `{"ack.json":"{}"}` let the same Pod recover. The included fence helper now validates this exact shape against the packaged publisher; seven CPU tests passed. Raw snapshots, runtime Secret, token material and per-person grants remain private and are not included here.

## Qualification remains open

Both normal controlled Starts failed at native acquire/readiness before a usable notebook Pod existed. No cross-Pod CUDA test executed. Normal Stop returned200 for both; all101native claims were released. The two temporary pilot grant renewals were restored exactly; the temporary admin token was revoked and its local file removed. Data and audit history remain.

A read-only installed-Gateway diagnostic reproduced the clock race: validation clock01:06:16.866534 was sampled before sequential reads; a real CIT heartbeat01:06:17.000201 appeared future-dated, while validation after the required reads at01:06:17.765625 accepted that same receipt. This establishes a readiness bug, not completed cross-Pod isolation. The bounded application fix is in progress.

`publication.py`, `bind_process.py` and `prepare_fence.py` are operator artifacts. They need the released compute package and actual private captures supplied explicitly. Their default invocation performs no live changes. Automatic recurring publication and Fleet persistence/promotion remain separate production gates.

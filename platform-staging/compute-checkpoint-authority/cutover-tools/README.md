# One-operation controller cutover tools

These are guarded operator tools for the reviewed 2026-11-18 planned handoff. They are not a controller, scheduler or automatic rollout. No production operation is released by committing them.

`phase_once.py` is byte-identical to the frozen I3 candidate. The observer reuses a verified HTTPS connection within each Source batch. The observer pins existing Source Pods and uses their existing in-memory credentials for strict TLS GETs. It measures from the first service restriction through independently attested preservation and verified recovery. Root's 12-second live prequalification passed all six authenticated normal APIs with maximum sample gap 0.788443733 seconds. This is not a timed cutover pass. The earlier generated-code failure and incomplete I2 observations remain in the public receipt.

`phase_once.py` submits only one hash-bound full-spec UID/resourceVersion CAS phase per invocation. Unknown replies require read-only reconciliation; it never retries, rolls back or invents process-stop or data-preservation evidence. It remains unarmed. Build fresh phase input specifications from the current delivery record and freshly reviewed live objects; the previous artifact inputs are not authorization.

`data-adapter/` preserves the exact separately frozen six-file DATA candidate and manifest. It intentionally pins the previously reviewed original protocol and I3 bounded stream under `/home/bjoern/artifacts/cps-upstream-sharing-20261116/`, with their SHA256 values. These are explicit external dependencies, not a portable installation. It requires fresh helper creation receipts, genuine stopped-writer and original-clock proofs. No production snapshot/install has been executed. Never fill proofs with fixture values or restart an existing case after an ambiguous reply.

Run observer/phase tests in this directory: `python3 -m unittest discover -p 'test_*.py' -v` (25). Run DATA tests in `data-adapter/`: `python3 -m unittest -v test_data_adapter` (12). Fixture-only SQLite resource warnings on local Python3.13 do not originate in the production protocol, which explicitly closes its native database connections.

See `docs/operations/evidence/upstream-sharing-20261116/controller-cutover-tools-prequalification-20261118.json` for exact proof limits. Fresh helpers, worker staging, the genuine process/caller proof collector, integration review and the actual planned handoff remain required. No old-store failback is automatic after possible target writes.

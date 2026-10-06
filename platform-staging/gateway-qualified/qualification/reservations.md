# Shared reservation qualification

Status: backend race and Kubernetes absence checks passed; live cross-Hub gateway integration remains open. No GPU profiles were enabled.

Compute source: `5771df5e3db86a59b20fcf965cc3ce273df0c503`.

## Separate-process races

Thirty-two rounds raced independent CPS and CIT processes against the same SQLite reservation database. Each contender first attempted its own member, then the same synthetic canonical person. Exactly one workspace acquired the shared person each round. The losing contender's earlier member insertion rolled back, verified by successfully acquiring that member in another workspace. Unconfirmed shutdown and stale-attempt release were rejected, the winning reservation remained active, and confirmed matching release permitted the other console to acquire the person.

Private evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/reservation-process-races/qualify.py` and `report.json`. These are real multiprocess backend transactions with synthetic identities, not authenticated gateway requests or actual GPU allocations.

## Actual Kubernetes shutdown observation

The released-source `observe_shutdown` helper was called against the actual Kubernetes API for a bounded credential-free CPU probe in `cps-hub-rtc-qualification`. A synthetic Hub response reported the named server stopped. The helper still returned false while the Pod was running and while its deletion timestamp was set during the 20-second termination grace period. It returned true only after the Pod disappeared and the labeled workspace Pod inventory was empty. The probe was deleted normally; no force deletion or GPU allocation was used.

Private evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/reservation-shutdown-observation/qualify.py` and `report.json`. This qualifies real Kubernetes observation under a synthetic stopped-Hub response. It does not qualify the live gateway's configured Hub clients, authenticated release endpoint or production reservation records.

## Remaining acceptance

Run concurrent authenticated CPS/CIT acquisitions through the qualified gateway with reviewed canonical identities, verify rollback and persisted attempt binding, then exercise actual Hub and Kubernetes shutdown observation before release. Confirm CPU sessions and independently entitled batch submissions remain available while a member holds an interactive reservation. GPU sharing additionally requires aggregate memory isolation and scheduling qualification; backend race success does not satisfy those gates.

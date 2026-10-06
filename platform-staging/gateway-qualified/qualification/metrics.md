# Reservation metrics deployment

Status: reservation-conflict exporter package, image, TLS authorization and live Prometheus scrape qualification passed. Full platform qualification remains open.

The compute SDK provides `/internal/v1/metrics` with durable, source-scoped reservation acquisition conflict counts. Dedicated tokens configured through `metrics_token_envs` can only scrape metrics; control-plane reads and mutations are denied. The historical generic denial records cannot be converted into exact conflict counts.

The staging chart defaults `metrics.enabled=false`. Opt-in creates one HTTPS ServiceMonitor per source and an ingress rule limited to Prometheus pods in the specified monitoring namespace. Credentials are Secret references, never literal values. CA validation and the gateway service DNS name are mandatory; insecure TLS is disabled. The chart injects `CPS_METRICS_CPS_TOKEN` and `CPS_METRICS_CIT_TOKEN` into the gateway from those references.

Before enabling, publish and qualify an immutable gateway image containing the read-only credential implementation; create two distinct random tokens in the configured Secret; and update the private runtime configuration with:

```json
{"metrics_token_envs":{"cps":"CPS_METRICS_CPS_TOKEN","cit":"CPS_METRICS_CIT_TOKEN"}}
```

Set `metrics.credentials.cps` and `.cit` to the corresponding Secret name/key pairs, then enable the chart option. Do not reuse console or Hub tokens. Verify that the installed Prometheus selector picks up both ServiceMonitors, both targets pass TLS/authentication and samples carry distinct `source` labels. Test missing/invalid tokens and control-plane denial with the actual image. Keep dashboards unavailable until these checks pass; only the conflict series is supplied by this exporter. Physical GPU availability, enforced caps and teaching protection require their own authoritative controllers.

The ingress rule restricts the destination to gateway pods and its service port; Kubernetes NetworkPolicy cannot filter HTTP paths. The metrics token boundary therefore remains essential even with restricted network access.

## Operator evidence (2026-10-06)

Deployed candidate: `ghcr.io/mul-cps/cps-compute:qualification-5771df5@sha256:627f093c3c96038c7ecd9e9b99f0138198c23c9460cabb7bd11b19e94f465096`. The policy hash remains `sha256:051cd754210af2830d67968eea898f674a55ff66f5c88b3db95dff205f04e33d`. All OCI blob hashes and SPDX/SLSA attestations were checked. The installed wheel passed 211 tests; the offline container smoke ran as UID 10001. A fresh compute-state backup preceded deployment, and the backup CronJob now uses the matching image.

Both actual Prometheus targets are up with no scrape error and separate CPS/CIT counter samples. Live verified TLS requests returned 200 for metrics, 403 for control-plane reads/writes using either metrics credential and 401 without authentication. Service discovery initially lacked the gateway Service label; applying the chart's `app=compute-gateway` label resolved discovery. Operator evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/metrics-live/gateway-report.json` and `prometheus-report.json`; image evidence is in `buildkit-overlay/`. Private token and rollback files must not be committed.

Counter samples are zero since no qualifying acquisition conflict has occurred since this implementation. Historic denied requests remain outside the counter; the live scrape proves transport and sample availability, not a full GPU pooling acceptance scenario. Physical device placement, isolation and teaching protection series remain unavailable.

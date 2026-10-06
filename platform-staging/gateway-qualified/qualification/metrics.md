# Reservation metrics deployment

Status: package and chart tests passed; image and live scrape qualification pending.

The compute SDK provides `/internal/v1/metrics` with durable, source-scoped reservation acquisition conflict counts. Dedicated tokens configured through `metrics_token_envs` can only scrape metrics; control-plane reads and mutations are denied. The historical generic denial records cannot be converted into exact conflict counts.

The staging chart defaults `metrics.enabled=false`. Opt-in creates one HTTPS ServiceMonitor per source and an ingress rule limited to Prometheus pods in the specified monitoring namespace. Credentials are Secret references, never literal values. CA validation and the gateway service DNS name are mandatory; insecure TLS is disabled. The chart injects `CPS_METRICS_CPS_TOKEN` and `CPS_METRICS_CIT_TOKEN` into the gateway from those references.

Before enabling, publish and qualify an immutable gateway image containing the read-only credential implementation; create two distinct random tokens in the configured Secret; and update the private runtime configuration with:

```json
{"metrics_token_envs":{"cps":"CPS_METRICS_CPS_TOKEN","cit":"CPS_METRICS_CIT_TOKEN"}}
```

Set `metrics.credentials.cps` and `.cit` to the corresponding Secret name/key pairs, then enable the chart option. Do not reuse console or Hub tokens. Verify that the installed Prometheus selector picks up both ServiceMonitors, both targets pass TLS/authentication and samples carry distinct `source` labels. Test missing/invalid tokens and control-plane denial with the actual image. Keep dashboards unavailable until these checks pass; only the conflict series is supplied by this exporter. Physical GPU availability, enforced caps and teaching protection require their own authoritative controllers.

The ingress rule restricts the destination to gateway pods and its service port; Kubernetes NetworkPolicy cannot filter HTTP paths. The metrics token boundary therefore remains essential even with restricted network access.

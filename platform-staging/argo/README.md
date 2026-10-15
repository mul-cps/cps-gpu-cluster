# Private Argo staging

Argo 3.7.18 runs in `cps-argo`; workloads run in `cps-workflows` with restricted Pod Security, bounded namespace quotas and no inbound workload traffic. Chart 0.45.26 is cached and rendered with explicit application digest overrides. Existing CRDs are retained. No public ingress is installed.

The API uses client authentication and an operator-provisioned TLS certificate (`cps-argo-server-tls`). Gateway clients must validate the CA and service DNS name. Network policy permits only gateway Pods from `cps-compute`. Artifact credentials and the artifact CA exist only as private Secrets; user main containers must not receive them. Trusted executor containers receive narrowly scoped credentials.

Apply `../workload-rbac.yaml` before the Helm release. Provision TLS and S3 Secrets outside Git. Install with `helm upgrade --install cps-argo <verified-chart-path> -n cps-argo -f values.yaml`, then apply `network-policy.yaml`.

Live controllers and TLS startup passed on 2026-10-05. Generated-Pod admission, credential isolation, successful/failed notebook artifact collection and gateway ownership checks remain required before release. A running controller alone does not qualify the compute platform.

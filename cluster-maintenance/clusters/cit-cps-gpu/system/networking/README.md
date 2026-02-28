# Networking Configuration

This document outlines the networking and IP assignment strategy for the `cit-cps-gpu` cluster, specifically focusing on MetalLB and Ingress controllers.

## LoadBalancer IP Assignments

IP addresses are allocated from the MetalLB `default-pool` (10.21.0.50 - 10.21.0.60).

| Service | IP Address | Purpose |
|---------|------------|---------|
| `ingress-nginx-controller` | `10.21.0.50` | Primary Ingress for `*.dshl.unileoben.ac.at` |
| `kourier` (Knative) | `10.21.0.51` | Ingress for Knative/Serverless workloads |

## IP Sharing and Conflicts

Both `ingress-nginx` and `kourier` are configured to allow IP sharing using the following annotations:

```yaml
metallb.io/allow-shared-ip: "ingress-shared"
# and (deprecated but still used for compatibility)
metallb.universe.tf/allow-shared-ip: "ingress-shared"
```

### Important Conflict Note
While IP sharing is enabled, **port conflicts** occur if both services attempt to bind to the same port (e.g., 80 or 443) on the same IP. 
- Originally, both attempted to use `.50`.
- To resolve this, `kourier` was moved to `.51`.
- `ingress-nginx` remains on `.50` as it is the primary target for the wildcard DNS record.

## DNS Resolution

DNS for the `dshl.unileoben.ac.at` domain is handled internally by CoreDNS via the `coredns-custom` ConfigMap in the `kube-system` namespace.

- `*.dshl.unileoben.ac.at` -> `10.21.0.50`
- `@ (dshl.unileoben.ac.at)` -> `10.21.0.50`

## Configuration Files

- **Ingress Nginx**: `system/networking/ingress-nginx/values.yaml` (claims `.50`)
- **Kourier**: `system/knative/knative-serving/kourier.yaml` (claims `.51`)
- **CoreDNS**: Managed via `kube-system/coredns-custom` ConfigMap (corrected manually and documented here).

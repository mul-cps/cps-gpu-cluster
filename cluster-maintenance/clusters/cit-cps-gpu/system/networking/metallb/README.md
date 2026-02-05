# MetalLB Load Balancer

MetalLB provides LoadBalancer service type implementation for bare-metal Kubernetes clusters.

## Configuration

**Mode:** Layer 2 (ARP-based)
**IP Pool:** 10.21.0.50 - 10.21.0.60 (VLAN 633)
**Network:** 10.21.0.0/16

## Deployment

MetalLB is deployed in two stages via Fleet:

1. **metallb-crds** bundle - Installs CRDs first
2. **metallb** bundle - Installs MetalLB controller, speaker, and configuration (depends on metallb-crds)

This ensures the Custom Resource Definitions are available before creating IPAddressPool and L2Advertisement resources.

## How It Works

1. When a service requests `type: LoadBalancer`, MetalLB assigns an IP from the pool
2. MetalLB speaker responds to ARP requests for that IP
3. Traffic to the IP is forwarded to the appropriate service

## IP Allocation

- **Pool**: 10.21.0.50-10.21.0.60 (11 IPs available)
- **Auto-assign**: Enabled (automatic IP allocation)
- **First service**: Will likely get 10.21.0.50

## DNS Configuration

After MetalLB is deployed and ingress-nginx gets an external IP:

```bash
# Check assigned IP
kubectl -n ingress-nginx get svc ingress-nginx-controller

# Configure DNS wildcard
*.cps.unileoben.ac.at → <EXTERNAL-IP> (e.g., 10.21.0.50)
```

## Monitoring

MetalLB integrates with Prometheus/Grafana for:
- IP pool usage
- ARP/BGP metrics
- Speaker health

## Troubleshooting

```bash
# Check MetalLB pods
kubectl -n metallb-system get pods

# Check IP pool configuration
kubectl -n metallb-system get ipaddresspool

# Check L2 advertisement
kubectl -n metallb-system get l2advertisement

# View speaker logs
kubectl -n metallb-system logs -l component=speaker

# View controller logs
kubectl -n metallb-system logs -l component=controller
```

## Service Example

To request a LoadBalancer IP:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
spec:
  type: LoadBalancer
  # Optional: request specific IP from pool
  # loadBalancerIP: 10.21.0.55
  ports:
  - port: 80
    targetPort: 8080
  selector:
    app: my-app
```

## Notes

- Layer 2 mode works on any network (no BGP required)
- All nodes participate in ARP responses
- IP failover happens automatically if a node fails
- Compatible with VLAN tagged networks

# kube-vip Control Plane VIP

## Overview

kube-vip provides a Virtual IP (VIP) for the Kubernetes control plane API server, ensuring high availability.

**VIP:** 10.21.0.100
**Port:** 6443 (Kubernetes API)
**Mode:** ARP/Layer 2

## Why kube-vip?

- **Single stable endpoint** for kubectl, Rancher, and cluster tools
- **Survives control plane failures** - automatically moves to healthy control plane node
- **Runs as static pod** - doesn't depend on cluster being operational
- **Critical infrastructure** - separate from application load balancing (MetalLB)

## Deployment Method

kube-vip should be deployed as a static pod on control plane nodes during cluster bootstrap.

### Option 1: Ansible Deployment (Recommended)

Update `bootstrap-cluster/ansible/playbooks/02-k3s-cluster.yml` to deploy kube-vip on control planes:

```yaml
- name: Deploy kube-vip on control plane
  hosts: control_plane
  tasks:
    - name: Create kube-vip static pod manifest
      shell: |
        docker run --rm ghcr.io/kube-vip/kube-vip:v0.8.7 manifest pod \
          --interface eth0 \
          --address 10.21.0.100 \
          --controlplane \
          --services \
          --arp \
          --leaderElection | tee /var/lib/rancher/k3s/agent/pod-manifests/kube-vip.yaml
```

### Option 2: Manual Deployment

On each control plane node:

```bash
# Generate and deploy kube-vip manifest
docker run --rm ghcr.io/kube-vip/kube-vip:v0.8.7 manifest pod \
  --interface eth0 \
  --address 10.21.0.100 \
  --controlplane \
  --services \
  --arp \
  --leaderElection | sudo tee /var/lib/rancher/k3s/agent/pod-manifests/kube-vip.yaml
```

## Configuration

- **Interface**: eth0 (primary network interface in VLAN 633)
- **VIP**: 10.21.0.100
- **Mode**: ARP (Layer 2)
- **Leader Election**: Enabled (only one node holds VIP at a time)

## Usage

After deployment, update kubeconfig and other tools to use the VIP:

```yaml
# Update kubeconfig server address
server: https://10.21.0.100:6443

# Or use DNS
server: https://k8s-api.cps.unileoben.ac.at:6443
# (Requires DNS: k8s-api.cps.unileoben.ac.at → 10.21.0.100)
```

## Verification

```bash
# Check which control plane holds the VIP
ip addr show eth0 | grep 10.21.0.100

# Test API access via VIP
curl -k https://10.21.0.100:6443/version

# Check kube-vip logs
kubectl logs -n kube-system -l app=kube-vip
```

## IP Allocation

- **Control Plane VIP**: 10.21.0.100 (kube-vip)
- **Service LoadBalancers**: 10.21.0.50-60 (MetalLB)

Clear separation between infrastructure (kube-vip) and application services (MetalLB).

## Notes

- kube-vip runs on control planes only
- Does not require external dependencies
- Failover is automatic via leader election
- Compatible with K3s embedded etcd clusters
- Can coexist with MetalLB for service load balancing

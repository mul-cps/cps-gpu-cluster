# MUL Network Configuration for CPS GPU Cluster

## Overview

This document describes the network configuration for the K3s GPU cluster running on VLAN 633 at MUL (Montanuniversität Leoben).

## Network Details

- **VLAN ID**: 633
- **Network**: 10.21.0.0/16
- **Gateway**: 10.21.1.17
- **DNS Primary**: 193.171.87.249
- **DNS Secondary**: 193.171.87.250
- **Bridge**: vmbr0

## VM Network Assignments

### Control Plane VMs

| VM Name   | Hostname                    | MAC Address       | IP Address    | DHCP/Static |
|-----------|----------------------------|-------------------|---------------|-------------|
| k3s-cp1   | cit-vm-35.cit-gpu.local    | 00:16:3e:63:79:26 | 10.21.0.35/16 | Static      |
| k3s-cp2   | cit-vm-36.cit-gpu.local    | 00:16:3e:63:79:27 | 10.21.0.36/16 | Static      |
| k3s-cp3   | cit-vm-37.cit-gpu.local    | 00:16:3e:63:79:28 | 10.21.0.37/16 | Static      |

### GPU Worker VMs

| VM Name      | Hostname                    | MAC Address       | IP Address    | GPUs     |
|--------------|----------------------------|-------------------|---------------|----------|
| k3s-wk-gpu1  | cit-vm-38.cit-gpu.local    | 00:16:3e:63:79:29 | 10.21.0.38/16 | 2x A100  |
| k3s-wk-gpu2  | cit-vm-39.cit-gpu.local    | 00:16:3e:63:79:2a | 10.21.0.39/16 | 2x A100  |
| k3s-wk-gpu3  | cit-vm-40.cit-gpu.local    | 00:16:3e:63:79:2b | 10.21.0.40/16 | 2x A100  |
| k3s-wk-gpu4  | cit-vm-41.cit-gpu.local    | 00:16:3e:63:79:2c | 10.21.0.41/16 | 2x A100  |

### Reserved/Available MACs (Not Currently Used)

The following MACs are allocated but not currently assigned:

| MAC Address       | IP Address    | Hostname                    | Notes              |
|-------------------|---------------|-----------------------------|--------------------|
| 00:16:3e:63:79:2d | 10.21.0.42/16 | cit-vm-42.cit-gpu.local    | Available for expansion |
| 00:16:3e:63:79:2e | 10.21.0.43/16 | cit-vm-43.cit-gpu.local    | Available for expansion |
| 00:16:3e:63:79:2f | 10.21.0.44/16 | cit-vm-44.cit-gpu.local    | Available for expansion |

## Terraform Configuration

The network settings are configured in the following files:

### `variables.tf`

Defines the network variables including:
- VLAN ID (633)
- Gateway and DNS servers
- MAC address lists for control plane and workers
- Static IP assignments

### `main.tf`

Network blocks for each VM include:
```hcl
network {
  id      = 0
  model   = "virtio"
  bridge  = var.network_bridge
  macaddr = var.control_plane_macs[count.index]  # or worker_macs
  tag     = var.vlan_id  # VLAN 633
}
```

Cloud-init configuration:
```hcl
ipconfig0  = "ip=${var.control_plane_ips[count.index]},gw=${var.gateway}"
nameserver = "${var.nameserver} ${var.nameserver_secondary}"
```

### `terraform.tfvars`

Contains the actual values:
- VLAN ID: 633
- Gateway: 10.21.1.17
- DNS: 193.171.87.249, 193.171.87.250
- MAC addresses for all VMs
- Static IP addresses

## Network Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        VLAN 633                              │
│                     10.21.0.0/16                             │
│                                                              │
│  Gateway: 10.21.1.17                                         │
│  DNS: 193.171.87.249, 193.171.87.250                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              │
              ┌───────────────┴───────────────┐
              │                               │
    ┌─────────▼─────────┐         ┌──────────▼──────────┐
    │  Control Plane    │         │   GPU Workers       │
    │                   │         │                     │
    │  k3s-cp1 (.35)   │         │  k3s-wk-gpu1 (.38) │
    │  k3s-cp2 (.36)   │         │  k3s-wk-gpu2 (.39) │
    │  k3s-cp3 (.37)   │         │  k3s-wk-gpu3 (.40) │
    │                   │         │  k3s-wk-gpu4 (.41) │
    └───────────────────┘         └─────────────────────┘
```

## VLAN Tagged Traffic

All VMs are configured with:
- **VLAN tagging enabled** on the virtual network interface
- **Tag ID: 633**
- **MAC addresses assigned** from MUL DHCP allocation
- **Static IP configuration** via cloud-init

The Proxmox host's bridge (vmbr0) must be configured to support VLAN 633 tagged traffic.

## Verification

After deployment, verify network configuration on each VM:

```bash
# Check IP address
ip addr show

# Check default gateway
ip route show default

# Check DNS configuration
cat /etc/resolv.conf

# Test connectivity to gateway
ping -c 3 10.21.1.17

# Test DNS resolution
nslookup google.com
```

## Notes

- All VMs use static IP assignment via cloud-init
- MAC addresses are pre-assigned by MUL IT to ensure correct DHCP/network access
- VLAN 633 is a tagged/trunked VLAN for the CIT GPU cluster
- The network configuration is compatible with Kubernetes/K3s networking
- Container networking within K3s will use overlay networks (Flannel/Calico) on top of this base network

## Future Expansion

Three additional MAC/IP pairs are available (cit-vm-42, 43, 44) for future expansion of the cluster.

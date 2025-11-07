#!/usr/bin/env bash
# Helper script to find VM IDs on Proxmox
# Run this ON THE PROXMOX HOST to get the VM IDs

echo "Finding VM IDs by name..."
echo "========================"
echo ""

# Use pvesh to query all VMs
pvesh get /cluster/resources --type vm --output-format json 2>/dev/null | jq -r '.[] | "\(.vmid)\t\(.name)\t\(.status)"' | column -t -s $'\t' || {
    echo "Trying qm list instead..."
    qm list
}

echo ""
echo "Update these values in setup-ssh-keys.sh:"
echo "  MAINTENANCE_VM=<id>  (k3s-maintenance)"
echo "  CONTROL_PLANE_VMS=(id1 id2 id3)  (k3s-cp1, k3s-cp2, k3s-cp3)"
echo "  WORKER_VMS=(id1 id2 id3 id4)  (k3s-wk-gpu1-4)"

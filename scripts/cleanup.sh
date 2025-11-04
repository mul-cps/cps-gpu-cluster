#!/bin/bash

# Cleanup script - destroys all cluster resources
# WARNING: This will delete all VMs and data!

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}==================================================="
echo "WARNING: CLUSTER CLEANUP"
echo "===================================================${NC}"
echo ""
echo "This will:"
echo "  1. Delete all Kubernetes resources"
echo "  2. Destroy all VMs via Terraform"
echo "  3. Remove local kubeconfig"
echo ""
echo -e "${YELLOW}All data will be lost!${NC}"
echo ""

read -p "Are you sure you want to continue? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Starting cleanup..."
echo ""

# Step 1: Delete Kubernetes resources (if accessible)
if [ -f "$PROJECT_ROOT/kubeconfig" ]; then
    export KUBECONFIG="$PROJECT_ROOT/kubeconfig"
    
    echo "Deleting JupyterHub..."
    kubectl delete namespace jupyterhub --ignore-not-found=true --wait=false || true
    
    echo "Deleting GPU Operator..."
    kubectl delete namespace gpu-operator --ignore-not-found=true --wait=false || true
    
    echo "Deleting Rancher..."
    kubectl delete namespace cattle-system --ignore-not-found=true --wait=false || true
    
    echo "Deleting Fleet..."
    kubectl delete namespace fleet-local --ignore-not-found=true --wait=false || true
    
    echo "Waiting for graceful shutdown..."
    sleep 10
fi

# Step 2: Destroy VMs with Terraform
cd "$PROJECT_ROOT/bootstrap-cluster/terraform"

if [ -f "proxmox.tfvars" ]; then
    echo ""
    echo "Destroying VMs with Terraform..."
    terraform destroy -var-file=proxmox.tfvars -auto-approve
else
    echo "proxmox.tfvars not found, skipping Terraform destroy"
fi

# Step 3: Cleanup local files
echo ""
echo "Cleaning up local files..."

rm -f "$PROJECT_ROOT/kubeconfig"
rm -f "$PROJECT_ROOT/bootstrap-cluster/ansible/inventory.ini"
rm -rf "$PROJECT_ROOT/bootstrap-cluster/terraform/.terraform"
rm -f "$PROJECT_ROOT/bootstrap-cluster/terraform/.terraform.lock.hcl"
rm -f "$PROJECT_ROOT/bootstrap-cluster/terraform/terraform.tfstate"
rm -f "$PROJECT_ROOT/bootstrap-cluster/terraform/terraform.tfstate.backup"

echo ""
echo -e "${RED}Cleanup complete!${NC}"
echo ""
echo "To redeploy, run: ./scripts/deploy.sh"

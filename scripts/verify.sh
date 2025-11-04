#!/bin/bash

# Verification script for GPU cluster
# Run this after deployment to verify everything is working

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

function print_section() {
    echo ""
    echo -e "${BLUE}=== $1 ===${NC}"
    echo ""
}

function check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

function check_fail() {
    echo -e "${RED}✗${NC} $1"
}

function check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check kubeconfig
if [ -z "$KUBECONFIG" ]; then
    if [ -f "$PROJECT_ROOT/kubeconfig" ]; then
        export KUBECONFIG="$PROJECT_ROOT/kubeconfig"
    else
        echo -e "${RED}Error: KUBECONFIG not set and kubeconfig file not found${NC}"
        echo "Set with: export KUBECONFIG=/path/to/kubeconfig"
        exit 1
    fi
fi

echo "==================================================="
echo "GPU Cluster Verification"
echo "==================================================="

# 1. Cluster connectivity
print_section "Cluster Connectivity"

if kubectl cluster-info &> /dev/null; then
    check_pass "Can connect to cluster"
    kubectl cluster-info
else
    check_fail "Cannot connect to cluster"
    exit 1
fi

# 2. Node status
print_section "Node Status"

TOTAL_NODES=$(kubectl get nodes --no-headers | wc -l)
READY_NODES=$(kubectl get nodes --no-headers | grep " Ready " | wc -l)

echo "Total nodes: $TOTAL_NODES"
echo "Ready nodes: $READY_NODES"

if [ "$TOTAL_NODES" -eq "$READY_NODES" ]; then
    check_pass "All nodes are Ready"
else
    check_fail "Some nodes are not Ready"
fi

kubectl get nodes -o wide

# 3. Control plane nodes
print_section "Control Plane Nodes"

CP_COUNT=$(kubectl get nodes -l node-role.kubernetes.io/control-plane=true --no-headers | wc -l)

if [ "$CP_COUNT" -ge 3 ]; then
    check_pass "HA control plane with $CP_COUNT nodes"
elif [ "$CP_COUNT" -eq 1 ]; then
    check_warn "Single control plane node (not HA)"
else
    check_fail "Expected 3 control plane nodes, found $CP_COUNT"
fi

# 4. GPU worker nodes
print_section "GPU Worker Nodes"

GPU_WORKERS=$(kubectl get nodes -l accelerator=nvidia --no-headers | wc -l)

if [ "$GPU_WORKERS" -ge 4 ]; then
    check_pass "Found $GPU_WORKERS GPU worker nodes"
else
    check_warn "Expected 4 GPU workers, found $GPU_WORKERS"
fi

# 5. GPU resources
print_section "GPU Resources"

GPU_TOTAL=$(kubectl get nodes -o json | jq -r '[.items[].status.capacity."nvidia.com/gpu" // "0" | tonumber] | add')

if [ "$GPU_TOTAL" -gt 0 ]; then
    check_pass "Total GPUs available: $GPU_TOTAL"
    echo ""
    kubectl get nodes -o json | jq -r '.items[] | select(.status.capacity."nvidia.com/gpu" != null) | "\(.metadata.name): \(.status.capacity."nvidia.com/gpu") GPUs"'
else
    check_fail "No GPUs detected in cluster"
fi

# 6. Storage classes
print_section "Storage Classes"

if kubectl get sc nfs-client &> /dev/null; then
    check_pass "NFS storage class exists"
else
    check_fail "NFS storage class not found"
fi

if kubectl get sc fast-scratch &> /dev/null; then
    check_pass "Fast-scratch storage class exists"
else
    check_warn "Fast-scratch storage class not found"
fi

kubectl get sc

# 7. GPU Operator
print_section "GPU Operator"

if kubectl get namespace gpu-operator &> /dev/null; then
    check_pass "GPU Operator namespace exists"
    
    GPU_PODS=$(kubectl get pods -n gpu-operator --no-headers 2>/dev/null | wc -l)
    GPU_RUNNING=$(kubectl get pods -n gpu-operator --no-headers 2>/dev/null | grep "Running" | wc -l)
    
    echo "GPU Operator pods: $GPU_RUNNING/$GPU_PODS running"
    
    if [ "$GPU_PODS" -gt 0 ] && [ "$GPU_RUNNING" -eq "$GPU_PODS" ]; then
        check_pass "All GPU Operator pods are running"
    else
        check_warn "Some GPU Operator pods are not running"
    fi
    
    echo ""
    kubectl get pods -n gpu-operator
else
    check_warn "GPU Operator not installed"
fi

# 8. Test GPU access
print_section "GPU Functionality Test"

echo "Creating CUDA test pod..."

cat <<EOF | kubectl apply -f - &> /dev/null
apiVersion: v1
kind: Pod
metadata:
  name: cuda-test-verify
  namespace: default
spec:
  restartPolicy: Never
  nodeSelector:
    accelerator: nvidia
  containers:
  - name: cuda-vectoradd
    image: "nvcr.io/nvidia/k8s/cuda-sample:vectoradd-cuda11.7.1"
    resources:
      limits:
        nvidia.com/gpu: 1
EOF

# Wait for pod to complete
echo "Waiting for test to complete..."
kubectl wait --for=condition=ready pod/cuda-test-verify --timeout=120s &> /dev/null || true

sleep 5

# Check result
if kubectl logs cuda-test-verify 2>/dev/null | grep -q "Test PASSED"; then
    check_pass "CUDA test passed"
    echo ""
    kubectl logs cuda-test-verify
else
    check_fail "CUDA test failed or incomplete"
    echo ""
    kubectl describe pod cuda-test-verify
fi

# Cleanup
kubectl delete pod cuda-test-verify --ignore-not-found=true &> /dev/null

# 9. JupyterHub (if installed)
print_section "JupyterHub"

if kubectl get namespace jupyterhub &> /dev/null; then
    check_pass "JupyterHub namespace exists"
    
    HUB_STATUS=$(kubectl get pods -n jupyterhub -l component=hub --no-headers 2>/dev/null | awk '{print $3}' | head -1)
    
    if [ "$HUB_STATUS" == "Running" ]; then
        check_pass "JupyterHub hub is running"
    else
        check_warn "JupyterHub hub status: $HUB_STATUS"
    fi
    
    echo ""
    kubectl get pods -n jupyterhub
else
    check_warn "JupyterHub not installed"
fi

# 10. Rancher (if installed)
print_section "Rancher"

if kubectl get namespace cattle-system &> /dev/null; then
    check_pass "Rancher namespace exists"
    
    RANCHER_STATUS=$(kubectl get pods -n cattle-system -l app=rancher --no-headers 2>/dev/null | grep "Running" | wc -l)
    
    if [ "$RANCHER_STATUS" -gt 0 ]; then
        check_pass "Rancher is running ($RANCHER_STATUS pods)"
    else
        check_warn "Rancher pods not running"
    fi
else
    check_warn "Rancher not installed"
fi

# 11. Fleet (if installed)
print_section "Fleet GitOps"

if kubectl get namespace fleet-local &> /dev/null; then
    check_pass "Fleet namespace exists"
    
    GITREPOS=$(kubectl get gitrepo -n fleet-local --no-headers 2>/dev/null | wc -l)
    
    if [ "$GITREPOS" -gt 0 ]; then
        check_pass "Found $GITREPOS GitRepo(s)"
        echo ""
        kubectl get gitrepo -n fleet-local
    else
        check_warn "No GitRepos configured"
    fi
else
    check_warn "Fleet not installed"
fi

# Summary
echo ""
echo "==================================================="
echo "Verification Summary"
echo "==================================================="
echo ""

CHECKS_PASSED=0
CHECKS_FAILED=0

# Count key metrics
if [ "$READY_NODES" -eq "$TOTAL_NODES" ]; then ((CHECKS_PASSED++)); else ((CHECKS_FAILED++)); fi
if [ "$GPU_TOTAL" -gt 0 ]; then ((CHECKS_PASSED++)); else ((CHECKS_FAILED++)); fi
if kubectl get sc nfs-client &> /dev/null; then ((CHECKS_PASSED++)); else ((CHECKS_FAILED++)); fi

echo "Cluster Status: $READY_NODES/$TOTAL_NODES nodes ready"
echo "GPU Status: $GPU_TOTAL GPUs available"
echo ""

if [ "$CHECKS_FAILED" -eq 0 ]; then
    echo -e "${GREEN}All critical checks passed!${NC}"
    exit 0
else
    echo -e "${YELLOW}Some checks failed. Review output above.${NC}"
    exit 1
fi

#!/bin/bash

# NVIDIA GPU Monitoring Stack Deployment Script
# This script deploys the Rancher monitoring stack with NVIDIA GPU metrics integration

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MONITORING_NAMESPACE="cattle-monitoring-system"
DASHBOARD_NAMESPACE="cattle-dashboards"
GPU_OPERATOR_NAMESPACE="gpu-operator"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    # Check if helm is available
    if ! command -v helm &> /dev/null; then
        print_error "helm is not installed or not in PATH"
        exit 1
    fi
    
    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Unable to connect to Kubernetes cluster"
        exit 1
    fi
    
    # Check if GPU operator is deployed
    if ! kubectl get namespace "$GPU_OPERATOR_NAMESPACE" &> /dev/null; then
        print_warning "GPU operator namespace not found. Please deploy GPU operator first."
        print_warning "Continuing anyway - you can deploy monitoring first if needed."
    fi
    
    print_success "Prerequisites check completed"
}

add_helm_repo() {
    print_status "Adding Rancher monitoring Helm repository..."
    helm repo add rancher-monitoring https://charts.rancher.io
    helm repo update
    print_success "Helm repository added and updated"
}

create_namespaces() {
    print_status "Creating namespaces..."
    kubectl apply -f "$SCRIPT_DIR/namespace.yaml"
    print_success "Namespaces created"
}

deploy_monitoring_stack() {
    print_status "Deploying Rancher monitoring stack..."
    
    # Check if already installed
    if helm list -n "$MONITORING_NAMESPACE" | grep -q "rancher-monitoring"; then
        print_warning "Rancher monitoring stack already installed. Upgrading..."
        helm upgrade rancher-monitoring rancher-monitoring/rancher-monitoring \
            --namespace "$MONITORING_NAMESPACE" \
            --values "$SCRIPT_DIR/values.yaml" \
            --wait \
            --timeout 10m
    else
        helm install rancher-monitoring rancher-monitoring/rancher-monitoring \
            --namespace "$MONITORING_NAMESPACE" \
            --values "$SCRIPT_DIR/values.yaml" \
            --wait \
            --timeout 10m
    fi
    
    print_success "Monitoring stack deployed"
}

deploy_dashboards_and_alerts() {
    print_status "Deploying GPU dashboard and alert rules..."
    
    # Deploy GPU dashboard
    kubectl apply -f "$SCRIPT_DIR/gpu-dashboard.yaml"
    
    # Deploy alert rules
    kubectl apply -f "$SCRIPT_DIR/gpu-alerts.yaml"
    
    print_success "GPU dashboard and alerts deployed"
}

verify_deployment() {
    print_status "Verifying deployment..."
    
    # Check monitoring pods
    echo "Monitoring pods status:"
    kubectl get pods -n "$MONITORING_NAMESPACE"
    
    echo ""
    
    # Check GPU operator if exists
    if kubectl get namespace "$GPU_OPERATOR_NAMESPACE" &> /dev/null; then
        echo "GPU operator pods status:"
        kubectl get pods -n "$GPU_OPERATOR_NAMESPACE" | grep dcgm-exporter || echo "DCGM exporter not found"
        
        echo ""
        
        # Check ServiceMonitor
        echo "ServiceMonitor status:"
        kubectl get servicemonitor -n "$GPU_OPERATOR_NAMESPACE" || echo "No ServiceMonitors found in gpu-operator namespace"
    fi
    
    echo ""
    
    # Check dashboard ConfigMaps
    echo "Dashboard ConfigMaps:"
    kubectl get configmap -n "$DASHBOARD_NAMESPACE" | grep dashboard || echo "No dashboard ConfigMaps found"
    
    echo ""
    
    # Check PrometheusRules
    echo "PrometheusRules:"
    kubectl get prometheusrule -n "$MONITORING_NAMESPACE" | grep gpu || echo "No GPU PrometheusRules found"
    
    print_success "Deployment verification completed"
}

get_access_info() {
    print_status "Getting access information..."
    
    echo ""
    echo "=== ACCESS INFORMATION ==="
    echo ""
    
    # Grafana access
    echo "Grafana Dashboard:"
    echo "  Method 1 (Rancher UI): Cluster → Monitoring → Grafana"
    echo "  Method 2 (Port Forward):"
    echo "    kubectl port-forward -n $MONITORING_NAMESPACE svc/rancher-monitoring-grafana 3000:80"
    echo "    Open: http://localhost:3000"
    echo "    Default credentials: admin/admin"
    echo ""
    
    # Prometheus access
    echo "Prometheus:"
    echo "  Method 1 (Rancher UI): Cluster → Monitoring → Prometheus"
    echo "  Method 2 (Port Forward):"
    echo "    kubectl port-forward -n $MONITORING_NAMESPACE svc/rancher-monitoring-prometheus 9090:9090"
    echo "    Open: http://localhost:9090"
    echo ""
    
    # Alertmanager access
    echo "Alertmanager:"
    echo "  Port Forward:"
    echo "    kubectl port-forward -n $MONITORING_NAMESPACE svc/rancher-monitoring-alertmanager 9093:9093"
    echo "    Open: http://localhost:9093"
    echo ""
    
    # Quick verification commands
    echo "=== VERIFICATION COMMANDS ==="
    echo ""
    echo "Test GPU metrics in Prometheus:"
    echo "  Query: DCGM_FI_DEV_GPU_UTIL"
    echo "  Query: DCGM_FI_DEV_FB_USED"
    echo "  Query: DCGM_FI_DEV_GPU_TEMP"
    echo ""
    
    echo "Import NVIDIA Official Dashboard:"
    echo "  In Grafana: + → Import → Dashboard ID: 12239"
    echo ""
}

main() {
    echo "========================================="
    echo "  NVIDIA GPU Monitoring Stack Deployment"
    echo "========================================="
    echo ""
    
    check_prerequisites
    add_helm_repo
    create_namespaces
    deploy_monitoring_stack
    deploy_dashboards_and_alerts
    verify_deployment
    get_access_info
    
    echo ""
    print_success "Deployment completed successfully!"
    echo ""
    print_status "Next steps:"
    echo "  1. Access Grafana and verify GPU metrics are available"
    echo "  2. Import the official NVIDIA dashboard (ID: 12239)"
    echo "  3. Configure alerting endpoints in Alertmanager if needed"
    echo "  4. Review and customize alert thresholds in gpu-alerts.yaml"
    echo ""
}

# Run main function
main "$@"

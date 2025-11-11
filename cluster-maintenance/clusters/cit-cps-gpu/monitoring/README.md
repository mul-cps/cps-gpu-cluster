# Rancher Monitoring with NVIDIA GPU Metrics

This directory contains the configuration for deploying Rancher monitoring stack integrated with NVIDIA GPU metrics from the GPU Operator's DCGM exporter.

## Overview

The monitoring stack includes:
- **Prometheus**: Collects and stores metrics from cluster and GPU resources
- **Grafana**: Visualizes metrics through dashboards
- **Alertmanager**: Manages alerts and notifications
- **DCGM Exporter**: Provides NVIDIA GPU metrics
- **ServiceMonitors**: Auto-discovery of GPU metrics by Prometheus

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GPU Nodes     │    │   Prometheus    │    │    Grafana      │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ DCGM        │ │───▶│ │ServiceMonitor│ │───▶│ │ Dashboards  │ │
│ │ Exporter    │ │    │ │Discovery     │ │    │ │ GPU Metrics │ │
│ │ :9400       │ │    │ └─────────────┘ │    │ └─────────────┘ │
│ └─────────────┘ │    └─────────────────┘    └─────────────────┘
└─────────────────┘
```

## Prerequisites

1. **GPU Operator**: Must be deployed first with ServiceMonitor enabled
2. **Storage Class**: Ensure `local-path` storage class exists (or update values.yaml)
3. **Rancher**: Cluster should be managed by Rancher for Fleet deployment

## Deployment

### 1. Deploy via Fleet (Recommended)

The monitoring stack will be automatically deployed via Fleet when this configuration is committed to the repository.

### 2. Manual Deployment (Alternative)

If you need to deploy manually:

```bash
# Create namespace
kubectl apply -f namespace.yaml

# Add Rancher monitoring Helm repository
helm repo add rancher-monitoring https://charts.rancher.io
helm repo update

# Install monitoring stack
helm install rancher-monitoring rancher-monitoring/rancher-monitoring \
  --namespace cattle-monitoring-system \
  --values values.yaml \
  --wait
```

## Verification

### 1. Check Pod Status

```bash
# Check monitoring pods
kubectl get pods -n cattle-monitoring-system

# Check GPU operator pods
kubectl get pods -n gpu-operator

# Look for dcgm-exporter and ServiceMonitor
kubectl get servicemonitor -n gpu-operator
kubectl get svc -n gpu-operator | grep dcgm-exporter
```

### 2. Verify Prometheus Targets

Access Prometheus UI through Rancher:
1. Navigate to your cluster in Rancher
2. Click **Monitoring** → **Prometheus**
3. Go to **Status** → **Targets**
4. Verify `dcgm-exporter` targets are **UP**

Alternative port-forward method:
```bash
kubectl port-forward -n cattle-monitoring-system svc/rancher-monitoring-prometheus 9090:9090
# Open http://localhost:9090/targets
```

### 3. Test GPU Metrics

In Prometheus UI, query for GPU metrics:
```promql
DCGM_FI_DEV_GPU_UTIL
DCGM_FI_DEV_FB_USED
DCGM_FI_DEV_GPU_TEMP
```

## Grafana Access

### Default Credentials
- **Username**: `admin`
- **Password**: `admin` (change this in production!)

### Access Methods

1. **Through Rancher UI**:
   - Navigate to cluster → Monitoring → Grafana

2. **Direct Port Forward**:
   ```bash
   kubectl port-forward -n cattle-monitoring-system svc/rancher-monitoring-grafana 3000:80
   # Open http://localhost:3000
   ```

### NVIDIA GPU Dashboards

The monitoring stack automatically provisions two NVIDIA GPU dashboards via ConfigMaps:

1. **NVIDIA DCGM Dashboard for Kubernetes (MIG & Non-MIG GPUs)** - Complete official dashboard (gnetId: 23382)
   - Location: General → NVIDIA DCGM Dashboard for Kubernetes
   - Features: Aggregate metrics, per-GPU details, MIG support, error monitoring, power/temperature tracking
   
2. **NVIDIA GPU Monitoring - Overview** - Simplified dashboard for quick overview
   - Location: General → NVIDIA GPU Monitoring - Overview
   - Features: Key aggregate metrics (GPU utilization, tensor cores, memory usage)
   
These dashboards are automatically loaded when you access Grafana.

**Fixed Issues:**
- ✅ Datasource template variables resolved (DS_PROMETHEUS → prometheus)
- ✅ All panel queries properly configured for Rancher monitoring stack
- ✅ Template variables (Hostname, GPU ID, MIG Profile) working correctly

### Key GPU Metrics Available

- **GPU Utilization**: `DCGM_FI_DEV_GPU_UTIL`
- **Memory Usage**: `DCGM_FI_DEV_FB_USED` / `DCGM_FI_DEV_FB_FREE`
- **Temperature**: `DCGM_FI_DEV_GPU_TEMP`
- **Power Usage**: `DCGM_FI_DEV_POWER_USAGE`
- **Memory Bandwidth**: `DCGM_FI_DEV_MEM_COPY_UTIL`

### Profiling Metrics (Advanced)
- **Tensor Core Activity**: `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE`
- **SM Activity**: `DCGM_FI_PROF_SM_ACTIVE`
- **Memory Activity**: `DCGM_FI_PROF_DRAM_ACTIVE`

## Troubleshooting

### ServiceMonitor Not Discovered

1. **Check ServiceMonitor exists**:
   ```bash
   kubectl get servicemonitor -n gpu-operator
   ```

2. **Verify Prometheus configuration**:
   ```bash
   kubectl get prometheus -n cattle-monitoring-system -o yaml | grep -A 5 serviceMonitorSelector
   ```

3. **Check namespace selector**:
   ```bash
   kubectl get prometheus -n cattle-monitoring-system -o yaml | grep -A 5 serviceMonitorNamespaceSelector
   ```

### DCGM Exporter Issues

1. **Check exporter pods**:
   ```bash
   kubectl get pods -n gpu-operator -l app=nvidia-dcgm-exporter
   kubectl logs -n gpu-operator -l app=nvidia-dcgm-exporter
   ```

2. **Test metrics endpoint**:
   ```bash
   kubectl port-forward -n gpu-operator svc/nvidia-dcgm-exporter 9400:9400
   curl http://localhost:9400/metrics
   ```

### No GPU Metrics in Grafana

1. **Verify Prometheus data source**: Ensure Grafana is using the correct Prometheus instance
2. **Check metric labels**: GPU metrics may have different labels than expected
3. **Time range**: Ensure dashboard time range covers when GPU workloads were running

## Customization

### Storage Classes

Update `storageClassName` in `values.yaml` if using different storage:
```yaml
prometheus:
  prometheusSpec:
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: "your-storage-class"
```

### Resource Limits

Adjust resource requests/limits in `values.yaml` based on cluster size:
```yaml
prometheus:
  prometheusSpec:
    resources:
      requests:
        memory: "2Gi"  # Increase for larger clusters
        cpu: "1000m"
```

### Custom Dashboards

Create persistent dashboards by adding ConfigMaps to `cattle-dashboards` namespace:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: custom-gpu-dashboard
  namespace: cattle-dashboards
  labels:
    grafana_dashboard: "1"
data:
  dashboard.json: |
    { "dashboard": { ... } }
```

## Maintenance

### Backup Considerations

- **Prometheus Data**: Stored in PVC, ensure backup strategy
- **Grafana Dashboards**: Export custom dashboards and store as ConfigMaps
- **Configuration**: This Git repository serves as configuration backup

### Updates

Update monitoring stack version in `fleet.yaml`:
```yaml
helm:
  version: "103.0.3+up45.31.1"  # Update as needed
```

Fleet will automatically apply updates when configuration changes are committed.

## Security Notes

1. **Change default passwords**: Update Grafana admin password in production
2. **Network policies**: Consider implementing network policies for monitoring namespace
3. **RBAC**: Review and customize RBAC permissions as needed
4. **TLS**: Configure TLS for external access in production environments

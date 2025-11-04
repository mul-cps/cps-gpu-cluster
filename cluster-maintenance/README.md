# Cluster Maintenance - Fleet GitOps

This directory contains declarative configurations for day-2 cluster operations managed by Rancher Fleet.

## Overview

Fleet enables GitOps-based management of Kubernetes clusters. All applications and configurations are defined as Helm charts or Kubernetes manifests in this repository.

## Prerequisites

1. K3s cluster running (deployed via bootstrap-cluster)
2. Rancher installed on the cluster
3. Fleet enabled in Rancher

## Structure

```
cluster-maintenance/
├── clusters/
│   └── homelab/
│       ├── fleet.yaml              # Fleet bundle configuration
│       ├── rancher/               # Rancher installation
│       ├── cert-manager/          # Certificate management
│       ├── ingress-nginx/         # Ingress controller
│       ├── gpu-operator/          # NVIDIA GPU Operator
│       ├── storageclasses/        # Storage configurations
│       ├── jupyterhub/            # JupyterHub deployment
│       └── tests/                 # Validation pods
└── README.md
```

## Installation

### 1. Install Rancher

First, install Rancher on the K3s cluster:

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Wait for cert-manager
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=300s

# Install Rancher
helm repo add rancher-stable https://releases.rancher.com/server-charts/stable
helm repo update

kubectl create namespace cattle-system

helm install rancher rancher-stable/rancher \
  --namespace cattle-system \
  --set hostname=rancher.cluster.local \
  --set bootstrapPassword=admin \
  --set replicas=3
```

### 2. Access Rancher UI

```bash
# Get Rancher URL
kubectl -n cattle-system rollout status deploy/rancher
echo "https://rancher.cluster.local"

# Or use port-forward for local access
kubectl -n cattle-system port-forward deploy/rancher 8443:443
```

Login with:
- Username: `admin`
- Password: `admin` (or retrieve with `kubectl get secret --namespace cattle-system bootstrap-secret -o go-template='{{.data.bootstrapPassword|base64decode}}{{"\n"}}'`)

### 3. Configure Fleet

From Rancher UI:

1. Navigate to **Continuous Delivery** (Fleet)
2. Click **Git Repos** → **Create**
3. Configure:
   - **Name**: `cluster-maintenance`
   - **Repository URL**: `https://github.com/<your-org>/cps-gpu-cluster`
   - **Branch**: `main`
   - **Paths**: `cluster-maintenance/clusters/homelab`
4. Click **Create**

Fleet will now automatically deploy and manage all applications defined in this path.

### 4. Alternative: Manual GitRepo Creation

```bash
cat <<EOF | kubectl apply -f -
apiVersion: fleet.cattle.io/v1alpha1
kind: GitRepo
metadata:
  name: cluster-maintenance
  namespace: fleet-local
spec:
  repo: https://github.com/<your-org>/cps-gpu-cluster
  branch: main
  paths:
  - cluster-maintenance/clusters/homelab
  targets:
  - name: local
    clusterSelector:
      matchLabels:
        management.cattle.io/cluster-display-name: local
EOF
```

## What Gets Deployed

Via Fleet, the following will be automatically deployed:

### Core Infrastructure
- **cert-manager**: SSL/TLS certificate management
- **ingress-nginx**: Ingress controller for external access

### Storage
- **StorageClasses**: NFS and fast-scratch configurations

### GPU Support
- **NVIDIA GPU Operator**: GPU drivers, device plugin, monitoring

### AI Platform
- **JupyterHub**: Multi-user notebook environment with GPU support

### Monitoring (Optional)
- **Prometheus**: Metrics collection
- **Grafana**: Dashboards

## Fleet Bundle Structure

Each application directory contains:
- `values.yaml`: Helm values or Kustomize configuration
- `fleet.yaml`: Fleet-specific configuration (targeting, dependencies)

Example `fleet.yaml`:

```yaml
namespace: jupyterhub
helm:
  chart: jupyterhub
  repo: https://jupyterhub.github.io/helm-chart
  version: 3.1.0
  releaseName: jupyterhub
  valuesFiles:
  - values.yaml
dependsOn:
- selector:
    matchLabels:
      app: gpu-operator
```

## Customization

### Modify Application Settings

1. Edit the `values.yaml` in the respective application directory
2. Commit and push to Git
3. Fleet will automatically detect changes and update the cluster

### Add New Applications

1. Create new directory under `clusters/homelab/<app-name>/`
2. Add Helm chart or Kubernetes manifests
3. Create `fleet.yaml` with bundle configuration
4. Commit and push

## Verification

Check Fleet bundle status:

```bash
# List all GitRepos
kubectl get gitrepo -n fleet-local

# Check bundle status
kubectl get bundles -n fleet-local

# View bundle details
kubectl describe bundle <bundle-name> -n fleet-local
```

Check deployed applications:

```bash
# GPU Operator
kubectl get pods -n gpu-operator

# JupyterHub
kubectl get pods -n jupyterhub

# StorageClasses
kubectl get sc
```

## Troubleshooting

### Bundle not deploying

```bash
# Check GitRepo status
kubectl get gitrepo cluster-maintenance -n fleet-local -o yaml

# Check bundle resources
kubectl get bundledeployments -A

# View Fleet logs
kubectl logs -n cattle-fleet-system -l app=fleet-controller
```

### Application failing

```bash
# Check bundle status
kubectl describe bundle <bundle-name> -n fleet-local

# Check Helm release
helm list -A

# Check pod logs
kubectl logs -n <namespace> <pod-name>
```

## Rollback

Fleet supports automatic rollback on failure. To manually rollback:

```bash
# Revert Git commit
git revert <commit-hash>
git push

# Fleet will automatically apply the previous state
```

## Best Practices

1. **Test changes locally** before committing
2. **Use branches** for testing major changes
3. **Set dependencies** in fleet.yaml to ensure proper ordering
4. **Monitor bundle status** after changes
5. **Keep secrets** in Kubernetes Secrets, not in Git

## Next Steps

After Fleet is configured:
1. Deploy JupyterHub (see [clusters/homelab/jupyterhub/README.md](clusters/homelab/jupyterhub/README.md))
2. Create user profiles for GPU access
3. Test GPU availability in notebooks
4. Configure monitoring and alerting

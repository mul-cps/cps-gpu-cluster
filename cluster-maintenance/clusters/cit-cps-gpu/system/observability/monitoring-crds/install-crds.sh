#!/bin/bash
set -e

echo "Installing Prometheus Operator CRDs..."

# Install all Prometheus Operator CRDs
kubectl apply --server-side=true --force-conflicts -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.73.0/example/prometheus-operator-crd/monitoring.coreos.com_alertmanagerconfigs.yaml
kubectl apply --server-side=true --force-conflicts -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.73.0/example/prometheus-operator-crd/monitoring.coreos.com_alertmanagers.yaml  
kubectl apply --server-side=true --force-conflicts -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.73.0/example/prometheus-operator-crd/monitoring.coreos.com_podmonitors.yaml
kubectl apply --server-side=true --force-conflicts -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.73.0/example/prometheus-operator-crd/monitoring.coreos.com_probes.yaml
kubectl apply --server-side=true --force-conflicts -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.73.0/example/prometheus-operator-crd/monitoring.coreos.com_prometheuses.yaml
kubectl apply --server-side=true --force-conflicts -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.73.0/example/prometheus-operator-crd/monitoring.coreos.com_prometheusagents.yaml
kubectl apply --server-side=true --force-conflicts -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.73.0/example/prometheus-operator-crd/monitoring.coreos.com_prometheusrules.yaml
kubectl apply --server-side=true --force-conflicts -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.73.0/example/prometheus-operator-crd/monitoring.coreos.com_scrapeconfigs.yaml
kubectl apply --server-side=true --force-conflicts -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.73.0/example/prometheus-operator-crd/monitoring.coreos.com_servicemonitors.yaml
kubectl apply --server-side=true --force-conflicts -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.73.0/example/prometheus-operator-crd/monitoring.coreos.com_thanosrulers.yaml

echo "Prometheus Operator CRDs installed successfully!"

# Create namespaces
kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: cattle-monitoring-system
  labels:
    name: cattle-monitoring-system
    monitoring: "rancher"
    cluster: "cit-cps-gpu"
---
apiVersion: v1
kind: Namespace
metadata:
  name: cattle-dashboards
  labels:
    name: cattle-dashboards
    monitoring: "rancher"
    cluster: "cit-cps-gpu"
    grafana_dashboard: "1"
EOF

echo "Namespaces created successfully!"

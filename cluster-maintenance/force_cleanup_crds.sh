#!/bin/bash
# Get all CRDs matching knative or kubeflow
CRDS=$(kubectl get crd -o name | grep -E "knative|kubeflow")

for crd in $CRDS; do
  echo "Processing $crd..."
  # Remove finalizers to prevent stuck deletion
  kubectl patch $crd --type merge -p '{"metadata":{"finalizers":[]}}'
  # Delete the CRD
  kubectl delete $crd --timeout=10s
done

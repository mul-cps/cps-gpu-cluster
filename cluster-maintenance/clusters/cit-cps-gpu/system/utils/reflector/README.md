# Kubernetes Reflector

Deploys [Kubernetes Reflector](https://github.com/emberstack/kubernetes-reflector) using the Emberstack Helm chart.

Reflector keeps secrets and configmaps synchronized across namespaces.

## Usage

Annotate the source secret/configmap:
```yaml
reflector.v1.k8s.emberstack.com/reflection-allowed: "true"
reflector.v1.k8s.emberstack.com/reflection-auto-enabled: "true" # Optional, for auto-replication
```

See upstream docs for more details.

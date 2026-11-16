# Released GPU Fractioning 0.1.9 manifests

These resources are rendered from the upstream chart, not a runtime fork.
The CRD and namespace install first; the operand bundle depends on them.
The default CR is restricted to GPU2 plus an explicit runtime nomination label.
Do not remove either selector until that worker has completed acceptance.

Chart archive SHA256: `238c08d45f1087b07b2793e7ee9e9e6b2f23a12e0bdbd680e37e3ab1b5479e58`.
Upstream source: https://github.com/kai-scheduler/gpu-fractioning/tree/v0.1.9

Reproduce the input from the repository root (CHART is the released archive):

```sh
helm template gpu-fractioning "$CHART" -n gpu-fractioning --include-crds \
  -f platform-staging/gpu/upstream-sharing/fraction-values.yaml \
  --set crdUpgrader.enabled=false > /tmp/fraction-raw.yaml
python3 platform-staging/gpu/upstream-sharing/prepare.py fraction-postrender \
  < /tmp/fraction-raw.yaml > /tmp/fraction-scoped.yaml
```

Split CustomResourceDefinition documents into the CRD bundle, adding the
`gpu-fractioning` Namespace there; put the other documents in this bundle.
Remove only `helm.sh/hook*` annotations from the default CR. It is an ordinary
GitOps-managed resource so the released post-install hook cannot create an
unscoped default configuration outside the post-renderer. The chart's CRD
upgrade hook is disabled because Fleet owns the released CRD directly.
The selector, K3s sockets, fail-open=false, retroactive enforcement=true,
maintenance toleration and time-slicing-only setting are CPS configuration;
operator, fractiond, mpsd and metricsd remain upstream 0.1.9.

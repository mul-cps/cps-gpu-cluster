# Released GPU Fractioning 0.1.9 manifests

These resources are rendered from the upstream chart, not a runtime fork.
The CRD installs first; the operand bundle depends on it. Fleet creates the
release namespace through defaultNamespace; the bundles do not own/delete it.
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

Split CustomResourceDefinition documents into the CRD bundle; put the other
documents in this bundle. Do not render a Namespace resource: Fleet creates
the release namespace before Helm and does not give it Helm ownership.
Remove only `helm.sh/hook*` annotations from the default CR. It is an ordinary
GitOps-managed resource so the released post-install hook cannot create an
unscoped default configuration outside the post-renderer. The chart's CRD
upgrade hook is disabled because Fleet owns the released CRD directly.
The selector, K3s sockets, fail-open=false, retroactive enforcement=true,
maintenance toleration and time-slicing-only setting are CPS configuration;
operator, fractiond, mpsd and metricsd remain upstream 0.1.9.

Verified registry manifest digests for the published `v0.1.9` tags:

- operator: `sha256:83e0aa29b0951c58b5565cbc50b2ae1900da25c78cdfcdf6eddea437748fe22c`
- fractiond: `sha256:29c5fca25c1b35f22cf9f1e6c53acaa79d0b9f722ed6e8417caf438c06cd3739`
- metricsd: `sha256:7a619c92651d0744bcd80745be264f3b6c213ad4f3a12fef19a339df422af2bf`
- mpsd: `sha256:f161d6c653c668e49e384ae15794421777464248c5e533660ac26b006787b102`

The unprefixed `0.1.9` image tags do not exist. The initial selected-node pilot
exposed this pinning mistake before daemon startup; corrected manifests use the
released chart appVersion `v0.1.9`. Rendering alone cannot verify image availability.

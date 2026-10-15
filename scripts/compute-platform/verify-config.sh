#!/usr/bin/env bash
# Offline assertions plus pinned chart downloads. No cluster writes or GPU jobs.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root"
cache=/tmp/cps-platform-charts
mkdir -p "$cache"
pull() {
  if [[ ! -f "$cache/$1" ]]; then
    local package=$1
    shift
    helm pull "$@" --destination "$cache"
  fi
}
pull jupyterhub-4.4.2.tgz jupyterhub --repo https://jupyterhub.github.io/helm-chart --version 4.4.2
pull loki-7.0.0.tgz loki --repo https://grafana.github.io/helm-charts --version 7.0.0
pull alloy-1.10.0.tgz alloy --repo https://grafana.github.io/helm-charts --version 1.10.0
pull descheduler-0.34.0.tgz descheduler --repo https://kubernetes-sigs.github.io/descheduler/ --version 0.34.0
pull kai-scheduler-v0.18.1.tgz oci://ghcr.io/kai-scheduler/kai-scheduler/kai-scheduler --version v0.18.1
pull kai-resource-isolator-1.1.0-chart.tgz oci://docker.io/projecthami/kai-resource-isolator --version 1.1.0-chart
(cd "$cache" && sha256sum -c "$root/platform-staging/chart-checksums.sha256")
for suite in compute_policy compute_platform observability descheduler; do
  python3 -m unittest discover -s "tests/$suite" -v
done
python3 -m unittest discover -s platform-staging/artifacts/truenas -v
python3 scripts/compile_compute_policy.py --check
helm lint platform-staging/chart
helm template jupyterhub "$cache/jupyterhub-4.4.2.tgz" -n jupyterhub \
  -f cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml > "$cache/hub-rendered.yaml"
helm template descheduler "$cache/descheduler-0.34.0.tgz" -n descheduler \
  -f cluster-maintenance/clusters/cit-cps-gpu/system/descheduler/values.yaml > "$cache/descheduler-rendered.yaml"
helm template kai-scheduler "$cache/kai-scheduler-v0.18.1.tgz" -n kai-scheduler \
  -f platform-staging/scheduler/kai-values.yaml > "$cache/kai-rendered.yaml"
# Apply the mandatory narrow webhook scope after rendering the upstream chart.
helm template kai-resource-isolator "$cache/kai-resource-isolator-1.1.0-chart.tgz" -n kai-resource-isolator \
  -f platform-staging/scheduler/isolator-values.yaml > "$cache/isolator-rendered.yaml"
cp platform-staging/scheduler/isolator-scope-patch.yaml "$cache/scope-patch.yaml"
cat > "$cache/kustomization.yaml" <<'YAML'
resources: [isolator-rendered.yaml]
patches: [{path: scope-patch.yaml}]
YAML
kubectl kustomize "$cache" > "$cache/isolator-scoped.yaml"
python3 - "$cache/isolator-scoped.yaml" <<'PY'
import sys,yaml
objects=list(yaml.safe_load_all(open(sys.argv[1])))
webhooks=[d for d in objects if d and d['kind']=='MutatingWebhookConfiguration']
assert len(webhooks)==1
hook=webhooks[0]['webhooks'][0]
assert hook['failurePolicy']=='Fail'
assert hook['namespaceSelector']=={'matchLabels': {'compute.cps.unileoben.ac.at/isolation':'required'}}
assert not hook.get('objectSelector')
assert hook['matchConditions'][0]['expression']=="object.spec.schedulerName == 'kai-scheduler'"
PY
kubectl kustomize cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring > "$cache/monitoring-rendered.yaml"
for check in tests/jupyterhub/*.sh tests/longhorn/*.sh; do
  bash "$check" >/dev/null
done
printf 'Configuration checks passed. This does not qualify live scheduling or releases.\n'

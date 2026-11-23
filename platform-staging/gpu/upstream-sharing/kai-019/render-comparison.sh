#!/usr/bin/env bash
set -euo pipefail
umask 077
package=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
charts=$(realpath "${1:?directory containing the two released charts required}")
output=${2:?new output directory required}
(cd "$charts" && sha256sum -c "$package/charts.sha256")
mkdir "$output"
helm list -n kai-scheduler --filter '^kai-scheduler$' -o json > "$output/live-release.json"
jq -e 'length == 1 and .[0].chart == "kai-scheduler-v0.18.1" and .[0].status == "deployed"' \
  "$output/live-release.json" > /dev/null
helm get values kai-scheduler -n kai-scheduler -o yaml > "$output/baseline-values.yaml"
helm get manifest kai-scheduler -n kai-scheduler > "$output/rollback.yaml"
helm get hooks kai-scheduler -n kai-scheduler > "$output/rollback-hooks.yaml"
helm template kai-scheduler "$charts/kai-scheduler-v0.18.1.tgz" -n kai-scheduler \
  --include-crds -f "$output/baseline-values.yaml" > "$output/rollback-chart-render.yaml"
helm template kai-scheduler "$charts/kai-scheduler-v0.19.0.tgz" -n kai-scheduler \
  --include-crds -f "$output/baseline-values.yaml" -f "$package/values.yaml" -f "$package/pinned-images.yaml" \
  > "$output/candidate.yaml"
helm template gpu-fractioning "$charts/gpu-fractioning-0.1.9.tgz" -n gpu-fractioning \
  --include-crds -f "$package/../fraction-values.yaml" > "$output/fractioning-reference.yaml"
kubectl get crd,validatingwebhookconfiguration,mutatingwebhookconfiguration -o json \
  | jq '{items: [.items[] | select(
      (.kind == "CustomResourceDefinition" and
        (.spec.group | IN("kai.scheduler", "scheduling.run.ai", "gpu-fractioning.kai.scheduler", "nvidia.com")))
      or any(.webhooks[]?; .clientConfig.service.namespace | IN("kai-scheduler", "gpu-fractioning"))
    )]}' \
  > "$output/live-admission.json"
kubectl get queues.scheduling.run.ai -o json > "$output/live-queues.json"
kubectl -n gpu-fractioning get gpufractioningconfigs,daemonsets,deployments -o json > "$output/live-fractioning.json"
kubectl -n kai-scheduler get pods -o json | jq '[.items[] | {
  pod: .metadata.name,
  images: [.status.containerStatuses[]? | {name,image,imageID}]
}]' > "$output/live-image-IDs.json"
while read -r image digest; do
  actual=$(skopeo inspect --no-tags --format '{{.Digest}}' "docker://$image")
  if [[ $actual != "$digest" ]]; then
    printf 'Image digest changed for %s\n' "$image" >&2
    exit 1
  fi
done < "$package/images.lock"
cat "$output/rollback.yaml" "$output/rollback-hooks.yaml" > "$output/baseline.yaml"
status=0
diff -u "$output/baseline.yaml" "$output/candidate.yaml" > "$output/release.diff" || status=$?
if (( status > 1 )); then
  exit "$status"
fi
python3 "$package/check-comparison.py" "$output" > "$output/comparison.json"

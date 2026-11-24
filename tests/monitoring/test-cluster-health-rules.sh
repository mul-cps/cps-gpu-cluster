#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT
kubectl kustomize cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring > "$temp_dir/bundle.yaml"

python3 - "$temp_dir" <<'PY'
import pathlib
import sys

import yaml


# The bundle contains SOPS YAML with an unquoted "=" key.
class BundleLoader(yaml.SafeLoader):
    pass


BundleLoader.add_constructor(
    "tag:yaml.org,2002:value", yaml.SafeLoader.construct_scalar
)

directory = pathlib.Path(sys.argv[1])
expected = {"cps-cluster-health", "nvidia-gpu-alerts-fleet"}
with (directory / "bundle.yaml").open() as bundle:
    for resource in yaml.load_all(bundle, Loader=BundleLoader):
        if not resource or resource["kind"] != "PrometheusRule":
            continue
        name = resource["metadata"]["name"]
        if name in expected:
            with (directory / f"{name}.yaml").open("w") as rule_file:
                yaml.safe_dump(resource["spec"], rule_file)
            expected.remove(name)

if expected:
    sys.exit(f"Missing rendered PrometheusRules: {', '.join(sorted(expected))}")
PY

cp tests/monitoring/cluster-health-rules.test.yaml "$temp_dir/"
"${PROMTOOL:-promtool}" check rules "$temp_dir/cps-cluster-health.yaml" "$temp_dir/nvidia-gpu-alerts-fleet.yaml"
"${PROMTOOL:-promtool}" test rules "$temp_dir/cluster-health-rules.test.yaml"

#!/usr/bin/env bash
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
monitoring="$root/cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
python3 - "$monitoring/storage-alerts.yaml" > "$scratch/storage.yaml" <<'PY'
import sys
import yaml

with open(sys.argv[1]) as source:
    yaml.safe_dump(yaml.safe_load(source)["spec"], sys.stdout)
PY
cp "$root/tests/monitoring/storage-rules.test.yaml" "$scratch/"
cd "$scratch"
"${PROMTOOL:-promtool}" check rules storage.yaml
"${PROMTOOL:-promtool}" test rules storage-rules.test.yaml

#!/usr/bin/env bash
# Local render/schema checks only. Never applies Kubernetes resources.
set -euo pipefail
charts=${1:?released chart directory required}
output=${2:?new output directory required}
live_kai=${3:-}
package=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mkdir "$output"
helm template gpu-fractioning "$charts/gpu-fractioning-0.1.9.tgz" -n gpu-fractioning \
  --include-crds -f "$package/fraction-values.yaml" > "$output/fraction-raw.yaml"
python3 "$package/prepare.py" fraction-postrender < "$output/fraction-raw.yaml" > "$output/fraction.yaml"
kai_args=()
if [[ -n "$live_kai" ]]; then kai_args=(-f "$live_kai"); fi
helm template kai-scheduler "$charts/kai-scheduler-v0.18.1.tgz" -n kai-scheduler \
  "${kai_args[@]}" -f "$package/kai-values.yaml" > "$output/kai.yaml"
helm template gpu-operator "$charts/gpu-operator-v26.7.1.tgz" -n gpu-operator \
  -f "$package/gpu-operator-lifecycle-values.yaml" -f "$package/gpu-operator-target-values.yaml" > "$output/gpu-operator.yaml"
python3 - "$output" <<'PY'
import json,sys
from pathlib import Path
import jsonschema,yaml
out=Path(sys.argv[1])
def documents(name):return [d for d in yaml.safe_load_all((out/name).read_text()) if d]
fraction=documents('fraction.yaml')
config=[d for d in fraction if d['kind']=='GpuFractioningConfig']
assert len(config)==1
config=config[0]
crd=next(d for d in fraction if d['kind']=='CustomResourceDefinition' and d['spec']['names']['kind']=='GpuFractioningConfig')
schema=next(v for v in crd['spec']['versions'] if v['name']=='v1alpha1')['schema']['openAPIV3Schema']
jsonschema.validate(config,schema)
assert config['spec']['nodeSelector']=={'kubernetes.io/hostname':'k3s-wk-gpu2','cps.unileoben.ac.at/fractioning-runtime':'upstream'}
agent=config['spec']['fractioningAgent']
assert agent['failOpen'] is False and agent['retroactiveEnforcement'] is True
assert agent['criSocketPath']=='/run/k3s/containerd/containerd.sock'
assert agent['nriSocketPath']=='/var/run/nri/nri.sock'
assert not any(d['kind']=='GpuFractioningConfig' for d in documents('kai.yaml'))
inline=[d for d in documents('kai.yaml') if d['kind']=='Config' and d.get('apiVersion')=='kai.scheduler/v1']
assert len(inline)==1
kai=inline[0]['spec']
assert not any(d['kind']=='Job' and 'kai-config' in d['metadata']['name'] for d in documents('kai.yaml'))
assert kai['global']['gpuSharingMode']=='NvFractions'
assert kai['binder']['plugins']['hamicore']['enabled'] is False
assert kai['binder']['service']['enabled'] is True
assert kai['binder'].get('cdiEnabled') is True
image=kai['binder']['service']['image']
assert (image['repository'],image['name'],image['tag'])==('ghcr.io/kai-scheduler/kai-scheduler','binder','v0.18.1')
gpu=documents('gpu-operator.yaml')
policy=next(d for d in gpu if d['kind']=='ClusterPolicy')['spec']
assert policy['daemonsets']['updateStrategy']=='OnDelete'
assert policy['driver']['upgradePolicy']['autoUpgrade'] is False
assert policy['mig']['strategy']=='none'
for key,version in [('toolkit','v1.20.1'),('devicePlugin','v0.20.1'),('gfd','v0.20.1')]:
 assert policy[key]['version']==version
assert policy['devicePlugin']['image']=='k8s-device-plugin'
for d in gpu:
 if d['kind']=='DaemonSet':assert d['spec']['updateStrategy']['type']=='OnDelete'
(out/'verification.json').write_text(json.dumps({'release_chart_rendering':'passed','fraction_crd_schema':'passed','stock_kai_overlay':'passed','gpu_operator_target_fields':'passed','deployed':False,'hardware_qualified':False,'r620_driver_image_configured':False},indent=2)+'\n')
print((out/'verification.json').read_text())
PY

#!/usr/bin/env python3
"""Read actual canary image/module/firmware/MIG and host process state."""
import datetime
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
IMAGE = 'nvcr.io/nvidia/driver@sha256:bc7572b7f14177c467e4dd8b66c4f4535f462ea9cf6a65cebd7603cc966ebbd7'
SCRIPT = r'''set -eu
printf 'driver_version\n'
cat /proc/driver/nvidia/version
printf 'gpu_and_mig_state\n'
nvidia-smi --query-gpu=uuid,driver_version,name,mig.mode.current,mig.mode.pending --format=csv,noheader
printf 'firmware_path='
cat /sys/module/firmware_class/parameters/path
printf '\nfirmware_sizes\n'
for f in gsp_tu10x.bin ucodes_tu10x.bin gsp_ga10x.bin ucodes_ga10x.bin; do
 stat -c '%n %s' "/proc/1/root/run/nvidia/firmware-r615-canary/nvidia/615.71.09/$f"
done
printf 'critical_host_processes\n'
for p in /proc/[0-9]*; do
 comm=$(cat "$p/comm" 2>/dev/null) || continue
 case "$comm" in k3s-agent|k3s|containerd)
  printf 'pid=%s comm=%s start_ticks=' "${p##*/}" "$comm"
  awk '{print $22}' "$p/stat"
  printf 'exe='
  readlink "$p/exe" || true
 ;; esac
done
printf 'host_boot_time='
sed -n 's/^btime //p' /proc/stat
printf 'clock_ticks_per_second='
getconf CLK_TCK
'''


if __name__ == '__main__':
    pods = json.loads(subprocess.check_output(['kubectl', '-n', 'gpu-operator', 'get', 'pods',
        '-l', 'app=gpu2-r615-driver-canary', '-o', 'json']))['items']
    assert len(pods) == 1
    pod = pods[0]
    assert pod['spec']['nodeName'] == 'k3s-wk-gpu2'
    status = next(c for c in pod['status']['containerStatuses'] if c['name'] == 'nvidia-driver-ctr')
    assert status['imageID'] == IMAGE
    output = subprocess.check_output(['kubectl', '-n', 'gpu-operator', 'exec', '-i', pod['metadata']['name'],
        '-c', 'nvidia-driver-ctr', '--', 'sh', '-s'], input=SCRIPT, text=True)
    receipt = {'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'pod': {'name': pod['metadata']['name'], 'uid': pod['metadata']['uid'],
                       'node': pod['spec']['nodeName'], 'imageID': status['imageID'],
                       'restartCount': status['restartCount'], 'ready': status['ready']},
               'readOnlyHostReceipt': output,
               'memoryIsolationQualified': False,
               'runtimeUnchanged': False,
               'initialContainerdPID': 954817}
    (HERE / 'healthy-driver-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt['pod']))

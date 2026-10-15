#!/usr/bin/env python3
"""Render a CPU-only cached-R580 firmware extraction proposal; never applies it."""
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parent
IMAGE = 'nvcr.io/nvidia/driver@sha256:41515698692bd5e192186e620b65717af960a66d22dbb5a06e3656575a5d9148'
FIRMWARE = '/run/nvidia/firmware-r615-canary'
SCRIPT = r'''set -euo pipefail
archive=/drivers/NVIDIA-Linux-x86_64-580.95.05.run
printf '%s  %s\n' 849ef0ef8e842b9806b2cde9f11c1303d54f1a9a769467e4e5d961b2fe1182a7 "$archive" | sha256sum -c -
# Cached makeself header508-511 emits only its embedded decoder and exits.
# Full wrapper extraction hid tar stderr and killed its parent on failure.
# List of this exact archive confirmed exactly these two regular members.
sh "$archive" --extract-decompress > /scratch/zstd
chmod 0700 /scratch/zstd
mkdir /scratch/r580
tail -n +1019 "$archive" | /scratch/zstd -d | tar --extract --file=- \
    --directory=/scratch/r580 --no-same-owner --no-same-permissions \
    firmware/gsp_tu10x.bin firmware/gsp_ga10x.bin
test ! -L /owned-firmware/nvidia
test ! -L /owned-firmware/nvidia/580.95.05
mkdir -p /owned-firmware/nvidia/580.95.05
for name in gsp_tu10x.bin gsp_ga10x.bin; do
    matches=$(find /scratch/r580 -type f -name "$name")
    test "$(printf '%s\n' "$matches" | wc -l)" -eq 1
    test -n "$matches" && test -f "$matches" && test ! -L "$matches"
    source_hash=$(sha256sum "$matches" | cut -d ' ' -f 1)
    destination=/owned-firmware/nvidia/580.95.05/$name
    if test -e "$destination" || test -L "$destination"; then
        test ! -L "$destination" && test -f "$destination"
        test "$(sha256sum "$destination" | cut -d ' ' -f 1)" = "$source_hash"
        printf 'EXISTING_MATCH %s %s\n' "$name" "$source_hash"
    else
        temporary=$destination.$POD_UID.tmp
        test ! -e "$temporary" && test ! -L "$temporary"
        cp -- "$matches" "$temporary"
        chmod 0644 "$temporary"
        ln -- "$temporary" "$destination"
        rm -- "$temporary"
        printf 'CREATED %s %s\n' "$name" "$source_hash"
    fi
done
printf 'EXTRACTION_ONLY_NO_DRIVER_INSTALL_COMPLETE\n'
'''


def proposal():
    return {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {
        'name': 'gpu2-r580-firmware-preload-v2', 'namespace': 'gpu-operator',
        'labels': {'qualification.cps/owner': 'gpu2-r580-firmware-preload'},
        'annotations': {'qualification.cps/state': 'proposal-not-applied',
                        'qualification.cps/expected-node-uid': '3336cdd5-d245-436e-b57c-2f66c6dcaa41'}},
        'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 300, 'template': {
            'metadata': {'labels': {'qualification.cps/owner': 'gpu2-r580-firmware-preload'}},
            'spec': {'nodeName': 'k3s-wk-gpu2', 'restartPolicy': 'Never',
                     'automountServiceAccountToken': False,
                     'securityContext': {'runAsUser': 0, 'runAsGroup': 0, 'seccompProfile': {'type': 'RuntimeDefault'}},
                     'containers': [{'name': 'extract-firmware-only', 'image': IMAGE,
                         'imagePullPolicy': 'Never', 'command': ['/bin/bash', '-ec'], 'args': [SCRIPT],
                         'env': [{'name': 'NVIDIA_VISIBLE_DEVICES', 'value': 'void'},
                                 {'name': 'TMPDIR', 'value': '/scratch'},
                                 {'name': 'POD_UID', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.uid'}}}],
                         'securityContext': {'privileged': False, 'allowPrivilegeEscalation': False,
                                             'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}},
                         'resources': {'requests': {'cpu': '100m', 'memory': '128Mi', 'ephemeral-storage': '1Gi'},
                                       'limits': {'cpu': '1', 'memory': '512Mi', 'ephemeral-storage': '3Gi'}},
                         'volumeMounts': [{'name': 'scratch', 'mountPath': '/scratch'},
                                          {'name': 'owned-firmware', 'mountPath': '/owned-firmware'}]}],
                     'volumes': [{'name': 'scratch', 'emptyDir': {'sizeLimit': '3Gi'}},
                                 {'name': 'owned-firmware', 'hostPath': {'path': FIRMWARE, 'type': 'Directory'}}]}}}}


if __name__ == '__main__':
    (HERE / 'r580-firmware-preload-v2-not-applied.yaml').write_text(yaml.safe_dump(proposal(), sort_keys=False))
    print('Rendered CPU-only firmware preload proposal; applied=false')

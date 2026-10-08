#!/usr/bin/env python3
"""Read-only GPU2 UVM, core, holders and runtime snapshot for root's guard test."""
import argparse
import datetime
import json
import hashlib
import struct
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
NODE_UID = '3336cdd5-d245-436e-b57c-2f66c6dcaa41'
POD_UID = 'fad28572-7be1-45c2-83d3-57392dd7acaf'
SCRIPT = r'''set -eu
uname -r
printf 'installed_module_files\n'
for module in nvidia nvidia_uvm; do
    path=$(modinfo -n "$module")
    printf 'module=%s path=%s\n' "$module" "$path"
    test -f "$path" && test ! -L "$path"
    sha256sum "$path"
    stat -c '%n %s' "$path"
    modinfo -F vermagic "$path"
    modinfo -F version "$path"
done
printf 'loaded_module_identity\n'
for module in nvidia nvidia_uvm; do
    printf 'module=%s srcversion=' "$module"
    cat "/sys/module/$module/srcversion"
    printf 'refcount='
    cat "/sys/module/$module/refcnt"
    printf 'taint='
    cat "/sys/module/$module/taint"
done
printf 'uvm_parameters\n'
for path in /sys/module/nvidia_uvm/parameters/*; do
    printf '%s=' "$path"
    cat "$path"
done
printf 'core_version\n'
cat /proc/driver/nvidia/version
printf 'core_gpu_state\n'
nvidia-smi --query-gpu=uuid,driver_version,mig.mode.current,mig.mode.pending --format=csv,noheader
printf 'critical_runtime_processes\n'
for process in /proc/[0-9]*; do
    comm=$(cat "$process/comm" 2>/dev/null) || continue
    case "$comm" in k3s-agent|k3s|containerd)
        printf 'pid=%s comm=%s start_ticks=' "${process##*/}" "$comm"
        awk '{print $22}' "$process/stat"
    ;; esac
done
'''


MODULE_PATHS = ['/lib/modules/6.8.0-134-generic/kernel/drivers/video/nvidia.ko',
                '/lib/modules/6.8.0-134-generic/kernel/drivers/video/nvidia-uvm.ko',
                '/var/tmp/cps-r615-uvm-guard-build-20261008/source/nvidia-uvm.ko']


def elf_versions(read):
    header = read(0, 64)
    assert len(header) == 64 and header[:6] == b'\x7fELF\x02\x01'
    offset = struct.unpack_from('<Q', header, 40)[0]
    entry_size, count, string_index = struct.unpack_from('<HHH', header, 58)
    assert entry_size == 64 and 0 < string_index < count < 1024
    table = read(offset, entry_size * count)
    assert len(table) == entry_size * count
    sections = [struct.unpack_from('<IIQQQQIIQQ', table, i * entry_size) for i in range(count)]
    string_section = sections[string_index]
    assert 0 < string_section[5] < 128 * 1024
    names = read(string_section[4], string_section[5])
    assert len(names) == string_section[5]
    matches = [section for section in sections
               if names[section[0]:].split(b'\0', 1)[0] == b'__versions']
    assert len(matches) == 1 and 0 < matches[0][5] < 128 * 1024
    data = read(matches[0][4], matches[0][5])
    assert len(data) == matches[0][5]
    return {'sectionBytes': len(data),
            'canonicalHexSHA256': hashlib.sha256(data.hex().encode()).hexdigest()}


def raw_sections(pod_name):
    prefix = ['kubectl', '-n', 'gpu-operator', 'exec', pod_name,
              '-c', 'nvidia-driver-ctr', '--']
    receipts = []
    for path in MODULE_PATHS:
        def read(offset, size):
            return subprocess.check_output(prefix + ['dd', 'if=' + path, 'bs=1',
                'skip=' + str(offset), 'count=' + str(size), 'status=none'])
        receipt = {'path': path, **elf_versions(read)}
        receipt['sha256'] = subprocess.check_output(prefix + ['sha256sum', path], text=True).split()[0]
        receipts.append(receipt)
    return receipts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['before', 'guard-loaded', 'original-restored'])
    arguments = parser.parse_args()
    destination = HERE / ('uvm-review-' + arguments.stage + '.json')
    if destination.exists():
        raise ValueError('Archive an earlier receipt explicitly before collecting a new stage')
    node = json.loads(subprocess.check_output(['kubectl', 'get', 'node', 'k3s-wk-gpu2', '-o', 'json']))
    assert node['metadata']['uid'] == NODE_UID
    pods = json.loads(subprocess.check_output(['kubectl', '-n', 'gpu-operator', 'get', 'pods',
                      '-l', 'app=gpu2-r615-driver-canary', '-o', 'json']))['items']
    assert len(pods) == 1
    pod = pods[0]
    assert pod['metadata']['uid'] == POD_UID and pod['spec']['nodeName'] == 'k3s-wk-gpu2'
    container = next(c for c in pod['status']['containerStatuses'] if c['name'] == 'nvidia-driver-ctr')
    outputs = []
    for script in (SCRIPT, (HERE / 'host_holders.sh').read_text()):
        outputs.append(subprocess.check_output(['kubectl', '-n', 'gpu-operator', 'exec', '-i',
                       pod['metadata']['name'], '-c', 'nvidia-driver-ctr', '--', 'sh', '-s'],
                       input=script, text=True))
    receipt = {'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'stage': arguments.stage,
               'nodeUID': node['metadata']['uid'],
               'pod': {'name': pod['metadata']['name'], 'uid': POD_UID,
                       'imageID': container['imageID'], 'ready': container['ready'],
                       'restartCount': container['restartCount']},
               'readOnlyModuleAndRuntimeReceipt': outputs[0],
               'readOnlyHolderReceipt': outputs[1],
               'rawElfVersionsSectionReceipts': raw_sections(pod['metadata']['name']),
               'tenantIsolationQualified': False}
    with destination.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'stage': arguments.stage, 'receipt': str(destination),
                      'tenantIsolationQualified': False}))

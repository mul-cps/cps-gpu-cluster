"""Read-only, UUID/minor-bound CDI validation and offline refresh proposal.

Never run CUDA/NVML, edit installed CDI or infer an NVML index is a device minor.
The approved common toolkit edits are pinned independently of selected minors.
"""
import copy
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

COMMON_SHA256 = 'a0d2763d0fe3b375260cf2604f3fb8f4363571a7d6efe1253e9c3486bf534e7e'
CDI_PATH = '/host/run/cdi/management.nvidia.com-native-pilot-r615.json'
PROC_PATH = '/host/proc/driver/nvidia/gpus'
OTHER_CDI_PINS = {
    'k8s.device-plugin.nvidia.com-gpu.json': '0058cb6ef0781012161ce35222639a127664c452352a992273226ff3ce729d73',
    'management.nvidia.com-gpu.yaml': 'bc51fe16025d67485693e7334366dca726f7e9e17bc6a5b80ba583e9d175c70f',
}
RUNTIME_PINS = {
    'var/lib/rancher/k3s/agent/etc/containerd/config.toml': 'cf9fedc8841bd35f741c0afdde70523909ce313d097b0650cea1e88bae1ecd9d',
    'usr/local/nvidia/toolkit/.config/nvidia-container-runtime/config.toml': 'eb2020d8c3bea75079f5ac524f058bf2a3ad2f1e67fdbf75bb32a449f180c1f2',
}


def require(value, message):
    if not value: raise ValueError(message)


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def valid_uuid(value):
    try: return isinstance(value, str) and value.startswith('GPU-') and str(uuid.UUID(value[4:])) == value[4:]
    except ValueError: return False


def validate_inventory(inventory):
    require(isinstance(inventory, list) and 1 <= len(inventory) <= 32, 'Complete bounded GPU inventory required')
    for row in inventory:
        require(isinstance(row, dict) and set(row) == {'gpu_uuid', 'pci_bdf', 'minor', 'device'}, 'Closed physical GPU mapping required')
        require(valid_uuid(row['gpu_uuid']) and isinstance(row['pci_bdf'], str)
            and re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]', row['pci_bdf'])
            and type(row['minor']) is int and 0 <= row['minor'] <= 255, 'Exact UUID/BDF/device minor required')
        dev = row['device']
        require(isinstance(dev, dict) and set(dev) == {'major', 'minor'}
            and type(dev['major']) is int and dev['major'] == 195
            and type(dev['minor']) is int and dev['minor'] == row['minor'], 'Actual NVIDIA GPU character device required')
    require(all(len({row[key] for row in inventory}) == len(inventory)
        for key in ('gpu_uuid', 'pci_bdf', 'minor')), 'Unique full GPU inventory required')
    return inventory


def selected_mapping(document, inventory, gpu_uuid, *, current=True):
    validate_inventory(inventory)
    require(valid_uuid(gpu_uuid), 'Canonical selected GPU UUID required')
    require(isinstance(document, dict) and set(document) == {'cdiVersion', 'kind', 'devices', 'containerEdits'}
        and document['cdiVersion'] == '0.5.0' and document['kind'] == 'management.nvidia.com/gpu', 'Exact selected CDI document required')
    require(sha(document['containerEdits']) == COMMON_SHA256, 'Unreviewed common CDI devices, hooks, mounts or environment')
    devices = document['devices']
    require(isinstance(devices, list) and len(devices) == 1 and isinstance(devices[0], dict)
        and set(devices[0]) == {'name', 'containerEdits'} and devices[0]['name'] == gpu_uuid,
        'Only the bound physical GPU may be injected')
    edits = devices[0]['containerEdits']
    require(isinstance(edits, dict) and set(edits) == {'deviceNodes'} and isinstance(edits['deviceNodes'], list)
        and len(edits['deviceNodes']) == 1, 'One selected GPU device node required')
    node = edits['deviceNodes'][0]
    require(isinstance(node, dict) and set(node) == {'path', 'hostPath'}
        and isinstance(node['path'], str) and re.fullmatch(r'/dev/nvidia(?:0|[1-9][0-9]{0,2})', node['path'])
        and node['hostPath'] == '/run/nvidia/driver' + node['path'], 'Exact trusted GPU node paths required')
    matches = [row for row in inventory if row['gpu_uuid'] == gpu_uuid]
    require(len(matches) == 1, 'Bound GPU missing from current physical inventory')
    row = matches[0]
    if current:
        require(node['path'] == '/dev/nvidia' + str(row['minor']), 'Stale CDI UUID/device minor mapping')
    return copy.deepcopy(row)


def validate_current_cdi(document, inventory, gpu_uuid):
    return selected_mapping(document, inventory, gpu_uuid)


def refresh_selected_cdi(document, inventory, gpu_uuid):
    row = selected_mapping(document, inventory, gpu_uuid, current=False)
    result = copy.deepcopy(document)
    path = '/dev/nvidia' + str(row['minor'])
    result['devices'][0]['containerEdits']['deviceNodes'] = [{'path': path, 'hostPath': '/run/nvidia/driver' + path}]
    validate_current_cdi(result, inventory, gpu_uuid)
    return result


def read_root_file(path, *, trusted_uid=0):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == trusted_uid and not info.st_mode & 0o022
            and info.st_size <= 262144, 'Protected bounded root-owned input required')
        raw = os.read(fd, 262145)
        require(len(raw) <= 262144, 'Oversized physical mapping input')
        return raw
    finally: os.close(fd)


def read_inventory(*, proc_path=PROC_PATH, host_root='/host', trusted_uid=0):
    rows = []
    root = Path(proc_path)
    for entry in sorted(root.iterdir()):
        require(entry.is_dir() and re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]', entry.name), 'Unexpected physical GPU inventory entry')
        text = read_root_file(entry / 'information', trusted_uid=trusted_uid).decode()
        fields = {}
        for line in text.splitlines():
            key, separator, value = line.partition(':')
            if key.strip() in ('GPU UUID', 'Bus Location', 'Device Minor'):
                require(separator and key.strip() not in fields, 'Duplicate physical GPU mapping field')
                fields[key.strip()] = value.strip()
        require(set(fields) == {'GPU UUID', 'Bus Location', 'Device Minor'}
            and fields['Bus Location'] == entry.name and re.fullmatch(r'(?:0|[1-9][0-9]{0,2})', fields['Device Minor']),
            'Complete current proc UUID/BDF/minor mapping required')
        minor = int(fields['Device Minor'])
        path = Path(host_root) / ('run/nvidia/driver/dev/nvidia' + str(minor))
        info = os.stat(path, follow_symlinks=False)
        require(stat.S_ISCHR(info.st_mode) and info.st_uid == trusted_uid, 'Actual root-owned NVIDIA device node required')
        rows.append({'gpu_uuid': fields['GPU UUID'], 'pci_bdf': entry.name, 'minor': minor,
            'device': {'major': os.major(info.st_rdev), 'minor': os.minor(info.st_rdev)}})
    return validate_inventory(rows)


def validate_cdi_search(*, host_root='/host', trusted_uid=0):
    """Pin actual configured CDI resolution and exclude alternate UUID providers.

    The reviewed YAML has only the separate `all` name; the reviewed device
    plugin JSON has a different kind. New files/configuration block sealing.
    """
    root = Path(host_root)
    proof = {}
    for path, expected in RUNTIME_PINS.items():
        raw = read_root_file(root / path, trusted_uid=trusted_uid)
        digest = hashlib.sha256(raw).hexdigest()
        require(digest == expected, 'Configured NVIDIA CDI resolution changed')
        proof[path] = digest
    etc = root / 'etc/cdi'
    require(not etc.exists() or not list(etc.iterdir()), 'Unreviewed alternate CDI provider')
    directory = root / 'run/cdi'
    require({entry.name for entry in directory.iterdir()} == set(OTHER_CDI_PINS)
            | {'management.nvidia.com-native-pilot-r615.json'}, 'Unexpected CDI search directory provider')
    for name, expected in OTHER_CDI_PINS.items():
        raw = read_root_file(directory / name, trusted_uid=trusted_uid)
        digest = hashlib.sha256(raw).hexdigest()
        require(digest == expected, 'Alternate CDI device definitions changed')
        proof[name] = digest
    return proof


def observe_current_cdi(gpu_uuid, *, cdi_path=CDI_PATH, proc_path=PROC_PATH, host_root='/host', trusted_uid=0):
    search = validate_cdi_search(host_root=host_root, trusted_uid=trusted_uid)
    raw = read_root_file(cdi_path, trusted_uid=trusted_uid)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate CDI JSON field')
            result[key] = value
        return result
    document = json.loads(raw, object_pairs_hook=unique)
    inventory = read_inventory(proc_path=proc_path, host_root=host_root, trusted_uid=trusted_uid)
    mapping = validate_current_cdi(document, inventory, gpu_uuid)
    return {'cdi_sha256': hashlib.sha256(raw).hexdigest(), 'mapping': mapping, 'inventory': inventory,
            'search': search}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal', action='store_true')
    parser.add_argument('--document', type=Path)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--gpu-uuid')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if not args.proposal:
        print(json.dumps({'state': 'inert', 'api_calls': False, 'gpu_calls': False, 'installed_cdi_changed': False}))
        return
    require(all((args.document, args.inventory, args.gpu_uuid, args.output)), 'Explicit captured inputs/output required')
    document = json.loads(args.document.read_bytes())
    inventory = json.loads(args.inventory.read_bytes())
    result = refresh_selected_cdi(document, inventory, args.gpu_uuid)
    raw = json.dumps(result, sort_keys=True, separators=(',', ':')).encode() + b'\n'
    with args.output.open('xb') as stream: stream.write(raw)
    print(json.dumps({'state': 'proposal', 'old_cdi_sha256': hashlib.sha256(args.document.read_bytes()).hexdigest(),
        'new_cdi_sha256': hashlib.sha256(raw).hexdigest(), 'inventory_sha256': sha(inventory),
        'mapping': validate_current_cdi(result, inventory, args.gpu_uuid), 'installed_cdi_changed': False}))


if __name__ == '__main__': main()

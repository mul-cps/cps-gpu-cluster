# Distinct-process VMM / POSIX-FD qualification

This bounded harness reuses the reviewed `vmm-cross-parent-diagnostic` endpoint,
Root one-FD bridge and kernel witness. It fixes the observed inherited-setgid
failure by explicitly chmodding **only successfully newly created** source and
socket directories to0700. Existing directories still fail; strict Root0700
attribution is unchanged. No old workload Pod UID is executable configuration.

Both actual directions passed on 17 October 2026; see [results](results/).
Independent offline replay verified the same actual FD in positive/cross transfers,
positive import/readback, CUDA800 denial with exact kernel correlation, continued
kernels, cleanup and unchanged sealed authorities. Both normal Stops completed;
all 106 native allocations were released and Gateway reservation tables empty.
Personal notebook Pod UIDs were preserved, temporary grant expiries restored and
the test token revoked. Raw event/witness logs remain private.

This is a bounded 5/5 GiB VMM/POSIX-FD result. Broad isolation and production flags
remain false. Default invocation is inert, including no manifest reads/API calls
or NVML initialization. CPU tests alone do not qualify isolation.

## Current pinned scope

Two normally approved, already running CPS (`jupyterhub`)5GiB workspaces on
`k3s-wk-gpu2`; notebook916786..., packaged node6083..., policyd48..., GPU
`GPU-16128952-b438-556a-00bb-93039ee24e56`, boot209f8bc9..., driver generation
b10498fc.... These are qualification pins, not discovery defaults. Other epochs
or images must be separately reviewed. No MIG/driver/cap/ledger mutation occurs.
The adapter reads actual sealed journals, exact native receipts, full admitted
Pod spec hashes, parent inode/device and finite native limits twice. It uses
`Nvml.get`, never a setter. All process Pods are re-read after each observation.

Create a private0600 target manifest from the **new** actual normal Starts:

```json
{"pods":{"a":{"namespace":"jupyterhub","name":"ACTUAL_NAME_A","uid":"ACTUAL_UID_A","cap_mib":5120},"b":{"namespace":"jupyterhub","name":"ACTUAL_NAME_B","uid":"ACTUAL_UID_B","cap_mib":5120}},"node":{"namespace":"cps-native-system","name":"ACTUAL_NODE_POD","uid":"ACTUAL_NODE_UID"},"observer":{"namespace":"gpu-operator","name":"cps-native-driver-control","uid":"ACTUAL_OBSERVER_UID"}}
```

Resolve the names/UIDs with read-only `kubectl get pod ... -o json`, preserve
that actual evidence, then independently review manifest SHA256. The local
file must be regular, owned, single-link0600; Root receives the identical bytes
as0400. Keys a/b are explicitly ordered independently of JSON insertion order.

## Root staging (operator action; does not run CUDA)

Set `D` to this committed directory, `TARGETS` to the reviewed manifest, and
`OBSERVER` to its actual observer name. Use the existing reviewed observer
transport; the following streams only hash-checked source bytes into the two
fixed operator source directories. It refuses existing differing files; no
production code/configuration is replaced. Root must first review the sources
and exact hashes rather than trust a generated manifest as authorization.

```bash
python -B - "$D" "$TARGETS" <<'PY' | kubectl -n gpu-operator exec -i "$OBSERVER" -c control -- nsenter -t 1 -m -u -i -n -p -- /usr/bin/python3.12 -c '
import sys,json,base64,hashlib,os,stat
from pathlib import Path
assert os.getuid()==os.geteuid()==os.getgid()==os.getegid()==0
packet=json.load(sys.stdin)
allowed={"/run/cps-native-gpu/operator/native-vmm-distinct-process-20261017":{"vmm_bridge.py","vmm_endpoint.py","targets.json"},"/run/cps-native-gpu/operator/vmm-kmsg-witness":{"kernel_witness_collector.py","kernel_witness_validator.py"}}
assert set(packet)==set(allowed)
for directory,files in packet.items():
 assert set(files)==allowed[directory]
 root=Path(directory)
 if not root.exists():root.mkdir(mode=0o700)
 info=root.lstat();assert stat.S_ISDIR(info.st_mode) and info.st_uid==info.st_gid==0 and stat.S_IMODE(info.st_mode)==0o700
 for name,entry in files.items():
  raw=base64.b64decode(entry["base64"],validate=True);assert 0<len(raw)<=100000 and hashlib.sha256(raw).hexdigest()==entry["sha256"]
  path=root/name
  if path.exists():
   info=path.lstat();assert stat.S_ISREG(info.st_mode) and info.st_uid==info.st_gid==0 and stat.S_IMODE(info.st_mode)==0o400 and info.st_nlink==1 and path.read_bytes()==raw
  else:
   fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
   with os.fdopen(fd,"wb")as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
 for name in (["bridge-sessions"]if "distinct-process" in directory else ["sessions"]):
  path=root/name
  if not path.exists():path.mkdir(mode=0o700)
  info=path.lstat();assert stat.S_ISDIR(info.st_mode) and info.st_uid==info.st_gid==0 and stat.S_IMODE(info.st_mode)==0o700
 fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);os.fsync(fd);os.close(fd)
print(json.dumps({"state":"sources-staged","gpu_calls":False}))
'
import sys,json,base64,hashlib
from pathlib import Path
root=Path(sys.argv[1]);targets=Path(sys.argv[2]);packet={}
for directory,names in {
 '/run/cps-native-gpu/operator/native-vmm-distinct-process-20261017':['vmm_bridge.py','vmm_endpoint.py','targets.json'],
 '/run/cps-native-gpu/operator/vmm-kmsg-witness':['kernel_witness_collector.py','kernel_witness_validator.py']}.items():
 packet[directory]={}
 for name in names:
  raw=(targets if name=='targets.json'else root/name).read_bytes()
  packet[directory][name]={'base64':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest()}
print(json.dumps(packet))
PY
```

If the fixed witness directory contains different bytes, STOP for review; do
not delete or overwrite it. Keep earlier witness sessions as evidence.

## Execute after source/manifest review

Run as the local operator, with `OUT_PARENT` an existing owned0700 directory.
Choose one direction per run. Shell substitutions below are file SHA256 values,
not tokens. Both directions are needed for the pair gate.

```bash
python -B "$D/run_vmm_cross_parent.py" --execute \
 --targets "$TARGETS" --targets-sha256 "$(sha256sum "$TARGETS" | cut -d' ' -f1)" \
 --observer-pod-uid "$ACTUAL_OBSERVER_UID" --direction a-to-b \
 --output "$OUT_PARENT/a-to-b" \
 --preflight-source-sha256 "$(sha256sum "$D/current_preflight.py" | cut -d' ' -f1)" \
 --wrapper-source-sha256 "$(sha256sum "$D/run_vmm_cross_parent.py" | cut -d' ' -f1)" \
 --endpoint-source-sha256 "$(sha256sum "$D/vmm_endpoint.py" | cut -d' ' -f1)" \
 --bridge-source-sha256 "$(sha256sum "$D/vmm_bridge.py" | cut -d' ' -f1)" \
 --witness-collector-sha256 "$(sha256sum "$D/kernel_witness_collector.py" | cut -d' ' -f1)" \
 --witness-validator-sha256 "$(sha256sum "$D/kernel_witness_validator.py" | cut -d' ' -f1)" \
 --witness-transport-sha256 "$(sha256sum "$D/kernel_witness_transport.py" | cut -d' ' -f1)"
```

Repeat with `--direction b-to-a --output "$OUT_PARENT/b-to-a"` using the same
still-current manifest. Do not rerun a failed direction blindly. Preserve
inconclusive receipts and resolve remote cleanup before proceeding.

Each trial exports one64MiB VMM allocation as a POSIX FD, forwards the same
actual FD first to a distinct-process same-parent importer (must succeed and
read19), then to the other capped parent (must return800). Unexpected cross
import success is **never mapped or touched**. Independent importer kernels,
exporter continuity and recovery, exact Root process/FD attribution, bounded
kernel witness (reason6/status27), all three explicit cleanups and final
unchanged native authority/charge checks are mandatory. A missing positive,
witness, cleanup or final proof is inconclusive, not successful isolation.
All broader production/full-isolation flags remainfalse even after this gate.

## CPU verification

```bash
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s "$D" -p 'test_*.py' -q
python -B "$D/run_vmm_cross_parent.py"
python -B "$D/vmm_bridge.py"
```

Copied protocol tests remain synthetic and use fixed fixture-only UIDs. Source
ancestry is the private reviewed diagnostic identified above; no private data,
credential, live target UID or previous run result is included.

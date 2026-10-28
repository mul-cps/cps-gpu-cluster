# Native shared MPS host attribution capture

`collect_host_attribution.py` is a read-only, host-side capture for a bounded
MPS workload. It records the MPS server/client PID lists, server status,
`nvidia-smi` PID-to-GPU UUID mapping, and each server/client process's UID/GID,
namespace PID list, cgroup, and `/proc` start time. It reads each process start
time before and after collecting the remaining fields and fails if the PID was
reused during the capture. It requires MPS server PIDs to appear in
`nvidia-smi`; MPS client PIDs may be absent there, since MPS can report device
work under the server. Missing client rows are retained as empty per-process
GPU mappings and must be resolved from the MPS server plus workload-side GPU
receipts by the offline verifier.

Run it on the GPU node while the reviewed hold is active, with permissions to
read those host processes and query the existing MPS control pipe:

```sh
python3 collect_host_attribution.py \
  --run-id <reviewed-run-id> \
  --mps-pipe-dir /run/nvidia/mps/nvidia.com/gpu/pipe \
  --output /path/on/private-evidence-storage/host-attribution.json
```

The output path must not already exist. The collector creates the evidence
file with mode `0600` and its directory with mode `0700`. Save it outside Git.
The collector does not launch a workload, execute a Kubernetes command, change
an MPS setting, or stop a process. A successful capture is not qualification:
the verifier must match the cgroup's Pod UID and container ID to independently
reviewed Pod/container records, compare namespace PIDs to workload logs, check
GPU UUID and image/runtime identities, and validate that the snapshot overlaps
the hold interval. `attributionQualified` therefore remains false.

The capture does **not** query NVML used-memory bytes and does not calculate
per-Pod GPU memory. It records PID-to-GPU UUID rows only; those rows do not
attribute memory to a Pod.

The earlier `dyn071552c` observer used this same evidence chain through the GPU
operator daemon's `/proc` and `nvidia-smi` views. Its receipt observed three
clients and exact cgroup/namespace-PID mappings, but its helper was coupled to
Kubernetes API credentials and reviewed artifacts, and final log/ConfigMap
capture and strict evaluation remained incomplete. This host capture removes
that API coupling from volatile process attribution; it does not close those
remaining verification gates.

Offline parser checks:

```sh
python3 -m unittest discover -s . -p 'test_collect_host_attribution.py' -v
```

No live GPU collection is run by these tests.

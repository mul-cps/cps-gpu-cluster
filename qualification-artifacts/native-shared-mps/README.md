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

## Same-Pod aggregate-cap evidence

`same_pod_probe.py` runs two independent CUDA client processes from a single
Pod. The survivor holds one allocation and continuously launches a small CUDA
work kernel. The challenger requests an allocation that fits below the cap by
itself but makes the combined allocations exceed the cap, requires CUDA OOM,
then allocates a smaller recovery buffer while the survivor keeps progressing.
It does not start or configure MPS, query Kubernetes, or make any cluster
changes. The parent avoids initializing CUDA so the host collector should see
exactly the two test client PIDs. Run only from an isolated, reviewed Pod whose
GPU memory cap is already configured. Example 5 GiB test:

```sh
python3 same_pod_probe.py \
  --run-id <reviewed-run-id> --pod-uid "$POD_UID" \
  --cap-bytes 5368709120 \
  --survivor-bytes 3221225472 --challenger-bytes 3221225472 \
  --recovery-bytes 134217728 \
  --output /private/evidence/workload-receipt.json
```

The MPS pipe directory must already be mounted and named by
`CUDA_MPS_PIPE_DIRECTORY`. The probe writes a mode-0600 JSON receipt with
`O_EXCL`, so it will not overwrite prior evidence. It bounds child startup to
120 seconds and keeps both CUDA clients alive for 30 seconds after recovery by
default, allowing the host-side collector to run while both PIDs are present.
Start the probe in one terminal; when it reports the recovery hold is active,
run the host collector from a second terminal during that window.

`verify_same_pod.py` checks an offline evidence bundle for that bounded test
and requires three independently captured JSON files:

* `--capture`: output from `collect_host_attribution.py`; one MPS server must
  report exactly two distinct client PIDs, whose host cgroup records both
  match the reviewed container cgroup. The MPS server must be visible on the
  expected GPU UUID.
* `--pod-receipt`: reviewed `runId`, `podUid`, `containerId` (including its
  runtime prefix), exact host `cgroup`, `gpuUuid`, and `gpuMemoryCapBytes` from
  the live GPU cap readback, plus non-empty `gpuMemoryCapEvidence`. The pod UID
  and container ID must be identifiable in the cgroup path. Host RAM cgroup
  limits are not GPU VRAM limits and must not be used here.
* `--workload-receipt`: the probe output with `runId`, `podUid`,
  `probeSucceeded: true`, `capBytes`, plus `survivor` (`namespacePid`,
  `heldBytes`, `progressBefore`, `progressAfter`) and `challenger`
  (`namespacePid`, `overCapRequestedBytes`, `overCapRejected`, `recoveryBytes`,
  `recoverySucceeded`), `holdStartedAt`, and `holdFinishedAt`. Host and pod
  clocks must be synchronized; the verifier requires the host capture interval
  to overlap the live two-client hold. Namespace PIDs must map one-to-one to
  the two host-captured MPS clients. The survivor and challenger allocations must each
  fit under the cap alone but exceed it in aggregate; the recovery allocation
  must fit alongside the survivor.

Example, after capturing and reviewing those files outside Git:

```sh
python3 verify_same_pod.py \
  --capture /private/evidence/host-attribution.json \
  --pod-receipt /private/evidence/pod-receipt.json \
  --workload-receipt /private/evidence/workload-receipt.json \
  --expected-cap-bytes 5368709120
```

The verifier rejects identity/cgroup/cap mismatches, fewer than two clients,
missing over-cap rejection or recovery, and a survivor that made no progress.
Its output always says `productionQualified: false`: one successful aggregate
test is only a focused qualification result, not the whole production gate.

### Qualification Pod cleanup

After the reviewed test completes, remove its exact Pod with the guarded
entrypoint. First capture the Pod UID from the intended namespace, then pass
that value to the helper:

```sh
POD_UID=$(kubectl get pod <pod-name> --namespace <namespace> -o jsonpath='{.metadata.uid}')
python3 cleanup_test_pod.py \
  --namespace <namespace> --pod <pod-name> --expected-uid "$POD_UID"
```

The helper reads the live Pod and refuses if its UID differs, then deletes it
with a Kubernetes UID precondition to close the replacement race. Cleanup is
limited to that Pod API object. Keep native controller state, retirement
journals, receipts, and evidence directories intact; do not remove a cohort
`state/` directory as part of workload cleanup. The protected journals are
needed to validate later cap-inventory changes, even after a test workload has
been retired.

Offline tests:

```sh
python3 -m unittest discover \
  -s qualification-artifacts/native-shared-mps -p 'test_*.py' -v
```

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

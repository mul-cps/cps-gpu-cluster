# Metrics cold-boot race: supported configuration candidate

Status: diagnosis and bounded configuration fixtures PASS; production configuration has **not** been changed. A subsequent real cold boot with the gate installed is still required. GPU2 remains fenced. The earlier finite per-Pod metrics qualification remains historical evidence; this boot's production metrics collector is unhealthy despite its HTTP probes passing.

## Reproduced cause

GPU2 boot ID: `ebcc5553-3251-43f7-95f2-236e5e3e6b70`. Stock Fractioning v0.1.9, final c3b driver and derived 6ce K3s outer artifact were present. All times below are UTC on 2026-11-16.

| Witness | Time / result |
| --- | --- |
| metricsd container runtime | 20:58:46: NVIDIA modules not loaded; wrapper invokes plain `runc` |
| metricsd | 20:58:46: `initialize NVML: ERROR_LIBRARY_NOT_FOUND`; selects permanent `NoopCollector` |
| GPU Operator driver validation | `driver-ready` written at 21:00:07.446903087 |
| toolkit validation | `toolkit-ready` written at 21:00:24.648697717 |
| Production Pod | Fractiond and metricsd report Ready, but metricsd never retries collector construction |

See `metricsd-current.log`, `runtime-wrapper-and-marker.txt`, `driver-validation.log`, `toolkit-validation.log`, and the retained Pod/DaemonSet JSON. The runtime wrapper skips NVIDIA injection before the module is loaded; starting a collector too early therefore loses both the library injection and the one-time NVML initialization. A retry-only application change would not reliably repair missing container mounts.

The latest released upstream Fractioning checked was [v0.1.9](https://github.com/kai-scheduler/gpu-fractioning/releases/tag/v0.1.9), published 2026-11-11. The collector and CRD type files are identical between that tag (`fb75540adca3392ab4b51d03e6c0da9b393fa842`) and inspected main (`c3d87f00259f6311d0457865e6186367d8154ca3`). There is no newer released fix in the retrieved release list. `upstream-releases.json` and `preparation-proof.json` retain release/source identities.

## Smallest supported configuration

`proposed-source.patch` changes only the Fleet-owned GpuFractioningConfig at `cluster-maintenance/clusters/cit-cps-gpu/system/gpu/gpu-fractioning/resources.yaml`. It adds one supported `metricsAgent.volumes` HostPath of **type File**, and one read-only `metricsAgent.volumeMounts` entry, for `/run/nvidia/validations/driver-ready`. It preserves every other manifest and spec field. Existing live volume/mount lists are absent; the preparation preserves the existing metricsAgent settings. If other volume/mount entries are introduced before application, append rather than replace them.

`proposed-config-merge-patch.json` is the equivalent API patch; `proposed-spec.diff` shows its narrow semantic scope. The installed CRD supports both fields, but does not expose initContainers, a custom Pod template, command overrides or probe overrides. Stock Fractioning appends these volumes to its Pod and mounts only the requested sidecar path. Kubelet waits for all Pod volumes before starting containers, so the marker gates the whole fractiond/metricsd Pod.

**Do not change the type to FileOrCreate:** that would manufacture the readiness witness. The root-owned file is not modified or read by metricsd; its existence and file type are checked by kubelet. No driver/runtime/application fork is needed for this candidate.

Validation already performed:

- `git apply --check proposed-source.patch`: PASS.
- YAML semantic comparison: only the specified GpuFractioningConfig metricsAgent additions; every other document unchanged.
- `kubectl patch gpufractioningconfig default --type=merge --patch-file proposed-config-merge-patch.json --dry-run=server -o json`: PASS; returned spec equals exactly the expected original plus additions. Output retained as `server-dryrun-config.json`.

## Readiness ownership and upgrade limits

The node's `/run` is tmpfs, so the marker cannot survive a cold boot. The actual installed validator image is **v25.10.0**, although the GPU Operator manager is v26.7.1. Its driver validator deletes an existing driver-ready file, validates the driver container and driver-library paths, successfully runs nvidia-smi with the located NVML library, creates device-character links, then writes driver-ready through a temporary file and atomic rename. The validator Pod's preStop deletes `*-ready` markers. The marker was root-owned, mode 0600, throughout both probes.

This is a **startup ordering gate**, not a continuous health monitor. During supported GPU Operator upgrades, stock Fractioning uses `nvidia.com/gpu.deploy.client=true` plus driver-upgrade affinity, so daemons are drained before driver unload and scheduled after completion. Marker deletion/revalidation is additional ordering. A stale marker during an out-of-band driver replacement, or driver loss after container creation, is not detected by this file gate; those cases must keep the existing maintenance/drain procedure. No supported in-place upgrade was performed by this task.

Primary source locations:

- [Fractioning collector, lines 269–282](https://github.com/kai-scheduler/gpu-fractioning/blob/v0.1.9/fractioning-manager/metricsd/internal/metrics/nvml_collector.go#L269-L282): one-time NoopCollector fallback.
- [Fractioning sidecar construction](https://github.com/kai-scheduler/gpu-fractioning/blob/v0.1.9/operator/internal/fractioningmanager/components/fractiond/fractiond.go#L159-L165): configured Pod volumes; configured mounts are appended in buildMetricsdContainer.
- [Exporter health handler](https://github.com/kai-scheduler/gpu-fractioning/blob/v0.1.9/fractioning-manager/metricsd/internal/metrics/exporter.go#L35-L38): HTTP 200 independently of NVML.
- [Installed validator driver validation](https://github.com/NVIDIA/gpu-operator/blob/v25.10.0/cmd/nvidia-validator/main.go#L733-L845) and [atomic marker write](https://github.com/NVIDIA/gpu-operator/blob/v25.10.0/cmd/nvidia-validator/main.go#L897-L915).
- [Installed validator lifecycle and volume](https://github.com/NVIDIA/gpu-operator/blob/v25.10.0/assets/state-operator-validation/0500_daemonset.yaml#L169-L187).
- [Stock Fractioning driver upgrade coordination](https://github.com/kai-scheduler/gpu-fractioning/blob/v0.1.9/README.md#L297-L304).
- Actual K3s vendored Kubernetes `pkg/kubelet/kubelet.go:2071` waits for mounts before container synchronization; `pkg/volume/hostpath/host_path.go:479` rejects a missing HostPath File. The live negative fixture demonstrates these semantics on the installed binary.

## Authorized bounded configuration fixtures

`check_hostpath_gate.py` created only two owned CPU-only Pods on fenced GPU2. Both use the pinned raw Python image, runtimeClass nvidia, utility-only NVIDIA capability, no GPU resource request, no service account token, a 90-second active deadline, non-root UID/GID 1000, RuntimeDefault seccomp, all capabilities dropped and no escalation. They make **zero CUDA calls**. The positive process uses only read-only NVML initialization/device UUID enumeration, then shuts NVML down and exits.

- Missing unique path `/run/nvidia/validations/cps-metrics-gate-missing-20261116`: observed kubelet FailedMount `is not a file`, with no containerID/running/terminated state. See `absent-events.json`, `absent-final.json`.
- Existing production marker: CPU process succeeded, NVML initialized and enumerated exactly `GPU-16128952-b438-556a-00bb-93039ee24e56` and `GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6`. See `present-latest.json`, `present.log`.
- Both Pods were normally deleted using exact UID preconditions; no force deletion. `cleanup-verification.json` confirms neither remains. Marker inode/size/mtime/owner/mode were unchanged; the negative path remained absent. See `gate-fixture-summary.json`, `marker-stat-before.txt`, `marker-stat-after.txt` and per-Pod deletion responses.

These fixtures prove configuration acceptance and kubelet ordering behavior. They do not claim the production cold-boot race is fixed. Parent/root owns applying the reviewed Fleet change and the next cold boot, then must retain marker-before-container timing, successful production `NVML initialized; GPU process metrics enabled`, healthy Prometheus targets and a bounded real-usage observation. Existing NRI/driver identity and fences must remain unchanged.


## Root-applied rollout (after preparation)

Root reviewed and committed the unchanged source patch as `b38e8eba`, then applied the Fleet root pin. This observer made no production mutations. Retained `rollout/` evidence confirms generation 2 with the intended File volume and read-only mount. New fractiond Pod `gpu-fractioning-fractiond-p57lq`, UID `9e2e3161-2b79-43d9-89cd-f959e107abc1`, started both containers at 21:12:19Z with restartCount 0. Stock metricsd logged `NVML initialized; GPU process metrics enabled` at 21:12:19.914970395Z. MPS Pod `gpu-fractioning-mpsd-2q2wm`, UID `9a73fb96-8018-40a2-bbd6-642fa79ad322`, remained Ready and unchanged (restartCount 4 from the preceding cold boot). GpuFractioningConfig became AllComponentsReady at 21:12:31Z and Fleet Ready 1/1 at 21:12:36Z. Both Prometheus targets were subsequently UP.

`observe_coldboot.py` starts a bounded 900-second read-only capture in `final-coldboot/`. It reads host boot ID, marker inode/mtime_ns/owner/mode, module presence and the exact runtime wrapper; dynamic fractiond/MPS Pod identities/container start times; current metricsd logs; raw GPU metrics; GpuFractioningConfig/Fleet state; and the stock Prometheus targets and series. Each read has a timeout; expected host/Pod unavailability is retained rather than retried without a bound. Root alone owns the VM power cycle and node fences. The capture launches no processes in workload containers and creates no cluster objects.


## Actual final cold boot: ordering PASS

Root performed the single additional VM cold boot; new boot ID is `8874dcda-ced2-4aa4-b5cb-71a0871abdd5`. No manual metricsd restart was used. `final-coldboot/ordering-summary.json` retains the result and exact current container identities.

The observer first saw the new boot at 21:21:36Z and retained 15 observations with no driver-ready marker. The old fractiond/metricsd containers were terminated and no new-boot container ran during those observations. Production kubelet events explicitly show the File gate rejecting the absent marker (`FailedMount`, first 21:21:38Z, last 21:22:44Z, count 8).

Both stock GPU Operator driver validators use the same installed v25.10.0 binary and write the same marker. The operator-validator init completed first and atomically wrote marker inode 6213 at **21:23:08.536923440Z**. The toolkit Pod's driver-validation init completed second and replaced it with inode 6277 at **21:23:13.456920254Z**. `all-driver-validation-statuses.json` and the host observations retain both versions and writer completion times. Both markers were root-owned mode 0600. The new marker/inodes and observed absence demonstrate that the previous boot's marker was not reused.

The same fractiond Pod UID `9e2e3161-2b79-43d9-89cd-f959e107abc1` then started its first new-boot fractiond and metricsd containers at **21:23:30Z**, restartCount 1 each (the cold boot). Stock metricsd successfully initialized NVML at **21:23:30.604580821Z**. Current logs contain neither the plain-runc fallback nor a NoopCollector warning. The actual runtime wrapper and its SHA256 are retained in every successful host observation. The MPS Pod retained UID `9a73fb96-8018-40a2-bbd6-642fa79ad322` and became Ready after its normal startup retries; its independent ungated startup reached restartCount 9.

GpuFractioningConfig and Fleet were both Ready after recovery. Both stock Prometheus targets were UP with empty lastError, including new metricsd endpoint `10.42.7.231:2112`. Raw metrics reads succeeded. This establishes production boot ordering and collector recovery on the final artifacts. It does not yet establish real workspace GPU usage attribution on this boot; that remains a separate observation when the authorized workspace runs.

The bounded observer finished normally at 2026-11-16T21:28:51.256231+00:00 after 118 observations. The 54 observations from 2026-11-16T21:23:40.480394+00:00 through 2026-11-16T21:28:47.214274+00:00 had zero read errors and unchanged postboot container restart counts. Both final targets remained UP with empty lastError. Expected boot-outage/read-before-container-start errors remain in the raw capture; they are not hidden. No workspace GPU series with a pod_uuid appeared during this window. `final-summary.json` contains the finite capture counts and coverage limitation.

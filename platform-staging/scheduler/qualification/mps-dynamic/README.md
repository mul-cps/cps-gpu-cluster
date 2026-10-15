# Dynamic MPS maintenance candidate

Status: **offline, disabled, not executed**. No GPU profile becomes enabled by
preparing or reviewing this candidate. `plan.py` has no process, Kubernetes, SSH,
network, CUDA, or driver execution. It emits one operation for a separate root
executor to review and perform. Tests use synthetic receipts; they are not GPU
qualification evidence.

The candidate temporarily raises the existing GPU2 MPS server's per-client memory
ceiling to `40960M` on its two inventoried A100s. It optionally raises that
server's active-thread ceiling to `100`. Defaults, controller configuration,
DaemonSet, device plugin, GPU compute modes, and GPU1 stay unchanged. The trusted
HAMi workspace cache remains responsible for the 5/10/20 GiB aggregate budgets.
A larger MPS ceiling does not qualify those budgets or their packing overhead.

The active-server commands affect clients created subsequently. Existing clients
retain their settings. Default commands affect later servers and are deliberately
absent from this candidate. Client-side MPS limits can reduce a server ceiling;
they cannot enlarge it. An active-thread percentage is an available execution
limit, not a reservation or guaranteed proportional throughput. See NVIDIA's
[legacy interface](https://docs.nvidia.com/deploy/mps/latest/mpsv2-interface.html)
and [client environment reference](https://docs.nvidia.com/deploy/mps/latest/appendix-environment-variables.html).

The existing five-second wrapper only reasserts compute mode. Device-plugin
`v0.18.0` sets memory/thread defaults at startup and restarts its daemon on
SIGHUP. Do not change its ConfigMap, send signals, replace its Pod, or roll its
DaemonSet for this experiment. Primary implementation:
[startup defaults](https://github.com/NVIDIA/k8s-device-plugin/blob/v0.18.0/cmd/mps-control-daemon/mps/daemon.go#L106-L122),
[SIGHUP handling](https://github.com/NVIDIA/k8s-device-plugin/blob/v0.18.0/cmd/mps-control-daemon/main.go#L127-L143).

## Reviewed reference, not fresh authorization

Root recorded these read-only observations on 2026-10-07:

- `dynamic-runtime-mps/readonly-server-identity.json`, 15:05:11 UTC.
- `dynamic-runtime-mps/process-details.json`, 15:05:49 UTC.
- `dynamic-runtime-mps/protected-hub-process-identity.json`, 15:17:34 UTC.

All reside beneath `/home/bjoern/cps-platform-evidence/2026-10-07/`, outside Git.
The server is PID `3166883`, start tick `792169718`, UID `10001`, GID `0`.
The controller is root PID `1260846`, command `nvidia-cuda-mps-control -d`, with
no multiuser option. Both active memory ceilings and defaults were `5G`;
active/default thread ceilings were `12.0`. GPU2 node UID and daemon UID are
pinned in `plan.py`, as are its image digest, container identities, and two GPU
UUIDs. The protected Hub process is UID `1000`, GID `100` on GPU1.

The reference files do not contain all Kubernetes resource versions, staged
qualification Pods, or a current workload inventory. Root must collect those
before preparing a candidate. A reference timestamp or old idle observation
cannot authorize a current change.

## Operator sequence

1. Choose the runtime UID decision described in [UID_COMPATIBILITY.md](UID_COMPATIBILITY.md).
   This exact candidate permits only the current server's UID `10001`. A new
   UID 1000 server requires new identity receipts and a separately reviewed
   candidate; do not edit a PID argument or automatically reapply settings.
2. Root stages the three controlled 5/10/20 GiB Pods through KAI while their
   main containers remain behind CPU-only initialization gates. Verify actual
   KAI-owned device-selection ConfigMaps and the same physical GPU for all
   three. Verify image and source digests, Job/Pod UIDs, main not started,
   actual process UID, and bounded Job deadlines. Do not force GPU selection.
3. Capture the normalized observation below. Include all running and already
   bound pending GPU Pods and all GPU processes; exclude only the exact reviewed
   gated qualification generations. Prepare the locked candidate.
4. Root reviews the full candidate, receipt hashes, optional thread change, and
   rollback. Its explicit review receipt names the candidate hash and every
   step. The review window is at most 180 seconds.
5. Unlock and execute `cordon` with node UID/current resource-version tests. This does
   not drain or evict existing workloads. All test Pods must already be staged;
   do not add an unschedulable toleration or bind new test Pods afterward. Root
   must confirm KAI respects the scheduling fence and no unrelated GPU starts
   are already in flight. Record the resulting node resource version.
6. For each active-server command, root collects another observation at most
   15 seconds old, unlocks exactly that step, rechecks all identity fences at
   the execution boundary, sends the command, then captures its readback.
   The transport is the exact GPU2 daemon Pod/container and
   `CUDA_MPS_PIPE_DIRECTORY=/mps/nvidia.com/gpu/pipe`. The output contains the
   Pod UID/RV and server PID/start-time/UID fences; root must enforce them.
   Kubernetes exec itself does not provide a UID/RV compare-and-swap, so the
   renderer does not claim an atomic exec guarantee.
7. Root releases only the already reviewed CPU gates after temporary ceilings
   match. Enforce the remaining deadline with a root monotonic-clock watchdog, not just this
   offline renderer. Capture actual client PIDs, process UIDs, physical GPU
   UUIDs, canonical HAMi quotas, independent workspace cache inodes, and
   5/10/20 budget/recovery cases. Keep protected GPU1 receipts before/after.
8. Synchronize outstanding CUDA work and confirm every controlled client has
   exited. Inspect both client lists and GPU inventory before restoring any
   ceiling. Failed/finished Pods alone do not establish this.
9. Restore original active ceilings, verify every readback, then restore the
   original node scheduling state/field presence. If the node was already
   cordoned, leave it cordoned. Defaults remain exactly unchanged.

The ordinary forward order is cordon, both memory changes, optional thread
change, qualification, optional thread restore, both memory restores, node
restore. Guarded rollback is also available after any partial prefix, even
after the 180-second deadline. Once rollback starts, forward steps are refused.
Lowering a ceiling does not reduce the allowance of an existing client, so all
clients must exit first. A replacement server, FAULT state, changed controller,
unready node, changed scheduling state, new workload, changed protected Pod,
or changed daemon/protected Pod resource version stops
the procedure for operator recovery. There is no restart, kill, drain,
replacement-server retry, or automatic reapplication path in this code.

## Observation schema

Root supplies JSON from actual read-only API/process/control observations. All
keys below are required; shorthand values here are explanatory placeholders.
The collector must obtain resource versions directly from API objects, parse
`/proc/PID/stat` field22 after the parenthesized command, and retain raw receipts.

```json
{
  "observedAt": "CURRENT UTC ISO TIMESTAMP",
  "node": {"name":"k3s-wk-gpu2","uid":"REVIEWED UID","resourceVersion":"API RV",
           "ready":true,"unschedulable":false,"unschedulablePresent":false},
  "daemon": {"namespace":"gpu-operator","name":"REVIEWED POD","uid":"REVIEWED UID",
             "resourceVersion":"API RV","nodeName":"k3s-wk-gpu2","phase":"Running",
             "containerStatuses":["EXACT normalized daemonStatuses FROM reference"]},
  "protected": {"namespace":"jupyterhub","name":"jupyter-bjoern","uid":"REVIEWED UID",
                "resourceVersion":"API RV","nodeName":"k3s-wk-gpu1","phase":"Running","restarts":0},
  "server": {"pid":3166883,"startTimeTicks":792169718,"uid":10001,"status":"ACTIVE","clients":[],
             "deviceMemoryLimits":{"GPU UUID0":"5G","GPU UUID1":"5G"},"activeThreadPercentage":"12.0"},
  "control": {"pid":1260846,"uid":0,"command":["nvidia-cuda-mps-control","-d"]},
  "defaults": {"deviceMemoryLimits":{"0":"5G","1":"5G"},"activeThreadPercentage":"12.0"},
  "gpus": [{"index":0,"uuid":"GPU UUID0","totalMiB":40960,"usedMiB":45,
            "migCurrent":"Disabled","migPending":"Disabled","computeMode":"Default"},
           {"index":1,"uuid":"GPU UUID1","totalMiB":40960,"usedMiB":45,
            "migCurrent":"Disabled","migPending":"Disabled","computeMode":"Default"}],
  "gpuProcesses": [{"gpuUuid":"GPU UUID0","pid":3166883,"uid":10001},
                   {"gpuUuid":"GPU UUID1","pid":3166883,"uid":10001}],
  "unexpectedGpuPods": [],
  "stagedPods": [{"namespace":"cps-gpu-qualification","name":"POD NAME","uid":"POD UID",
                  "jobUid":"OWNER JOB UID","resourceVersion":"API RV","nodeName":"k3s-wk-gpu2",
                  "runId":"REVIEWED RUN ID","gpuUuid":"ACTUAL KAI DEVICE UUID","memoryMiB":5120,
                  "processUid":10001,"image":"APPROVED IMAGE@sha256:DIGEST","probeSha256":"SOURCE HASH",
                  "gateRunning":true,"mainStarted":false,"processesExited":false,"phase":"Pending"},
                 "SECOND POD with memoryMiB 10240", "THIRD POD with memoryMiB 20480"]
}
```

`ready` must be a boolean derived from the actual current Node `Ready` condition
whose status equals `"True"`. Missing, unknown, false, or unnormalized readiness
is refused at preparation and every step, including rollback. Do not infer
readiness from running Pods or from an older receipt.

`unschedulablePresent` distinguishes an absent Kubernetes field from an explicit
false value. Preserve it for exact rollback. Before cordoning, both scheduling
value and field presence must still match the original observation; afterward
the field must remain present and true. Benign Node status updates may advance
its resource version while the UID, readiness, scheduling state, and all other
fences remain valid. They do not block raising or guarded restoration of active
ceilings. Cordon and node-restore JSON patches use the current freshly observed
resource version as their CAS test, rather than the original or recorded cordon
version. Record the cordon result version in the journal for audit. Original
field presence still determines whether node restoration replaces false or
removes the field. Daemon and protected Pod resource versions remain pinned.

During rollback, all started test
Pods must be terminal and their processes independently confirmed exited;
unreleased CPU-gated Pods can remain staged. The client/process inventory must
still prove an idle GPU2 server. Readbacks accept equivalent integer G/M units.
Before main starts, `processUid` is the root-verified planned main UID, checked
against the actual CPU gate UID. Record the real CUDA client UID after release.

The request is a closed schema:

```json
{"runId":"reviewedrun0716a","maxWindowSeconds":180,"raiseActiveThreads":false}
```

CLI preparation is read-only:

```bash
python plan.py prepare --identity /private/readonly-server-identity.json \
  --process-details /private/process-details.json --observation /private/fresh-observation.json \
  --request /private/request.json > /private/candidate.json
```

The separate review receipt is operator evidence, not a cryptographic signature
or a replacement for cluster authorization:

Candidate and source-receipt hashes use canonical JSON objects, rather than raw
file bytes. Preserve checksums of the raw evidence files separately.

```json
{"schemaVersion":1,"candidateSha256":"EXACT CANDIDATE HASH","actor":"REVIEWING OPERATOR",
 "reviewedAt":"CURRENT UTC ISO TIMESTAMP","statefulStepsReviewed":true,
 "steps":["EXACT candidate.steps LIST"]}
```

The initial journal is `[]`. Root appends each successfully executed/read-back
step with `step` and `candidateSha256`. For cordon, also append
`resultNodeResourceVersion` from the resulting API object. Never advance the
journal on an attempted or failed operation.

```bash
python plan.py step --candidate /private/candidate.json --review /private/review.json \
  --observation /private/fresh-observation.json --journal /private/journal.json \
  --step cordon --authorize-stateful-step
```

This prints the guarded operation; it executes nothing. An explicit flag without
the exact receipt, or a receipt without that flag, fails. All credentials and
raw evidence remain outside Git. Public PR CI runs only offline tests.

```bash
python -m unittest discover -s platform-staging/scheduler/qualification/mps-dynamic -p 'test_*.py' -v
```

# Fresh147 marked cross-parent IPC measurement

Default-inert operator wrapper for the existing fresh QA cohort. It imports no
old Node/head authority, retirement allowlist or hardware result. The five
original endpoint, host mapper and kernel witness files change only their exact
boot, generation and protected QA operator path. The protocol,64-byte handle,
64MiB allocation,5120MiB parent, rawCUDA denial800, kernel status27/reason6,
PID lifetime, complete kernel sequence and cleanup thresholds are unchanged.
The copied session engine adds isolated Python `-I` to its original transport.

Root must first review and stage these protected files on the selected host:

```text
ROOT=/var/lib/cps-native-gpu/qualification/1f7d941a-872d-4453-a1ba-fd489d8aff14/cohorts/6ba3353d-bf13-4cad-9c35-3119dd279a67/ipc-kmsg-witness
ROOT/                                  root:root0700
ROOT/sessions/                         root:root0700
ROOT/ipc_host_pid.py                   root:root0400
ROOT/kernel_witness_collector.py       root:root0400
ROOT/kernel_witness_validator.py       root:root0400
```

Stage only the independently reviewed exact source bytes; do not run a witness
on another boot, generation, cohort or host. Root owns all staging, credentials
and API/SSH execution. The collector's explicit `--execute --qualification`
permits only its existing bounded `/dev/kmsg` trial markers and exclusive
protected capture files. It does not mutate GPU caps, modules, Source or custody.

The current actual manifest is the same reviewed private manifest used by the
first peer/OOM gate. A second independently raw-SHA-pinned transport JSON is
closed to `version:1`, `attribution_argv`, and `witness_argv`. Both are split,
separately reviewed SSH argument vectors. The attribution vector invokes exact
`ROOT/ipc_host_pid.py --execute`; the wrapper appends its own current `--request`
using shell quoting appropriate for SSH. Do not preinsert a request. The witness
vector invokes exact `ROOT/kernel_witness_collector.py --execute --qualification
--source-sha256 COLLECTOR_SHA --validator-sha256 VALIDATOR_SHA`.

These vectors are explicit trusted Root transport boundaries, not authentication
inferred from a JSON label. The wrapper checks the source bindings and complete
raw transport hash; Root separately reviews the remote target and executable.

```text
python -I -B run_cross_pod.py --execute
  --manifest ACTUAL_MANIFEST --manifest-sha256 REVIEWED_RAW_SHA
  --transports ACTUAL_ROOT_VECTORS --transports-sha256 REVIEWED_RAW_SHA
  --runner-sha256 REVIEWED_RUNNER_SHA
  --direction a-to-b --output NEW_PRIVATE_DIRECTORY
```

Use `b-to-a` for the reversed measurement. No new Pod, mount or shared exchange
volume is needed: Root relays the opaque handle from the trusted exporter.
The wrapper first proves the same handle works in the exporter's own parent.
It then holds the opposite-parent importer, maps its exact actual host
PID/start/cgroup, acknowledges a fresh Root begin marker, performs the single
controlled open, and closes the Root marker window before importer completion.
The original validator requires actual kernel-origin status27/reason6 in the
complete contiguous sequence between the exact nonce/trial markers, correlated
with that PID and bounded actual API call window. API denial alone cannot pass.

Importer kernels must survive, and the exporter must continue kernels before
and after denial, recover byte37 and preserve original byte19. All endpoint
cleanup and fresh final observer checks must pass: same Pods and actual notebook
lifetimes, original protected seals/journals, caps and recovered charges. Every
partial, timeout, missing-kernel, cancellation, late-proof or cleanup failure
remains inconclusive and retains protection. Root still performs actual Pod stop
and the original full controller cleanup after the complete measurement series.

Passing this wrapper is bounded marked cross-parent IPC evidence. The receipt
still keeps `production_qualified:false` and
`cross_parent_isolation_qualified:false`; a reviewed complete qualification
report is a separate operation. It does not establish all external-memory/VMM
protocols, exporter-process death,10GiB behavior, MPS, restart-cleanup, six-gate
completion or recovery of the29 missing historical journals.

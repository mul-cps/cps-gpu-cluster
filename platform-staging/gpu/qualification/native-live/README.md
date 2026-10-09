# Native no-MIG qualification evidence

Production and group GPU sharing remain disabled. These files describe bounded,
trusted hardware experiments; passing one experiment does not complete the
platform qualification gates.

The guarded driver is a custom, experimental build of NVIDIA's R615.71.09 open
kernel modules. The core module (`nvidia.ko`) contains local allocation/import
ownership patches, and a separately built custom UVM module (`nvidia_uvm.ko`)
adds managed-memory denial. The official NVIDIA base image does not contain
these guards. Maintaining this build requires reviewed source revisions and
patched-source/kernel ABI, module-symbol CRC and compatibility checks for both
modules; it has no upstream qualification. SDK/runtime health enforcement and
native Hub integration remain activation gates. All production qualification
and group-sharing flags remain false.

[The synchronized MPS assessment](results/synchronized-mps-20261009.json) records
the 2026-10-09 run against the experimental R615.71.09 core ELF
`59f623fe5fdc89ef06f8055ee4dbfafeabe70b1d0bcabc487bc6fe04b78d6e77`.
Each of two Pods had a 5 GiB native parent cap and its own private MPSv2 daemon.
The runner started the peer first and inspected both actual registered CUDA
client PIDs during the main client's 30-second held window.

| Measured check | Result |
| --- | --- |
| Two registered clients with distinct native parents | Passed; two registration snapshots and an independent host process/parent mapping |
| Main ordinary allocation, over-cap refusal and recovery | Passed; numeric CUDA results `0`, `2`, `0`, followed by a successful kernel tick |
| Fresh managed allocation | Refused with numeric CUDA result `801`; no managed touch or prefetch attempted |
| Independent peer | Passed; 300 successful ticks over 60.15 seconds, bracketing every recorded main milestone |
| Native usage during the simultaneous held window | Main 465,911,488 bytes; peer 465,963,712 bytes; each cap 5,368,709,120 bytes |
| Main shutdown while the peer remained registered and active | Passed; main native usage returned to zero while the peer retained its charge and continued ticking |
| Both private daemons stopped | Passed; both native usages zero, no same-GPU compute clients and no cleanup uncertainty |

The four native accounting samples cover the clean baseline, simultaneous held
state, main cleanup with the peer active, and final cleanup. They do not capture
the brief OOM or managed-allocation attempts themselves. The assessment preserves
that measurement boundary and includes SHA-256 hashes of the private captures
without publishing raw Pod/Node records, credentials, hostnames or person
identifiers.

The earlier marked-core capture missed the concurrent MPS inspection window; it
remains partial evidence. This synchronized run supplies the missing measured
registration, charging and cleanup observations. It does not qualify a shared
host MPS daemon or compute-percentage fairness. Driver/node restarts, the broader
memory-import matrix, production reservation lifecycle and the remaining
acceptance scenarios are separate gates.

[The import assessment](results/import-matrix-20261009.json) records the fresh
four-case matrix against the same core ELF and driver epoch. Same-parent VMM and
IPC imports succeeded. Cross-parent VMM and IPC imports returned numeric CUDA
`800`, each corroborated by a fresh driver denial with reason `6`. The generic
probe exits `1` and reports `inconclusive` for those expected refusals; the
assessment preserves those raw outcomes.

The observer captured 225 accounting samples across the experiment and **34
samples inside the 9.000546-second same-parent retained-backing window**. After
the exporter released its local VMM references, the owner remained charged
1,002,601,856 bytes throughout that window, 134,217,728 bytes (128 MiB) above the
measured pre-fill baseline of 868,384,128 bytes. The importer could still read the
backing after the hold. This delta covers retained backing and the importer's
fill allocation; it is not attributed solely to the imported 64 MiB. The
independent peer completed 449 successful ticks over 90.05 seconds. The exporter
remained alive with its context until the importer finished, so **exporter
context/process death before importer completion remains untested**.

[The container restart assessment](results/container-restart-20261009.json)
records an exact CRI stop of the peer's main container and its restart inside the
same Pod UID and unchanged complete specification. The replacement container saw
the 5 GiB cap, returned numeric CUDA `2` on its over-cap attempt, and completed the
pinned probe's recovery checks. An independent main-Pod heartbeat completed 150
successful ticks over 30.07 seconds, bracketing the stop and restarted probe.
The controller subsequently reported both Pods sealed in two iterations. The
probe asserts recovery allocation, touch and kernel results before its successful
completion; it does not emit a separate raw recovery phase. This test covers a
main-container restart within the existing Pod parent, and does not cover Pod
replacement, node reboot or driver reload.

`collect_evidence.py` retains its original fixed capture names and
`cps-native-live-evidence/v1` output. The synchronized result uses the distinct
`cps-native-synchronized-mps-assessment/v1` schema; it is not output from that
historical collector. CPU JSON validation verifies evidence consistency and
sanitization, and establishes no additional GPU behavior.

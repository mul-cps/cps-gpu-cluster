# Native no-MIG qualification evidence

Production and group GPU sharing remain disabled. These files describe bounded,
trusted hardware experiments; passing one experiment does not complete the
platform qualification gates.

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
acceptance scenarios are separate gates. Fresh same-parent and cross-parent VMM
results for this core are awaiting their own evidence assessment.

`collect_evidence.py` retains its original fixed capture names and
`cps-native-live-evidence/v1` output. The synchronized result uses the distinct
`cps-native-synchronized-mps-assessment/v1` schema; it is not output from that
historical collector. CPU JSON validation verifies evidence consistency and
sanitization, and establishes no additional GPU behavior.

# Gateway census provenance correction — 20 October 2026

This records a corrected census classifier and its completed Gateway-only trust
handover. It does **not** establish normal Hub GPU Start, CUDA, cross-Hub pooling
or production qualification. The next normal Hub pilot was unfinished at this
checkpoint; its eventual result belongs in separate evidence.

The preceding ordinary shared-workspace Start returned 409 before CUDA. The GPU
census treated the CPU Gateway's `cps.compute/native-hub-consumer-revision`
annotation as evidence of GPU execution. Normal Stop succeeded; the new claim
was released, all 159 earlier claims were unchanged, reservations were empty,
workspaces were stopped and the protected notebook was unchanged.

Source [`2575fa1`](https://github.com/mul-cps/cps-compute/commit/2575fa1233d55f6e9f196c4faa377c672bef7d02)
excludes only that exact provenance annotation from execution classification.
GPU resource requests, native pending/unknown annotations, CDI/run.ai metadata
and the GPU-group label remain execution signals and still cause an unknown
active workload to be denied. The eight-case regression traverses three actual
mocked API pages (offsets 0/20/40), checks unchanged input rows and retains the
positive reservation verifier. The full source suite passed 3975 tests; the
installed Gateway image passed 969 tests.

The deployed immutable image is
`ghcr.io/mul-cps/cps-compute@sha256:d3da41df09a02c5480608e6948626513989f0cc639b3a62e2be8cbfa5f5551ca`.
The completed handover retained all 205 prior archive files and reached 42 journal
rotations/210 archives. Node 793, both Hub 9088 and patched writer a52 images were
unchanged; only required trust/configuration references changed. All six
components were Ready. All 160 released ledger rows remained byte-equivalent,
the protected notebook specification/restarts were unchanged, and temporary
rotation permissions were absent. Policy D48 and approval 0e07 remained unchanged.
No fence/deadline extension, ACK fabrication, journal reanchor or GPU execution
was part of this rollout.

The publication receipt's `live_deployed:false` describes publication time; the
later independent rollout receipt establishes deployment. These are separate
stages. [receipt.json](receipt.json) retains sanitized facts and hashes of the
original private failure, publication, source-verification and rollout receipts.
Private payloads, credentials and person identifiers are excluded.

The earlier [trusted no-MIG 5/20 GiB pair](../native-trusted-pair-20261020/README.md)
retains its own scope. Remaining gates include current normal Hub Start/CUDA,
kernel-witness correlation, cross-parent VMM, managed-memory/restart checks,
cross-Hub pooling, packing/scheduling and the remaining production release gates.

# Controlled dynamic-cache result — 2026-10-07

Run `dyn071421c` passed `bounded-standard-cases-passed` on `k3s-wk-gpu2`.
Both trusted fixture Pods succeeded on the same physical GPU
`GPU-16128952-b438-556a-00bb-93039ee24e56`. This is one bounded standard-case
sample, not production or hostile-isolation qualification. No MIG, GPU mode,
MPS server ceiling, device selection, live ConfigMap or production profile was
changed.

The source was `036c85daba96df55a84a4f952cf31ea0a2d38324`.
The evaluator source SHA256 was
`c61652203abc898eef9ae639b09b76923de709d7f1a66757e85ae729fef31511`;
the saved `evaluation.json` SHA256 was
`3350e6243f2186cbaf59f8f35715d6152ab6a1739de7a2c413c559ae4e15a0a3`.
Re-evaluating the saved logs, final Pods, node inventory and complete before/after
owned ConfigMaps produced the identical result. The private operator-local
record is `/home/bjoern/cps-platform-evidence/2026-10-07/dynamic-cache/dyn071421c/`;
its preflight is in the sibling `20261007T141933Z-preflight/` directory.
These paths identify local evidence, not published artifacts.

Two earlier attempts stopped at the CPU review gate before CUDA allocation.
`dyn071359a` exposed KAI 0.18.1 rounding: requesting 5120 MiB on the 40960 MiB
GPU became fraction 0.13 and injected global `CUDA_DEVICE_MEMORY_LIMIT=5324m`.
The trusted fixture now retains that scheduler value and sets
`CUDA_DEVICE_MEMORY_LIMIT_0=5120m`. The installed hook actually reported
5120 MiB for the single visible CUDA device. `dyn071408b` selected the other
GPU2 card while the fixture still expected the initial preflight choice.
The fixture now binds its expectation to the operator-reviewed actual KAI
selection, without overriding placement, and releases the workspace only on
the independently running peer's physical GPU.

The completed run established:

- With A holding 3072 MiB, B's 3072 MiB allocation returned actual
  `CUDA_ERROR_OUT_OF_MEMORY` (2). A continued successful CUDA writes. After A
  freed its own allocation, B allocated and wrote successfully.
- All 16 synchronized rounds had strict overlapping allocation intervals;
  each produced one success and one OOM, with the successful process's exact
  CUDA write receipt. The children retained the same accounting device/inode;
  the explicit cache mapping was verified without fallback or replacement.
- A separate Pod held 256 MiB and kept writing on the same physical GPU across
  the complete workspace window, including the required boundary heartbeats.
- Actual loaded library bytes, preload, mapping and exported quota were
  verified. The library SHA256 was
  `79bdbf5bf819de4fda3710235c9eac6bf91ece674eb2891728069a9d0b0c8542`.
  Its correspondence to reference source revision
  `5496322f2fb3e71bf1eca014fba3c9bc59ab8ffd` remains unverified.

The evaluator retains `productionQualified=false`,
`hostileIsolationQualified=false`, `exactProfileQuotaQualified=false` and
`tamper.status=not-run`; the existing hostile bypass failure remains applicable.
Scheduler quota drift remains visible despite the measured canonical hook
limit. The MPS snapshot during the run captured only the independent peer;
it does not prove a simultaneous three-client workspace MPS receipt.

Remaining gates include hostile quota enforcement and build provenance, the
complete dynamic 5/10/20 GiB profile and packing matrix, explicit MPS client
receipts, process exit/crash accounting recovery, notebook kernel restart,
cross-Hub reservation and membership revocation, normal-user public Argo
authentication/ownership, and native RTC group-workspace acceptance. Ten and
twenty GiB profiles require separate authorized MPS-ceiling qualification.
Sixteen rounds cannot exclude a rare race. Group GPU sharing and production
profiles remain disabled pending the full acceptance gates.

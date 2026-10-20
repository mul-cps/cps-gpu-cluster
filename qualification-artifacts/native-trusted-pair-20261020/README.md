# Current no-MIG 5/20 GiB trusted pair — 20 October 2026

**Bounded hardware measurements passed; full GPU isolation and platform production
qualification remain open.** [receipt.json](receipt.json) records sanitized results
and hashes of the retained private artifacts. This run used two controlled operator
Jobs on one qualified A100, outside normal Hub start/pooling. It enabled no policy,
profile or production release and does not qualify all eight GPUs.

The current 615.71.09 managed/import-guard driver ran with MIG current/pending disabled.
Existing `NativeCapController` and `QualificationNodeBackend` applied exact 5120/20480 MiB
soft=hard caps to independently identified Pod-parent cgroups before GPU execution.
The original cap gate was followed by a CPU-only shared pair barrier: no GPU identity
initializer could proceed until both current seals/readbacks were verified. The
identity initializer checked the selected physical UUID before CUDA initialization.
No allocation hooks, manual user-Pod cap bypass, reset or MIG change was used.

| Actual measurement | Result and limit |
| --- | --- |
| 5 GiB OOM with 20 GiB peer | Typed OOM after 4608 MiB held; recovery passed; 53 peer ticks bracketed OOM/recovery |
| 20 GiB OOM with 5 GiB peer | Typed OOM after 19968 MiB held; recovery passed; 53 peer ticks bracketed OOM/recovery |
| Same-parent imports | Direct VMM, IPC and VMM passed with peer continuity; these positive controls do not prove cross-parent isolation |
| Private MPS | Two clients held 4096 MiB in aggregate; the next 256 MiB allocation, targeting 4352 MiB total, returned CUDA OOM 2; both clients recovered; daemon cleanup left no private MPS processes or errors |
| Independent cap observation | 50 NVML samples during MPS preserved exact caps; the workload probe itself does not verify the native cap or driver generation |
| Cross-parent IPC | Both 5→20 and 20→5 imports returned 800 (`CUDA_ERROR_NOT_PERMITTED`); same-parent positive controls, exporter continuity/recovery and importer kernels survived. **Kernel-witness correlation remains pending**, so this is an observed API denial, not a completed guard attribution/isolation qualification |

The 5/20 GiB caps were not inferred from KAI fractions: the receipt
contains actual native soft/hard byte readbacks. OOM allocation amounts include
only the measured held payload; context/runtime overhead means they are not a
claim of that much usable application VRAM. The raw Torch probe's legacy field
`physical_reported_total_bytes` actually reports the CUDA-visible capped totals
(5/20 GiB), **not** physical GPU capacity. Independent NVML reports a 40960 MiB
physical A100. Peer logs independently bracketed OOM and recovery; maximum tick
gaps were 0.503 seconds or less, within the reviewed 5-second limit.

Both original journals reached `retired-inert-cap`: exact dead zero-charge cgroups
were retained as historical accounting, with no path reset or replacement adoption.
Gate receipts were removed. Fixture Pods, Jobs, source ConfigMap, controller and all
eight temporary RBAC resources were confirmed absent. Gateway and Node original full
specifications returned one Ready replica each; GPU2 was uncordoned. All 159 ledger claims remained
byte-unchanged and released, SQL reservations/bindings were zero, nine workspace
records were stopped, and the protected personal notebook was unchanged.

The first attempt failed on an oversized review record before NVML/cap/CUDA work.
R2 used new immutable Job/STATE identities and a digest of the exact full ledger data,
retaining the original private capture and the existing 32 KiB private-reader bound.
Temporary Gateway/Node writer pauses and a GPU2-only scheduling hold were restored;
there was no driver epoch, historical proof or delivery-journal rebaseline.

## Still required

- Correlated current kernel witnesses for cross-parent IPC denials.
- Cross-parent VMM and managed-memory current-run checks.
- Stop/restart with new actual lifetimes and fresh automatic cap assignment.
- Normal Hub GPU Start through KAI/Binding followed by CUDA; these trusted Jobs do
  not close the separate transaction/startup issue.
- Cross-Hub pooling, broader packing, scheduling/reclaim and startup SLOs.
- The complete original release and platform acceptance gates.

Earlier dated receipts stay valid only for their own measured source, hardware and
lifetime pins. They are not relabeled as this run's missing evidence. No credential,
raw IPC handle, personal identity or full private cluster object is published here.

# Current CPS 5 GiB / CIT 10 GiB import measurements

The controlled run on 2026-10-12 measured successful same-parent imports and
kernel-enforced cross-parent denials in both directions for the existing CPS
`native-group-b` (`interactive-shared-5`) and CIT `native-group-a`
(`interactive-shared-10`) workspaces. This is a scoped measurement report;
complete isolation, general GPU access, production and the 20 GiB profile remain
unqualified. It changes no activation or deployment configuration.

[measurement.json](measurement.json) binds the exact Pod lifetimes, protected
cap seals, notebook image, node/boot/driver generation, policy `d48f6553…` and
controller model `630d43cc…`. The two finite caps total 15 GiB on one selected
GPU. Both use the approved notebook image digest `91678610…`.

| Measurement | Observed result |
|---|---|
| Ordinary CUDA kernels and recovery in both parents | Verified 64 MiB vector kernels before and after managed-memory denial |
| Managed allocation | Typed `cuMemAllocManaged` denial, CUDA result 801 |
| IPC CPS → CIT and CIT → CPS | Same-parent import succeeds (0); cross-parent import denied (800) |
| VMM CPS → CIT and CIT → CPS | Same-parent import succeeds (0); cross-parent import denied (800) |
| Import kernel witnesses | Exact importer lifetime, GPU and bounded marker sequence; kernel status 27, reason 6, client kind 4 |
| Continuity and cleanup | Exporter continuity/recovery and importer kernels survive; participants explicitly clean up |
| Before/after authority | Exact Pod lifetimes, seals and 23 finite retirements unchanged; both active charges return to zero |

VMM positive and cross-parent transfers used one identical original 64 MiB
backing descriptor per trial. Raw kernel captures were revalidated with the
pinned witness validators; the CUDA error alone was not accepted as proof.
Every host preflight and postflight retained the exact 13-row cleared baseline,
selected GPU/device checks, bounded complete cgroup inode-absence proof and
rejection of unknown or changed inventory rows.

The original v3 VMM CPS → CIT trial remains **inconclusive** and preserved. Its
protected bridge staging file was missing; no same-parent positive control or
cross-parent VMM attempt completed. The recorded postflight showed 436,341,440
bytes charged to CPS. A later complete inventory snapshot returned to zero and
exactly matched the original pinned baseline. The separate v4 trials ran after
exact bridge/endpoint staging and passed in both directions. Earlier failures
and counterexamples are retained; this report does not reinterpret them as
passes.

Current cap exhaustion, peer continuity, aggregate-cap and CIT10 MPS tests are
separate pending gates at this report's capture boundary. Root normal Stop,
physical retirement, restoration, creator-exit retention and maximum-profile
capacity evidence must be reviewed separately. The ordinary 64 MiB controls
here do not establish fresh over-cap or child-cgroup denial. Neither this report
nor the prepared harness grants production or general GPU access.

Only sanitized summaries and raw SHA256 evidence/source pins are published.
Protected original captures, import handles and command transcripts remain
private. The report contains no credentials, personal account identities or
private filesystem paths.

Follow the canonical [compute operations guide](../../../../../docs/compute-platform/operations.md)
for platform rollout and lifecycle controls, and the
[controlled measurement protocol](../README.md) for the remaining GPU gates.

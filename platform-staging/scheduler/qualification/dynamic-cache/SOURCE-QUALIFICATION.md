# Dynamic shared GPU runtime qualification — 2026-10-07

**Status: source, package and offline manifest checks passed; final compiled
runtime GPU qualification pending.** The selected mechanism is dynamic
KAI/HAMi/MPS sharing. GPU group activation remains gated; MIG is not part of
this rollout. This receipt records qualification artifacts, not a production
release or deployment.

## Exact artifact tuple

| Artifact | Identifier |
|---|---|
| `cps-compute` source | `2f43f59aa319f8a114bae41ff89226018e3e5089` |
| Wheel SHA-256 | `06939b3e4cefc882f419635129e982f46d40f376e9f6b3122e51ab4bed96febe` |
| Published qualification image | `ghcr.io/mul-cps/cps-compute:qualification-2f43f59aa319@sha256:38dad2077eb1552683cdb54c1ee50ffdf42d63e4a7dcd322f95f9f0236261c04` |
| Image config SHA-256 | `18f6a061f8c6ac5c0bb3e8c9da3d3e385217a22af7c5dbf1c991a5541ebcf0c4` |
| Installed `gpu_runtime.py` SHA-256 | `93f4e01c3682e52192d43c130073b3daf50c59ea7bd06342971f5f4add0a2b68` |
| Installed `hub.py` SHA-256 | `ca4d60d62cd016fac0ab830673d86549628dd34ae9fe4d0c8b34a3f1994e9333` |

The captured remote OCI manifest hashes to the published digest above and
references that exact image config. The local build manifest has a different
digest, `sha256:3fcec33717550520786823291f6a008fbc4479b9b3c4cfd0654a97cfc692417a`;
use the **published digest** in any future reviewed cluster test.

## What passed

- Exact source: **599 Python tests and 10 addon tests**, with matching local and
  remote source revisions and a clean whitespace check.
- Packaging: all **86 tracked archive files**, **24 Python modules** and **five
  addon files** verified; wheel and installed image bytes match. Imports and
  `pip check` passed; dependencies match the pinned inherited base. Both wheel
  hash labels, component, source revision and artifact-module hash were checked.
- Final image initializer: nonroot UID/GID **10001/10001**, read-only root,
  no network, dropped capabilities; created an empty regular cache with a
  `0700` private directory and `0600` file. A second invocation failed with
  `FileExistsError` while preserving the accounting marker and inode. This used
  a private local tmpfs, not Kubernetes `emptyDir`/`subPath` execution.
- Actual **KubeSpawner 7.1.0 / JupyterHub 5.5.2**: **38 manifest checks plus nine
  saved-model/security/provenance checks**. Real memory traits accepted integer
  byte values; real `V1Pod` construction preserved storage and applied the
  shared runtime, then removed it on CPU transition. The test intentionally
  used UID/GID **1500/2500**, synthetic image digests, guarded infrastructure
  factories and mocked gateway requests. It executed no initializer or GPU and
  made no real network calls. The earlier `db095f7e` memory-trait failure remains
  preserved; this tuple contains its source correction.

## Earlier GPU evidence is a separate experiment

Run **`dyn071421c`** completed ordinary same-cache accounting, free/recovery,
**16 tested overlapping allocation rounds**, and continued progress by a
separate Pod on the same GPU. It used the earlier fixture image
`qualification-a7abe7d13465a8ea@sha256:f107b407f3e6c9218a4a9b5ec4df9f0ea013f4abd0a177e474013ff6b682c893`,
embedded `/probe/initialize.py`, and a flat `usage.cache` subPath. It did **not**
run the new compiler or its packaged initializer/private cache layout.

KAI injected **5324 MiB / 0.13**, while the fixture's indexed override enforced
**5120 MiB**. Its evaluator therefore retains `schedulerQuotaDrift=true`,
`exactProfileQuotaQualified=false`, `hostileIsolationQualified=false` and
`productionQualified=false`. The prior intentional tampering failure remains.
The observed HAMi library hash was
`79bdbf5bf819de4fda3710235c9eac6bf91ece674eb2891728069a9d0b0c8542`;
a matching source-build revision was not proved. The bounded success does not
establish rare-race, crash, kernel-restart or hostile-user isolation guarantees.

## Remaining integration gates

Read-only observations on **2026-10-07** found MPS server UID **10001** at
**15:05 UTC**, with **5G pinned-memory limits** and **12% active-thread limits**.
The protected existing Hub single-user process was observed at **15:17 UTC**
as UID/GID **1000/100**. Its Pod startup configuration used root plus
`NB_UID=1000`; neither that startup UID nor the offline 1500/2500 model proves
the effective live process identity. These are historical observations, not
assumptions about unchanged current state.

Before activation, qualify effective client/server UID compatibility and the
intended dynamic memory/compute budgets. The observed 5G/12% ceilings do not
qualify 10/20 GiB or mixed-size packing. Then test the **published final image
and compiler-generated, finally injected Hub/Argo/JobSet Pods**, including
admission exceptions, actual library/cache identity and limits, independent
peer progress, crash/restart accounting, and safe OOM recovery. Native Shares,
RTC revocation and global cross-Hub group reservations remain separate gates.
Software accounting remains cooperative; no daemon or GPU mode change follows
from this receipt.

## Private proof index

Operator-local evidence is retained outside Git under
`/home/bjoern/cps-platform-evidence/2026-10-07/`:

| Receipt | SHA-256 |
|---|---|
| `dynamic-runtime-source/2f43f59aa319/source-verification.json` | `4e5105cfe4be4461ce075ffa8a6ca723e64c1e42d9854a0bb676b05e0c82332b` |
| `dynamic-runtime-packaging/2f43f59aa319/verification-report.json` | `1d2ec7342503150753bb78e197b960681cc48ba39907571ade35e782915d5a74` |
| `dynamic-runtime-kubespawner/2f43f59aa319/qualification.json` | `e834caa671c9f16ba9e2904f89d8603b2dd144346d07f427993f1c515acea031` |
| `dynamic-runtime-kubespawner/2f43f59aa319/final-model-review.json` | `1fdac95586254476ad61ecee117706d0a2e069e938c343c123db6d1268348b8f` |
| `dynamic-cache/dyn071421c/evaluation.json` | `3350e6243f2186cbaf59f8f35715d6152ab6a1739de7a2c413c559ae4e15a0a3` |
| `dynamic-runtime-mps/readonly-server-identity.json` | `e9ee45a48283f73ab3e134ac3318dedb1b8b47a2369064bdcfcd92b84a881708` |
| `dynamic-runtime-mps/process-details.json` | `0b77eac0662ec82f8141130d3bcc309205a56fc7f5ff8071eefcd749bbb45dda` |
| `dynamic-runtime-mps/protected-hub-process-identity.json` | `f6f484d9c633a0a9328e0507030be99bb2eb1513eb84457e77514e4b18028138` |

The packaging receipt predates publication and the later model result; its
original pending flags are preserved. The separate source and remote-manifest
receipts establish those later facts. Canonical runtime/API documentation stays
in [`cps-compute`'s shared GPU runtime guide](https://github.com/mul-cps/cps-compute/blob/2f43f59aa319f8a114bae41ff89226018e3e5089/docs/shared-gpu-runtime.md).

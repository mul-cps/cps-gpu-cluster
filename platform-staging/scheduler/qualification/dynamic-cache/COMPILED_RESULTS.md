# Packaged dynamic runtime: bounded GPU evidence

Dynamic KAI/HAMi/MPS sharing remains the selected implementation. These results
do not qualify MIG, production group access, or hostile isolation.

Two distinct runs establish different evidence. Keep their receipts separate;
do not combine their logs into one synthetic successful run.

| Run | Verified evidence | Still missing |
| --- | --- | --- |
| `dyn071542c` | Packaged compiler, private cache initializer, ordinary aggregate OOM/recovery and 16 actual-overlap allocation rounds; independent peer kept writing | Three-client MPS snapshot |
| `dyn071552c` | Three actual MPS clients on one physical GPU/server, exact host/container PID and Pod/container mapping | Final log/ConfigMap capture and strict final evaluation |

Both used `cps-compute` source
`2f43f59aa319f8a114bae41ff89226018e3e5089`, wheel SHA256
`06939b3e4cefc882f419635129e982f46d40f376e9f6b3122e51ab4bed96febe`,
and image
`ghcr.io/mul-cps/cps-compute:qualification-2f43f59aa319@sha256:38dad2077eb1552683cdb54c1ee50ffdf42d63e4a7dcd322f95f9f0236261c04`.
The installed GPU runtime module SHA256 is
`93f4e01c3682e52192d43c130073b3daf50c59ea7bd06342971f5f4add0a2b68`.
Actual workload UID/GID was `10001/10001`; this is not proof of Hub UID1000
compatibility.

## Compiler-runtime run

The strict evaluator returned `bounded-standard-cases-passed` and
`compilerGeneratedRuntimeQualified=true` for `dyn071542c`. It reconstructed
the original trusted Jobs and checked the complete effective executable Pod,
including both the quota/device ConfigMap and its empty `envFrom` ConfigMap.

The two workspace children used one private cache inode. A 3 GiB allocation
succeeded, the second 3 GiB allocation exceeded their shared 5 GiB budget and
returned CUDA OOM, the first child kept writing, and freeing its allocation
allowed recovery. All 16 measured overlapping allocation rounds passed while
an independent peer continued CUDA writes.

KAI injected `5324m` / `0.13`; the packaged compiler's indexed device limit
was `5120m`. The measured HAMi limit was 5120 MiB. Scheduler rounding remains
explicitly unqualified as an exact profile implementation. The observed
HAMi binary SHA256 is
`79bdbf5bf819de4fda3710235c9eac6bf91ece674eb2891728069a9d0b0c8542`;
its source revision remains unattested.

The first collector omitted the required empty `envFrom` map from its after
receipt, so its evaluation correctly failed closed. The corrected
`complete-final` capture includes both maps; the failed capture was preserved.
The first observer queried logs before the main container started, then a
later retry correctly refused the ended hold. No three-client snapshot is
claimed for this run.

Private evidence root:
`/home/bjoern/cps-platform-evidence/2026-10-07/dynamic-cache/dyn071542c/`.
The 52-file checksum seal was independently rechecked. Important hashes:

- `complete-final/evaluation.json`:
  `3d0e474cce156b11ef0e9a1cd7f05623ecb25478c5fb0412436a02e58c39dd5c`.
- `operator-conclusion.json`:
  `be13d733d179096e19bc9360837cdc4df409ba7f04f4ddd99ba0c649bcfbcf59`.
- Evaluator:
  `c573be93eab6ee669d781942e77f0242cd5d2df974dead42078454577dce22af`.

Postflight confirmed GPU2 idle, existing MPS server ACTIVE with no clients,
unchanged 5G/12% active and default settings, MIG disabled, and the protected
GPU1 notebook's UID and zero restarts unchanged.

## Actual three-client MPS snapshot

The repaired observer waited for the exact reviewed workspace container to
run before reading logs. During the 20-second CUDA hold, it observed three
clients on server PID `3166883`: two workspace children and the independent
peer. All clients were on
`GPU-16128952-b438-556a-00bb-93039ee24e56`, node `k3s-wk-gpu2`.

The observer checked actual MPS client lists, successful CUDA writes, process
UID/GID, `/proc` start times, namespace PIDs, cgroups, exact Pod/container
identities and pinned image IDs. Saved process records and all five saved
operator-helper checksums were independently rechecked offline afterward.

Private evidence root:
`/home/bjoern/cps-platform-evidence/2026-10-07/dynamic-cache/dyn071552c/`.
`mps-three-client-receipt.json` SHA256:
`fd79c873f04cca65ff6666212543aa794b73b1d676fcdf17c86df54742b50931`.

The operator subsequently observed both Pods `Succeeded` with exit code 0 in
a tool response at 2026-10-07 16:19 UTC; that terminal observation was not saved
in the private evidence directory. Cluster access was then denied by the
execution environment. No fresh postflight or final logs/ConfigMaps were
captured for this run. Complete those checks before extending its
qualification claim.

## Remaining gates

Run the separately rendered `dyn071555u` Hub UID1000/GID100 compatibility
fixture only after a fresh idle inventory. It has not been applied. Normal
MPS UID handover can replace the idle UID10001 server; never reuse that old
PID's maintenance approval for a replacement server.

The separate mixed 5/10/20 GiB fixture uses the fixed runner image from
source `40b9525097776e0d5927242ca625a27dadbd797c`. Its UID1000 fresh-server,
temporary active-ceiling, strict admission, mixed packing, kernel restart,
membership revocation, fairness and startup gates remain required. Current
production and hostile-isolation qualification flags remain false.

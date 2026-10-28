# CPS/CIT implementation checkpoint — 28 October 2026

The platform remains a limited pilot, not a qualified production release. This update supersedes only the named observations in the [27 October audit](current-state-20261027.md); historical acceptance remains evidence for its measured application/policy/device tuple.

## Live outcomes

- Rino (`cit-jhub`, account `m12113877`) has the restored `mujoco-desktop-exclusive` workspace, original home and one A100. CUDA, NVIDIA EGL MuJoCo rendering and the authenticated Xpra endpoint passed bounded checks. A later live check confirmed Ready, zero restarts, CUDA available, MuJoCo 3.12.0 and writable home. This does not qualify fractional MuJoCo or the student's complete training run. See the [restoration receipt](../../qualification-artifacts/rino-mujoco-restoration-20261028/README.md).
- DCGM collection again reports eight fresh physical GPU UUIDs, two per worker. The reviewed coverage alert is loaded and healthy; its incomplete-coverage condition cleared. Only the GPU2 exporter label was restored after the exact collector image passed a temporary probe. Driver, toolkit, sharing and research workloads were preserved. See the [telemetry receipt](../../qualification-artifacts/gpu-telemetry-coverage-20261028/README.md). Eight observable GPUs do not mean eight qualified dynamic-sharing roots. The live rule patch still needs runtime-preserving GitOps promotion.

## Committed software and packages

Compute source `bf532fce21b3ae462314b3d430812c6bfbdf1ae4` includes the managed runtime/shared-lifecycle checkpoint and its direct pinned Hub FastAPI dependency. The preceding checkpoint records real PostgreSQL and signed Node tests for installed ownership, successor-head handling, original terminal cleanup and fresh-read history stability. The focused Hub package suite passes 15 checks; an isolated installed-wheel Hub import and dependency check pass, while Node imports retain the lean optional-dependency boundary. See [compute PR 2](https://github.com/mul-cps/cps-compute/pull/2) and its committed `docs/integration-checkpoint-20261028.md` for exact scopes, not an aggregate test count.

Admin source `53d9dcd50b230102af8ab863ac7aec329dbe6da3` adds lifecycle behavior to the actually routed `AdminRecords` page: runtime status polling, returned removal-operation state and resumption with the exact input hash. Three focused lifecycle cases and all 20 UI tests pass. A clean archive frontend build and installed wheel contain the changed JavaScript. The operation reference is held in page memory; browser-reload recovery is not established. See [admin PR 2](https://github.com/mul-cps/e2x-course-hub/pull/2).

The local Node candidate digest is `sha256:6932965a09f01a34fd87faf4447533aead183990927ed24d929f05ba41ee4661`, built from the exact compute source archive. Its pinned install, package ownership/import checks and network-disabled dependency checks passed. It has not been pushed or deployed. Local build evidence does not qualify a host rollout or physical isolation. The matching Hub candidate is also built at digest `sha256:968e695e048fd6c7a15db731ee0ead1aafe980bfce1b5e0ad47627094e91bbba`; its pinned dependency, installed-file inventory and import checks pass. Neither image is published or deployed. See the [package receipt](../../qualification-artifacts/runtime-packaging-20261028/README.md).

## Immediate remaining implementation and activation

1. Complete the final admin image and preserve source/wheel/image provenance; matched local Node/Hub checks are recorded above.
2. Implement the dedicated production coordinator startup boundary: the existing generic Gateway factory does not assemble the managed selected-node owner/server. Then install and enable the managed runtime on a selected Node through the supported explicit installation path and retained installation bindings. The live agents do not currently pass `--selected-runtime`. Distinguish a genuinely never-installed local consumer from lost prior history; never recreate lost history. See the [activation preflight](../../qualification-artifacts/native-selected-runtime-activation-20261028/README.md).
3. Complete the managed shared lifecycle beyond the bounded membership slice: standalone admin Stop auditing, assignment closure/archive, full reconciliation and durable UI operation discovery.
4. Verify the installed final tuple on missing/changed hardware scopes, global cross-Hub accounting, scheduling/reclaim, distributed cleanup, startup bursts, session maximum/warnings and the final user-interface/image matrix.
5. Complete coordinated connected restore/off-host recovery and a reviewed compatibility release/promotion. Preserve existing successful RTC, notebook submission, retention and bounded GPU results; rerun only what the changed tuple or unproved requirement requires.

Direct university federation remains deferred to ICT. Email verification remains optional; reviewed directory identity is authoritative. Moodle remains planned and disabled. None of these deferred integrations substitutes for the local implementation and qualification work above.

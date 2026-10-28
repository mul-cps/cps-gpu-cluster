# CPS/CIT implementation checkpoint — 28 October 2026

The platform remains a limited pilot, not a qualified production release. This update supersedes only the named observations in the [27 October audit](current-state-20261027.md); historical acceptance remains evidence for its measured application/policy/device tuple.

## Live outcomes

- Rino (`cit-jhub`, account `m12113877`) has the restored `mujoco-desktop-exclusive` workspace, original home and one A100. CUDA, NVIDIA EGL MuJoCo rendering and the authenticated Xpra endpoint passed bounded checks. A later live check confirmed Ready, zero restarts, CUDA available, MuJoCo 3.12.0 and writable home. This does not qualify fractional MuJoCo or the student's complete training run. See the [restoration receipt](../../qualification-artifacts/rino-mujoco-restoration-20261028/README.md).
- DCGM collection again reports eight fresh physical GPU UUIDs, two per worker. The reviewed coverage alert is loaded and healthy; its incomplete-coverage condition cleared. Only the GPU2 exporter label was restored after the exact collector image passed a temporary probe. Driver, toolkit, sharing and research workloads were preserved. See the [telemetry receipt](../../qualification-artifacts/gpu-telemetry-coverage-20261028/README.md). Eight observable GPUs do not mean eight qualified dynamic-sharing roots. The live rule patch still needs runtime-preserving GitOps promotion.

## Committed software and packages

Compute source `bf532fce21b3ae462314b3d430812c6bfbdf1ae4` includes the managed runtime/shared-lifecycle checkpoint and its direct pinned Hub FastAPI dependency. The preceding checkpoint records real PostgreSQL and signed Node tests for installed ownership, successor-head handling, original terminal cleanup and fresh-read history stability. The focused Hub package suite passes 15 checks; an isolated installed-wheel Hub import and dependency check pass, while Node imports retain the lean optional-dependency boundary. See [compute PR 2](https://github.com/mul-cps/cps-compute/pull/2) and its committed `docs/integration-checkpoint-20261028.md` for exact scopes, not an aggregate test count.

Admin source `53d9dcd50b230102af8ab863ac7aec329dbe6da3` adds lifecycle behavior to the actually routed `AdminRecords` page: runtime status polling, returned removal-operation state and resumption with the exact input hash. Three focused lifecycle cases and all 20 UI tests pass. A clean archive frontend build and installed wheel contain the changed JavaScript. Follow-up admin commit `e90de7b57e7ac2a2642a3ee07b6f1217740f6969` adds authorized read-only discovery of durable operation references after browser reload; execution still requires an explicit resume action. The installed-wheel backend checks passed 44 tests with 78 subtests; focused UI tests, build and lint passed. This is packaged source evidence, not a live deployment. See [admin PR 2](https://github.com/mul-cps/e2x-course-hub/pull/2).

The local Node candidate digest is `sha256:6932965a09f01a34fd87faf4447533aead183990927ed24d929f05ba41ee4661`, built from the exact compute source archive. Its pinned install, package ownership/import checks and network-disabled dependency checks passed. It has not been pushed or deployed. Local build evidence does not qualify a host rollout or physical isolation. The matching Hub candidate is also built at digest `sha256:968e695e048fd6c7a15db731ee0ead1aafe980bfce1b5e0ad47627094e91bbba`; its pinned dependency, installed-file inventory and import checks pass. Neither image is published or deployed. See the [package receipt](../../qualification-artifacts/runtime-packaging-20261028/README.md).

The protected selected-Node peer configuration adapter is now committed in compute source
`9e6ccf3` and passes 11 focused tests in a dependency-complete environment,
including construction against an actually started NodeService fixture. It
reuses HTTPS CA/projected-token transport and Kubernetes TokenReview/SAR.
It is not yet wired into `create_runtime`; this does not close the production
coordinator assembly or live selected-peer exchange gate.

The private Source observation route and matching coordinator HTTPS client are
now implemented, committed and tested across a real TLS connection. Clean,
installed wheels pass 36 compute tests and 15 admin tests plus 20 subtests,
without implementation source paths. They remain unconnected to the production
activation factory; bounded observations are not complete-history or backup
proof. See the [transport receipt](../../qualification-artifacts/source-runtime-transport-20261028/README.md).

## Immediate remaining implementation and activation

1. Complete the final admin image and preserve source/wheel/image provenance; matched local Node/Hub checks are recorded above.
2. Verify the deployed v3 coordinator configuration and retained qualification coverage against the original production requirements. The managed selected-node installation framework is an optional replacement lane, not automatically a prerequisite for the existing path. If that replacement is selected, its dedicated startup/installation boundary remains unfinished; never recreate lost history. See the [review reconciliation](review-reconciliation-20261028.md) and [optional activation preflight](../../qualification-artifacts/native-selected-runtime-activation-20261028/README.md).
3. Complete the managed shared lifecycle beyond the bounded membership slice: standalone admin Stop auditing, assignment closure/archive, full reconciliation and durable UI operation discovery.
4. Verify the installed final tuple on missing/changed hardware scopes, global cross-Hub accounting, scheduling/reclaim, distributed cleanup, startup bursts, session maximum/warnings and the final user-interface/image matrix.
5. Complete coordinated connected restore/off-host recovery and a reviewed compatibility release/promotion. Preserve existing successful RTC, notebook submission, retention and bounded GPU results; rerun only what the changed tuple or unproved requirement requires.

Direct university federation remains deferred to ICT. Email verification remains optional; reviewed directory identity is authoritative. Moodle remains planned and disabled. None of these deferred integrations substitutes for the local implementation and qualification work above.


## Architecture review reconciliation

The live mounted values Secrets, installed application bytes and private compute source were checked alongside GitOps. The legacy repository alone is not the production source of truth.

Confirmed legacy CPS launch gaps have focused source fixes: freeform GPU/image/custom-NFS overrides are rejected before launch side effects; validation resolves the final server-owned KubeSpawner profile callback including native profiles and default REST launches; optional NFS presets default off; unsupported Dask/Slurm choices are filtered; course-priority student profiles require student membership even for power users; and future notebooks use a dedicated unprivileged ServiceAccount with token automount disabled. Existing Dask accounts and running notebooks are preserved. LDAP lookup now uses a bounded positive UID/GID cache and runs off the Hub event loop; permission/group data is not cached there.

KubeSpawner already validates selected profile slugs. The absence of a duplicate check was not proof of an exploitable ordinary-user GPU-profile bypass. The independent freeform resource and storage issues were real configuration gaps.

A four-file compatibility backport is published as [compute PR 4](https://github.com/mul-cps/cps-compute/pull/4), source `16fa7670601546ba7c1ec1bf58eb3e8b38c67619`. Candidate image `ghcr.io/mul-cps/cps-compute@sha256:f00f8c5b63bdce6348153aab6e11c1fd5cbf638ed1b50ef27bdda346ad202b75` was inspected remotely. It retains all 20 existing Hub package files, all 84 SDK files and all 137 installed distribution versions unchanged; only two packaged helper modules are added. The wheel RECORD audit, imports, dependency check and 43 focused helper tests passed. The companion mounted configuration and compatibility image are now deployed to CPS only; a crafted GPU override was rejected and a normal CPU launch reached readiness in 50.37 seconds. See the [live remediation receipt](../../qualification-artifacts/fixed-launch-rollout-20261028/README.md).

The source proxy configuration now restricts remote targets to explicit loopback addresses. CIT desktop registration is gated by the image's actual Xpra executables and assets in [CIT PR 20](https://github.com/bjoernellens1/cit-teaching-platform/pull/20); 13 executable configuration tests passed. Existing Rino image assets satisfy that gate. The CPS proxy predicate is now in the live mounted configuration for future notebook starts; already running notebook processes have not been restarted. CIT capability gating remains source-only. The stale CPS `/hub/ssh` link returned HTTP 404; source documentation now links the canonical SSH guide.

### Lifetime audit correction

Both live Hubs install the profile lifetime controller; its API route returned 403 without credentials, rather than 404. A ConfigMap-only audit missed the actual mounted Secret overlays. Profile-specific current deadlines were not retrieved, so no current per-user deadline is inferred here.

The independent global culler remains a separate constraint: CPS has a 48-hour idle timeout and no max-age argument, while CIT has a 24-hour idle timeout and 24-hour maximum age, with administrators included. The lifetime-controller protected-server records do not exempt users from that independent culler, and their Pod UIDs must match the current generation. Rino's restored CIT account is not listed as protected. A point-in-time GPU utilization sample does not prove an idle duration and does not authorize stopping research work.

Remaining review work includes exact-reference production pre-pull alignment, warm/cold/queue-separated startup measurements and measured caching benefits, the role-specific deployed UI/API matrix, and eventual reduction of legacy embedded configuration through the released adapter. Do not silently combine this remediation with a Hub/chart migration or a broad watched-Fleet reconciliation.

The combined cluster change passed 71 compute-policy tests with 167 subtests and 13 executable proxy configuration tests. These scopes exercise request rejection before side effects, default and final native profile resolution, directory caching, role visibility and ServiceAccount rendering. Those source tests alone do not establish deployment or latency; the subsequent bounded live CPS rollout and single CPU timing sample are recorded separately above.

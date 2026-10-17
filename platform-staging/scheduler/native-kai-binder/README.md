# Disabled native KAI terminal binder staging patch

This is an offline patch/build recipe for official KAI v0.18.1 commit `bdf434e5e9201cccf4e05fad04d814363653f692`. It does not install a coordinator, configure a cluster, produce/publish an OCI image, grant GPU access or qualify the pending native route. The CLI is inert by default. A marked Pod is denied when the required coordinator, uncached reader or reservation custody bridge is absent. Application wiring is opt-in and remains disabled. The separately implemented Python server is pinned to cps-compute source `74ccb2d9cdb1e91ea9750d335e1389c0d2d3a916`; its exact config/seed/writer/cleanup contract is in that repository's `docs/contracts/native-kai-coordinator.md`. Neither implementation is activated by these artifacts.

The SDK contract is based on cps-compute `0451fd9cc9bcb5ba55b2d35c5aca84fc52f5fad3`, with the exact centrally approved qualification-profile compatibility correction in source74ccb2d. Its compiler marker is `cps.compute/native-pending=kai-v0.18.1-gpu2-cm/v1`. That marker selects this fail-closed path; it is not authority. Authenticated protected registry/current central grant and attempt checks must authorize the actual full Pod. The Python prototype uses actual version1 operator qualification10 only. No20GiB, v2/approval_ref, DRA, SM, NUMA, legacy group-list fallback or new owner/profile permissions are added.

## Exact upstream seam and interfaces

Pinned original `pkg/binder/binding/binder.go:42-94` runs reservation, all PreBind plugins, then `patchPodBindingAnnotations` at76-79. The patch inserts a dedicated terminal call after that persisted patch and before original Binding83-89. Appending an ordinary PreBind plugin would run too early. Original `plugins/interface.go:17-25` has only Name/PreBind/PostBind/Rollback; original `plugins/state/state.go:6-9` has actual binding annotations and reserved GPU ID strings. Both interfaces stay unchanged.

New `Binder.SetNativeTerminal(reader, authorityNamespace, coordinator)` supplies an uncached `mgr.GetAPIReader()` and a protected coordinator implementation at startup. Original `cmd/binder/app/app.go:94-98` constructs a cache-backed client, so supplying `app.Client` as a terminal reader is insufficient. The opt-in App startup wiring configures both custody and terminal bridges before the initial reservation Sync goroutine. Its flags are disabled/empty by default, and no credentials are included here.

`NativeTerminalCoordinator.Prepare` receives fresh upstream Pod/Node/BindRequest/BindingState types and returns a retained `NativeAllocationFence`. It must run the SDK `build_pending_allocation_record`, publish/read back immutable v1 enrollment and ACK, and retain the lifecycle/capacity writer fence. `NativeAllocationFence.ValidateCurrent` must independently re-read full raw API documents, registry/maps/enrollment/epoch/current central authority and call `validate_pending_allocation_ack` plus `validate_current_pending_allocation`. Typed Go Pod serialization is not a substitute for full raw API document fidelity or the SDK's complete P/B hashes. ConfigMaps bind UID/RV/data hashes, with no invented generation field.

The patch verifies that final annotations are actually persisted, then reads the actual immutable ACK using its exact authority namespace, name, UID and RV. It re-reads the current Pod/Node/BindRequest generations, checks actual reserved GPU UUID without index inference, and sends an exact closed unstructured `v1/Binding` body. `ValidateBinding` must call SDK `validate_pending_binding_request` on that actual body. Unstructured encoding prevents typed ObjectMeta's `creationTimestamp:null` from expanding the strict reviewed schema. The body carries actual PodUID/currentRV and exact approved NodeUID. The retained fence is closed only after successful accepted-Binding publication or a bounded independent-context Hold attempt. A lost Binding response remains held.

Kubernetes v1.34.9 [BindingREST](https://github.com/kubernetes/kubernetes/blob/v1.34.9/pkg/registry/core/pod/storage/storage.go#L196-L227) preserves Binding UID/RV and uses both as Pod storage preconditions. This source review does not verify installed K3s behavior. Target NodeUID is sent and strictly compared by the coordinator; API storage assigns `Target.Name`, so Target.UID alone is not a Node replacement precondition. The protected admission/lifecycle fence and unchanged actual post-Bind nodeUID/epoch/native-cap gate remain required. No pre-Bind ACK claims CRI/cgroup/cap sealing.

## Cancellation and cleanup

Original controller `bindrequest_controller.go:162-168` rolls back every Bind error, and original GPUSharing.Rollback170-221 deletes maps by name. Marked attempts now return `ErrNativeCustodyHeld`; the controller skips unconditional rollback and status writes that would invalidate the ACK's prepared BindRequest generation. Other controller behavior remains unchanged.

Explicit `Binder.Rollback` on a marked attempt enters controlled cancellation. If the exact PodUID still exists, it first asks the coordinator to retain custody, then requests deletion with actual UID and current RV preconditions. Even DELETE success returns held. Cancellation has its own bounded context so cancellation of the caller cannot silently skip the hold. A replacement Pod with the same name is never deleted or patched.

Only after a later uncached absence/replacement observation and coordinator `CleanupMaps` proof of old PodUID absence plus native-zero may the patch remove the two exact compiler-named ConfigMaps. It checks their current UID/RV and exact Pod owner, and deletes with UID/RV preconditions. It does not patch the replacement/absent workload's GPU-group labels. Unknown native-zero or map replacement remains held.

An authenticated actual empty cleanup array means the server completed the exact never-enrolled normal-release proof, or genuine existing native-zero cleanup followed by actual Kubernetes GC. The server retains its durable barrier through exact Pod/map UID/RV deletion, absence and publication/ledger rereads; it never fabricates a native-zero receipt or absent map snapshot. Go rejects null/object evidence and independently reads both compiled names as actual404 before reservation custody reconciliation. A present map, unknown outcome or denied coordinator response remains held. See `WIRE_CONTRACT.md` for both exact outcomes.

Reservation service `SetNativeCustody(reader, guard)` must be wired to the same protected coordinator. `NativeReservationCustody.MayDeleteReservation` gates every reservation-pod deletion and must include pending/enrolling/enrolled/releasing allocations, including after Pod absence while native-zero is unresolved. Configured deletion re-reads current reservation UID/RV uncached and uses both as API deletion preconditions. A native terminal coordinator cannot activate without this custody guard. Legacy unconfigured reservation behavior remains unchanged. The central bridge must preserve all existing unrelated allocations and exact live pool accounting; this patch supplies no new capacity ledger or release protocol.

## Reproduce offline

`source-manifest.json` records original and patched source hashes, the patch hash and unchanged go.mod/go.sum hashes. The manifest lists every exact modified/added upstream path. No new Go dependencies are introduced. Exact Go1.26.8 is required by upstream go.mod. The private preparation downloaded the official Linux AMD64 archive and verified SHA256 `d0f743b33e8d8945e6b1f432edd15785c70507121d6e2a723b21285eddf8b57b`; that toolchain is outside the repository.

The canonical package is imported without changing its twelve-file Go patch from
cluster source `1060fd1`. The historical coordinator references above describe
that prototype. Current-group SDK source
`36b91d33da4508e54de74a900ee039cd01d14cb4` retains the same closed eight-operation
wire protocol; its typed v3 authority and placement context are validated by the
Python coordinator, not invented by this Go bridge. This package does not prove
live current-group scheduling or production qualification.

From this directory (Python 3.12+):

```sh
python3 -B recipe.py
python3 -B -m pytest -q test_recipe.py
python3 -B recipe.py --build \
  --source /absolute/path/to/CLEAN_LOCAL_UPSTREAM \
  --output /absolute/path/to/NEW_PRIVATE_BUILD \
  --toolchain-archive /absolute/path/to/go1.26.8.linux-amd64.tar.gz
```

The default does no file or process I/O. Explicit build verifies a clean local
checkout at the exact upstream commit (including refusal of ignored/untracked
files), then clones it without hardlinks. It never edits that source. The target
must not exist. No fetch/download is performed: source, toolchain archive and
module cache must already exist. `GOPROXY=off`, `GOSUMDB=off`, `GOTOOLCHAIN=local`
and `-mod=readonly` refuse missing dependencies or toolchain substitution.

The complete original file hashes and dependency hashes are checked before
`git apply --check --index --whitespace=error-all`; exact full-file preimages
exclude offset/fuzz drift. All twelve postimage hashes, lengths and changed-path
membership are checked after application and after build. The official archive
SHA256 is verified before extraction into the new build directory. Four complete
Go packages run with `GOMAXPROCS=4` and `-p 2`. Two Linux AMD64 builds use
`CGO_ENABLED=0`, `-trimpath`, `-buildvcs=false`, and an empty build ID; their bytes
must match. Source provenance is recorded in the receipt rather than relying on
Go's historical dirty-upstream VCS label. The input checkout is reverified after
all work. No binder binary is executed by the recipe.

The private output contains `recipe.log`, `recipe-receipt.json`, `binder`, and
`binder.rebuild`. The checked-in `verification.json` and `test-results.log` below
remain the earlier prototype evidence; `local-build-verification.json` records
this hardened recipe's separate reproducibility gate.

Focused tests exercise final-annotation/ACK/Binding ordering; missing coordinator denial; Pod UID/spec, Node UID, BindRequest generation and ACK changes; cancellation and lost responses; hold-before-fence-close; exact old PodUID/RV cancellation; native-zero holds; map replacement and exact cleanup; reservation replacement; and preserving the prepared request generation. The fake coordinator validates only the Go seam/order, with synthetic placeholder ACK data. It is not an SDK authority validator or accepted allocation receipt. The complete upstream tests for all affected packages also pass; TLS transport tests exercise closed messages, no redirects, duplicate/oversized responses, token rotation and disabled defaults.

The fresh successor recipe passed all four packages and built a98,713,592-byte binder with SHA256 `8c451ff2f7f9dedb02febd1d73de8d92ffb3fab2a38214afabf68062aaa2b314`; patch SHA256 is `9f6511d36d2cc1f910ab940ccb1186ac5936dec2e061e447740113965e9b220b`. go.mod/go.sum and dependency versions are unchanged. The rendered metadata text trims trailing whitespace; the private exact recipe receipt retains raw `go version -m` output.

Activation still requires installing the tested disabled coordinator/Hub pending hook, exact signed-SA RBAC/config/bootstrap and every writer guard, current operator/node maintenance fencing, post-Bind strict CRI/cgroup/native-cap readiness, and supervised live/GPU evidence. Root's separate actual CPU-only k3s1.34.9 acceptance qualified Pod UID/RV Binding CAS, not NodeUID API CAS or native cap sealing. These artifacts remain an offline implementation handoff.

## Local OCI packaging

`Dockerfile` inherits the exact inspected stock binder image
`ghcr.io/kai-scheduler/kai-scheduler/binder@sha256:1d10b1b212faddab22cdaea5da2f9d17e1d4154d68d7d0f4bfc44dc6a343624b`.
It changes only `/workspace/app` to the reviewed static binary and adds three
provenance labels. Stock user `65532:65532`, entrypoint `/workspace/app`, workdir
`/workspace`, environment, CA certificates and NOTICE are retained. No Go build,
package install, shell or credential is added to the image.

The base image must already be available locally. With the binary and successful
receipt produced above:

```sh
python3 -B oci.py
python3 -B -m pytest -q test_recipe.py test_oci.py
python3 -B oci.py --build \
  --binary /private/build-03/binder \
  --receipt /private/build-03/recipe-receipt.json \
  --output /private/NEW_OCI_OUTPUT
```

Default invocation is inert. Explicit packaging verifies the exact binary,
ELF static proof, original twelve source-file pins and successful Go test/build
receipt. It requires the pinned base config, builds twice with
`--pull=never --network=none --timestamp 0 --no-cache`, and compares image IDs.
It compares every exported filesystem entry except `/workspace/app`, including
ownership, mode, link target and content hash. The installed binary must have
exact bytes, uid65532/gid0 and mode0755. It then executes only `--help`, as the
inherited nonroot user, with no network, read-only root filesystem, no Linux
capabilities, no-new-privileges and bounded CPU/memory. This does not start KAI,
read Kubernetes credentials or exercise scheduling/GPU operations.

Output includes `image.oci/` (a local OCI layout), `verification.json`, build
log and installed help output. The local tags are
`localhost/cps-native-kai-binder:qualification-bdf434e-9f6511d3` and its rebuild
suffix. Packaging never pushes an image or applies cluster configuration.
`oci-verification.json` records the independently reproducible local image gate;
publication, coordinated operator ownership, signed coordinator configuration,
and actual scheduler/GPU qualification remain separate Root-owned steps.

## Operator-aware binder ownership

KAI v0.18.1's Config API has no binder extra-arguments or volume fields. Editing
its generated Deployment alone is therefore not a persistent activation path.
`operator_handover.py` renders CAS patches only; it makes no API/process calls.
The intended sequence is:

1. Capture the actual Config, operator Deployment, complete operator Pod list,
   binder Deployment/Service/ServiceAccount, reservation ServiceAccount and any
   `binder-pdb`. Confirm no nonterminal BindRequests and preserve rollback copies.
2. Pause only the operator with the rendered replicas CAS; wait for its observed
   zero replicas and actual absence of all operator Pods, including terminating
   Pods. Other KAI controllers and the existing binder remain running.
3. Remove only the captured Config owner from the four required operands and any
   binder PDB, assigning their management label to `cps-compute-gitops`. Preserve
   every spec and existing UID, particularly both ServiceAccounts. Then disable
   only `spec.binder.service.enabled` in the Config, with UID/RV/value tests.
4. Freshly read all transferred objects and the disabled operand before rendering
   the operator resume CAS. Resume its other reconciliation. Do not start a second
   binder. The existing single Recreate Deployment can now consume reviewed flags,
   token/CA mounts and a digest-pinned image through the cluster deployment source.

The pinned operator's collectible indexes use the Config controller reference;
objects without that owner are outside its current-state set. Its binder operand
returns no desired objects when disabled. This is an explicit ownership transfer,
not a change to KAI's scheduling predicates. Enabled VPA is rejected because it
would require an additional, separately reviewed operand transfer.

The helper refuses running/unobserved operators, remaining Pods, missing/extra or
foreign-owned operands, deletion/replacement drift, overlapping binder strategies
and incomplete resume readback. Partial failure must leave the operator paused
until either all transfers finish or exact recorded ownership is restored; never
resume a disabled operand while any of its still-owned resources can be pruned.
Rollback stops any successor binder first, restores captured fields/ownership and
enables the stock operand before restoring operator reconciliation. No GPU driver,
node cordon, workload Pod or storage setting is changed by these metadata/Config
patches. An applied handover and successful live binder health check are separate
gates from these offline tests.

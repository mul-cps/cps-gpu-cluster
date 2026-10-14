# Disabled native KAI terminal binder staging patch

This is an offline patch/build recipe for official KAI v0.18.1 commit `bdf434e5e9201cccf4e05fad04d814363653f692`. It does not install a coordinator, configure a cluster, produce/publish an OCI image, grant GPU access or qualify the pending native route. The CLI is inert by default. A marked Pod is denied when the required coordinator, uncached reader or reservation custody bridge is absent. The application wiring remains absent deliberately.

The SDK contract is pinned to cps-compute `0451fd9cc9bcb5ba55b2d35c5aca84fc52f5fad3`. Its compiler marker is `cps.compute/native-pending=kai-v0.18.1-gpu2-cm/v1`. That marker selects this fail-closed path; it is not authority. Authenticated protected registry/current central grant and attempt checks must authorize the actual full Pod. Only the existing bounded GPU2 5/10 GiB ConfigMap route is represented; no20GiB, DRA, SM, NUMA, legacy group-list fallback or new owner/profile permissions are added.

## Exact upstream seam and interfaces

Pinned original `pkg/binder/binding/binder.go:42-94` runs reservation, all PreBind plugins, then `patchPodBindingAnnotations` at76-79. The patch inserts a dedicated terminal call after that persisted patch and before original Binding83-89. Appending an ordinary PreBind plugin would run too early. Original `plugins/interface.go:17-25` has only Name/PreBind/PostBind/Rollback; original `plugins/state/state.go:6-9` has actual binding annotations and reserved GPU ID strings. Both interfaces stay unchanged.

New `Binder.SetNativeTerminal(reader, authorityNamespace, coordinator)` supplies an uncached `mgr.GetAPIReader()` and a protected coordinator implementation at startup. Original `cmd/binder/app/app.go:94-98` constructs a cache-backed client, so supplying `app.Client` as a terminal reader is insufficient. No startup wiring or credentials are included here.

`NativeTerminalCoordinator.Prepare` receives fresh upstream Pod/Node/BindRequest/BindingState types and returns a retained `NativeAllocationFence`. It must run the SDK `build_pending_allocation_record`, publish/read back immutable v1 enrollment and ACK, and retain the lifecycle/capacity writer fence. `NativeAllocationFence.ValidateCurrent` must independently re-read full raw API documents, registry/maps/enrollment/epoch/current central authority and call `validate_pending_allocation_ack` plus `validate_current_pending_allocation`. Typed Go Pod serialization is not a substitute for full raw API document fidelity or the SDK's complete P/B hashes. ConfigMaps bind UID/RV/data hashes, with no invented generation field.

The patch verifies that final annotations are actually persisted, then reads the actual immutable ACK using its exact authority namespace, name, UID and RV. It re-reads the current Pod/Node/BindRequest generations, checks actual reserved GPU UUID without index inference, and sends an exact closed unstructured `v1/Binding` body. `ValidateBinding` must call SDK `validate_pending_binding_request` on that actual body. Unstructured encoding prevents typed ObjectMeta's `creationTimestamp:null` from expanding the strict reviewed schema. The body carries actual PodUID/currentRV and exact approved NodeUID. The retained fence is closed only after successful accepted-Binding publication or a bounded independent-context Hold attempt. A lost Binding response remains held.

Kubernetes v1.35 [BindingREST](https://github.com/kubernetes/kubernetes/blob/v1.35.0/pkg/registry/core/pod/storage/storage.go#L162-L210) preserves Binding UID/RV and uses both as Pod storage preconditions. This source review does not verify installed K3s behavior. Target NodeUID is sent and strictly compared by the coordinator; API storage assigns `Target.Name`, so Target.UID alone is not a Node replacement precondition. The protected admission/lifecycle fence and unchanged actual post-Bind nodeUID/epoch/native-cap gate remain required. No pre-Bind ACK claims CRI/cgroup/cap sealing.

## Cancellation and cleanup

Original controller `bindrequest_controller.go:162-168` rolls back every Bind error, and original GPUSharing.Rollback170-221 deletes maps by name. Marked attempts now return `ErrNativeCustodyHeld`; the controller skips unconditional rollback and status writes that would invalidate the ACK's prepared BindRequest generation. Other controller behavior remains unchanged.

Explicit `Binder.Rollback` on a marked attempt enters controlled cancellation. If the exact PodUID still exists, it first asks the coordinator to retain custody, then requests deletion with actual UID and current RV preconditions. Even DELETE success returns held. Cancellation has its own bounded context so cancellation of the caller cannot silently skip the hold. A replacement Pod with the same name is never deleted or patched.

Only after a later uncached absence/replacement observation and coordinator `CleanupMaps` proof of old PodUID absence plus native-zero may the patch remove the two exact compiler-named ConfigMaps. It checks their current UID/RV and exact Pod owner, and deletes with UID/RV preconditions. It does not patch the replacement/absent workload's GPU-group labels. Unknown native-zero or map replacement remains held.

Reservation service `SetNativeCustody(reader, guard)` must be wired to the same protected coordinator. `NativeReservationCustody.MayDeleteReservation` gates every reservation-pod deletion and must include pending/enrolling/enrolled/releasing allocations, including after Pod absence while native-zero is unresolved. Configured deletion re-reads current reservation UID/RV uncached and uses both as API deletion preconditions. A native terminal coordinator cannot activate without this custody guard. Legacy unconfigured reservation behavior remains unchanged. The central bridge must preserve all existing unrelated allocations and exact live pool accounting; this patch supplies no new capacity ledger or release protocol.

## Reproduce offline

`source-manifest.json` records original and patched source hashes, the patch hash and unchanged go.mod/go.sum hashes. Seven upstream paths change: three existing files and four additions. No new Go dependencies are introduced. Exact Go1.26.8 is required by upstream go.mod. The private preparation downloaded the official Linux AMD64 archive and verified SHA256 `d0f743b33e8d8945e6b1f432edd15785c70507121d6e2a723b21285eddf8b57b`; that toolchain is outside the repository.

From this directory:

```sh
python3 recipe.py
python3 recipe.py --prepare NEW_PRIVATE_DIRECTORY --go-bin /absolute/path/to/go1.26.8/bin/go --test --build
```

The second command creates a new private local checkout of the existing public upstream repository, verifies the exact Git pin and source bytes, checks/applies the patch, tests all three affected packages, builds the binder CPU binary and writes private receipts. It never changes an existing checkout or invokes the binary/cluster. It downloads public source/dependencies only; it does not create a GitHub repository.

Focused tests exercise final-annotation/ACK/Binding ordering; missing coordinator denial; Pod UID/spec, Node UID, BindRequest generation and ACK changes; cancellation and lost responses; hold-before-fence-close; exact old PodUID/RV cancellation; native-zero holds; map replacement and exact cleanup; reservation replacement; and preserving the prepared request generation. The fake coordinator validates only the Go seam/order, with synthetic placeholder ACK data. It is not an SDK authority validator or accepted allocation receipt. The complete unchanged upstream tests for the three affected packages also pass.

Activation still requires a reviewed authenticated coordinator transport, protected immutable publication and staged-map admission, actual SDK raw-document comparisons, distributed lifecycle/capacity fencing, startup bridge wiring, current Binding API race qualification, post-Bind strict native enrollment/cap sealing, and supervised live/GPU evidence. Until those exist, this artifact is an offline implementation handoff only.

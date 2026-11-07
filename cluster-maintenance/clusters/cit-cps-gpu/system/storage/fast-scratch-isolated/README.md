# Isolated NVMe scratch provisioner

This Fleet bundle adds a second Local Path Provisioner with its own namespace,
ConfigMap, service account, RBAC, and provisioner identity. It creates the
opt-in `fast-scratch-isolated` StorageClass for new claims. Its node-path map
allows `/mnt/nvme/scratch` only on the four GPU workers and refuses requests on
other nodes.

The K3s packaged `local-path` provisioner, its `local-path-config` ConfigMap,
the legacy `fast-scratch` StorageClass, and all existing PV/PVC bindings remain
outside this bundle. No workload or existing PVC is migrated automatically.
The chart is vendored from rancher/local-path-provisioner v0.0.36 at commit
`5d4bfc84b32cd9c5f56ed3aba921b1a3924ea2f0` under its Apache-2.0 license; both
the controller and helper images are pinned by digest.

Before a workload adopts `fast-scratch-isolated`, verify the Fleet bundle is
Ready, the controller is Ready, and a disposable claim binds on an eligible GPU
worker and is rejected on an ineligible node. Then update only the intended
new-claim templates to request `fast-scratch-isolated`. Existing claims stay
bound to their original PVs and storage class. A separate maintenance plan is
required if the legacy `fast-scratch` class or its existing claims are ever to
be retired.

This bundle is intentionally independent of `storage-classes` so it can stage
while that bundle is blocked on the K3s-owned `local-path-config`. The current
`storage-classes` Helm release manifest still contains that ConfigMap; removing
it from the old release source could prune the live object. This change leaves
that release source untouched and does not claim to clear its dependency. A
separate, reviewed Helm ownership transition is required before removing the
ConfigMap from that release.

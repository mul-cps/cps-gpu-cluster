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
while that bundle is blocked on the K3s-owned `local-path-config`. The checked-in
ConfigMap carried Helm's `resource-policy: keep` in handover stage 1. That
stage changes only metadata: its data remains identical to the current Helm
release manifest. It does not remove the ConfigMap or clear the dependency.
Fleet currently reports the ConfigMap as outside this BundleDeployment's
object-set inventory, but that is a monitor status, not a dependency on this
bundle's deployment: `storage-classes` declares no `dependsOn`, and Fleet checks
only declared dependencies before running its Helm upgrade. Stage 1 follows the
non-force Helm patch path; it has not been applied to the live cluster as part
of this change. Fleet `Ready` may remain false because the K3s object-set owner
marker is still different.

This branch is stage 2 and must only be deployed after the deployed
`storage-classes` release manifest and the live ConfigMap both show
`helm.sh/resource-policy: keep`. Confirm the live object is still owned by the
K3s `local-storage` Addon, the ConfigMap data is unchanged from the stage-1
snapshot, the provisioner is healthy, and existing PV/PVC bindings are intact.
If the live keep annotation is absent, do not remove the manifest: Fleet's
embedded Helm 3 checks the live annotation before deleting an omitted resource.
After stage 2, verify the release no longer contains the ConfigMap while the
K3s-owned object, provisioner, and all existing claims remain intact.

The JupyterHub bundle depends on `storage-classes`. A non-Ready dependency can
block a future JupyterHub deployment, but Fleet checks dependencies before
calling Helm and does not uninstall or roll back an already deployed release
when dependency readiness changes. This handover does not change the Hub chart
or request a Hub rollout; existing Hub workloads remain on their deployed
release.

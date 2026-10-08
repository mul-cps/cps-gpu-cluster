There is no currently enabled MIG device on GPU2 to subdivide online. A fresh
read-only query returned R580.95.05 and current/pending MIG Disabled on both
`GPU-16128952-b438-556a-00bb-93039ee24e56` and
`GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6` (A100 PCIe 40 GB).
No mode command, reset, reboot, instance creation/deletion, Pod restart, node
label or DaemonSet mutation was performed.

NVIDIA documents that setting A100/A30 MIG mode requires a GPU reset; after
enablement, instance management is dynamic. On Ampere passthrough VMs, the
hypervisor can prohibit the reset and a VM reboot may be necessary. GPU2 is a
QEMU/Q35 passthrough VM and hosts 55 running CPU/PVC/system Pods. Consequently,
this audit does not prove a reset/reboot-free path from its current disabled
state. The existing R580 driver already supports MIG: R615 is not an initial
MIG prerequisite. [NVIDIA deployment considerations](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/deployment-considerations.html),
[Ampere enablement and VM limitation](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/getting-started-with-mig.html).

For a future GPU already in MIG mode, a supported API building block exists:
query possible placements, create a GI at one free compatible placement, then
create its CI. Deletion targets an exact unused CI/GI; the API rejects active
instances with `IN_USE`. Reset/unbind invalidates handles and is excluded.
This supports an operator algorithm that leaves existing active GI/CI identities
unchanged; it does not prove this cluster's Kubernetes allocation continuity.
[NVML instance API contracts](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlMultiInstanceGPU.html).

That conditional algorithm must:

1. Discover exact GPU UUID, current/pending enabled mode, existing GI/CI IDs,
   MIG UUIDs, placements/profiles, active processes, assigned Pod/container UIDs
   and device-plugin allocations. Require a placement that is genuinely free
   and legal for the requested profile. Free aggregate memory alone is not
   enough: profile alignment and fragmentation may prevent placement.
2. Lock mutations per physical GPU and retain a generation/provenance journal.
   Revalidate occupancy immediately before one create. Never destroy, relocate,
   resize or reset an active GI to make room. Reject or queue when placement is
   unavailable. GI size choices are hardware profiles, not arbitrary GiB.
3. Create exactly one new GI/CI at that placement through privileged operator
   control, returning its exact IDs. Keep normal workloads from receiving the
   `mig/config` management capability. Existing active GI/CI IDs, MIG UUIDs,
   processes and continuous CUDA result/checksum must stay unchanged.
4. Retire only a journal-owned idle CI, then its idle GI, after allocations and
   live processes are absent. Re-read identity/placement before destroy; treat
   `IN_USE` as a refusal. Never issue global instance-delete commands or a full
   geometry replacement.

MIG Manager is not the online control path for that algorithm. NVIDIA states
that it stops operator GPU clients while applying a new geometry; the current
intent is `all-disabled`. A future node-only manual control qualification must
first ensure that the existing manager cannot reconcile those devices back to
the default geometry. No disable or label change was attempted here.
[MIG Manager behavior](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/25.10/gpu-operator-mig.html).

Kubernetes resource publication has two additional blockers:

- The actual v0.18.0 device plugin and GFD both set `MIG_STRATEGY=none` in their
  environment. Their config-manager watches `nvidia.com/device-plugin.config`
  and can signal the node process, but selecting the existing `mig-mixed` key
  alone cannot override that environment. Upstream priority is command line,
  environment, then configuration file. A future GPU2-only mixed plugin/GFD
  deployment would need separate review; global ClusterPolicy/DS edits are
  excluded. [Pinned v0.18.0 configuration precedence](https://github.com/NVIDIA/k8s-device-plugin/blob/v0.18.0/README.md#as-a-configuration-file).
- In v0.18.0, `ListAndWatch` publishes the resource manager's existing device
  map and updates health, while its NVML health subscription covers Xid/ECC
  events. These paths do not establish discovery of newly created/deleted GI
  topology. A plugin restart or reinitialization plus CDI refresh is therefore
  a candidate refresh step, not proven online continuity. It must be node-only
  and preserve stable existing device IDs and kubelet allocation checkpoints;
  refreshing labels/resources is not itself proof that active CUDA survives.
  [Pinned ListAndWatch implementation](https://github.com/NVIDIA/k8s-device-plugin/blob/v0.18.0/internal/plugin/server.go#L265-L284),
  [Pinned NVML event mask](https://github.com/NVIDIA/k8s-device-plugin/blob/v0.18.0/internal/rm/health.go#L66-L104).

A future bounded acceptance test must run one long-lived client on an existing
GI, record allocation identity and device memory/checksum/kernel progress,
create and remove only a separate free GI/CI, refresh discovery on GPU2, and
verify the existing client never restarted or lost progress. It must also show
new allocatable resource counts and a second exact-MIG-device client, then
clean only that new instance. This is still an unexecuted acceptance plan.
Initial enablement/reset permissions and preservation of GPU2 CPU/PVC services
must be resolved before such a test can be authorized on the current node.

R615 remains unapplied. Its managed-memory accounting gap is recorded by the
parallel primary-source researcher; upgrading is not an established isolation
fix. Neither R615 nor this conditional MIG plan activates dynamic sharing.

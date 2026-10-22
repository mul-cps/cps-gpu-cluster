# Pinned R615 driver rollout

User-directed standardization on **615.71.09**, matching the working GPU2
release. This is NVIDIA's unmodified image, not a custom driver build:

```
nvcr.io/nvidia/driver@sha256:bc7572b7f14177c467e4dd8b66c4f4535f462ea9cf6a65cebd7603cc966ebbd7
```

The manifest reuses GPU2's working driver/firmware specification. It selects
only nodes explicitly labelled `cps.unileoben.ac.at/driver=615.71.09`.
GPU2 retains its original DaemonSet and is not selected. The existing firmware
path name is retained intentionally; changing a name is not part of recovery.
The API-mutating driver manager is absent: the operator manually quiesces each
node before activation. The ordinary managed-driver label must remain false
on migrated nodes to prevent competing driver owners.

For each node, in order GPU3, GPU1, GPU4:

1. Save original labels/schedulability. Cordon and verify no user GPU workloads.
2. Disable managed driver and GPU operands; wait for their Pods to disappear.
3. Verify actual host NVIDIA clients and loaded modules are absent or safely
   quiesced before activation. Never forcibly unload a module with live users.
4. Activate the exact driver selector. Verify official image digest,
   615.71.09, both GPU UUIDs and MIG disabled.
5. Restore original operand labels except managed driver; verify plugin GPU
   registration and run vector addition separately on each GPU.
6. Restore original schedulability only after successful validation; then
   proceed to the next node. Keep a failed node quarantined for investigation.

No host reboot, MIG reconfiguration, forced GPU reset, user Pod deletion or
changes to GPU2's qualified driver/isolation configuration are required.
This bounded recovery does not qualify broader sharing/packing on new nodes.

Latest published standalone release and container availability differ: on
22 October NVIDIA lists 615.71.10, but the registry's newest Ubuntu24.04 R615
driver tag is 615.71.09. Newer versions require separate qualification.

The immutable Ubuntu sources ConfigMap changes only official archive/security
URLs from HTTP to HTTPS. Suites, components and Ubuntu signing key remain
unchanged. An incident probe fetched the same 14.845 MB package at roughly
26.5 MB/s over HTTPS while the concurrent HTTP download averaged roughly
50 KB/s. This is a bounded observation, not a network throughput guarantee.
Driver bytes remain the same pinned official image. Apply the ConfigMap before
the DaemonSet; OnDelete deliberately avoids restarting an active driver Pod.

# Qualified physical GPU inventory

Status: source implementation and offline qualification in progress; not deployed.

The native group pilot currently authorizes one physical GPU. KAI selects a
logical fractional group, while the NVIDIA device plugin chooses the physical
device for KAI's ordinary `nvidia.com/gpu: 1` reservation Pod. The reservation
process reports the device it actually received. That report must remain an
output, not an operator-supplied device selector.

An observed normal workspace start selected the other, unqualified A100. The
native binder correctly held the request before binding or CUDA execution.
Repeated starts until a favorable random allocation are not qualification.

## Design

Maintain a small patch against the pinned NVIDIA device-plugin source. Add an
optional, configuration-only allowlist of canonical physical GPU UUIDs. Filter
the actual NVML inventory before registering resources with kubelet. Continue
to advertise the ordinary `nvidia.com/gpu` resource and each selected physical
GPU exactly once. Keep the existing physical device IDs, health handling and
allocation responses.

An absent allowlist preserves upstream behavior. An explicitly empty list,
malformed or duplicate UUID, or a configured UUID missing from actual inventory
must fail startup. Preserve the absent-versus-empty distinction through the
configuration manager's serialization. With the allowlist enabled, reject MIG,
NVIDIA replication/time-slicing and NVIDIA MPS modes, and discovery backends
that cannot enforce the physical NVML inventory. KAI remains the placement and
sharing owner.

Only cluster operators configure this inventory. User Pod annotations,
environment variables, course memberships and entitlement grants cannot alter
it. The existing native UUID, epoch, resource, enrollment and readiness checks
continue to apply independently.

This changes device-plugin inventory, not the NVIDIA driver. It introduces no
MIG instances or static VRAM partitions. Dynamic VRAM allocation remains the
responsibility of the qualified native execution path.

## Upstream constraints

The observed plugin version is v0.18.0. Its startup calls
`DisableResourceNamingInConfig` before adding default resources. That sanitizer
discards custom resource naming and replicated-device selectors. The replica
parser also requires at least two replicas, so a one-replica configuration
cannot express the required plain physical inventory. Product-name patterns
are not physical UUID selectors.

See the pinned upstream [startup](https://github.com/NVIDIA/k8s-device-plugin/blob/v0.18.0/cmd/nvidia-device-plugin/main.go),
[configuration sanitizer](https://github.com/NVIDIA/k8s-device-plugin/blob/v0.18.0/api/config/v1/config.go),
[replica parser](https://github.com/NVIDIA/k8s-device-plugin/blob/v0.18.0/api/config/v1/replicas.go),
and [device inventory](https://github.com/NVIDIA/k8s-device-plugin/blob/v0.18.0/internal/rm/device_map.go).

## Required offline evidence

- Default configuration remains compatible with the pinned upstream source.
- Configuration and configuration-manager round trips preserve absent,
  explicitly empty, valid and invalid allowlists.
- Inventory enumeration order cannot change the selected physical UUIDs.
- Missing, malformed and duplicate devices fail closed.
- Resource registration and ListAndWatch expose only the selected physical
  devices, once each, with ordinary health handling.
- Allocate rejects excluded UUIDs; supported allocation/CDI responses for
  included devices retain upstream behavior.
- Focused tests and the upstream CPU test suite pass against frozen source.
- A reviewed source patch, upstream revision, reproducible build instructions,
  image digest and installed-binary evidence accompany any activation proposal.

## Live activation boundary

Selecting one of two physical GPUs reduces the node's advertised GPU capacity
from two to one. Physical NVML inventory and GFD labels may still report two.
The existing capacity-two maintenance guards must reject that transition;
they must not be edited to pretend it has already happened.

Before activation, separately qualify KAI's accounting for physical count two
and advertised count one. Review every native qualification declaration and
readiness/census consumer affected by that distinction. Capture actual
preimages, prove the node is idle, retain the current device-plugin inputs and
rollback artifact, and bind the intended capacity change to an explicit
inventory transition. Keep existing notebooks and storage mappings intact.

After actual inventory readback and matching authority/readiness proof, retry
the normal shared-workspace lifecycle and run CUDA only on the approved UUID.
Then complete the controlled 5/20 GiB isolation, import, restart and MPS tests.

A singleton inventory is a pilot prerequisite. Production still requires
independent qualification of all eight GPUs, authority and accounting for
their actual UUIDs, and expansion of the qualified inventory. This document
does not approve a singleton pool as the final platform.

## Scheduler accounting dependency

KAI v0.18.1 prefers the physical `nvidia.com/gpu.count` label for shared-GPU accounting. When the device plugin advertises one GPU but GFD reports two physical GPUs, a half-GPU allocation incorrectly leaves 1.5 GPUs idle. The inventory transition requires a separately tested scheduler patch that caps this count by the present `nvidia.com/gpu` allocatable resource, including zero. Absent-resource MIG/DRA paths retain their existing behavior. This patch and the live transition have not yet been qualified.

## Reproduce the source artifacts

Use clean upstream worktrees at the commits in `source-lock.json` and `scheduler-source-lock.json`, then apply the corresponding patch with `git apply`. Both complete patches passed reverse-application checks against the qualified source trees.

For NVIDIA, run the upstream `cmd-nvidia-device-plugin` Makefile target with `CGO_ENABLED=1`, `GOOS=linux`, `GOARCH=amd64`, `GOFLAGS="-mod=vendor -trimpath"`, the recorded upstream-plus-patch identity, and version `v0.18.0+cps.inventory.527808084182`. Its existing linker flags are required. Replace only `/usr/bin/nvidia-device-plugin` in the pinned stock image. Config-manager forwards the selected configuration file unchanged; it does not need a binary change. GFD and MPS binaries also remain upstream.

For KAI, use Go 1.26.8 and `CGO_ENABLED=0`, `GOOS=linux`, `GOARCH=amd64`, `-mod=readonly`, `-trimpath` and `-buildvcs=false`. Build `./cmd/scheduler` and inject the upstream scheduler version package's `gitCommit`, `gitVersion` and `gitTreeState` fields. Replace only `/workspace/app` in the pinned deployed scheduler image. The full scheduler CPU suite passed before packaging. Binder does not import the changed scheduler package and does not require rebuilding for this patch.

The image references in `inventory-images.json` and `operator-images.json` are qualification artifacts. Their registry manifests and raw configurations were compared to the locally tested images. They are not deployment instructions and are not proof of GPU isolation. The native inventory image's OCI conversion omits Docker's build-only `Shell` field; runtime command, arguments, environment, user and other runtime fields are unchanged.

The next live step requires a new inventory-transition baseline and rollback receipt. Keep existing capacity-two captures and their guards unchanged. Confirm idle native sessions, released global reservations, unchanged protected notebook identity and current operator ownership before changing the pilot's advertised capacity. Qualify placement and CUDA isolation afterwards; a one-device pilot does not satisfy the planned eight-GPU pool acceptance criteria.

## Recorded runtime smoke

`runtime-smoke.json` records the default-inventory image rollout and the initial missing-pull-secret rollback. The cluster credential was verified against the image and made available through `devicePlugin.imagePullSecrets`; no credential contents are stored here. All four plugin pods subsequently became Ready on the exact published image digest, with eight GPUs still advertised. This is a temporary qualification deployment, not GitOps production promotion or CUDA isolation acceptance.

The captured GPU2 node has no physical-count GFD label. Preserve that absence. Its current scheduler fallback already uses advertised allocatable capacity; the accounting patch is still required before restricting inventory on nodes whose physical-count label exceeds their advertised capacity. Do not enable GFD or synthesize a count label merely to fit an older snapshot.

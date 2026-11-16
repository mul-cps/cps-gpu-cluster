# Upstream GPU sharing rollout candidate

This is a runtime preparation package outside Fleet's original watched
`cluster-maintenance/clusters/cit-cps-gpu` tree. It does not replace the gateway,
reservation store, launch adapters, admission policy, custom Binder or node cap
writer. GPU2 remains fenced by its existing accelerator label. The separate GitOps OS pilot bundle is at `cluster-maintenance/clusters/cit-cps-gpu/system/os/gpu2-ubuntu`. No worker is accepted and no legacy allocation custody has been released.

The supplied rollout order is GPU2 → GPU3 → GPU1 → GPU4, one worker at a time.
Ubuntu 26.04.1 and R620.70.06 are fixed targets. MIG remains disabled. Do not
nominate the next worker because a SUC Job/Plan completed.

See [current compatibility and live evidence](../../../docs/operations/upstream-sharing-20261116.md).

## Contents

- `os-upgrade/`: one-shot host-systemd release upgrade and read-only Kubernetes
  preflight. Requires evidence references for every preparation gate, a
  digest-addressed image, an explicitly nominated already-cordoned worker,
  three Ready peers advertising two GPUs each, and no remaining live
  non-DaemonSet workloads on the selected worker except its own SUC Pod.
- `prepare.py os-plan`: emits a separate SUC Plan; never applies it or labels a
  node. `concurrency: 1`, `exclusive: true`, exact hostname plus operation label.
- `prepare.py fraction-postrender`: scopes the upstream chart's generated CR to
  GPU2 plus an explicit runtime label, disables fail-open, enables retroactive
  enforcement and sets the K3s CRI socket. Rejects unexpected/multiple CRs.
- `fraction-values.yaml`: released operator 0.1.9, no SM sharing or version-check
  bypass. Daemon selection is in the CR, **not** Helm's controller nodeSelector.
- `kai-values.yaml`: overlay on captured live values, stock v0.18.1 Binder,
  `NvFractions`, bundled fractioning subchart off, explicit HAMi disable.
- GPU Operator lifecycle and target overlays: preparation only. The lifecycle
  overlay also prevents NFD worker rolling updates. It must accompany complete
  installed operand pins at each 25.10 → 26.3 → 26.7.1 controller step.
- `containerd-nri.toml`, `nvidia-misc.conf`, `workspace-annotations.yaml`: candidate
  integration fragments/contracts, not deployed host configuration or admission
  enforcement. The registered NRI plugin is `gpu-fractioning` (binary: fractiond).

## Local preparation and verification

Requires Python 3, PyYAML, Helm 3 and the exact released chart archives:

```sh
helm pull oci://ghcr.io/kai-scheduler/gpu-fractioning --version 0.1.9 --destination "$CHARTS"
helm pull oci://ghcr.io/kai-scheduler/kai-scheduler/kai-scheduler --version v0.18.1 --destination "$CHARTS"
helm pull gpu-operator --repo https://helm.ngc.nvidia.com/nvidia --version v26.7.1 --destination "$CHARTS"
python3 -m unittest discover -s tests/upstream-sharing -v
platform-staging/gpu/upstream-sharing/verify-candidates.sh "$CHARTS" "$OUTPUT"
```

The verification script renders released charts, merges the KAI overlay with
captured live Helm values when supplied, checks CR fields against the released
CRD and verifies the stock Binder image and disabled HAMi plugin. It does not
claim runtime, kernel, restore or end-to-end workspace qualification.

## OS operation and reconciliation

**User override (2026-11-16): no clone or fresh test VM. Test the rollout directly on real GPU2 using the existing backup.** The pilot authorization receipt records this waiver explicitly; do not claim a clone rehearsal or restore test occurred. The following isolation guidance applies if a rehearsal is separately authorized later: use a disposable clone whose production NIC is disconnected before its first boot. Never boot a cloned production K3s identity on a reachable network;
mask K3s, kured and storage agents before providing isolated package-mirror
network access. Do not connect cloned Longhorn data to production. Record clone
VM ID, network isolation, source snapshot, image/payload hashes, package logs,
target kernel, boot IDs, console access and restore results.

Apply Ubuntu 24.04 prerequisite updates with Canonical's documented process,
install `ubuntu-release-upgrader-core`, set `Prompt=lts` and complete any required
prerequisite reboot on the selected pilot worker. Record the exact commands and
configuration decisions. Do not rewrite repository codenames or use `-d`.
The release payload deliberately refuses a pending prerequisite reboot or a
nonempty `dpkg --audit` result. It uses `do-release-upgrade -f
DistUpgradeViewNonInteractive`; that frontend/configuration handling is part of the explicitly authorized real-VM pilot; unit tests do not qualify it.

Build `os-upgrade/Dockerfile` using an immutable Ubuntu 24.04 `BASE_IMAGE`, publish
it to the approved registry, then record and use its final digest. Do not reuse a
mutable image tag. The image's Python preflight needs only the existing SUC
service account's nodes/pods read permissions; that account currently has
cluster-admin, which this package does not expand.

A root administrator installs a mode-0600 authorization receipt at
`/var/lib/cps-os-upgrade/authorization/OPERATION.json` on the selected worker:

```json
{
  "node": "k3s-wk-gpu2",
  "target": "26.04.1",
  "payload_sha256": "SHA256_OF_EXACT_host_upgrade.py",
  "evidence": {
    "compatibility": "artifact reference and digest",
    "rollout_authorization": "user-authorized direct real-VM pilot; no clone",
    "recovery_backup": "verified existing backup reference plus current configuration backup",
    "console": "artifact reference and digest",
    "prerequisites": "artifact reference and digest",
    "jobs_finished": "artifact reference and digest",
    "custody_cleanup": "artifact reference and digest",
    "storage_evacuated": "artifact reference and digest",
    "maintenance_lock": "artifact reference and digest",
    "peer_health": "artifact reference and digest"
  }
}
```

This receipt is **administrator attestation**, not automatic verification of
referenced artifacts. Do not create it from this example. In particular, retain
unresolved GPU allocations until processes are confirmed stopped and charges
have returned. Verify recovery of local files and both Longhorn disk paths;
completed backup objects alone are insufficient. Coordinate kured and all other
automatic maintenance across all four workers for the whole maintenance window.

After waiting for jobs and moving Longhorn replicas safely, pre-cordon and drain
with standard eviction (PDBs enabled), `--ignore-daemonsets`, **without** `--force`,
`--disable-eviction` or `--delete-emptydir-data`. An emptyDir or PDB block is a
blocked gate, not grounds to add destructive flags. The Plan intentionally does
not set SUC `drain` or `cordon`: SUC would otherwise uncordon at Job completion.
The node must stay cordoned until full worker acceptance. Retain a separate GPU
placement fence throughout OS, driver and enforcement work.

Render the Plan with `prepare.py os-plan --node k3s-wk-gpu2 --operation OPERATION
--image REGISTRY/IMAGE@sha256:DIGEST`. Once preparation evidence passes, put the
rendered Plan in a dedicated Fleet-managed OS bundle with `fleet.yaml` and
`kustomization.yaml`. Preserve Rancher's existing K3s Plans and ownership. Do not
publish placeholder images or a pre-nominated active bundle. Add the matching
`cps.unileoben.ac.at/os-upgrade=OPERATION` label only to the selected worker after
all preparation gates pass.

SUC completion means **host operation submitted**, not Ubuntu upgraded. The
payload is copied to `/var/lib/cps-os-upgrade/payloads/SHA256.py`, then runs as
`cps-os-upgrade-OPERATION.service`. State, receipt, upgrader output and systemd
output are retained under `/var/lib/cps-os-upgrade/OPERATION/`; Canonical also
keeps `/var/log/dist-upgrade/`. It never automatically reboots or retries.

Run `status` through the copied payload after any disconnect. A duplicate
submission is rejected even if systemd's reply was lost. After a confirmed
`reboot-required` state, arrange the selected worker's reboot through the
coordinated maintenance process, then run `reconcile`. A reboot before confirmed
upgrade completion becomes `unknown`; do not erase state or choose a new
operation ID to force a retry. Failure recovery is a verified restore, never a
release downgrade or restoration of stale authoritative Longhorn replicas.

`os-verified` means only the exact Ubuntu release and package audit passed after
a changed boot ID. Networking, mounts, K3s/containerd, storage writes, driver,
CUDA, reservation cleanup and workspace acceptance remain separate gates.

## Runtime cutover after OS acceptance

Preserve installed operand image/env/config pins while stepping the GPU Operator
controller through supported adjacent major releases. Compare rendered
ClusterPolicy and all DaemonSet strategies before reconciliation; the supplied
lifecycle overlay alone cannot preserve fields omitted from Helm values. New
operands must stay disabled. A changed DaemonSet template with OnDelete does not
authorize deleting peer pods. Preserve NFD image pins too.

Quiesce the selected worker's old loader, MPS clients and cap writer only after
confirmed allocation cleanup. Remove only proved-obsolete worker-specific
module/firmware overrides. Never force module unload or reset a GPU with users.
Install one driver owner using the built/published R620 Ubuntu 26.04 artifact,
verify module/firmware/NVML/MPS match and `RmMemacctMode=1` is actually effective.
Do not infer accounting enabled from the absence of `dmem.*` files.

Install standard toolkit 1.20.1 and device plugin/GFD 0.20.1 deliberately on the
selected worker. Merge the NRI fragment into the existing K3s
`config-v3.toml.tmpl` and inspect the regenerated config/socket after restart.
Protect the mandatory-plugin annotation from tenant edits. Recheck CPU/storage
workloads and missing/disconnected/hung-plugin behavior.

Install Fractioning independently before enabling KAI NvFractions. Its default
CR is a Helm post-install/upgrade hook: ensure the Fleet post-render path changes
the **hook CR**, not just the ordinary chart manifests. If that cannot be proved,
use the verified render as a raw Fleet bundle with CRD ordering. Do not install
the unmodified chart with its all-GPU selector. Only label GPU2
`cps.unileoben.ac.at/fractioning-runtime=upstream` after old runtime ownership has
been removed. The selector still requires GPU2's exact hostname.

Drain old Binder requests/custody before replacing the custom Binder. Maintain
one authoritative CPS/CIT reservation store. The gateway/Hub adapters and
admission controls must emit/protect the workspace contract, constrain new and
restarted shared sessions to qualified capacity, and prevent fallback to legacy
nodes. These adapter, admission and qualified-pool changes are **not implemented
by these overlays**; keep shared starts fenced until they are delivered and
qualified. Existing allocations retain their original custody.

## Acceptance still required

| Gate | Required evidence |
| --- | --- |
| OS/management/storage | Clone and real worker Ubuntu/kernel, K3s/containerd, Rancher, Longhorn, mounts, package audit, read/write, backup and restore |
| Placement | Both cards, mixed 5/10/20 GiB profiles, fill A→B and B→A |
| Isolation | Child-process aggregation, typed OOM/recovery, independent peer progress |
| Driver boundary | Managed/UVM, raw APIs, altered environment, MPS bypass, pools, VMM/imports/IPC, nested-cgroup escapes |
| Lifecycle | Missing/disconnected/hung NRI, startup races, restart/reboot, duplicates/lost replies, ambiguous cleanup, process/cgroup reuse |
| Release ordering | Confirmed process shutdown and charge return before reservation release |
| CPS/CIT | Start → CUDA → stop → returned capacity, membership removal, retained files, canonical-person allowance across both services |
| Promotion | Explicit acceptance receipt for selected worker and healthy peers, then next nomination |
| Final platform | All eight GPUs, controller cutover ≤60 s, startup burst p95 ≤180 s and maximum ≤300 s; ordinary/distributed/external/teaching/monitoring/recovery/restore requirements |

Managed/UVM must be bounded or rejected at the driver boundary. NVIDIA still
documents managed-memory limitations; an environment-variable shim or library
interceptor does not satisfy that gate. Reproduce any upstream failure on the
exact final artifact, consider configuration/released fixes, then make only the
smallest necessary patch and repeat full artifact qualification.

R620 cgroup routing, SM sharing, supported hardware SM partitions, burstable
limits and dmem each get independent qualification after the first usable fixed
profile cycle. Retire superseded custom runtime only after equivalent acceptance;
preserve its source and causal failure evidence until then.

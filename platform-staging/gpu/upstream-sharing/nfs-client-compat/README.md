# Selected-worker NFS client compatibility configuration

This is a prepared operator helper, not a daemon, boot receiver or live rollout. It persists one standard option:

```conf
options nfsv4 directory_delegations=N
```

Linux7.0 exposes `directory_delegations` as a writable boolean, default on, in [upstream delegation.c](https://github.com/torvalds/linux/blob/v7.0/fs/nfs/delegation.c#L30). Module options belong in standard [kmod configuration](https://github.com/kmod-project/kmod/blob/master/man/modprobe.d.5.scd). Kmod combines module/alias options, so contradictory options and command-line spellings are refused rather than resolved by ordering.

The motivating case is retained under `/home/bjoern/artifacts/cps-upstream-sharing-20261116/personal-gpu-B-home-upstream-research-20261118`, with owned failing case `personal-gpu-qa-21eecb4ba3a4`. Released Longhorn1.9.2 dependency source sends operation46 to OP_ILLEGAL, while the new client can request directory delegation. [Ganesha1385](https://github.com/nfs-ganesha/nfs-ganesha/issues/1385) documents this compatibility class and the client option. This helper does not independently prove the individual wire exchange or replace physical acceptance. The100GiB home's separate replica-scheduling problem remains a separate gate.

## Inspection and release

Run on the selected worker using the existing reviewed operator transport. For an existing host-PID maintenance container, enter the selected host's mount, UTS and network namespaces; do not create a new Pod/DaemonSet. Host networking is needed for the local K3s API proxy. The helper reads its own Node through the installed kubelet kubeconfig and `k3s kubectl get --raw`; it creates no credential and needs no broad new RBAC.

Copy `selection.UNARMED.json` to a separate Root-owned release file. For inspection, fill exact node name/UID, boot UUID and kernel. Obtain those from fresh Kubernetes and host observations; never reuse a previous boot's selection. Leave release/operation/evidence fields null:

```sh
sudo python3 nfs_client_compat.py --selection /root/selected-nfs-inspection.json
```

Default inspection changes no configuration, runtime parameter or initramfs. It reports the target's byte hash/mode/owner/inode, loaded parameter, standard modprobe options and selected kernel initramfs contents. It uses installed `lsinitramfs`, or `lsinitrd` when that is the available native tool. No tool installation is attempted. Missing/unsupported tooling holds for review.

Before a separately released persistence operation, Root must accept the runtime-only canary on the same original failing home and unchanged storage options, retained-file read/write and clean recovery, plus peer storage/GPU progress. The NFS option is node-wide, not fixture-only. Preserve active user jobs/mounts; do not drain, unload modules or restart services. This helper requires runtime `N` already active and never changes that runtime value itself. The existing reviewed runtime canary is a separate operation.

Fill `root_release`, a fresh canonical UUID `operation_id`, the accepted canary/peer receipt SHA256 values and exact `expected_preimage` returned by fresh inspection. Review serialization with other host-config writers. Then Root may explicitly invoke:

```sh
sudo python3 nfs_client_compat.py --selection /root/ROOT-RELEASED-nfs-persistence.json --apply
```

Live Node UID/boot/kernel/Ready and host identity are checked again before replacement and afterward. Only Ubuntu26.04.1/kernel7 GPU workers are accepted. Existing prior bytes/owner/mode are preserved in a root-only preimage under `/var/lib/cps-nfs-client-compat/<operation_id>/`; the standard file is appended without discarding unrelated content and replaced atomically with file/directory fsync. Before any target replacement, both backup-directory entries are fsynced in their parents; a failure holds before the configuration write. Configuration symlinks, unsafe parents, changed preimages, contradictory alias/kernel options and custom NFS install overrides hold. The actual `modprobe --showconfig` result must select only `N`.

An existing operation ID is never replayed. A timeout/lost reply or verification failure means unknown/HOLD, with durable intent and preimage retained. Inspect the same operation/file and reconcile; do not rerun with a fresh UUID to conceal uncertainty. No automatic rollback restores potentially stale bytes. Any later Root-approved restore must compare the current file against that operation's `desired_sha256`, preserve mode/owner and unrelated newer edits, and use an atomic replacement; the original preimage is not permission to overwrite subsequent changes. Runtime `N` remains unchanged by persistence or failure.

## Initramfs and cold-boot qualification

The helper NEVER runs a generator or reboot. [lsinitramfs](https://manpages.ubuntu.com/manpages/resolute/man8/lsinitramfs.8.html) lists contents; filename presence does not prove embedded option content.

- If the selected image contains `nfsv4.ko*`, verify the embedded configuration's exact bytes. Missing target entry requires a separately reviewed image update; an existing entry requires content verification before deciding whether any rebuild is needed.
- Identify the worker's installed initramfs generator/backend first. Ubuntu26.04 may expose a dracut-backed [update-initramfs](https://manpages.ubuntu.com/manpages/resolute/man8/update-initramfs.8.html); do not assume the old generator. Prepare only a selected-kernel update (`-u -k <exact kernel>`) under a separate release, with prior boot-image backup/space/recovery checks. Do not update all kernels.
- For initramfs-tools images, [unmkinitramfs](https://manpages.ubuntu.com/manpages/resolute/man8/unmkinitramfs.8.html) can extract a retained image to an operator-controlled offline scratch directory for byte/hash comparison. For dracut use its installed native inspection tools. No extraction/regeneration is performed by this helper.
- If `nfsv4` is absent from the image, root-filesystem modprobe configuration is used on later module loading; still qualify it at the next separately authorized normal maintenance boot. A built-in module requires a separate kernel-command-line proposal and is refused here.

Cold-boot acceptance remains false in every helper receipt. Later acceptance must observe a fresh boot identity, loaded parameter `N`, effective configuration, the same persistent home/storage read/write and retained-file witnesses, CUDA/peer progress and ordinary cleanup. Do not reboot/unload a live NFS client merely to test persistence. Retire the compatibility option only after a released server fix is actually serving the affected RWX volumes and the same cases pass; a changed manager version alone is insufficient.

## Separately released native boot-image rebuild

`regenerate_selected.py` retains the exact runner used for the four-worker 2026-11-18 integration. It defaults to proposal-only. This cluster's measured backend is initramfs-tools0.151ubuntu1; dracut-install alone did not indicate a dracut backend. An exact selection binds the current native tool and boot-image hashes, Node/boot identity, original boot metadata, and the completed persistence journal. Run only through a retained standard systemd oneshot after a separate explicit Root release; never through an ephemeral container command that can die with the transport.

The runner obtains native apt/dpkg locks and an operator lock, checks independent or combined filesystem space, retains verified root0600 original images/configuration, and invokes exactly `update-initramfs -u -k 7.0.0-43-generic`. It verifies other boot metadata, unchanged runtime/host identity, retained nfsv4, and exact embedded option bytes after native extraction. It does not install packages, choose another kernel, retry, restore, reboot, or unload a module. A lost reply requires read-only reconciliation of the same systemd unit and operation journal. Successful regeneration remains coldboot-pending.

The public [boot-configuration receipt](../../../../docs/operations/evidence/upstream-sharing-20261116/nfs-client-boot-config-20261118.json) records the actual four serial operations. Their private frozen selections, backups, logs and submit/reconcile transport remain in the Root evidence directory; they are not automatic GitOps actions.

## Offline checks

```sh
python3 -m unittest discover -s platform-staging/gpu/upstream-sharing/nfs-client-compat -p 'test_*.py' -v
```

Tests use temporary roots and fake read-only command boundaries. They cover default inspection, unarmed/stale identity, conflicting options, exact old bytes/mode, symlinks/preimage races, no automatic replay, post-write failure/Node replacement and initramfs decisions. They establish software behavior, not a live NFS fix or boot qualification. No host write/persistence, generator, reboot or source-owner nomination was performed during preparation.

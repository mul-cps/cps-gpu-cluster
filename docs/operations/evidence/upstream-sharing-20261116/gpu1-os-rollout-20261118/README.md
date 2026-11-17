# GPU1 Ubuntu release operation

Standard PDB-respecting drain passed after graceful controller/storage relocations. Current Ubuntu24.04 prerequisites completed without removals, then the deliberate prerequisite reboot was reconciled. Both disk UUIDs/fstab remained exact, package audit/check passed, reboot marker cleared and timer policy restored. Existing full VM backup remains the accepted fallback; the current private configuration archive is a small configuration backup, not a full VM image or restore rehearsal.

The separately owned SUC Plan uses the unchanged GPU2/GPU3-tested payload/image, concurrency1, exact hostname+explicit nomination selector and no automatic uncordon. Only GPU1 was nominated. The host systemd operation is observed running in the linked receipt; SUC Job success proves submission only. Ubuntu26.04.1, post-upgrade reboot, runtime and worker acceptance remain pending. Any lost connection or unexpected boot requires status/log reconciliation before further action, never blind resubmission.

All17 attached Longhorn volumes retained at least two distinct current writable copies outside GPU1. Their degraded redundancy during selected-replica shutdown is recorded honestly; no three-copy healthy claim, global replica policy change, forced detach, replica deletion or stale-copy restore occurred. GPU1 stays cordoned/fenced, and three peers were Ready with two advertised GPUs each at nomination.

Only safe identities/metadata are published. Configuration contents, credentials, private databases and archives are excluded. The operation identity retains the prepared November17 UTC date; this directory uses November18 local date.

# Canonical workspace POSIX permission qualification

Status: bounded checks passed; production rollout remains unqualified.

The workspace RPC requires POSIX/DISCARD datasets, actual UID/GID 1000,
mode 0770, a trivial three-entry POSIX ACL and no default ACL before returning
writable provisioning evidence. Existing incompatible storage is rejected
without rewriting permissions or creating an export. The matching compute
controller requires this evidence before creating a Kubernetes binding.
Deploy the compatible NAS RPC before the matching gateway.

A fresh canonical synthetic dataset was provisioned through the current RPC
import and actual TrueNAS middleware. Restricted, tokenless CPU pods mounted
it through the unchanged NFS address 193.170.30.58. UID 1000 created a 0600
file; UIDs 1001 and 950 were denied reads and writes. After all writers were
removed, archiving set ZFS readonly. A fresh mount returned EROFS on creation
and retained the original file checksum. See the adjacent JSON report.

The namespace was deleted. The Retain PV and read-only synthetic dataset
remain as evidence. No human dataset permissions were changed.

This does not qualify the installed forced SSH transport, authenticated
controller HTTP flow, same-UID isolation, or the full workspace lifecycle.
The gateway source change is a8426ede088b3a2e458eaa177c2ef2d8743b1a2a;
the live gateway still uses qualification-5771df5. GPU sharing remains
unqualified independently of these storage checks.

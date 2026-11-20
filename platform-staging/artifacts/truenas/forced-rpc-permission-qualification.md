# Forced SSH permission evidence qualification

Status: bounded live transport checks passed on 2026-10-07.

The NAS forced command at `/home/truenas_admin/.ssh/cps-workspace-rpc.py`
was backed up by previous content hash and atomically replaced with cluster
commit 17525b5 source. The installed SHA256 is recorded in the adjacent report.
The file is private mode 0600 and is invoked by the existing SSH key restriction.

From the live gateway pod, SSHJSONTransport used its existing restricted key,
strict host verification and TCP 8022 relay path. A fresh synthetic group
provision returned verified POSIX1E/DISCARD, UID/GID 1000, mode 0770 and no
default ACL. Archive and subsequent status both confirmed ZFS readonly.
The synthetic dataset/export remain retained. No human dataset was rewritten.

This completes the bounded forced SSH transport check previously open in
posix-permission-qualification.md. It does not qualify authenticated HTTP
provisioning, Kubernetes PV/PVC binding or full writer shutdown reconciliation.
The production gateway image remains qualification-5771df5.

A matching application candidate a8426ed was built locally with runtime
constraints committed at 658dc4c. The OCI index digest is
`sha256:0b98f7fccb25e6e189693056bff2ad1def7fc276242255ece545e1fb55c01f52`.
It includes SBOM and provenance attestations; dependency checks passed and
all 20 installed application files matched the tested source. The installed
wheel suite passed 240 tests. This candidate has not been promoted or published.

# Isolated V2 live storage qualification

Status: bounded source/controller storage path passed; production gateway unchanged.

The dual-version forced NAS command was installed atomically with a private
content-hash backup. Its exact hashes are in isolated-v2-live-report.json.
Legacy V1 status returned its unchanged archived path. A synthetic V2 group
was provisioned through the real restricted SSH transport using tested source
executed in a transient gateway-pod subprocess. The running gateway process,
configuration and image were not replaced.

The real source controller inventoried live mounts before NAS provisioning,
validated private POSIX evidence, created a real PV/PVC and reached Bound.
An actual tokenless restricted CPU Pod mounted the sibling dataset and created
a 0600 file. It was removed and its absence confirmed before archive. The
controller writer inventory allowed archive, ZFS readonly was verified, and
the controller's RW-client mount verifier succeeded only after EROFS enforcement.
A fresh NFS client read all three retained synthetic files and verified their
checksums. Verifier workloads and read/write probes are gone; PVC removed,
Retain PV Released, dataset retained read-only. No human session or data changed.

Live reprovisioning exposed an API default mismatch: Kubernetes omitted NFS
readOnly=false. Compute commit 3d6de75 now normalizes only that false default;
true readonly remains rejected. Its regression failed then passed, and the
same live group was successfully reprovisioned without replacing its PV.
All 256 compute tests and 13 NAS tests pass. Fixture transport/log parsing and
filename failures are recorded in the report rather than counted as acceptance.

Limits: operator Kubernetes credentials, not production gateway RBAC; no
production authenticated HTTP/Hub lifecycle, cross-group privacy, backup,
permanent parent-mount prevention or legacy-group migration qualification.
The verifier image was the previously pinned Python gateway image. A matching
new release image and controlled service lifecycle qualification remain required.

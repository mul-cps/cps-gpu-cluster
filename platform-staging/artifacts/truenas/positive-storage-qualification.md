# Positive storage API qualification

Status: provisioning passed; archive and full isolation blocked.

Using the installed candidate wheel, an isolated ASGI application exercised
the real internal API and controller code. A real isolated JupyterHub 5 fixture
provided the neutral account role check. Synthetic credentials and canonical
members were confined to fixture state. The real NAS forced SSH transport and
Kubernetes APIs were used; Kubernetes requests used operator credentials.

Registration succeeded, CIT access to the CPS workspace was denied, NAS
provisioning returned private POSIX permission evidence, and the real PVC
became Bound. See positive-storage-partial-report.json.

Archive returned 409. Direct investigation confirmed a running notebook mounts
`/mnt/persistent1/cps_persistent1_shared` writable without subPath confinement.
This parent contains the canonical compute tree. The writer barrier correctly
identified overlapping access. The fixture shutdown observer also returned
false; its exact cause remains unqualified.

Do not bypass the writer barrier or claim group storage privacy under this
layout: existing broad writable parent mounts can reach nested group datasets,
particularly when workloads share UID 1000. A reviewed storage layout/mount
migration is required before activating group storage in production. Preserve
homes and data, inventory references, and stop affected writers before archive.

No human session or dataset was changed. The synthetic PVC was deleted; its
Retain PV is Released and the synthetic dataset remains retained writable.
The isolated Hub was stopped. This is not production gateway RBAC, mounted
archive, identity linkage or full end-to-end qualification.

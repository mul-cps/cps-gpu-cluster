# CPS / CIT compute platform

The implementation uses one shared compute policy and gateway, two JupyterHub
frontends, and **separate CPS and CIT admin applications/databases/OAuth clients**.
Local course management is active in the application. Moodle is planned and disabled.

See the [28 October implementation checkpoint](current-state-20261028.md) for the latest bounded outcomes and next steps.
See the [23 October current state and completion order](current-state-20261023.md)
for the broader live acceptance boundary and remaining production gates.
The [28 October CIT MuJoCo restoration](../../qualification-artifacts/rino-mujoco-restoration-20261028/README.md)
records the later personal desktop recovery and its exact limits.

| Repository | Canonical responsibility | Implementation branch |
| --- | --- | --- |
| [cps-gpu-cluster](https://github.com/mul-cps/cps-gpu-cluster) | Policy catalog/compiler, GitOps, admission, monitoring, deployment and recovery | `feat/compute-platform-v1` |
| [cps-compute](https://github.com/mul-cps/cps-compute) | SDK, gateway, reservations, Hub adapter, Papermill runner, prebuilt Lab addon | `feat/platform-v1` |
| [e2x-course-hub CPS fork](https://github.com/mul-cps/e2x-course-hub) | Admin UI, local providers, assignment/project/workspace APIs, audit | `feat/cps-platform-v1` |
| [cps-jupyter-notebook](https://github.com/mul-cps/cps-jupyter-notebook) | Runtime image release overlay and all notebook variants | `feat/compute-platform-v1` |
| [cit-teaching-platform](https://github.com/bjoernellens1/cit-teaching-platform) | CIT deployment/console settings consuming shared released software | `feat/compute-platform-v1` |

Application/API docs belong to the application repositories. This section describes
cluster deployment and acceptance. The admin fork retains upstream history at
`db04b6f02a54392f78479303bbed326627fa13c5` and pins e2x-hub-rbac
`4683d1a09051f8aa0d38a2e6ab181b4979b246b2`.

## Shared policy and identity

`compute-policy/catalog.json` defines profiles, entitlement bundles, priority values
and labels. `scripts/compile_compute_policy.py` deterministically produces the
versioned policy, queues/PriorityClasses and compatibility lock; CI rejects drift.
All consumers verify and record `policyHash`. Definitions do not grant membership.
GPU profiles and empty image allowlists remain fail closed until qualification.

The eight GPUs are **A100 PCIe 40 GiB**, as verified from all four nodes' NVIDIA
feature labels on 2026-10-05. Nominal 5/10/20 GiB profiles are not measured safe
packing counts; usable memory and HAMi/MPS overhead still require measurement.

Authentik is the authoritative directory for explicit, reviewed CPS/CIT account
mappings to a stable canonical person UUID. Email verification is optional under
the later operator decision; accounts without an email challenge use the reviewed
directory-identity route described in [identity verification](identity-verification.md).
An email match can identify candidates for review, but does not authorize
linkage. The separate `scripts/compute-platform/link-identity-emails.py`
tool retains its verified-address, review and collision checks; optional email
verification does not relax that tool. Existing usernames, PVCs and NFS paths
remain unchanged. Keep private mappings outside Git. Matching usernames, display
names, unverified self-declared addresses or login-time group replacement are not
migration. Direct university federation remains deferred until ICT registration.

Cross-Hub grants resolve to the maximum effective allowance, rather than adding
CPS and CIT grants. Shared GPU workspace reservations consume one allowance from
every canonical member. Reservations are transactional, source-qualified and
released only after the trusted Hub observer confirms shutdown. Expiry is not
shutdown evidence. CPU and independent batch entitlements remain separate.

## Deployment boundary

`platform-staging/` is deliberately outside Fleet's watched
`cluster-maintenance/clusters/cit-cps-gpu` path. Its Helm chart defaults to disabled
and renders no resources. Activation requires released digest images, a matching
compiled policy, private runtime identity/credential configuration and qualification.
Each console runs one replica with its own SQLite PVC and SQLite backup CronJob;
the shared gateway runs one replica with one global durable accounting store.

The candidate workload namespace is separate from the control applications.
Pod Security, scoped admission, resource quota and workflow executor RBAC provide
a lower enforcement layer. The empty admission image allowlist denies execution.
GPU injector host-mount exceptions are not enabled by the candidate admission
policy. Its deny rule must not be broadly removed to make an unqualified injector
work. JobSet launchers remain disabled until distributed retry/cleanup passes.

Production targets are chart **4.4.2**, Hub **5.5.2**, KubeSpawner **7.x**.
CIT was already at 5.5.2/7.1.0 before this change. CPS's baseline promotion is
complete at 5.5.2/7.1.0 with preserved API identities/groups and PVC bindings;
real browser login remains a qualification gate. Hub **6.0.1** remains a separate
qualification target. The gateway and admin branches are implementation artifacts;
there are no pilot, candidate or production release tags yet.

Hera remains the workflow language; Argo executes, KAI schedules. No CPS DAG
language, separate snippet repository or Moodle deployment was introduced.

SeaweedFS is running on the existing TrueNAS with authenticated TLS on port 8333.
Its [deployment and recovery runbook](https://github.com/mul-cps/cps-gpu-cluster/blob/feat/compute-platform-v1/platform-staging/artifacts/truenas/README.md)
records persistence and authorization checks. The existing cluster/NFS addresses
are preserved. [Recorded staging tests](qualification.md#2026-10-05-live-staging-evidence)
verified both Hubs' relay connectivity, authenticated TLS and signed 50 MiB
upload/download with cleanup. Current student notebook artifact acceptance is
recorded in the [completion ledger](production-completion-20261013.md).
Automated retention and matching-version production restore remain separate
qualification gates.

# CPS / CIT compute platform

The implementation uses one shared compute policy and gateway, two JupyterHub
frontends, and **separate CPS and CIT admin applications/databases/OAuth clients**.
Local course management is active in the application. Moodle is planned and disabled.

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

User guidance identifies **email** as the account-linking authority. Use an
explicit, reviewed mapping of verified normalized addresses to a stable canonical
person UUID. `scripts/compute-platform/link-identity-emails.py` validates directory
exports, rejects missing/unverified/unreviewed addresses and duplicate accounts
within a Hub, and preserves explicitly supplied person IDs during email changes.
It never changes existing usernames, PVCs or NFS paths. Mappings contain private
identity data and must be stored outside Git. Matching usernames, display names,
unverified self-declared email or login-time group replacement are not migration.

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
are preserved. Hub-to-S3 connectivity and automated retention remain unqualified.

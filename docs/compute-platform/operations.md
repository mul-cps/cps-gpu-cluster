# Operator deployment and recovery

Fleet watches `cluster-maintenance/clusters/cit-cps-gpu` on main. Merging a change
there is a deployment action through webhook/polling reconciliation; staging
chart/source artifacts outside that path do not deploy. On 2026-10-05 the live
GitRepo had `disablePolling: true`, so the baseline promotion required an explicit
`forceSyncGeneration` increment. Verify the observed commit and bundle state; do
not treat a push alone as deployment evidence or re-enable polling incidentally. Preserve dirty checkouts and implement in isolated worktrees.

## Inventory and backup first

```bash
python scripts/compute-platform/inventory.py /PRIVATE/PATH/new-evidence-directory
scripts/compute-platform/restore-hub-dumps.sh /PRIVATE/PATH/new-evidence-directory
```

The inventory exports no Kubernetes Secrets. Its consistent custom PostgreSQL dumps
contain sensitive identity/grant/configuration data; the directory is private and
must remain outside Git. It records live Hub images, PVC/PV bindings, queues and
Fleet state. The local restore script uses an isolated CPU-only container with no
network access and verifies identity counts. PostgreSQL 18 logical restoration
is a useful check, **not a matching-version Hub launch or an NFS restore**.
Do not disable authenticator-managed groups until reviewed canonical upstream subject mappings
and existing group/grant imports have been seeded and checked against backups.

For the current role-preserving bundles from `backup-hubs.py`, use the separate
matched-image recovery command. First validate the entire private bundle:

```bash
python scripts/compute-platform/restore-hub-backups.py /PRIVATE/PATH/bundle
python scripts/compute-platform/restore-hub-backups.py /PRIVATE/PATH/bundle \
  --execute --output /PRIVATE/PATH/new-restore-evidence
```

Validation checks every manifest size/checksum, private file permissions and a
single immutable recorded database image per Hub before any container starts.
Execution requires those images already cached locally (`--pull=never`). It
uses separate network-disabled containers, synthetic bootstrap administrators,
role replay and `pg_restore --create --exit-on-error`, preserving owners and ACLs.
It leaves the backup untouched and removes the containers and bootstrap env files.
Error diagnostics remain private. The report records restored schema, database
version and user counts; it does not independently compare source rows or prove
connected Hub, OAuth/spawning, NFS, coordinated snapshots or off-host recovery.
The legacy inventory-only helper above does not accept current backup bundles.

The 2026-10-05 CPS baseline rollout reached JupyterHub 5.5.2, KubeSpawner 7.1.0
and OAuthenticator 17.4.0 on chart 4.4.2. Before/after API checks preserved all
six existing users' names, administrator flags, groups and roles, and all 19 PVC
names, UIDs and volume bindings. The Hub Deployment and Fleet bundle became ready;
the OAuth login route returned a redirect. A real browser login remains untested.
Private database dumps were restored into an isolated PostgreSQL container and
matched the CPS/CIT identity counts. This evidence does not qualify NFS recovery,
cross-Hub identity mapping or the full platform release.

Before a Hub chart upgrade, audit named-server slugging, bound PVC names, storage
classes and NFS paths; record old image/application versions and freeze unrelated
configuration changes. Keep running user workloads protected. After reconciliation,
check the actual installed Hub/KubeSpawner versions, API users/groups/roles, PVC/PV
identifiers, OAuth redirect and metrics. Verify a real login and CPU workspace
before reporting complete authentication/storage qualification. A redirect alone
is not an end-to-end login test.

Rollback requires the matching application **and database** backup if migrations
changed the schema. Reverting only a chart tag is not a proven rollback. Console
SQLite backups use SQLite's backup API and integrity checks, one replica and
Recreate rollout to prevent overlapping writers. Console backup PVCs alone are
not offsite disaster recovery; export encrypted backups to reviewed durable storage.
Back up the global gateway control/reservation databases consistently with the
application/policy version; never create independent per-Hub accounting stores.
The candidate gateway backup job locks both databases against concurrent writers
before using SQLite's backup API, validates each snapshot and records image,
policy hash and checksums in a manifest. Failed jobs publish no partial snapshot.
Back up immutable input snapshots and private runtime configuration separately;
restoration must reconcile reservations against actual Hub server shutdown state.

## Candidate activation

1. Pass the full qualification matrix and resolve immutable application/runner image
   digests. Verify the versioned policy and evidence hashes.
2. Install Argo/JobSet and qualify KAI 0.18.1 plus resource-isolator 1.1.0-chart,
   HAMi-core and MPS as a reviewed dependency group. Rendered candidate values live
   in `platform-staging/scheduler`. They are not a live scheduler upgrade.
   Pin the trusted Argo executor digest as `gateway.executorImage`; the admission
   `ComputeAdmissionPolicy` combines it with the catalog's approved workload images. Empty image
   lists stay denied. User containers run as the credential-free `cps-workflow`
   principal with automatic token mounts disabled. Argo init/wait containers alone
   receive the restricted `cps-workflow-executor` credentials. Qualify generated
   Pod mounts and absence of kernel access to executor credentials before activation;
   the shared executor role must never be mounted in user containers.
   Follow [Argo's workflow security guidance](https://argoproj.github.io/argo-workflows/security/)
   for separating automatic user token mounts from executor credentials.
   Install `platform-staging/admission-parameters-crd.yaml` before enabling the
   application chart and binding. This general compute CRD avoids the stopped
   typed ConfigMap informer observed during repeated K3s 1.34.9 qualification.
   Source inspection points to [policy informer cancellation](https://github.com/kubernetes/kubernetes/blob/v1.34.9/staging/src/k8s.io/apiserver/pkg/admission/plugin/policy/generic/policy_source.go#L338)
   and [shared factory reuse](https://github.com/kubernetes/kubernetes/blob/v1.34.9/staging/src/k8s.io/client-go/informers/factory.go#L130);
   it is an inferred diagnosis, not inspection of each API server's cache.
   The executor baseline uses Argo 3.7.18 `argoexec init/wait`, info/text/0 log flags
   and no extra executor arguments. A controller configuration change requires
   updating and requalifying the exact command allowlist. Provision only the
   declared artifact/CA secrets and explicit executor token Secret. None belongs
   in the user container, its environment or its shared process namespace.
   Custom executor environment variables, template ConfigMap offload and arbitrary
   shared executor mounts are denied. Qualify any necessary additional Argo feature
   against the reviewed environment/mount allowlist before admitting it.
3. Apply the mandatory isolator webhook scope patch. The upstream chart's default
   broad opt-out selector with `Ignore` is insufficient for enforcing caps. The
   candidate uses `Fail`, a controlled namespace label and no client opt-out.
   Injected host mounts need an exact reviewed admission/Pod Security exception.
4. Register independent CPS/CIT service OAuth clients and least-privileged service
   credentials with their Hubs; provision separate console SQLite PVCs. Browser
   visitors use OAuth tokens through the console proxy with CSRF protection.
   Keep internal policy and Kubernetes/Argo credentials out of browsers.
   Provision a private gateway TLS certificate for its service DNS name, referenced
   by `gateway.tlsSecretRef`, and a trusted CA ConfigMap containing `ca.crt` at
   `gateway.caConfigMapRef`. Both console URLs use `gateway.url` over HTTPS and
   validate that CA through `SSL_CERT_FILE`. Never bypass certificate verification.
5. Configure gateway `CPS_COMPUTE_CONFIG` from a private secret: policy_file,
   policy_hash, state_directory, argo_url/token environment reference, trusted
   hubs and reviewed canonical_people maps, owner-bound console service token
   environment references, and source-qualified workspace shutdown mappings.
   See the compute repository's runtime docs for the exact schema. Explicit empty canonical maps keep human linkage disabled while email
   verification is deferred. The Argo client uses the projected token file, read
   per request, so token rotation does not require a restart.
6. Mount the compiled policy read-only and activate the digest-only staging Helm
   chart through a reviewed Fleet bundle. Its disabled default emits no workloads.
7. Import reviewed local course/grant records; confirm grant retention through
   login. Replace embedded profile code only after the released adapter enforces
   all required lifecycle and policy behavior. GPU adapter activation remains
   blocked until reservation/injection/idle/age checks are qualified.
8. Provision neutral workspace principals, native Shares, RTC and narrowly scoped
   NFS mounts. Membership removal stops and confirms shutdown, revokes access,
   updates Shares/reservations, then recalculates the selected fixed profile.
   Assignment closure stops writers before an operator makes the archive read-only.
   Never delete research files as an assignment deletion side effect.

## Monitoring

Four Git-owned dashboards cover overview, packing, KAI fairness and teaching
readiness. Existing upstream dashboards remain pinned in their manifests. KAI
ServiceMonitors use inspected service labels/ports. Both Hubs have authenticated monitors with separate metrics-only service
credentials and scoped network access. Live qualification on 2026-10-05 observed
both Hub targets and the KAI binder, scheduler, admission and queue-controller
targets UP. The Argo controller and all four isolator monitors were subsequently observed UP.
The Argo metrics endpoint uses the chart-supported internal HTTP option with
ingress restricted to Prometheus pods on port 9090; API and artifact TLS are
unchanged. Per-container cap telemetry and the short-lived Descheduler CronJob
still require qualification. The dashboards explicitly mark absent/stale
controller series as unavailable; they do not equate VRAM or utilization with
placement-eligible free physical GPUs.

Loki retention is under `loki.limits_config` and enables compactor deletion;
render tests prove the effective 336h configuration. Alloy's DaemonSet discovers
only `spec.nodeName=HOSTNAME`, injected from the downward API. Descheduler remains
slow and opts in only controller-reviewed restartable batch pods, with priority
below 11 and known gang labels excluded. Qualify it against KAI alone and remove
it after the published defragmentation gate passes. No policy PriorityClass or
dashboard alone proves protected-session behavior.

Operational Grafana access is for trusted viewers. Ordinary users obtain authorized
personal/workspace data through the addon. Link control operations to each Hub,
Rancher, Argo and TrueNAS; do not grant users broad Grafana data access to implement
their personal workload view.

### Restricted workspace controller credentials

Enable `gateway.kubernetes.enabled` only for a qualified controller deployment.
The gateway runs one worker and receives an explicitly projected Kubernetes token;
consoles and backup jobs receive no API token. The controller may observe writers
cluster-wide, create retained NFS volumes and source-scoped claims/verifier Jobs,
and manage distributed workloads in `cps-workflows`. It cannot read Secrets or
delete persistent volumes. Admission restricts its volume roots and verifier Jobs.

Set `gateway.storageBridgeSecretRef` to a dedicated Secret containing only the
forced-command NAS key and trusted host keys. Use the private relay service on
port 8022, with strict host-key checking for `truenas.local`. Never use the operator
SSH key. NFS continues using `193.170.30.58`; the overlay carries control and S3.
Pin `gateway.storageVerificationImage` to a tested digest. Verify permissions with
an actual service-account token: Rancher proxy impersonation is not sufficient.
A neutral notebook uses `/workspace`; personal homes retain their existing paths.

### Database restore qualification

The 2026-10-05 live restore Jobs copied the CPS console, CIT console and gateway
backups into isolated temporary directories. They verified recorded image/policy
provenance, database SHA-256 hashes and SQLite integrity, then opened the copies
with the matching deployed application. Each console also rejected the other
console's ownership. Production databases and source backups were untouched.
Console snapshots include schema/user versions and a schema digest. This checks
application readability; it does not qualify offsite recovery, matching-version
Hub startup, human login or workspace reconciliation after a disaster.

### Loki volume recovery

Before scaling or replacing Loki, check both the StatefulSet claim-retention
policy and the PV reclaim policy. The chart now explicitly retains claims on
scaling and deletion. Preserve the original volume, never create a new empty
claim as a substitute for its contents, and record the exact PV/claim binding.

On 2026-10-05 an accidental scale-down removed the old claim under the chart's
previous Delete policy. The original Longhorn volume was protected with Retain
and rebound to a replacement claim. No original volume deletion was observed.
GPU1 had an orphan iSCSI session; Loki was placed temporarily on GPU2 instead of
restarting shared node storage services. Its 50Gi filesystem was full. A separate
PVC expansion to 55Gi restored startup. Recent logs and a query restricted to
seven days ago through 24 hours ago both returned entries. Loki and Alloy Helm
releases subsequently reached Deployed, with Loki 2/2 and Alloy 7/7 ready.

The StatefulSet claim template remains 50Gi because that field is immutable;
existing claim expansion is a separate operation. Check Longhorn allocation
limits before expansion; do not increase global overprovisioning to force it.
The stale GPU1 session and permanent placement still require maintenance review.
Retention compaction is configured for 14 days, but cleanup latency and steady
storage growth require observation before sizing is considered qualified.

The matching-version Hub database exercise restored CPS PostgreSQL 15.17 and CIT
PostgreSQL 18.4, then opened each database with the exact deployed JupyterHub
5.5.2 image through an isolated Unix socket. Transactions were forced read-only,
containers had no network or published ports, and users/groups/services/server
counts matched the dumps before and after. This qualifies matching-version ORM
readability, not Hub process startup, OAuth login or live spawner recovery.

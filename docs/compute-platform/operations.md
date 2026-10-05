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
Do not disable authenticator-managed groups until reviewed canonical email mappings
and existing group/grant imports have been seeded and checked against backups.

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
   See the compute repository's runtime docs for the exact schema.
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
ServiceMonitors use inspected service labels/ports. CPS metrics scraping already
exists; CIT requires its own authenticated monitor/credential and network-policy
qualification before activation. The dashboards explicitly mark absent/stale
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

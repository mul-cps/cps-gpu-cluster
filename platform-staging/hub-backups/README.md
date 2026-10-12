# Hub PostgreSQL backup jobs

This chart is outside Fleet's watched paths. It backs up the actual PostgreSQL databases used by both Hubs, independently of the console/gateway SQLite backups. CPS and CIT use separate jobs, existing namespace-local database credential Secrets, dedicated 1 GiB Longhorn PVCs, and the exact PostgreSQL image digests qualified by isolated restores. No credential values are in this directory.

The chart defaults to disabled and suspended. Qualification starts with the owner values and `--set suspend=true`, followed by one-shot jobs created from each CronJob. Qualified activation uses `--set suspend=false`. Default jobs are confined to database port 5432 and cluster DNS and have no Kubernetes API token or role. Optional fresh capture adds named API reads and explicit API egress. All containers run without root, writable root filesystem or additional capabilities. Pod affinity keeps the backup on the database node. The source database volumes are not mounted.

```sh
helm template hub-backup platform-staging/hub-backups/chart \
  -f platform-staging/hub-backups/cps-values.yaml --set suspend=true | kubectl apply -f -
helm template hub-backup platform-staging/hub-backups/chart \
  -f platform-staging/hub-backups/cit-values.yaml --set suspend=true | kubectl apply -f -
```

Jobs use `pg_dump` custom format with owners and ACLs excluded, validate the archive with `pg_restore --list`, write a checksum/provenance manifest, flush files and atomically publish a private bundle. Partial failures remove their own temporary directory and keep previous completed bundles. Database diagnostics remain inside the job's private temporary directory because they may contain confidential data. Backups contain real Hub user and token records: any export must remain private and outside Git.

## Optional role and ACL capture (not live-qualified)

`roleCapture.enabled` defaults to **false** and remains false in both owner value files. This mode uses a separate, explicitly supplied `roleCapture.privilegedCredentialSecretRef` with `userKey` and `passwordKey`; the reference must differ from the application credential Secret. The job verifies that this identity is already a PostgreSQL superuser. It does not create a role or promote the CIT application account. A superuser credential grants broad database access and requires independent operator review and qualification before scheduling. Keep `suspend=true` for one-shot qualification. Unsuspending this mode additionally requires `credentialQualified=true` and a nonempty private `qualificationEvidence` reference; these declared settings do not constitute restore evidence.

The mode captures `pg_dumpall --roles-only` to a private `roles.sql` and uses `pg_dump --format=custom --create` without excluding owners or ACLs. By default it copies four required, nonempty files from a read-only `protectedConfigurationSecretRef`: `workloads.json`, `configmaps.json`, `secrets.json`, and `running-images.txt`. This is an **operator-supplied configuration snapshot**. Supply its declared `configurationSnapshot.uid`, `resourceVersion`, and `capturedAt`. The manifest records those inputs with `observed_live=false` and checksums the copied bytes; the job cannot verify the declared UID, version, capture time, completeness, or freshness against Kubernetes. Mounting a mutable Secret also does not establish a coordinated database/configuration snapshot.

### Optional fresh named-resource API capture (source only)

`roleCapture.freshApi.enabled` defaults to **false**. When enabled alongside role capture, it replaces the supplied configuration Secret with a dedicated init container. Supply an immutable `freshApi.image` providing `sh`, Python 3 standard-library HTTPS and Linux `renameat2`, an explicit literal IPv4 `apiServerHost` and `apiServerPort`, and exact namespace-local resource names under `resources.deployments`, `statefulsets`, `configmaps`, `secrets`, and `pods`. At least one workload plus nonempty ConfigMap, Secret and Pod lists are required. Include every configuration dependency and the actual current Hub/database Pod names. Completeness means this reviewed named set; the job does not discover other namespace objects. A rolling Pod name change fails closed until reviewed names are updated.

The chart creates only a namespace Role with `get` on those `resourceNames`, a dedicated ServiceAccount and binding. It grants no list, watch, exec, mutation or cluster-wide access. A 600-second projected API token and cluster CA are mounted only in the init container. That container has neither database credentials nor the backup PVC. The database container has no token mount; it receives read-only capture files. HTTPS verifies the CA, ignores proxy environment variables, refuses redirects and limits each API response to 4 MiB. NetworkPolicy adds only the supplied API IPv4 `/32` and TCP port. Verify service-IP versus post-DNAT endpoint enforcement on the deployed CNI before qualification; this source does not promise that arbitrary API addresses work.

The init container captures fresh `List` files and immutable running image IDs, recording schema-versioned `source=kubernetes-api`, `observed_live=true`, namespace, capture time, capture-image digest and each actual object UID/resourceVersion. Every configured Pod must expose all regular containers with repository-qualified SHA-256 image IDs; pending Pods and unsupported digest-only runtime formats fail closed. These observations remain separate from optional operator-declared Hub versions. Missing or denied reads, identity mismatches, incomplete image status, mutable image IDs and failed writes publish no completed capture. Files use mode `0600` in a mode `0700` directory; publication cannot replace an existing capture. API bodies, credentials and diagnostics never enter logs. The subsequent database bundle is still sequential and unqualified for recovery.

Keep `suspend=true` for a bounded one-shot test. Scheduled fresh capture additionally requires the Boolean `freshApi.captureQualified=true` and a nonempty private `freshApi.qualificationEvidence`, as well as the independent privileged-credential gate. These declarations are operator inputs, not evidence generated by the chart. No owner value file enables this feature, no image is selected or published by this change, and no fresh API capture or connected restore has been live-qualified.

Optional `hub.image`, `hub.chartVersion`, and `hub.appVersion` record trusted operator settings when known. Unknown fields are JSON `null`; they are not inferred from the database image or claimed as observed running versions. Review them against the snapshot before a matched-version recovery. The declared PostgreSQL image remains the immutable image running the job. Table-space definitions and files, NFS data, production OAuth, server spawning, connected recovery, capture coordination, and off-host durability are not qualified by this package.

Both modes write only a new private directory with data and manifest files at mode `0600` and the directory at `0700`. Roles, password hashes, credentials, configuration bytes, and file checksums are never printed by the script. Any role dump, database dump, archive validation, or required configuration-copy failure removes the partial directory, publishes no bundle or readiness receipt, and retains existing completed backups. No retention purge runs. `recovery_qualified` remains false in every manifest. The role mode is an intermediate capture capability; its scheduled capture and connected restore have not been exercised with a reviewed privileged credential.

`convert_capture_bundles.py` bridges **two role-mode captures** to the existing dual-Hub restore validator. Run it from this repository checkout with explicit CPS and CIT input directories and a new output name beneath an existing operator-owned mode `0700` directory, all outside Git. Input files must be operator-owned regular files at mode `0600`; symlink paths, extra or missing files, logical-mode inputs, wrong owners, duplicate manifest fields, corrupt checksums, and unsupported/ambiguous database images are rejected. It verifies the original snapshot's database digest against the capture manifest image and fails on disagreement; it does not invent image rows. Source manifests and data are copied byte-for-byte into a private namespace-prefixed bundle; the outer manifest checksums all 14 copied files and links each namespace to its original capture manifest. Source capture times, declared snapshot metadata, unknown Hub versions, and limitations remain in those original manifests. The new `assembled_at` records conversion time only. The tool invokes the unchanged restore **validator**, never a database container or Kubernetes API.

```sh
python platform-staging/hub-backups/convert_capture_bundles.py \
  --cps-bundle /private/recovery/cps-capture \
  --cit-bundle /private/recovery/cit-capture \
  --output /private/recovery/new-dual-hub-bundle
```

Atomic publication requires Linux `renameat2(RENAME_NOREPLACE)` and fails closed if unavailable. Existing outputs are never replaced; copy, validation, or flush failures remove only the tool's new staging/published directory. Conversion validates both provenance forms independently. Fresh schema version 1 requires the exact named scope, matching namespace/object UID/resourceVersion in captured bytes, complete Pod identities and immutable image rows agreeing byte-for-byte with `running-images.txt`. Forged live flags, unknown schemas, missing/extra objects, mismatched versions and mutable images are rejected. It preserves supplied `observed_live=false` or fresh `observed_live=true` byte-for-byte and leaves unknown Hub versions unknown. Conversion itself does not establish capture freshness or coordination between database/roles/configuration or the two Hubs, source row/role/ACL equality, a matched-version connected Hub restore, NFS recovery, or off-host durability. It records `recovery_qualified=false`, `productionQualified=false`, and `coordinated_capture=false`. Synthetic conversion tests demonstrate format compatibility and provenance consistency, not historical authenticity, live privileged capture or recovery qualification.

Run the synthetic atomic-failure and chart tests without credentials or cluster access:

```sh
python -m unittest discover -s platform-staging/hub-backups/tests -v
python -m unittest discover -s tests/compute_platform -p test_hub_backup_chart.py -v
```

The daily schedule is **02:31 UTC**, concurrency is forbidden and the deadline is five minutes. Backups are retained; no automatic deletion runs before an approved off-host durability/retention policy exists. Check PVC usage and failed Jobs, and do not treat an active CronJob as proof that recent backups succeeded. Failure to capture a new bundle does not remove older bundles.

For recovery, export an archive and its manifest using a credential-free reader pod with a read-only mount on the database node. Verify its checksum, restore to a fresh isolated database using the recorded image version, and initialize the matching Hub image against the restored database. Never apply exported production Secrets or start restored Hub services in a connected test environment without an explicit reviewed recovery procedure.

Qualification evidence is private under `/home/bjoern/cps-platform-evidence/2026-10-06/hub-scheduled-backup/`: one-shot Job reports, checksummed job archives, matching isolated restore reports and a controller-trigger report. The restore tests verify Hub schema `4621fec11365`, 17 tables and six CPS/thirteen CIT users. They do not cover row-by-row comparison, PostgreSQL roles/ACLs, production OAuth, server spawning, NFS recovery, off-host durability or a complete platform restore. Those remain release gates. See [Hub recovery evidence](../gateway-qualified/qualification/hub-database-restore.md).

## Operational alerts

`alerts.yaml` supplies five dedicated Rancher Monitoring rules: stale success (>26 hours), absent expected CronJob telemetry, no success telemetry after two hours, suspended backups and failed owned Jobs. Successful historical runs do not suppress a retained failed-Job alert; inspect and resolve the failure. Prometheus confirmed successful-run metrics for both Hubs. Free-space samples for these PVCs were absent during qualification, so this deployment does not claim continuous filesystem-capacity telemetry.

```sh
kubectl apply -f platform-staging/hub-backups/alerts.yaml
python tests/observability/check_hub_backup_alerts.py
```

The checker extracts the Kubernetes rule spec and runs `promtool` syntax validation plus six synthetic metric scenarios. To use the exact deployed Prometheus image, pull the digest named in the checker and run with `--podman`; containers have networking disabled and no cluster credentials. Live rule-loading/health evidence is under `/home/bjoern/cps-platform-evidence/2026-10-06/hub-backup-alerts/`. Loading and evaluating rules does not qualify notification delivery, backup durability or full recovery.

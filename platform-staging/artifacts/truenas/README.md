# SeaweedFS on TrueNAS: deployed artifact service

The dedicated TrueNAS Custom App `cps-compute-artifacts` is **running**, deployed
through authenticated middleware over SSH, without sudo. The existing `pbs1`
application, NFS exports, network addresses and other datasets were not changed.
TrueNAS is 25.10.3.1. Management SSH is `truenas_admin@truenas.local`
(`10.71.1.55`); the existing cluster-facing address is `193.170.30.58`.

Only authenticated HTTPS S3 on host port **8333** is published. Master, volume,
filer, gRPC and administration ports remain inside the application network.
SeaweedFS 4.48 is pinned to the Linux amd64 image digest recorded in `compose.json`.
The process runs as UID/GID 568 with all capabilities dropped, no privilege gain,
read-only root filesystem, a bounded tmpfs, and 2 GiB memory / 2 CPU limits.
This is a single-node service, not an HA storage configuration.

Storage is the new, owned `persistent1/cps_compute_artifacts` dataset, mounted at
`/mnt/persistent1/cps_compute_artifacts`, LZ4, no executable files, POSIX permissions
and a 256 GiB pilot quota. Seaweed data, master metadata and LevelDB filer metadata
are persistent. Config and TLS/S3 secrets are stored in its `config` directory;
S3 credentials and the TLS private key are UID/GID 568, mode 0600. The dataset
root is mode 0750. Other datasets were neither re-permissioned nor overwritten.

## TLS and credentials

Clients use `https://193.170.30.58:8333` from the cluster, or
`https://10.71.1.55:8333` from the management network. `ca.crt` is the public,
service-specific CA; explicitly configure `AWS_CA_BUNDLE` or boto3 `verify` to
that mounted certificate. Do not disable TLS verification or add this CA to a
system-wide trust store. The server certificate covers `truenas.local`, both
existing IP addresses and loopback for its health check. Renew the service
certificate before its one-year expiry; the private CA key is not on TrueNAS.

An operator identity administers buckets. A separate gateway identity has
Read/Write/List/Tagging access to **only `cps-compute`**, the provisioned bucket.
There is no anonymous identity. The gateway's ListBuckets response is filtered;
it cannot read or write another bucket. No browser or ordinary user receives
these credentials. Notebook workers must obtain a narrowly scoped run credential
or signed transfer URLs before production activation; the broad gateway credential
is not appropriate for arbitrary user kernels.

Private credentials and CA/server keys are kept outside Git at
`/home/bjoern/cps-platform-evidence/2026-10-05/truenas-artifacts/private/`, directory
0700 and files 0600. `credentials.json` contains separate `operator` and `gateway`
objects with accessKey/secretKey. Transfer the gateway credential into the
cluster's SOPS-managed Secret through the operator workflow. Never print or commit
it. The Compose configuration references files and contains no credentials.

## Retention implementation and qualification boundary

`lifecycle.json` is applied and read back successfully through the genuine S3 API.
Temporary notebook inputs use 14 days and run artifacts 90 days. Rules match only
`notebook-inputs/` / `run-artifacts/` plus all three tags: the appropriate
`retention=temporary-expirable` / `run-expirable`, `active=false` and
`retained=false`. Missing or conflicting tags do not expire. No blanket bucket
expiration is installed.

The deployed standalone Seaweed server does not run the scheduled native
lifecycle worker. API configuration acceptance therefore **does not prove
expiration runs**. The implemented operator
`scripts/compute-platform/truenas-artifacts-retention.py` provides executable
cleanup with stronger protection: verified HTTPS Argo lookup, exact workflow UID,
namespace and notebook-ID binding, terminal status and completion age, immutable
object ETag conditional deletion, a deletion limit, and dry-run default. Unknown
metadata, missing proof, changed eligibility, API errors, active inputs and
retained outputs are preserved. Completed runs must be marked eligible by a
trusted controller, which adds `cps-workflow` / `cps-workflow-uid` object metadata.
Current uploads without that evidence are preserved.

Configure its private JSON with endpoint, bucket, accessKey, secretKey, ca,
argoUrl, namespace, argoTokenFile and optional argoCa. Run with the released
boto3 environment; `--apply` is explicit and `--max-deletes` defaults to 10.
A scheduler and completion/tag reconciler are **not activated** until live Argo
proof, retention-change coordination and retained-object protection are qualified.
Tag changes and deletion across separate systems are not one atomic transaction;
production retention/retain actions need a shared controller lease or native legal
hold before race-free protection can be claimed.

## Evidence

`qualification.json` records genuine TLS-authenticated put/get/list/delete,
anonymous get/list/put denial, cross-bucket denial, and a retained fixture's
checksum after explicit service stop/start. `retention-fixture.json` records a
real conditional S3 delete of one owned expired fixture while active, retained and
unknown fixtures survived. That test used a simulated clock and a fixture terminal
proof; it does not qualify a deployed Argo controller or 14/90-day scheduler.
Remaining test fixtures are restricted to the owned qualification prefix.

Both CPS and CIT Hub pods, and this workstation, currently time out connecting to
`193.170.30.58:8333`; both Hubs also time out on the management IP. This is a
**cluster connectivity gate**. Read-only NAS inspection confirms a listener on both host IP families and a
route to the existing cluster-facing IP through its gateway `10.71.1.1`. Kernel
firewall inspection requires root and was denied to the SSH admin; that prevents
pinning the timeout to a specific firewall chain. A network owner must inspect
the existing endpoint forwarding/ACL path for TCP 8333. No route, NAT, firewall,
NFS or interface setting was changed. The existing addresses remain authoritative; the network owner must
make the new authenticated S3 port reachable before application integration.

Restore into a separate dataset/application has not been exercised. Successful
restart demonstrates persistence, not backup recovery. No production release,
image promotion or artifact retention qualification is claimed.

## Deployment, backup and recovery

For a fresh host/dataset only, render and inspect with:

```
python3 scripts/compute-platform/truenas-artifacts-deploy.py --private PRIVATE_DIR
python3 scripts/compute-platform/truenas-artifacts-deploy.py --private PRIVATE_DIR --deploy
```

The script refuses an existing dataset or app, uses exclusive creation for secret
files, creates only its dedicated dataset/directories, and applies the reviewed
Compose object via `app.create`. It never overwrites an existing deployment.
Updates must name this owned app and be reviewed separately; retain the pinned
old image, Compose config and application data before changing versions.

Back up using a consistent, complete dataset snapshot:

1. Pause artifact producers and cleanup; wait for uploads to settle.
2. Through middleware, `midclt call -j app.stop '"cps-compute-artifacts"'`.
3. Create a `pool.snapshot.create` snapshot of the dedicated dataset, using the
   current host's `core.get_methods` schema. Include data, master metadata, filer
   LevelDB, config and TLS/S3 identity files together.
4. Replicate the snapshot to an encrypted, access-controlled backup destination;
   snapshot on the same pool alone is not disaster protection.
5. Start the same app revision with `midclt call -j app.start
   '"cps-compute-artifacts"'`; verify authenticated fixture checksum and health.
6. Back up the private CA key separately in the operator vault. Record snapshot,
   image digest, public CA fingerprint and application configuration revision.

For restore qualification, clone/restore the backup into a **new** owned dataset,
use the same pinned image and complete metadata/config, and deploy an isolated
application on a different authenticated TLS endpoint. Verify object ownership,
byte checksums, authorization and lifecycle policy readback. Do not roll back or
replace the live dataset for a test. Stop and remove only the explicitly owned
restore-test app/dataset after evidence is reviewed. Production cutover requires
paused writers, matching credentials/CA, an approved network endpoint and a tested
rollback. Existing research data is never deleted to make an upgrade succeed.

Primary references: [TrueNAS Custom Apps](https://www.truenas.com/docs/scale/25.10/scaleuireference/apps/installcustomappscreens/),
[SeaweedFS 4.48](https://github.com/seaweedfs/seaweedfs/releases/tag/4.48),
[S3 credentials](https://github.com/seaweedfs/seaweedfs/wiki/S3-Credentials),
[Lifecycle operator guide](https://github.com/seaweedfs/seaweedfs/wiki/S3-Lifecycle-Operator-Guide).

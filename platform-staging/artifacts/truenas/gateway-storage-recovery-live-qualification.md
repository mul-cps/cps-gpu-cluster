# Live CPS/CIT storage failure recovery

Status: bounded acceptance passed using the published `111dc2d` candidate; production rollout remains pending.

## Actual fixture and authorization

The disposable gateway used `ghcr.io/mul-cps/cps-compute:qualification-recovery-111dc2d@sha256:30c09221af83a13cb46c81e1c98b66f7c80467726f6bd38e3ce6fdb06880a520`, the real `cps-compute-controller` service account and existing TLS/CA and console service credential references. Requests verified the HTTPS hostname and CA. A real isolated JupyterHub 5.5.2 fixture supplied the neutral workspace role and shutdown APIs, with synthetic canonical person mapping. The Pod did not match the production Service selector. Its SQLite database and lock directory stayed on one emptyDir filesystem throughout failures and restart; this is not an off-host restore or Pod replacement test.

## Failure, retry and archive

For both CPS and CIT, the fixture initially lacked relay ingress. Authenticated provisioning returned 409 and durably fenced generation 1. The original registrations, random group IDs and fixture nonce were saved before requests. A narrow temporary NetworkPolicy restored only the fixture label's TCP 8022 access to the existing storage bridge. Repeating the authenticated request on the same database succeeded at generation 2 through forced SSH, TrueNAS, and actual source-bound Kubernetes PV/PVC creation. No fence or database was reset.

The fixture deliberately selected a verifier image that the existing admission policy does not permit. Archive returned 409 while retaining the archiving fence at generation 3. Forced SSH status reads independently confirmed both NAS datasets were already read-only. Provision requests stayed denied; recovery did not reopen either dataset.

The fixture ConfigMap was changed to the already approved verifier digest. Projected file hash was checked before stopping the gateway. An attempted SIGKILL from within the PID namespace did not terminate PID 1; unchanged restart count and live API responses proved it ineffective, and it is not crash evidence. Uvicorn's handled SIGTERM then stopped the gateway. Kubernetes restarted only that container under the fixture's Always policy. The same Pod UID remained, gateway restart count advanced from 0 to 1 with previous exit code 0, and the fixture Hub restart count stayed 0.

After restart, both archive requests succeeded at generation 4. Actual verifier Jobs completed with UID 1000 and writable client PVC mounts, so the server-side EROFS check was exercised rather than inferred from a read-only mount option. The database retained the original nonce and all audit history. Each source's audit sequence was started/failed/resumed/completed for provisioning, then started/failed/resumed/completed for archival, with generations 1,1,2,2,3,3,4,4 and the authenticated source actor. Both archived groups still denied provisioning.

## Cleanup and limits

The fixture Pod, ConfigMap, synthetic Hub token Secret, temporary relay rule, two verifier Jobs and two claims were removed. Both PVs remain Retain/Released with the archived NFS paths preserved. The production gateway image was explicitly checked unchanged. Exact objects, NAS evidence, API results, audit records and cleanup outcomes are recorded in `gateway-storage-recovery-live-report.json` and `gateway-storage-recovery-live-cleanup.json`.

This proves failure/retry without a database reset and handled restart after failed operations for both sources. It does not prove hard crash during an in-flight NAS mutation, persistent-volume restore/Pod replacement, production identity linkage, browser authorization, RTC spawn, data-bearing workspace recovery, cross-group privacy, future broad-parent mount prevention, legacy root handover, off-host backups or GPU pooling. The source suite separately exercises a spawned process killed while holding a lock; that remains Linux lock/generation evidence rather than a live NAS crash test.

## Operator retry procedure

Repair the underlying connectivity, admission, permission or binding problem, then repeat the owning console's original provision or archive request. Do not clear the durable fence or delete lock files. A live lock holder remains a conflict; only the same fenced operation can resume. Before upgrading a gateway that has fenced work, fully stop the old process and keep the control database and lock directory together on the supported local filesystem. Never run old/new gateway versions concurrently. Archive retries require fresh owner/shutdown checks, the cluster writer barrier and the actual immutable NAS/read-only mount proof.

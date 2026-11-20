# Gateway hard-crash and Pod replacement qualification

Status: bounded CPS acceptance passed; production migration remains pending.

The published `111dc2d` gateway candidate ran in the same isolated, non-Service-selected fixture used for earlier HTTP qualification, with actual control service credential references, verified HTTPS TLS, real `cps-compute-controller` permissions, a real isolated Hub 5.5.2, forced SSH to TrueNAS and source-bound Kubernetes storage. A separate operator-owned 1 GiB Longhorn claim held the synthetic control database and lock directory. Production state and the NFS server address were unchanged.

A fixture-only wrapper around the original `SSHJSONTransport.action` awaited the **real** NAS result, wrote a boundary marker and paused before returning it to the controller. It did this once for provision and once for archive, retaining the markers on the fixture state volume. The wrapper did not fabricate NAS responses, change bindings or alter the published application files. A fixture-only SIGUSR1 handler called `os._exit(137)`, allowing an actual ungraceful process termination despite PID 1's default signal restrictions. This hook is test instrumentation and must not be deployed in production.

## Provision crash

The authenticated provision request acquired generation 1's durable fence and process lock. TrueNAS created the private POSIX V2 dataset/export and returned real permission evidence. Before the gateway could create Kubernetes bindings or record success, the boundary marker was checked and the process was terminated. Kubernetes reported exit code 137 / Error and restarted the gateway; the fixture Hub did not restart. The probe's kubectl exec session terminated with code 137, an expected fault result rather than a passing HTTP response.

The owning CPS request then resumed on the same database at generation 2, revalidated existing NAS evidence and created its deterministic PV/PVC binding. It recorded active state. The NAS dataset was not replaced or rebound.

## Archive crash and Pod replacement

The authenticated archive request fenced generation 3, checked Hub shutdown and cluster writers, and received an immutable, preserved NAS result. Before client-mount verification and database completion, the wrapper paused. A simultaneous provision request remained denied. The process was again terminated with exit code 137 / Error; Kubernetes verified a second gateway restart while the Hub restart count remained zero.

The whole fixture Pod was then removed and recreated, deliberately retaining the same Longhorn state claim. The new Pod UID differed, while the PVC UID, CSI PV name and `driver.longhorn.io` driver remained the same. The database nonce and all earlier audit records survived. The next archive request resumed at generation 4, verified server EROFS using an actual completed UID 1000 Job with a writable client PVC mount, and recorded archived state. Provisioning remained denied afterward.

The audit sequence was storage_started, storage_resumed, storage_completed for provisioning, then the same sequence for archive, with generations 1,2,2,3,4,4. The hard-crashed process could not write a failure/completion audit; the retained start and subsequent resume make those incomplete operations visible. Exact NAS results, process exit/restart observations, state-volume identities, immutable binding, verifier and audit records are in `gateway-storage-hard-crash-report.json`.

## Cleanup and remaining gates

The fixture, synthetic Hub-token Secret, ConfigMap, relay ingress exception, verifier Job, workspace claim and synthetic state PVC/CSI PV were removed. The immutable NAS dataset and Retain/Released workspace PV remain preserved. Production gateway image was checked unchanged; cleanup is recorded in `gateway-storage-hard-crash-cleanup.json`.

This proves recovery after committed external NAS side effects but before local completion, including persistent local state across both process death and Pod replacement. It uses one empty CPS workspace; CIT failed-operation/handled-restart coverage is in the preceding live report. It does not prove interruption during the SSH RPC itself, off-host backup restore, a data-bearing recovery, production identity/permission migration, future parent-mount prevention, cross-group privacy or GPU sharing. It provides no authorization to clear production fences or migrate legacy paths without the remaining review and restore gates.

# Packaged gateway storage refusal — 2026-10-07

The current immutable gateway candidate ran in a bounded CPU Job using the real `cps-compute-controller` service account. Its SelfSubjectReview confirmed that identity. The initial Job could not pull the private GHCR image because its imagePullSecrets reference was absent. That attempt was retained; the replacement reused the deployed gateway's existing pull-secret reference. Production was unchanged.

The adjacent JSON records the runtime image digest, fixture checksum, terminal Job/Pod identities and exact results. The probe used an isolated temporary control/reservation database, generated operator fixture credentials, an ASGI HTTP client and fixture neutral-owner/shutdown checks. It mounted no NAS credentials and its NAS adapter raises if invoked. Real Kubernetes inventory reads found one active parent NFS mount for each CPS/CIT workspace path.

For each source: missing/invalid bearer credentials returned 401; a metrics-only credential returned 403; wrong-console and source-authorized unsafe provisioning returned 409. No storage binding was created and NAS calls stayed zero. The Job completed with container exit 0; its Job, Pod and ConfigMap were removed after evidence capture. Private evidence: `/home/bjoern/cps-platform-evidence/2026-10-07/gateway-6bb6a57-service-account-guard/`.

This proves the packaged internal authorization/refusal path with actual service-account inventory access. It does not qualify production OAuth, actual Hub neutral ownership or shutdown, network HTTP transport, successful NAS lifecycle or storage provisioning. The active parent mount still blocks successful provisioning; this result does not authorize stopping its workload or advancing the storage handover.

The adjacent Python fixture is for trusted operator jobs using the pinned candidate, not public PR cluster runners. Keep a temporary filesystem for its databases, no NAS secrets, a bounded deadline, restricted pod security, the controller service account and the existing registry pull-secret reference. It performs only cluster API reads and temporary local database writes.

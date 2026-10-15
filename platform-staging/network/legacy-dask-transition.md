# Legacy Dask transition

Status: staged admission guard; production transition is not active.

The CPS notebook service account `jupyterhub:dask-sa` retains a projected Kubernetes token. Its live RoleBinding targets `jupyterhub`, whereas the checked-in Dask RBAC manifest targets `dask-compute`. Both locations must be inventoried during promotion. Do not assume changing the checked-in binding removes the live grant.

The inventory on 2026-10-07 found one DaskCluster and its WorkerGroup in `default`, created in December 2025. Its status says Running, but no Dask Pods existed at inspection. Preserve these records; a stale status does not authorize deletion or establish ongoing work.

The optional `legacyDaskBoundary.enabled` chart switch blocks CREATE, UPDATE and DELETE of Dask resources (including WorkerGroup scale) by the two known notebook Dask service accounts, in every namespace. Reads remain subject to existing RBAC. Operators and Dask reconciliation service accounts are unaffected by this guard. Admission protects already-issued tokens when activated; disabling automount alone only affects newly created Pods. The switch is independent of gateway deployment and defaults to false.

This is a narrow transition guard, not a general distributed-launcher implementation. Another principal, additional resource-creating APIs, Pod credentials, host networking and namespace-wide egress require separate review. Do not grant direct Dask mutation permissions to a replacement notebook account. Approved launcher templates must pass central policy before adding Dask execution through the gateway.

Before promotion:

1. Inventory all Dask bindings, accounts, cluster-wide grants and active workers again. Review both CPS and CIT ownership and any alternate notebook service accounts.
2. Offer policy-controlled Hera CPU/batch submission and qualify the required distributed launcher. Document the interruption to direct Dask creation, scaling and deletion; operators handle legacy lifecycle until migration.
3. Apply the admission guard together with removal of notebook Dask mutation grants and explicit `singleuser.automountServiceAccountToken: false` for future servers. Check effective Helm output and embedded spawner/profile overrides. Preserve running notebook files and avoid an unannounced restart.
4. Qualify complete execution-Pod egress and mount admission, then exercise real authorized Hub/SDK submissions. The existing singleuser-only egress fixture is insufficient.
5. Reconcile these changes through the actual Fleet configuration. A rollback restoring notebook mutation permissions also restores the policy bypass and requires an explicit containment decision.

No production RBAC, notebook server, Dask resource or egress rule is modified by this staged work. GPU isolation, identity/grant migration and the remaining release gates stay open.

## Qualification

Two chart regressions passed after watching the missing enabled-policy test fail: disabled rendering emits no guard; enabled rendering covers all mutation operations, both known principals and scale without relying on an object being present for DELETE. Kubernetes server dry-run accepted both production-named admission manifests. A separately named policy and binding were then restricted to an operator-owned test namespace. A real projected service-account token with Dask create RBAC received HTTP 201 for server dry-run creation before admission and HTTP 422 containing the guard message afterward. No Dask resource persisted. The account name/namespace in the isolated policy were substituted only for the test principal. That initial live test qualified CREATE only; the follow-up mutation matrix below covers UPDATE and DELETE. Operator reconciliation remains a separate integration gate. It does not use Rancher impersonation. The isolated policy, binding and namespace were removed; production guards remain disabled. Exact bounded results are in `legacy-dask-boundary-report.json`.

## Follow-up mutation matrix

A real projected token was independently identified through SelfSubjectReview as the isolated notebook service account. An operator-created DaskAutoscaler pointed to an absent test cluster with minimum and maximum zero; it launched no execution Pods. Before applying the namespace-scoped guard, CREATE, PATCH/UPDATE and DELETE server dry-runs returned 201/200/200. Afterward all three returned 422 with the guard message. Operator PATCH and DELETE server dry-runs still succeeded. The autoscaler spec remained unchanged, and only the probe Pod existed. The test namespace, autoscaler, credential references and admission fixtures were removed afterward. Production remains untouched and the deployment switch stays disabled.

For DELETE, send `dryRun: ["All"]` in the DeleteOptions body as well as the query. The first fixture incorrectly relied on the query while supplying a body without this field; its idle test object was deleted and subsequent checks failed with 404. That attempt is not passing evidence. The corrected run asserts that the object survives both baseline and post-guard requests. A separate fixture CLI error using unsupported `kubectl delete -o json` was corrected to `-o name` before the final passing run. Exact final results are retained in `legacy-dask-mutation-report.json`.

These tests cover the real API admission boundary for autoscaler mutations, plus the earlier DaskCluster CREATE case. These earlier mutation tests did not exercise the scale subresource. Its subsequent two-principal PATCH/PUT dry-run qualification is recorded below. Alternate identities, actual Dask operator reconciliation, namespace-wide workload isolation and a gateway distributed launcher remain transition requirements.

## Scale subresource qualification

The installed WorkerGroup CRD serves scale using `.spec.worker.replicas` and `.status.replicas`. A new isolated namespace held a zero-replica WorkerGroup referencing an absent cluster and two projected-token probe Pods. Both principals were confirmed through SelfSubjectReview; the production policy's CPS/CIT identities were substituted only for these isolated principals. The binding matched only the test namespace.

For each principal, PATCH and PUT scale requests with server dry-run returned 200 before the guard, then 422 containing the guard message after activation. Operator scale PATCH dry-run still returned the requested one-replica response. The persisted WorkerGroup spec stayed unchanged at zero replicas, no DaskCluster existed, and only the two probe Pods were present. No execution workload was launched. Policy type checking had no warnings.

The namespace, temporary credentials, idle WorkerGroup, policy and binding were removed and their absence verified. Production RBAC and the disabled chart switch were untouched. Exact results are in `legacy-dask-scale-report.json`; private fixture source is `/home/bjoern/cps-platform-evidence/2026-10-07/dask-scale-boundary/qualify-scale.py`. This closes the bounded scale admission dry-run gap, not production transition, alternative credentials, actual operator scaling or full privacy qualification.

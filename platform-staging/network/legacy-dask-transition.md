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

Two chart regressions passed after watching the missing enabled-policy test fail: disabled rendering emits no guard; enabled rendering covers all mutation operations, both known principals and scale without relying on an object being present for DELETE. Kubernetes server dry-run accepted both production-named admission manifests. A separately named policy and binding were then restricted to an operator-owned test namespace. A real projected service-account token with Dask create RBAC received HTTP 201 for server dry-run creation before admission and HTTP 422 containing the guard message afterward. No Dask resource persisted. The account name/namespace in the isolated policy were substituted only for the test principal. This live test qualifies CREATE, not live UPDATE/DELETE or operator reconciliation. It does not use Rancher impersonation. The isolated policy, binding and namespace were removed; production guards remain disabled. Exact bounded results are in `legacy-dask-boundary-report.json`.

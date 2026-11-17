# Legacy vcluster-ckf retirement preparation

The former Charmed Kubeflow bootstrap is unused: fresh tenant inventory has only the four default namespaces, CoreDNS Pod/Deployment and two Kubernetes/DNS Services. There are no tenant user workloads, Jobs, PVCs/PVs, Ingresses or CRDs. No current in-cluster cross-namespace consumer was found. CPS/CIT Hubs, Gateway, Argo and the qualified shared5 workflow run in host namespaces independently.

The user authorized full removal. This source change removes only the old `.vcluster-ckf` bundle/bootstrap configuration. The parent GitRepo path still exists; no GitRepo.paths change is required. Historical evidence remains in Git. Actual target removal has **not** been applied by this preparation commit.

A native read-only SQLite snapshot plus stable PKI/non-database files was verified before preparation:706307bytes, SHA256 `1e0fe1ed95be0f15ac8f8951a23b3cf07359ab359dc29d0bbcac1a2bfe52099b`. Quick/full integrity and catalog/row counts pass in the helper and host copies. Secret configuration/PKI is retained only in a private0600 recovery archive outside Git. No full restore rehearsal is claimed. The bounded CPU-only read-only helper and its deny-network policy were cleaned normally.

Root must first hold only the exact Fleet Bundle and BundleDeployment with paused=true, keepResources=true and deleteNamespace=false, verify retention, then pin the reviewed source removal. The intended guard was to prevent Fleet recreation and namespace/PVC cascade; the actual retention behavior is recorded below. The Helm manifest does not own the Namespace/PVC/PV. Normal exact-name Helm uninstall is followed by exclusive residue reconciliation. Namespace and PVC/PV/local-path removal require root's reviewed backup/exclusivity gate; namespace is last. No forced deletion, finalizer stripping, upgrade, broad RBAC deletion or changes to other workloads are part of this source commit.

The sole cluster role/binding is `vc-vcluster-ckf-v-vcluster-ckf`; its only subject is the vcluster namespace service account and there are no shared/aggregate consumers. The5Gi local-path control-plane PVC is onGPU4 and uses Delete reclaim policy. Its data is not removed by this preparation commit. See the safe inventory and backup records here; the guarded operator packet and raw recovery configuration remain private.

## Applied owner and application removal

At14:15Z both exact Fleet holds were read back true/true/false. Root pinned source df0eaa883106d9d7ad4b6ae901ba926a9907dd0e. The removed Bundle remained paused/OutOfSync, so root authorized ordinary deletion of its exact UID with fresh resourceVersion. Bundle and BundleDeployment disappeared normally.

**Unexpected retention behavior:** Fleet also removed the Helm release, StatefulSet/control-plane Pod, translated CoreDNS and exclusive RBAC despite the recorded keepResources holds. The subsequent manual Helm preflight refused at release-not-found; no manual Helm uninstall was executed or retried. The application removal was within the user-authorized scope; original namespace and PVC/PV remained Active/Bound/Bound with unchanged identities. No force, finalizer changes or manual host deletion occurred.

An exhaustive235 namespaced-API inventory had no list errors and showed only the original PVC, default ServiceAccount, two CA ConfigMaps and Events; no Pods, Secrets, Services or RoleBindings remained. The private backup SHA was reverified. Comparison of1896 protected unrelated resource UID/spec checksums found1895 unchanged and only the independently authorized Turtles Deployment update; all seven Nodes were Ready. Root subsequently released exact storage and namespace deletion after reviewing these guards.

## Completed storage and namespace removal

Root released the exact original PVC deletion. The ordinary UID/resourceVersion-guarded request at14:24:10Z completed through normal Delete reclaim: the local-path provisioner explicitly confirmed the exact GPU4 volume directory deleted at14:24:13Z; PVC/PV were absent by14:24:14Z. No explicit PV deletion, manual host-path removal or finalizer change was used.

With zero Pods/PVCs, expected PV absent, owner absent and backup hash reverified, the original namespace was deleted LAST using fresh UID/resourceVersion guards. It was absent at14:25:04Z. At14:25:34Z all235 namespaced APIs returned zero resources and zero errors; Helm, Fleet Bundle/BundleDeployment, the namespace, original PVC/PV, exclusive cluster role/binding and translated Pod residue were absent. The final unrelated comparison again found1895/1896 unchanged, only root's authorized Turtles update, no missing unrelated resource and all seven Nodes Ready.

The private consistent backup is retained. Retiring the active legacy bundle does not erase historical causal evidence from Git. No vCluster upgrade, production Source token, user workspace start or unrelated namespace/data change was performed by this retirement.

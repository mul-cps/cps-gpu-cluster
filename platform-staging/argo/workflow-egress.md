# Workflow standard RPC/NFS egress

Canonical source: `../workload-rbac.yaml`, applied before the Argo Helm release
(see `README.md`). The compute chart does not render this bootstrap bundle.
`network-policy.yaml` protects the Argo server in `cps-argo`; user workflows run
in `cps-workflows` (`values.yaml`, `controller.workflowNamespaces`).

`cps-workload-standard-rpc-nfs-egress` selects every current/future Pod in
`cps-workflows`. It permits TCP/UDP destination ports 1–65535 except 111 and
2049, for all destinations and both IP families. DNS, HTTPS/Kubernetes API,
gateway (8000), S3 (8333), and distributed TCP/UDP ports remain allowed by this
egress policy; destination ingress policies still apply. Other protocols are
not explicitly allowed. Enforcement requires the cluster CNI to support
NetworkPolicy `endPort`.

This closes standard RPC/NFS Pod egress only. It does not establish whether a
mount exploit was possible, inventory nonstandard RPC ports, alter NAS exports,
or affect kubelet/CSI host-originated volume mounts. The audited NAS addresses
are 193.170.30.58 and legacy 10.21.0.44; this policy does not change server,
route, or export configuration.

NetworkPolicies are additive. Before rollout and after reconciliation, inspect
all `cps-workflows` policies; any selected broad egress allowance can reopen
these ports. The regression test evaluates the canonical bundle plus enabled
compute Helm output and confirms this additive behavior. Notebook live policy
port filters were observed separately; notebook values/canonical drift is not
resolved by this change.

## Review and rollout

Run from the repository root. Extract only the reviewed object (the bootstrap
bundle also contains RBAC and a service-account-token declaration):

```sh
umask 077
python3 - <<'PY' > /tmp/cps-workload-standard-rpc-nfs-egress.yaml
import yaml
with open('platform-staging/workload-rbac.yaml') as source:
    for obj in yaml.safe_load_all(source):
        if obj and obj.get('kind') == 'NetworkPolicy' and obj['metadata']['name'] == 'cps-workload-standard-rpc-nfs-egress':
            print(yaml.safe_dump(obj, sort_keys=False), end='')
PY
python3 -m unittest discover -s tests/compute_platform -p test_workflow_egress.py -v
kubectl -n cps-workflows get networkpolicies -o yaml
kubectl diff -f /tmp/cps-workload-standard-rpc-nfs-egress.yaml
```

After explicit review/approval, apply that exact extracted object:

```sh
kubectl apply -f /tmp/cps-workload-standard-rpc-nfs-egress.yaml
kubectl -n cps-workflows get networkpolicy cps-workload-standard-rpc-nfs-egress -o yaml
```

Rollback (restores the previous unisolated egress if no other egress policy
selects the Pods):

```sh
kubectl -n cps-workflows delete networkpolicy cps-workload-standard-rpc-nfs-egress
```

Remove/revert the source addition before any subsequent bootstrap reconciliation
if rolling back permanently.

## Controlled connectivity qualification proposal

Requires separate approval for test Pod creation/exec and any temporary
NetworkPolicy. Use a pinned, approved non-GPU image, restricted security context,
no service-account token, no volumes, bounded CPU/memory, and a short deadline.
Record the pre/post policy set. Probe TCP connect only to the two audited NAS
addresses on 111/2049 (no mount, RPC request, directory read, or data access).
A timeout alone is inconclusive without an approved pre-policy baseline or CNI
drop evidence. Check DNS resolution, HTTPS, Kubernetes API TLS (no credential),
and approved gateway/S3 endpoints (8000/8333) separately.

For deterministic TCP and UDP qualification, use an approved controlled listener
in a separate test namespace, with explicit ingress allowing only the test
source. Exercise 111, 2049 and allowed range boundaries 110/112/2048/2050 plus
53/443/8333/29500. Require successful baseline exchanges and, after rollout,
blocked exchanges only on 111/2049; UDP silence without listener/baseline is not
proof. Existing workflow ingress isolation means listeners in cps-workflows
would otherwise obscure the result. Delete test resources afterward. IPv6
requires a reachable controlled IPv6 listener if the cluster is dual stack;
static tests cover IPv6 semantics, not live CNI enforcement.

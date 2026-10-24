# Workflow egress qualification — 2026-10-24

Source policy: `../workload-rbac.yaml`, introduced by commit
`46cedc915ff88612d1c11f6ae4e73e0b71f3c76f`. Applied only the extracted reviewed
NetworkPolicy using server-side apply, manager
`cps-workflow-nfs-egress-20261024`; no bootstrap Secret/RBAC apply.

Preflight found only the existing Ingress isolation policy in `cps-workflows`
and no Egress policies. The target object was absent. Admission was inspected;
the workflow prober used `cps-workflow`, `kai-scheduler`, and the explicitly
approved image
`ghcr.io/mul-cps/cps-jupyter-notebook@sha256:1fab06639346f69e96cda6c8f551d761cc51c47de85cdc0ec42ef31bf2ef2c7f`.

Restricted, nonroot, token-free test Pods used no GPU, PVC, host namespace,
host mounts, or added capabilities. Each requested 100m CPU/128Mi and was limited
to 500m CPU/512Mi, with a 1200-second deadline. A synthetic TCP/UDP listener and
control prober ran in a unique owned restricted QA namespace; a workflow prober
ran in `cps-workflows`. No NAS traffic, RPC, mount, or file access was attempted.

| Measurement | Control | Workflow |
| --- | --- | --- |
| Before policy | 20/20 exchanges successful | 20/20 successful |
| After policy | 20/20 exchanges successful | 16/20 successful |

Each measurement exercised TCP and UDP ports 53, 110, 111, 112, 443, 2048,
2049, 2050, 8333, and 29500. After apply, exactly TCP 111/2049 returned connection
refused and UDP 111/2049 timed out for the workflow prober. The same listener
remained reachable on those ports from control. All other tested workflow
exchanges succeeded. UDP timeout is supported here by successful before-policy
and concurrent control exchanges, rather than interpreted alone.

The retained live spec exactly matched the reviewed extracted object:

- UID: `2517a6dd-d4ed-4615-9b52-7c0c22274fd1`
- resourceVersion: `382464977`
- field manager: `cps-workflow-nfs-egress-20261024`

All owned test Pods and the QA namespace were deleted with recorded UID
preconditions. Workflow Pod deletion was awaited; zero QA Pods remained.
All three baseline user notebook Pod UIDs remained unchanged, and all previously
Ready notebook Pods remained Ready. Across the complete preflight snapshot,
all 231 baseline Ready Pod UIDs remained present and Ready after measurement.

Private evidence is stored in the operator's
`~/.local/state/workflow-nfs-egress-20261024/` directory (0700, files 0600):
`baseline.json`, `after.json`, `owned.json`, `retained-policy.json`,
`summary.json`, and test logs. Private full Kubernetes GET snapshots are not
committed.

This qualifies IPv4 synthetic Pod egress enforcement of these standard ports
and preservation of the listed TCP/UDP exchanges. It does not qualify live
IPv6, DNS resolution, TLS/application behavior, nonstandard RPC ports, all
nodes, NAS export safety, or notebook canonical/live drift. Host/CSI-originated
NFS mounts were not changed or exercised. The policy remains active.

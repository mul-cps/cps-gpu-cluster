# GPU Node Pools Runbook

This Fleet bundle (`fleet.yaml`) deploys no manifests of its own — it's an
empty bundle (`defaultNamespace: kube-system` only) that exists purely to
carry this runbook doc. It has no functional dependency on any particular
`gpu-pool` labeling scheme; nothing here selects or enforces node labels.

Previously this doc described an aspirational `gpu-pool=courses` /
`gpu-pool=research` two-pool split for KAI Scheduler. That scheme was
never actually applied to nodes and does not correspond to any real
labels or manifests in this repo — it's being replaced below with the
labeling that is actually live.

## Current node labeling in practice

The GPU Operator's `node-labeler.yaml` Helm hook (in
`system/gpu/gpu-operator/`) applies `gpu-pool=mig` / `gpu-pool=full`
labels, which are historical/superseded artifacts of the retired
static-MIG layout (see `system/gpu/gpu-operator/README.md` for the full
MIG-to-MPS migration context). All 4 GPU nodes now run in full/non-MIG
mode (`nvidia.com/mig.config=all-disabled`), so the MIG/full distinction
those labels encode no longer reflects an active partitioning scheme —
they're being phased out, not actively relied on for scheduling
decisions.

GPU sharing for interactive/course workloads going forward is handled by
NVIDIA MPS + KAI Scheduler's `gpu-memory` annotation, configured via
JupyterHub server profiles (see
`user/jupyter/jupyterhub/values.yaml`'s `PROFILE_CONFIGS`), not via
node-level `gpu-pool` labels.

## Verification
To see the current node pool labels:
```bash
kubectl get nodes -L gpu-pool
```

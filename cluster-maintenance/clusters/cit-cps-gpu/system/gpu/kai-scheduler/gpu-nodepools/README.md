# GPU Node Pools Runbook

This bundle documents the node labeling strategy for the GPU cluster to support differentiated scheduling via KAI.

## Node Labeling Commands

Apply the following labels to categorize nodes into pools:

### Course Pool (4 GPUs total)
```bash
kubectl label node k3s-wk-gpu2 gpu-pool=courses --overwrite
kubectl label node k3s-wk-gpu3 gpu-pool=courses --overwrite
```

### Research Pool (Remaining GPUs)
```bash
kubectl label node k3s-wk-gpu1 gpu-pool=research --overwrite
kubectl label node k3s-wk-gpu4 gpu-pool=research --overwrite
```

## Verification
To see the current node pools:
```bash
kubectl get nodes -L gpu-pool
```

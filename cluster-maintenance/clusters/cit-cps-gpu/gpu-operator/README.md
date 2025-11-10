# GPU Operator Mixed MIG Configuration

This folder deploys the NVIDIA GPU Operator via Fleet with a mixed MIG strategy. Your cluster has 4 GPU nodes with **2× A100 40GB** each, and only ONE node should be MIG-enabled.

## Goal
Provide both:
- One full, non-partitioned A100 for jobs needing the entire GPU (request `nvidia.com/gpu: 1`).
- One A100 split into the smallest MIG slices for high concurrency / small jobs (request `nvidia.com/mig-1g.5gb` or `nvidia.com/mig-1g.10gb` depending on model).

## Profiles
For A100 40GB, the smallest slice is `1g.5gb`. The charted config creates 8 slices on GPU index 1 and keeps GPU index 0 full.

## Configuration Source
`values.yaml` defines multiple MIG configs and sets default to `all-disabled`.
Activate MIG on exactly one node by labeling it with the desired config:

```bash
kubectl label node <node-name> nvidia.com/mig.config=mixed-one-node-40gb-small --overwrite
```

This will:
- Keep GPU index `0` full (for `nvidia.com/gpu: 1`)
- Partition GPU index `1` into 8× `nvidia.com/mig-1g.5gb`

## Apply / Update
If using Fleet (Rancher): it will reconcile automatically after Git push.
If applying manually with Helm (Ansible playbook currently sets `migManager.enabled=false`):
1. Update the Ansible playbook `04-gpu-operator.yml` to remove the forced `--set migManager.enabled=false` (or pass `-f values.yaml`).
2. Then deploy:
   ```bash
   helm upgrade --install gpu-operator nvidia/gpu-operator \
     --namespace gpu-operator \
     -f values.yaml \
     --wait
   ```

## Verify MIG State
```bash
kubectl -n gpu-operator get pods -l app=gpu-operator
kubectl describe node <gpu-node> | grep -i mig -A2
nvidia-smi -L                # From a privileged debug pod / node shell
nvidia-smi mig -lgi          # List GI instances
nvidia-smi mig -lci          # List CI instances
```

Device Plugin resources should show on the MIG-enabled node:
- `nvidia.com/gpu: 1` (from the full GPU index 0)
- `nvidia.com/mig-1g.5gb: 8` (from GPU index 1)

List allocatable:
```bash
kubectl get nodes -o json | jq '.items[] | {name: .metadata.name, alloc: .status.allocatable | with_entries(select(.key|test("nvidia")))}'
```

## Requesting GPUs
Full GPU example:
```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```
Single MIG slice (on the MIG-enabled node):
```yaml
resources:
  limits:
    nvidia.com/mig-1g.5gb: 1
```
Multiple slices (parallel small jobs): schedule multiple pods each asking for 1 slice.

## Overcommit / Time-Slicing Notes
MIG already provides strong isolation. Additional overcommit via time-slicing (device plugin "replicas") is generally NOT recommended on MIG slices. If you still want to oversubscribe the **full** GPU for lighter workloads:
```yaml
devicePlugin:
  config:
    name: time-slicing-config
    sharing:
      timeSlicing:
        resources:
          - name: nvidia.com/gpu
            replicas: 2  # Presents one physical GPU as 2 logical for scheduling
```
Caveats:
- No guaranteed performance; jobs share context.
- Do NOT apply time-slicing to MIG resources simultaneously.

## Changing Strategy Later
Switching a GPU between full and MIG partitions restarts workloads using that GPU. Plan a maintenance window:
1. Drain node: `kubectl drain <gpu-node> --ignore-daemonsets --delete-emptydir-data`
2. Adjust `values.yaml` (profile counts or disable MIG) and redeploy.
3. Uncordon: `kubectl uncordon <gpu-node>`

## Troubleshooting
| Symptom | Action |
|---------|--------|
| MIG resources not visible | Check `migManager` pod logs; ensure correct profile names. |
| Full GPU disappeared | Ensure at least one GPU has `migEnabled: false`. |
| Slice count mismatch | Verify model (40GB vs 80GB) and adjust `count`. |
| Pods pending on MIG | Confirm resource name matches (`nvidia.com/mig-1g.*`). |

## Next Steps
- Add monitoring alerts for slice utilization (DCGM exporter metrics).
- Optionally provide a higher-profile slice (e.g., `2g.*`) for medium workloads.
- Consider a Node label/taint to steer MIG workloads to the specific MIG node if you add more GPU nodes later.

---
Update this doc if hardware changes or additional GPUs are added.

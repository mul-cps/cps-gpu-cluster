# NOS (Dynamic MIG Partitioning)

Dynamic MIG partitioning for A100 40GB nodes (k3s-wk-gpu1..3) using nebuly `nos` Helm chart vendored under `chart/`.

## Layout
- gpu1–gpu3: labeled `gpu-pool=mig-dynamic` and `nos.nebuly.com/gpu-partitioning=mig`; MIG mode kept enabled and controlled by NOS.
- gpu4: labeled `gpu-pool=full`, `nvidia.com/mig.config=all-disabled`, tainted `gpu-pool=full:NoSchedule` (full GPUs only).

## Prereqs
- MIG mode must be enabled on gpu1–gpu3 (one-time): `sudo nvidia-smi -i <index> -mig 1` on each GPU (reboot if required).
- GPU Operator deployed (device plugin config name `device-plugin-config` in namespace `gpu-operator`).

## Chart wiring
- Chart: vendored `chart/` from nebuly-ai/nos (v0.1.2).
- Namespace: `nos` (created by `namespace.yaml`).
- Values: `values.yaml` sets `nvidiaGpuResourceMemoryGB: 40`, disables telemetry, points to GPU Operator device plugin ConfigMap, trims MIG geometries to A100 40GB.
- Depends on GPU Operator bundle via Fleet `dependsOn`.

## Labels/taints
- Applied by `gpu-operator/node-labeler.yaml` (Helm hook) or manually:
  - `kubectl label node k3s-wk-gpu{1..3} gpu-pool=mig-dynamic nos.nebuly.com/gpu-partitioning=mig nvidia.com/mig.config=all-enabled nvidia.com/mig.strategy=mixed --overwrite`
  - `kubectl label node k3s-wk-gpu4 gpu-pool=full nvidia.com/mig.config=all-disabled nvidia.com/mig.strategy=single --overwrite`
  - `kubectl taint node k3s-wk-gpu4 gpu-pool=full:NoSchedule --overwrite`

## Usage
- Schedule MIG workloads with `nvidia.com/mig-1g.5gb` or `nvidia.com/mig-2g.10gb` plus nodeAffinity `gpu-pool=mig-dynamic`.
- Full-GPU workloads: request `nvidia.com/gpu` with nodeAffinity `gpu-pool=full` and toleration for the `gpu-pool=full:NoSchedule` taint.
- NOS will re-partition MIG GPUs based on pending workloads within allowed geometries from `values.yaml` / `custom-mig-config.yaml`.

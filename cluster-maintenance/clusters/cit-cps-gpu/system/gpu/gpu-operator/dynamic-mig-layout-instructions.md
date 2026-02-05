Here’s the **minimal, code-agent-friendly summary** of what you need to change to automate **dynamic MIG repartitioning** (like the Medium post) using **nebuly NOS** (or equivalent), while **reusing your existing NVIDIA GPU Operator**.

I’m writing this as a checklist + concrete “what to add/change” so you can drop it straight into a Codex-Max agent plan.

---

## What we’re implementing

* 4 GPU nodes (`k3s-wk-gpu1..4`), each with **2× A100 40GB**.
* **gpu1–gpu3**: **dynamic MIG-only** pool (NOS manages MIG layouts automatically based on pending pods).
* **gpu4**: **full GPU only**, **MIG disabled**.

Key concept:

* GPU Operator’s **MIG Manager** applies MIG configs by watching node labels (e.g., `nvidia.com/mig.config`) and will stop GPU operands to reconfigure. ([NVIDIA Docs][1])
* NOS runs alongside GPU Operator and automates MIG partitioning **based on cluster demand** (pending/running pods). ([Medium][2])

---

## Changes required (high level)

### A) Node pool separation (labels + optional taints)

1. Label node pools:

```bash
kubectl label node k3s-wk-gpu1 gpu-pool=mig-dynamic --overwrite
kubectl label node k3s-wk-gpu2 gpu-pool=mig-dynamic --overwrite
kubectl label node k3s-wk-gpu3 gpu-pool=mig-dynamic --overwrite
kubectl label node k3s-wk-gpu4 gpu-pool=full --overwrite
```

2. Strongly recommended: taint gpu4 so only “full GPU” workloads land there:

```bash
kubectl taint node k3s-wk-gpu4 gpu-pool=full:NoSchedule
```

### B) Keep GPU Operator (no reinstall), but ensure MIG is controllable

* Verify GPU Operator MIG Manager is present and uses `nvidia.com/mig.config` + `default-mig-parted-config`. ([NVIDIA Docs][1])
* Ensure device plugin MIG strategy supports multiple MIG resources (commonly “mixed” in GPU Operator setups if you want multiple MIG types advertised). (This is often already handled in your operator install; just verify.)

### C) Install NOS (new component) to drive “dynamic MIG partitioning”

* Deploy NOS via Helm or manifests (recommended: Helm) into its own namespace (e.g. `nos`).
* NOS will watch pending pods and (re)configure MIG accordingly. ([GitHub][3])

### D) Enable MIG mode on the MIG-dynamic nodes

NOS docs explicitly note MIG must be enabled on the GPUs (may require reboot depending on platform). ([nebuly-ai.github.io][4])

Practical implementation options:

* **One-time manual enable** on gpu1–gpu3 (both GPUs per node).
* Or add a privileged DaemonSet/bootstrapping step to ensure `nvidia-smi -mig 1` has been applied (only once per node).

### E) Tell NOS which nodes to manage for MIG

NOS uses node labels to enable partitioning on selected nodes (analogous to how their MPS example works with `nos.nebuly.com/gpu-partitioning=...`). ([Medium][5])
For MIG, apply the NOS MIG label on gpu1–gpu3 (exact key/value from NOS docs/chart—agent should confirm in NOS chart values/README):

```bash
kubectl label node k3s-wk-gpu1 nos.nebuly.com/gpu-partitioning=mig --overwrite
kubectl label node k3s-wk-gpu2 nos.nebuly.com/gpu-partitioning=mig --overwrite
kubectl label node k3s-wk-gpu3 nos.nebuly.com/gpu-partitioning=mig --overwrite
```

And **do not** label gpu4 for NOS.

### F) Keep gpu4 permanently MIG-disabled

Set GPU Operator MIG config label on gpu4 to disabled:

```bash
kubectl label node k3s-wk-gpu4 nvidia.com/mig.config=all-disabled --overwrite
```

(Confirm the exact profile name exists in your operator ConfigMap; “all-disabled” is the documented default label.) ([NVIDIA Docs][1])

---

## Workload-side requirements (so scheduling is deterministic)

### 1) MIG workloads (students / small jobs)

* Must request MIG resources:

  * `nvidia.com/mig-1g.5gb: 1`
  * `nvidia.com/mig-2g.10gb: 1`
* Must be constrained to `gpu-pool=mig-dynamic` via nodeAffinity.

### 2) Full GPU workloads (researchers wanting max perf)

* Request `nvidia.com/gpu: 1`
* Must tolerate the gpu4 taint + nodeAffinity to `gpu-pool=full`.

This ensures:

* MIG jobs never touch gpu4.
* Full GPU jobs never land on MIG nodes (where they’d otherwise block waiting for MIG-off transitions).

---

## Fleet/GitOps deliverables for the code agent

### 1) Add a new Fleet bundle: `nos`

* Namespace: `nos` (or `gpu-partitioning`)
* Helm release for `nebuly-ai/nos` (chart source from their repo/docs) ([GitHub][3])
* Values to set (agent should wire these):

  * enable MIG dynamic partitioning
  * nodeSelector/affinity so NOS components run on control-plane or anywhere appropriate
  * RBAC permissions (cluster-wide read pods/nodes + patch node labels as needed)

### 2) Add a “node labeling” manifest bundle (or Ansible step)

* Applies the labels/taints for:

  * `gpu-pool` separation
  * `nos.nebuly.com/gpu-partitioning=mig` on gpu1–gpu3
  * `nvidia.com/mig.config=all-disabled` on gpu4

### 3) Add example K8s manifests / templates

* `pod-mig-1g.yaml`, `pod-mig-2g.yaml`, `pod-full-gpu.yaml`
* Include nodeAffinity + tolerations (for full node).

---

## Operational notes / gotchas (important for correctness)

1. **MIG config changes require workloads to be stopped on the affected GPU/node** (GPU Operator MIG Manager behavior). This is why dynamic repartitioning works best with many short jobs or where a small pause is acceptable. ([NVIDIA Docs][6])

2. **Driver/version pitfalls**: there are known cases where some driver versions can cause MIG enablement / reconfig issues on A100 (worth pinning to known-good versions in your operator stack). ([GitHub][7])

3. Confirm your desired MIG profiles exist:

* NOS will try to pick layouts that satisfy demand; GPU Operator only supports profiles listed in `default-mig-parted-config` unless you extend it. ([NVIDIA Docs][1])

---

<!-- ## “Equivalent” options if NOS doesn’t fit

If NOS is problematic, the “equivalent” is:

* a small custom controller (CronJob/operator) that:

  * watches pending pods for requested MIG profiles
  * selects an idle MIG node
  * patches `nvidia.com/mig.config` label accordingly
    This directly uses GPU Operator MIG Manager semantics. ([NVIDIA Docs][6])
    NOS basically productizes this loop. ([Medium][2]) -->


[1]: https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-operator-mig.html?utm_source=chatgpt.com "GPU Operator with MIG"
[2]: https://medium.com/data-science/dynamic-mig-partitioning-in-kubernetes-89db6cdde7a3?utm_source=chatgpt.com "Dynamic MIG Partitioning in Kubernetes | by Michele Zanotti"
[3]: https://github.com/nebuly-ai/nos?utm_source=chatgpt.com "nebuly-ai/nos: Module to Automatically maximize ..."
[4]: https://nebuly-ai.github.io/nos/dynamic-gpu-partitioning/getting-started-mig/?utm_source=chatgpt.com "Getting started with MIG partitioning - nos"
[5]: https://medium.com/data-science/how-to-increase-gpu-utilization-in-kubernetes-with-nvidia-mps-e680d20c3181?utm_source=chatgpt.com "How to Increase GPU Utilization in Kubernetes with NVIDIA ..."
[6]: https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/1.8/gpu-operator-mig.html?utm_source=chatgpt.com "GPU Operator with MIG"
[7]: https://github.com/NVIDIA/gpu-operator/issues/1845?utm_source=chatgpt.com "MIG Stuck in Pending enable state in A100 with 580 driver"

Here’s a **code-agent plan** to add the **KAI Scheduler policy layer** (queues + priority/preemption glue + node-pool labels) into your **Fleet repo first**, *without changing JupyterHub yet*.

I’m assuming you already have the **KAI Scheduler bundle installed** (or you’ll add it in parallel). The queue objects are CRDs (`kind: Queue`, `apiVersion: scheduling.run.ai/v2`). ([exostellar.ai][1])

---

# Plan: Fleet bundles to add (policy first)

## A) Bundle 1 — `kai-policy` (queues + rules)

Create a new bundle directory:

```
fleet/
  kai-policy/
    fleet.yaml
    queues.yaml
    priorityclasses.yaml
    (optional) rbac.yaml
    (optional) examples/README.md
```

### `fleet/kai-policy/fleet.yaml`

* Make this bundle **depend on** your `kai-scheduler` install bundle so CRDs exist first (`dependsOn`). ([fleet.rancher.io][2])

Example skeleton:

```yaml
defaultNamespace: kai-scheduler

dependsOn:
  - name: <YOUR_GITREPO_NAME>-fleet-kai-scheduler   # adjust to your actual bundle name

# raw YAML bundle (no helm) is fine; ensure this directory contains at least one manifest.
```

> Fleet `dependsOn` is supported and is the right mechanism for “CRDs first, CRs second”. ([fleet.rancher.io][2])

---

## B) Define the queue tree (what KAI actually uses)

### `fleet/kai-policy/queues.yaml`

Create three queues matching our agreed policy:

1. `courses`

* quota: **gpu=4**
* highest priority / strongest access

2. `phd-interactive`

* quota: **gpu=1.5** (6 × 0.25)
* high priority (below courses)

3. `batch`

* quota: **gpu=0**
* lowest priority, reclaim-first

Queue CRD uses `apiVersion: scheduling.run.ai/v2` and `kind: Queue`. ([exostellar.ai][1])

**Implementation notes for the agent:**

* Put `cpu/memory` quota/limit as `-1` (unlimited) initially unless you also want strict CPU/mem fairness.
* Set `gpu.limit` to `-1` (no hard cap) unless you explicitly want caps.
* Use `overQuotaWeight` to control who gets idle GPUs first (e.g., `courses=1`, `phd-interactive=2`, `batch=10` if you want batch to soak leftovers; or the inverse if you want interactive to win more often).

(Exact field names are stable in examples: `quota`, `limit`, `overQuotaWeight`). ([exostellar.ai][1])

---

## C) Preemption / reclaim behavior (cluster-wide glue)

Because you said:

* no scheduled taints
* batch + phd big burst can borrow course nodes

…you need **preemption/reclaim to be real**, otherwise borrowed workloads can block lecture demand.

### `fleet/kai-policy/priorityclasses.yaml`

Add Kubernetes `PriorityClass` objects you’ll later reference from workloads (JupyterHub profiles later), e.g.:

* `kai-course-high` (highest)
* `kai-phd-interactive` (high)
* `kai-batch-low` (low; preemptible)

This doesn’t change anything yet, but it sets the policy primitives in GitOps so later changes are just “apply priorityClassName”.

> KAI integrates with queue priority and workload priority concepts; Ray docs and KAI guides emphasize priority + queues + (optionally) preemption. ([docs.ray.io][3])

---

## D) Bundle 2 — `gpu-nodepools` (labels only, no scheduling changes)

Create:

```
fleet/
  gpu-nodepools/
    fleet.yaml
    node-labels.yaml
```

### `node-labels.yaml`

Add a lightweight, explicit node labeling mechanism.

**What we want:**

* 2 nodes (4 GPUs total) labeled `gpu-pool=courses`
* remaining GPU nodes labeled `gpu-pool=research`

Because Kubernetes doesn’t let you “apply labels declaratively” without a controller, the clean GitOps pattern is to deploy a tiny controller you already trust (or write a tiny job) — but simplest for now:

**Instruction to agent:**

* Do **not** attempt to label nodes via manifests unless you already have a node-labeling controller in the repo.
* Instead, add a `README.md` runbook in this bundle that tells ops exactly which nodes to label and the one-liners.

Example runbook commands:

```bash
kubectl label node <nodeA> gpu-pool=courses --overwrite
kubectl label node <nodeB> gpu-pool=courses --overwrite
kubectl label node <nodeC> gpu-pool=research --overwrite
...
```

(We keep it explicit until you decide to automate node labeling.)

---

# Required “other rules” for KAI (now, before JupyterHub)

## 1) Ensure the label/scheduler interface is documented

Add a short `fleet/kai-policy/README.md` that states:

To use KAI for a workload:

* set `spec.schedulerName: kai-scheduler`
* set label `kai.scheduler/queue: <queueName>` ([docs.opennebula.io][4])

This prevents later confusion and makes the cutover mechanical.

---

## 2) Optional: create a default queue fallback

Some setups expect a `default` queue to exist; include it if you want “safe default” behavior for ad-hoc tests.

* Create `Queue/default` with `gpu.quota=-1` etc.
* You won’t route JupyterHub there later, but it helps early smoke tests. ([exostellar.ai][1])

---

## 3) Add a policy “smoke test” manifest (still no JupyterHub)

Add a pod that explicitly targets KAI + a queue, so you validate:

* KAI is running
* queue CRDs work
* podgrouper/scheduler honors queue label

Example requirements are consistently documented: schedulerName + queue label. ([docs.opennebula.io][4])

---

# What NOT to do in this phase

* **Don’t** patch or mutate workloads cluster-wide.
* **Don’t** set KAI as default scheduler.
* **Don’t** change JupyterHub helm values yet.

This keeps the change low-risk: you’re only adding CRDs/CRs and policy objects.

---

# Deliverables for the code agent

1. `fleet/kai-policy/queues.yaml` with queues: `courses`, `phd-interactive`, `batch` (+ optional `default`)
2. `fleet/kai-policy/priorityclasses.yaml` with 3 priority classes
3. `fleet/kai-policy/fleet.yaml` with `dependsOn` pointing to the kai-scheduler install bundle ([fleet.rancher.io][2])
4. `fleet/gpu-nodepools/README.md` + optional runbook bundle (labels)
5. (Optional) `fleet/kai-policy/smoke-test.yaml` for queue validation

If you paste your Fleet repo’s current bundle names (especially the actual **bundle name** Fleet generates for your `kai-scheduler` path), I can write the exact `dependsOn.name` string so the agent doesn’t have to guess.

[1]: https://www.exostellar.ai/post/gpu-sharing-in-kubernetes-nvidia-kai-vs-exostellar-sdg-e4887?utm_source=chatgpt.com "Exploring GPU Sharing in Kubernetes with NVIDIA KAI ..."
[2]: https://fleet.rancher.io/0.11/ref-fleet-yaml?utm_source=chatgpt.com "fleet.yaml - Rancher"
[3]: https://docs.ray.io/en/latest/cluster/kubernetes/k8s-ecosystem/kai-scheduler.html?utm_source=chatgpt.com "Gang scheduling, queue priority, and GPU sharing ... - Ray Docs"
[4]: https://docs.opennebula.io/7.0/solutions/deployment_blueprints/ai-ready_opennebula/nvidia_kai_scheduler/?utm_source=chatgpt.com "Deployment of NVIDIA KAI Scheduler | - docs - OpenNebula"

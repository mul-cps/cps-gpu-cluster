What we’re deploying (constraints)

KAI Scheduler v0.12.11 (current release as of 2026-02-04)

New namespace: kai-scheduler

No changes to default scheduler (KAI runs in parallel; opt-in per pod)

1) Add a new Fleet bundle folder

Create:

fleet/
  kai-scheduler/
    fleet.yaml
    values.yaml


If your repo uses a different convention (e.g., bundles/), adapt paths accordingly; keep it as an isolated bundle.

2) Fleet bundle definition (Helm deploy)
fleet/kai-scheduler/fleet.yaml

Use Fleet’s Helm support to deploy the chart (recommended: reference the upstream chart location you already standardize on; see two supported options below).

Option A (recommended for reproducibility): vendor the chart from the KAI repo

Add the KAI chart as a vendored directory in your repo (e.g. vendor/kai-scheduler/deployments/kai-scheduler/ from NVIDIA/KAI-Scheduler).

Then point Fleet at the local chart path.

KAI is published as a Helm chart in its repo (under deployments/kai-scheduler).

Example (Fleet bundle):

defaultNamespace: kai-scheduler

helm:
  chart: ./vendor/kai-scheduler/deployments/kai-scheduler
  valuesFiles:
    - values.yaml

# If you use target customization, add selectors here
# targets:
# - clusterSelector:
#     matchLabels:
#       env: prod


Option B: install from NVIDIA’s NGC Helm repo
Some guides install nvidia-k8s/kai-scheduler from https://helm.ngc.nvidia.com/nvidia/k8s.
If you already allow external helm repos in Fleet, use that; otherwise stick to Option A.

3) Provide chart values (pin version, avoid runtimeclass footgun)
fleet/kai-scheduler/values.yaml

Set explicit image registry/tag and a few safe defaults.

global:
  # Prefer explicit registry+tag pin. Version pin is important for reproducibility.
  # v0.12.11 is the latest release as of 2026-02-04.
  tag: v0.12.11

  # Registry depends on how you deploy:
  # - If using GHCR images:
  registry: ghcr.io/nvidia/kai-scheduler

  # If you want GPU sharing later, keep this false for now (since you’re not switching workloads yet).
  # gpuSharing: false

admission:
  # IMPORTANT: if your cluster does NOT have an "nvidia" RuntimeClass,
  # set this to "" to avoid install/runtime issues.
  # (This is a common install gotcha discussed upstream.)
  gpuPodRuntimeClassName: ""

# Optional: keep resource usage modest on control plane
# scheduler:
#   resources: ...


Why the gpuPodRuntimeClassName: ""?

Upstream installation troubleshooting explicitly recommends setting it to empty when there is no nvidia runtime class.
If your GPU Operator already creates an nvidia RuntimeClass, you can later remove this override.

4) Add a minimal “smoke test” workload (optional but useful)

Do not change JupyterHub. Instead add a tiny manifest in the same bundle (or separate kai-scheduler-tests/) that validates the scheduler exists.

Example pod (does not request GPU, just confirms scheduler wiring):

apiVersion: v1
kind: Pod
metadata:
  name: kai-smoke
  namespace: default
spec:
  schedulerName: kai-scheduler
  containers:
  - name: pause
    image: registry.k8s.io/pause:3.9


KAI usage is opt-in by setting spec.schedulerName: kai-scheduler.

If you want to validate queue wiring too, you’ll later add a label like kai.scheduler/queue: <name> (but that requires queue CRs, which we’re not introducing yet).

5) Deploy via Fleet (repo change only)

Commit the new bundle folder(s).

Let Fleet reconcile.

No JupyterHub changes are required (and none should be made in this step).

6) Post-deploy verification commands (runbook)

Have the agent add these checks to your ops notes:

kubectl get ns kai-scheduler
kubectl -n kai-scheduler get pods
kubectl -n kai-scheduler get deploy
kubectl get pods kai-smoke -n default -o wide


Also confirm the scheduler name exists by trying the smoke pod; if it stays Pending with scheduler errors, check scheduler deployment logs.

7) Guardrails (don’t break existing scheduling)

Do not set KAI as the default scheduler.

Do not mutate workloads cluster-wide.

Treat KAI as “installed but unused” until the later JupyterHub migration step.

This matches KAI’s intended “run alongside other schedulers” model.
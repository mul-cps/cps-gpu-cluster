# Troubleshooting Guide

Common issues and solutions for the GPU cluster setup.

## Table of Contents

- [Terraform Issues](#terraform-issues)
- [Ansible Issues](#ansible-issues)
- [K3s Issues](#k3s-issues)
- [GPU Issues](#gpu-issues)
- [Storage Issues](#storage-issues)
- [Fleet/GitOps Issues](#fleetgitops-issues)
- [JupyterHub Issues](#jupyterhub-issues)

---

## Terraform Issues

### Proxmox API connection failed

**Symptom**: `Error: error creating Proxmox client: error reading API token`

**Solution**:
```bash
# Verify API token
pveum user token list terraform@pam

# Recreate if needed
pveum user token add terraform@pam terraform-token --privsep=0

# Update proxmox.tfvars with new token
```

### VM creation fails with GPU passthrough

**Symptom**: `Error: unable to create VM: invalid PCI device`

**Solutions**:

1. Verify GPU is bound to vfio-pci:
```bash
lspci -nnk | grep -A 3 NVIDIA
```

2. Check IOMMU groups:
```bash
find /sys/kernel/iommu_groups/ -type l | grep -i nvidia
```

3. Verify PCI address format in tfvars (must be `0000:XX:YY.Z`)

### Cloud-init timeout

**Symptom**: VMs created but no IP assigned

**Solution**:
```bash
# Check cloud-init status in VM
sudo cloud-init status

# View cloud-init logs
sudo cat /var/log/cloud-init.log

# Verify network bridge in Proxmox
pvesh get /nodes/<node>/network
```

---

## Ansible Issues

### SSH connection failed

**Symptom**: `Failed to connect to the host via ssh`

**Solutions**:

1. Verify VMs are running:
```bash
pvesh get /nodes/<node>/qemu --output-format=json
```

2. Check SSH key:
```bash
ssh -i ~/.ssh/id_rsa ubuntu@10.0.0.11
```

3. Update known_hosts:
```bash
ssh-keygen -R 10.0.0.11
```

### K3s installation hangs

**Symptom**: Ansible task "Install K3s" never completes

**Solutions**:

1. Check network connectivity:
```bash
ansible -i inventory.ini all -m ping
```

2. Verify firewall rules:
```bash
# On nodes
sudo ufw status
sudo ufw allow 6443/tcp
sudo ufw allow 10250/tcp
```

3. Check system resources:
```bash
free -h
df -h
```

### Helm installation fails

**Symptom**: `Error: failed to download "nvidia/gpu-operator"`

**Solutions**:

1. Manually add repo:
```bash
helm repo add nvidia https://nvidia.github.io/gpu-operator
helm repo update
```

2. Check connectivity:
```bash
curl -I https://nvidia.github.io/gpu-operator/index.yaml
```

---

## K3s Issues

### Nodes not joining cluster

**Symptom**: `kubectl get nodes` shows only control planes

**Solutions**:

1. Check K3s agent status:
```bash
sudo systemctl status k3s-agent
sudo journalctl -u k3s-agent -f
```

2. Verify K3s token:
```bash
# On control plane
sudo cat /var/lib/rancher/k3s/server/node-token

# On worker
sudo cat /etc/systemd/system/k3s-agent.service.env
```

3. Check network connectivity:
```bash
# From worker to control plane
nc -zv 10.0.0.11 6443
```

### Control plane not HA

**Symptom**: Only one control plane is leader

**Solutions**:

1. Check etcd status:
```bash
sudo k3s kubectl get endpoints -n kube-system kube-controller-manager
```

2. Verify cluster-init flag:
```bash
sudo systemctl cat k3s | grep cluster-init
```

3. Check etcd member list:
```bash
sudo k3s etcd-snapshot ls
```

### Pods stuck in ContainerCreating

**Symptom**: Pods never start, stuck in `ContainerCreating`

**Solutions**:

1. Check pod events:
```bash
kubectl describe pod <pod-name> -n <namespace>
```

2. Check CNI:
```bash
kubectl get pods -n kube-system -l k8s-app=flannel
```

3. Restart containerd:
```bash
sudo systemctl restart k3s
```

---

## GPU Issues

### GPUs not visible in VMs

**Symptom**: `lspci` shows no NVIDIA devices

**Solutions**:

1. Check Proxmox host:
```bash
lspci | grep -i nvidia
lspci -nnk | grep -A 3 vfio-pci
```

2. Verify VM configuration:
```bash
qm config <vmid> | grep hostpci
```

3. Check VM logs:
```bash
journalctl -u pve-cluster -f
```

### GPU Operator pods failing

**Symptom**: `kubectl get pods -n gpu-operator` shows CrashLoopBackOff

**Solutions**:

1. Check driver installation:
```bash
kubectl logs -n gpu-operator -l app=nvidia-driver-daemonset
```

2. Verify kernel headers:
```bash
# On GPU workers
dpkg -l | grep linux-headers
uname -r
```

3. Check device plugin:
```bash
kubectl logs -n gpu-operator -l app=nvidia-device-plugin-daemonset
```

### nvidia-smi not working

**Symptom**: `nvidia-smi: command not found` in pods

**Solutions**:

1. Check GPU operator installation:
```bash
kubectl get pods -n gpu-operator
```

2. Verify container runtime:
```bash
kubectl get runtimeclass
```

3. Check pod GPU requests:
```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

### No GPUs allocated to pods

**Symptom**: Pods scheduled but `nvidia-smi` shows "No devices found"

**Solutions**:

1. Check node capacity:
```bash
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'
```

2. Verify device plugin:
```bash
kubectl get daemonset -n gpu-operator nvidia-device-plugin-daemonset
```

3. Check node labels:
```bash
kubectl get nodes --show-labels | grep accelerator
```

### ClusterPolicy stuck NotReady / MIG config stuck in "failed"

**Symptom**: `kubectl get clusterpolicy cluster-policy -o jsonpath='{.status.conditions}'` shows
`states not ready: [state-operator-validation state-device-plugin]` (or similar) indefinitely.
A specific node shows `nvidia.com/mig.config.state=failed`, its
`nvidia-device-plugin-daemonset` is `CrashLoopBackOff` with
`unable to create cdi spec file: ... invalid spec, no devices`, and
`nvidia-cuda-validator`/`nvidia-operator-validator` are stuck
`Init:CrashLoopBackOff`.

**Root cause**: `nvidia-mig-manager` hit a transient Kubernetes API conflict
while trying to reconcile the node's MIG geometry (`Operation cannot be
fulfilled on nodes "...": the object has been modified`), gave up, wrote
`mig.config.state=failed`, and then just sits waiting for the
`nvidia.com/mig.config` label to change again — it does not keep retrying on
its own. The node label conflict is usually caused by something else writing
to the node object around the same time (another controller, another
`kubectl label` call, a Fleet reconcile, etc.), not a real hardware fault.

**Fast fix** (works when the node's actual MIG *mode* already matches the
target — i.e. you're only fixing a stuck *geometry* reconcile, not asking it
to flip MIG mode on/off): force a fresh reconcile attempt by deleting the
stuck `nvidia-mig-manager` pod on that node. It restarts, re-reads the label,
and — if there's no real mode change needed — converges cleanly within
seconds, no drain/reboot required:
```bash
kubectl get pods -n gpu-operator -l app=nvidia-mig-manager --field-selector spec.nodeName=<node> -o name
kubectl delete pod -n gpu-operator <that-pod>
# watch for convergence:
kubectl get node <node> -o jsonpath='{.metadata.labels.nvidia\.com/mig\.config\.state}{"\n"}'
```
If the label still flips back to `failed` once, that's usually one more
transient conflict clearing itself — delete the (now-new) mig-manager pod
once more and it should settle to `success`.

Once fixed on all nodes, if `ClusterPolicy` is still reporting stale
conditions despite every pod being `Running`/`Completed`, its controller may
just need a nudge to recompute status — restart it:
```bash
kubectl delete pod -n gpu-operator -l app.kubernetes.io/name=gpu-operator
```

### MIG mode toggle needs a REAL reset — in-guest reboot is not enough on passthrough GPUs

**Symptom**: `nvidia-mig-manager` logs show one of:
```
Error applying MIG configuration with hooks: error initializing NVML: ERROR_LIBRARY_NOT_FOUND
```
or, after an in-guest `systemctl reboot`:
```
Resetting GPU 00000000:XX:YY.Z is not supported.
Error applying MIG configuration with hooks: error resetting all GPUs: exit status 3
```

**Root cause**: unlike a geometry-only reconcile (see above), actually
flipping the MIG *mode* bit (MIG-enabled ↔ MIG-disabled) on a GPU requires a
real device reset (FLR/bus-reset). On PCIe passthrough (VFIO), that reset
only happens when QEMU releases and reacquires the device — i.e., on a full
VM stop/start. A `systemctl reboot` run **inside the guest** only restarts
the guest OS; QEMU and the passed-through GPU never stop, so the device
keeps its prior MIG-mode state across the guest reboot. This is standard,
documented VFIO/QEMU passthrough behavior, not specific to this cluster —
NVIDIA's own MIG guidance for virtualized/passthrough A100s says to reboot
the **VM**, not the guest kernel.

There is no way to make a guest-triggered reboot propagate to a QEMU
restart — that boundary is fundamental to how passthrough works. Kured (this
cluster's automated reboot daemon) is fine for routine OS-patch reboots, but
cannot fix this case by itself.

**Fast fix**: power-cycle the VM at the Proxmox host level (not the guest):
```bash
# on the Proxmox host, replacing <vmid>:
qm stop <vmid>
qm start <vmid>
```
Do this *after* setting the target `nvidia.com/mig.config=all-disabled` (or
whatever geometry you want) on the node — mig-manager will pick it up and
converge once the node rejoins with a genuinely reset GPU. Expect the
driver/device-plugin/validator pods to crashloop transiently for a minute or
two immediately after the node rejoins — that's normal settling, not a new
failure, unless it's still crashlooping after several minutes (see next
entry).

**Before doing this**: cordon and drain the node first (see the Longhorn
entry below for a drain gotcha), and check whether the node hosts a
Longhorn storage replica, an ingress-nginx replica, or other singleton
workloads that would be disrupted — `kubectl get pods -A --field-selector
spec.nodeName=<node>` and cross-check against
`kubectl get replicas.longhorn.io -n longhorn-system` for volumes with only
one replica on that node.

### Driver DaemonSet pod stuck in CrashLoopBackOff after being manually deleted/cycled

**Symptom**: after deleting an `nvidia-driver-daemonset` pod (e.g. to pick up
a config change — this DaemonSet uses `updateStrategy: OnDelete`, so it
never rolls out template changes on its own; you must delete each pod by
hand to force it), the replacement pod's `k8s-driver-manager` init container
crashloops with:
```
Failed to unload kernel module nvidia_uvm: resource temporarily unavailable
Could not unload NVIDIA driver kernel modules, driver is in use
Auto eviction of GPU pods on node <node> is disabled by the upgrade policy
Auto drain of the node is disabled by the upgrade policy
failed to uninstall nvidia driver components: failed to unload driver: resource temporarily unavailable
```

**Root cause**: this cluster's GPU Operator config sets
`ENABLE_GPU_POD_EVICTION: "false"` and `ENABLE_AUTO_DRAIN: "false"`
(`system/gpu/gpu-operator/values.yaml`, `driver.manager.env`) — the driver
manager will not forcibly evict pods still using the GPU, it just fails.
Any pod actively holding the GPU (check
`kubectl get pods -A -o json | jq` for containers requesting
`nvidia.com/gpu` on that node) keeps the kernel module's refcount above zero.

**Fast fix**: identify and delete the pod(s) actually using the GPU on that
node first:
```bash
kubectl get pods -A -o json | python3 -c '
import json,sys
d=json.load(sys.stdin)
for p in d["items"]:
    if p["spec"].get("nodeName") != "<node>": continue
    for c in p["spec"].get("containers", []):
        if any("gpu" in k for k in c.get("resources",{}).get("requests",{})):
            print(p["metadata"]["namespace"], p["metadata"]["name"])
'
kubectl delete pod -n <namespace> <pod-using-gpu>
```
The crashlooping driver pod will succeed on its next automatic retry once
the module's refcount drops to zero — you generally don't need to delete it
yourself, just wait one backoff cycle. If it's still failing with the same
"in use" error after several retries with no decreasing refcount, delete the
crashlooping pod to force a clean init attempt:
```bash
kubectl delete pod -n gpu-operator <driver-daemonset-pod>
```
**Before deleting a GPU-holding pod**: check whether it's a real user's live
session (e.g. a JupyterHub notebook) — this will abruptly kill their running
work. Confirm with the pod's owner/user first if at all possible; this is a
disruptive action, not a routine one.

### GPU Operator daemonsets never scheduling on one specific node

**Symptom**: one GPU worker shows `nvidia.com/gpu` allocatable = 0
indefinitely, and `kubectl get pods -n gpu-operator -o wide` shows **no**
`nvidia-device-plugin-daemonset`/`nvidia-mig-manager`/`gpu-feature-discovery`
pods scheduled there at all (not even in a crash state — just absent),
while the driver daemonset itself did make it onto the node.

**Root cause**: the node has a custom taint (e.g. `gpu-pool=full:NoSchedule`,
used to reserve certain nodes for full-GPU-only workloads) that the GPU
Operator's own daemonsets don't tolerate. The driver pod is often already
running because it was scheduled *before* the taint was applied — taints
don't evict already-running pods, only block new ones.

**Fast fix**: add a matching toleration to
`system/gpu/gpu-operator/values.yaml`'s `daemonsets.tolerations`, then apply
(or, for a quick live check before merging to Git, patch the live
`ClusterPolicy` directly — remember to land the same fix in the repo
afterward so Fleet doesn't fight it on the next sync):
```yaml
daemonsets:
  tolerations:
    - key: gpu-pool
      operator: Exists
      effect: NoSchedule
```
```bash
kubectl patch clusterpolicy cluster-policy --type=json \
  -p='[{"op":"add","path":"/spec/daemonsets/tolerations/-","value":{"key":"gpu-pool","operator":"Exists","effect":"NoSchedule"}}]'
```

### MPS-based GPU sharing setup — full incident and the fast path (RESOLVED, 2026-07-06)

**Update: MPS works fine on this K3s cluster.** An earlier version of this
entry treated an upstream GitHub issue
(https://github.com/NVIDIA/k8s-device-plugin/issues/712) as an unresolved
K3s-specific MPS blocker. It wasn't — the real blockers were four separate,
fixable misconfigurations, found by actually running an end-to-end test
pod rather than trusting the pessimistic issue thread. If MPS sharing looks
broken again in the future, check these four things **in this order**
before assuming it's a platform-level dead end:

**1. `--mig-strategy=mixed is not supported with MPS`** (device-plugin logs)

Symptom: `nvidia-device-plugin-daemonset` crashloops with exactly that
error after selecting an `mps-sharing` device-plugin config.

Root cause: the field that actually drives the device plugin's
`--mig-strategy` flag is `mig.strategy` in `gpu-operator/values.yaml` — a
**separate, different key** from `devicePlugin.migStrategy` (which exists
in this chart's values schema but is functionally inert; setting it alone
does nothing). Confirm which one the live cluster is actually using:
```bash
kubectl get clusterpolicy cluster-policy -o jsonpath='{.spec.mig.strategy}{"\n"}'
```
Fix: set `mig.strategy: none` in `gpu-operator/values.yaml`, then a REAL
`helm upgrade` (not just `kubectl patch`/`kubectl set env` — those get
silently reverted by GPU Feature Discovery re-deriving state from
ClusterPolicy's live spec on its own reconcile cycle):
```bash
helm upgrade gpu-operator nvidia/gpu-operator --version <version> \
  -n gpu-operator -f system/gpu/gpu-operator/values.yaml --reuse-values
```

**2. KAI admission webhook: `"GPU sharing is disabled"`**

Symptom: creating any pod with a `gpu-memory` annotation is flat-out
rejected by `admission.kai-scheduler.svc` before it even reaches the
scheduler.

Root cause: KAI Scheduler's own `global.gpuSharing` Helm value defaults to
`false` — fractional/shared GPU requests are rejected outright until this
is explicitly enabled in `system/gpu/kai-scheduler/values.yaml`.

Fix: `global.gpuSharing: true` in that file, then
`helm upgrade kai-scheduler oci://ghcr.io/nvidia/kai-scheduler/kai-scheduler --version <version> -n kai-scheduler -f values.yaml --reuse-values`.

**3. `nvidia.com/gpu` and `gpu-memory` combined on one pod → `"cannot request both GPU and GPU memory"`**

They're alternative allocation paths, not additive — see the KAI example
manifests in `system/gpu/kai-scheduler/examples/` for the correct shape of
each (whole-GPU jobs use only `nvidia.com/gpu`; MPS-shared jobs use only
the `gpu-memory` annotation, no `nvidia.com/gpu` resource request at all).

**4. `NonPreemptibleOverQuota`: `"Workload requested 0.05 GPUs, but batch quota is 0 GPUs..."`**

This is the subtle one. **KAI treats any PriorityClass value `>= 100` as
non-preemptible, and non-preemptible workloads are hard-capped at their
queue's deserved quota — they can never burst over quota, no matter how
high `overQuotaWeight` is set.** If a queue is deliberately given `quota: 0`
to rely entirely on bursting into idle capacity (as this cluster's `batch`
queue does), every PriorityClass used by that queue's workloads MUST be
kept under 100, or nothing in that queue can ever schedule, full stop. This
cluster's priority classes were originally `1000`/`5000`/`10000`
(`kai-batch-low`/`kai-phd-interactive`/`kai-course-high`) — all comfortably
above the threshold, silently breaking the `batch` queue from day one of
the design. Rescaled to `10`/`50`/`90` (same relative order, same
preemption behavior among each other, just under the hard non-preemptible
line). See `system/gpu/kai-scheduler/kai-policy/priorityclasses.yaml` for
the current values and the full explanation, and
`system/descheduler/values.yaml`'s `priorityThreshold` (which must track
the `kai-batch-low` value + 1, due to a separate strict-less-than
comparison — see that file's own comment).

Reference: `PriorityClass.value` is immutable once created —
`kubectl apply` on a changed value fails with `"may not be changed in an
update"`; use `kubectl delete -f ... && kubectl create -f ...` instead.

**Verification that all four are fixed**: a synthetic pod with a
`gpu-memory` annotation, `kai.scheduler/queue: batch` label, and
`kai-batch-low` priority class should reach `Running`, and
`kubectl exec <pod> -- nvidia-smi` should show the GPU with
`MIG M.: Disabled`. Confirmed working end-to-end on this cluster
2026-07-06.

**Reaching `Running` is not enough — a fifth issue lurks past this point:**
see the next entry. A pod can be `Running` with the correct
`CUDA_MPS_PINNED_DEVICE_MEM_LIMIT` env var set and still have **zero actual
memory enforcement**, silently.

### `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT` set correctly but not enforced at all

**Symptom**: a pod requesting an MPS-shared `gpu-memory` tier runs fine,
`nvidia-smi` shows the GPU, `env | grep CUDA_MPS` shows the limit env var
present and correct — but a workload inside the pod allocates far beyond
that limit with no error at all (confirmed live 2026-07-06: a test pod with
`CUDA_MPS_PINNED_DEVICE_MEM_LIMIT=0=1024M` allocated 16 GiB via PyTorch
before the test script simply ran out of loop iterations, never hitting an
OOM).

**Root cause**: `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT` only has any effect on a
process that actually connects to the MPS control daemon as a client. That
connection requires `CUDA_MPS_PIPE_DIRECTORY` and `CUDA_MPS_LOG_DIRECTORY`
env vars pointing at the daemon's actual socket/log directories, **plus**
volume mounts backing them with the correct hostPath. Without these, CUDA
silently falls back to plain direct GPU access — no MPS, no limit, no
error, nothing in the daemon's logs indicating a client ever tried to
connect. This is easy to get wrong because the pod still schedules,
starts, and runs `nvidia-smi` successfully either way; there is no
observable difference until you specifically try to exceed the limit.

**Fast fix**: every container using `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT` must
also set:
```yaml
env:
  - name: CUDA_MPS_PINNED_DEVICE_MEM_LIMIT
    value: "0=<MiB>M"
  - name: CUDA_MPS_PIPE_DIRECTORY
    value: "/mps/nvidia.com/gpu/pipe"
  - name: CUDA_MPS_LOG_DIRECTORY
    value: "/mps/nvidia.com/gpu/log"
volumeMounts:
  - name: mps-pipe
    mountPath: /mps/nvidia.com/gpu/pipe
  - name: mps-log
    mountPath: /mps/nvidia.com/gpu/log
```
```yaml
volumes:
  - name: mps-pipe
    hostPath:
      path: /run/nvidia/mps/nvidia.com/gpu/pipe
      type: DirectoryOrCreate
  - name: mps-log
    hostPath:
      path: /run/nvidia/mps/nvidia.com/gpu/log
      type: DirectoryOrCreate
```
The exact hostPath is confirmed by checking the real MPS control daemon
pod's own mounts (`kubectl get pod -n gpu-operator -l
app=nvidia-device-plugin-mps-control-daemon -o
jsonpath='{.items[0].spec.containers[0].volumeMounts}'`): it mounts
`/run/nvidia/mps` (host) to `/mps` (container) and creates
`nvidia.com/gpu/{pipe,log}` underneath that at runtime — client pods need
the same host path, one level deeper.

This wiring is now included in `user/jupyter/jupyterhub/values.yaml`'s
`apply_profile_settings` (all VRAM-tier profiles) and in every example in
`system/gpu/kai-scheduler/examples/` — if you write a new MPS-sharing
manifest by hand, copy this pattern rather than just the memory-limit env
var alone.

**How to verify enforcement is actually working**, not just assumed:
deliberately try to exceed the configured limit from inside the pod (e.g. a
small PyTorch script allocating in a loop) and confirm it fails with a CUDA
OOM error at approximately the configured limit, not far beyond it.

### RESOLVED (corrected, 2026-07-06): MPS-shared and multi-GPU-exclusive requests DO coexist on the same node — prior "static split required" conclusion was wrong

**The question**: can a single cluster serve both (a) MPS-shared fractional
GPU requests (`gpu-memory` annotation, this cluster's interactive/student
tier) and (b) genuine multi-GPU-per-pod exclusive requests
(`nvidia.com/gpu: 2` or more, needed for real NVLink/PCIe P2P in distributed
training) on the *same* device-plugin config? This was flagged as an open,
unverified "elastic pool" question throughout this project's design phase.

**Answer: yes, on a plain/exclusive-mode device-plugin node, KAI schedules
both request types side by side via its reservation-pod mechanism.** An
earlier pass through this test (documented in an now-superseded version of
this section) concluded the opposite — that "no config serves both" and a
static per-node split was required. That conclusion was an artifact of an
incomplete test procedure, not a real platform limitation. Root-caused and
corrected live 2026-07-06 after an external review flagged the discrepancy.

**What went wrong the first time**: the original test switched
`k3s-wk-gpu2` to plain mode via a live ConfigMap patch + node label
override, then immediately tried scheduling a `gpu-memory`-annotated pod
and saw it rejected (`didn't have enough resources: GPU memory`), with
scheduler logs showing `Gpus: 51.2` for a 5120 MiB request. That number
is suspicious in isolation — it's exactly what `5120 / 100` gives, and 100
is KAI's internal `DefaultGpuMemory` fallback used when it can't read a
valid `nvidia.com/gpu.memory` node label (the correct A100 computation is
`5120 / 40960 = 0.125`) — but a live label check on that same rejection
attempt was never actually done before writing up the conclusion.

**Redone properly this time**: flipped `k3s-wk-gpu2` back to plain mode
(fresh ConfigMap key `plain-exclusive`, no `sharing.mps` block, same
node-label-override mechanism as before) and immediately checked
`nvidia.com/gpu.memory` — it read `40960`, correctly populated, not
missing/stale. So the specific label-artifact theory doesn't hold either,
at least not on this repeat. What actually happened: on retest, a
`gpu-memory: "5120"` pod scheduled and ran (`Running`) on the plain-mode
node, and KAI automatically created a reservation pod
(`gpu-reservation-k3s-wk-gpu2-*`) in the `kai-resource-reservation`
namespace to back it — the mechanism the earlier design docs flagged but
never confirmed live. With that reservation holding one physical GPU, a
second pod requesting `nvidia.com/gpu: 2` correctly stayed `Pending`
(`GPUs` insufficient — only 1 of 2 physical GPUs free, correct behavior,
not a failure), and a `nvidia.com/gpu: 1` pod scheduled fine on the
remaining free physical GPU, running real `nvidia-smi` output. Both
requests bound successfully on the same node at the same time.

**Practical consequence — reversed from the prior write-up**: the
"elastic unified pool" model (any GPU serves either mode, arbitrated
automatically) is achievable. A static per-node MPS-vs-exclusive split is
NOT required.

**UPDATE (2026-07-06, later same day): rolled out cluster-wide, with one
real blocker found and fixed.** Switched `gpu-operator/values.yaml`'s
`devicePlugin.config.default` from `mps-sharing` to a new `plain` key
(`migStrategy: none`, no `sharing` block) and applied via `helm upgrade`
to all 4 nodes. This is strictly more capable than the old `mps-sharing`
default: it restores real `nvidia.com/gpu: 2+` requests cluster-wide
(needed for genuine multi-GPU/NVLink distributed batch jobs, impossible
under `mps-sharing` due to `failRequestsGreaterThanOne`) while KAI's own
`gpu-memory` + reservation-pod mechanism continues to provide fractional
sharing for interactive/student sessions.

**The real blocker**: GPU Operator's own
`nvidia-device-plugin-mps-control-daemon` DaemonSet only schedules onto
nodes labeled `nvidia.com/mps.capable=true`, and GPU Feature Discovery
only sets that label `true` when the node's resolved device-plugin config
contains a `sharing.mps` block. Switching the cluster-wide default to
`plain` made `mps.capable=false` on every node, and the daemon's
`desiredNumberScheduled` dropped to `0` cluster-wide — killing the MPS
server entirely, which would have silently broken `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT`
enforcement for every JupyterHub session (see the "not enforced at all"
finding above for what that failure mode looks like). Overriding the
`mps.capable` label via a Helm hook was not viable — GFD re-derives it
continuously (same class of problem as the earlier `mig.strategy` label
fight), so any static override would be reverted on GFD's next scan.

**Fix**: deployed a standalone MPS control daemon
(`gpu-operator/mps-control-daemon-standalone.yaml`), cloned from the
operator's own DaemonSet spec but with the `mps.capable` node-selector
requirement dropped, and with no `ownerReference` to `ClusterPolicy` so
the operator's controller does not reconcile/revert it. It reads the
`mps-sharing` ConfigMap key purely for its pipe/log resource-name
definition (`nvidia.com/gpu`), not for Kubernetes-level resource sharing.
Verified live: MPS server healthy and accepting connections on all 4
nodes; a real PyTorch allocation loop with a 1024 MiB
`CUDA_MPS_PINNED_DEVICE_MEM_LIMIT` failed at ~800-878 MiB as expected
(not 40GB), confirming enforcement survived the architecture change; a
`gpu-memory` pod scheduled via a reservation pod on gpu1 and gpu3 (not
just the original gpu2 test), confirming the mechanism generalizes across
nodes, not a one-node fluke.

**Current state**: cluster-wide default is now `plain` device-plugin mode
+ standalone always-on MPS daemon + KAI-native `gpu-memory` sharing. The
`mps-sharing` ConfigMap key is retained (for the standalone daemon's
config, and as a documented fallback/comparison option) but is no longer
selected as any node's actual device-plugin config.

**Lesson for future incidents on this exact question**: don't harden a
single live-test result into a permanent "RESOLVED (empirically)"
conclusion, especially one reached via a config shortcut (ConfigMap +
label patch) rather than the real Helm-driven path. Re-run the discriminator
test — a `gpu-memory` pod and an `nvidia.com/gpu: N` pod both targeting the
same node, with node labels checked immediately beforehand — before trusting
either verdict again.

**Bonus finding from the same test session — real intra-node/intra-pod
multi-GPU bandwidth**: a single pod requesting 2 GPUs on a plain-mode node
measured ~100-116 GB/s effective NCCL all-reduce bandwidth (PCIe P2P), vs.
~0.9-1.4 GB/s for the same benchmark run across 4 separate single-GPU pods
co-located on one MPS-sharing node (NCCL falls back to socket/TCP transport
between separate pods regardless of physical co-location — pods don't share
NVLink/P2P transport unless they're the same process). For real distributed
training performance, genuine multi-GPU-per-pod placement matters far more
than merely scheduling pods onto the same physical node.

**Follow-up (2026-07-06): real 8-GPU/4-node gang-scheduled job, full
cluster.** Ran a genuine `torchrun --nnodes=4 --nproc_per_node=2` job across
all 4 nodes (all 8 physical GPUs, real `nvidia.com/gpu: 2` per pod, explicit
`PodGroup` gang scheduling via KAI). Correctness check passed
(`all_reduce` sum across all 8 ranks matched expected value exactly).
Bandwidth results, untuned defaults:
- All-8-GPU ring `all_reduce`: only ~0.13-0.23 GB/s busbw at every message
  size from 1MB to 1GB — bottlenecked by the slowest link in the ring
  (inter-node, over this cluster's 10GbE fabric), as expected for ring
  collectives.
- Intra-node point-to-point (PCIe, same physical node): 229.8 GB/s at
  256MB — consistent with the earlier 2-GPU finding above.
- Inter-node point-to-point (10GbE): only 0.39 GB/s at 256MB (~3.1 Gbit/s
  of the nominal 10 Gbit/s link) — well under line rate. NCCL's default
  socket transport does not saturate a single 10GbE NIC out of the box.

**Fix applied to the batch job examples**: set `NCCL_SOCKET_NTHREADS=4` /
`NCCL_NSOCKS_PERTHREAD=4` (standard NCCL tuning knobs for non-RDMA
Ethernet fabrics) and `OMP_NUM_THREADS` explicitly (torchrun defaults this
to 1 per process when it can't see the real CPU request, printing
`Setting OMP_NUM_THREADS ... to be 1` on every launch — confirmed live,
leaves most of a multi-core CPU request idle for data-loading/
preprocessing) in `kai-scheduler/examples/pytorch-multi-gpu-training-job.yaml`
and `batch-gang-job.yaml`. These are a reasonable starting point, not
verified-optimal for this exact NIC/driver combination — re-run the
inter-node point-to-point discriminator test above after changing them to
confirm actual improvement before trusting a specific value in production.

**Also applied: `hostNetwork: true` + `NCCL_SOCKET_IFNAME=eth0`** on the
multi-GPU examples. A `hostNetwork` debug pod on `k3s-wk-gpu1` confirmed
pod traffic by default transits this cluster's Flannel CNI overlay
(`cni0`/`flannel.1`, VXLAN, MTU 1450) rather than the physical NIC
(`eth0`, MTU 1500, the node's real IP) directly — extra
encapsulation/copy overhead on every inter-node NCCL packet. This is the
standard fix used by NCCL-on-Kubernetes reference architectures
(Kubeflow Training Operator, cloud GPU node-pool guides) for exactly
this class of problem. Trade-off: `hostNetwork` gives up per-pod network
isolation (the pod uses the node's network namespace and IP directly) —
acceptable for this cluster's trusted internal batch queue, reconsider
for less-trusted workloads. **Not yet re-benchmarked** — re-run the
inter-node point-to-point test after this change to confirm the expected
improvement.

**SUSPECTED BIGGER FACTOR, needs Proxmox-host-level investigation (not
yet actioned — outside this repo's scope, flagged here for whoever has
Proxmox host access)**: this cluster's nodes are Proxmox VMs using
virtio-net for their (virtual) "10GbE" links. virtio-net defaults to a
**single queue**, and all traffic through a single-queue virtio device is
serviced by **one `vhost-net` kernel thread on the Proxmox host** — this
means NCCL's socket-level parallelism (`NCCL_SOCKET_NTHREADS`/
`NCCL_NSOCKS_PERTHREAD`) may have limited effect regardless of tuning,
since all those parallel sockets still funnel through one host CPU
thread. This would fully explain being stuck at ~30% of nominal link
speed independent of any in-guest NCCL tuning. **Before spending more
time on NCCL env vars**, whoever has Proxmox access should:
1. Check whether `vhost-<pid>` threads on the Proxmox host(s) are pinned
   near 100% CPU during an NCCL run (`top`/`htop` on the host) — the
   smoking gun for this bottleneck.
2. Check/enable virtio-net multiqueue: `multiqueue=N` in each GPU
   worker's Proxmox VM config (N matching vCPU count), AND activate it
   inside the guest (`ethtool -L eth0 combined N` — Proxmox creating the
   queues is not enough, the guest must turn them on too).
3. Run a plain `iperf3` test VM-to-VM (no Kubernetes/NCCL involved) to
   establish the actual achievable virtio bandwidth ceiling before
   trusting any further NCCL-level tuning — this isolates the
   infrastructure bottleneck from application-level configuration.
4. Worth checking whether any two GPU worker VMs happen to share the
   same physical Proxmox host — traffic between them would use the
   host's internal bridge, not the physical NIC at all, and could/should
   be far faster than 10GbE if so.

**Operational note**: the 8-GPU run also surfaced a real incident —
force-deleting a stuck pod holding a GPU on one node left that node's
GPUs in a "device busy" state for any subsequent real CUDA workload; see
the dedicated entry below ("Force-deleting a pod with a live CUDA context
can leave the GPU stuck") for the cause and fix.

### Force-deleting a pod with a live CUDA context can leave the GPU stuck ("device busy or unavailable") until the MPS daemon restarts

**Symptom**: after force-deleting a pod that was mid-spawn/holding a GPU
(`kubectl delete pod ... --grace-period=0 --force`), every subsequent real
CUDA workload on that node's GPUs fails deterministically with
`RuntimeError: CUDA error: CUDA-capable device(s) is/are busy or
unavailable`, even in complete isolation (a single pod, no other workload,
no other process shown by `nvidia-smi`/`--query-compute-apps` other than
`nvidia-cuda-mps-server`). `nvidia-smi` itself (query-only) still works
fine, and ECC/throttle status is clean — this is not a hardware fault.

**Root cause**: found live 2026-07-06 on `k3s-wk-gpu4`, hit while
force-deleting a stuck user JupyterHub pod (`jupyter-gottam`) that was
occupying a GPU during an unrelated NCCL benchmark test. Both GPUs on the
node were in `Exclusive_Process` compute mode (required for the MPS
control daemon's server context) — force-killing a client process
mid-context-teardown, or simply the general churn of pods rapidly
claiming/releasing a device in this mode, can leave a stale exclusive-mode
lock at the driver level that a plain `nvidia-smi --gpu-reset` cannot
clear either (`In use by another client` — referring to the still-running
MPS server's own persistent context).

**Fix (verified, no Proxmox-level power cycle needed)**: delete and let
the DaemonSet recreate the `mps-control-daemon-standalone` pod on the
affected node (`kubectl delete pod -n gpu-operator
mps-control-daemon-standalone-<node-suffix>`). This cleanly tears down and
re-establishes the MPS server's own context, which clears the stuck lock.
Verified: a real 2-GPU PyTorch compute workload that failed deterministically
before the daemon restart succeeded immediately after, with correct
results on both devices. This is a much cheaper fix than the VFIO
passthrough GPU reset documented elsewhere in this file (which needs a
real Proxmox-level `qm stop`/`qm start`) — try this first for any
"device busy" error on a node running the standalone MPS daemon before
escalating to a full VM power cycle.

---

## Storage Issues

### kured stuck unable to reboot a node for days ("Cannot evict pod as it would violate the pod's disruption budget")

**Symptom**: `kubectl logs -n kured <kured-pod-on-node>` shows repeated
```
error when evicting pods/"instance-manager-..." -n "longhorn-system" (will retry after 5s): Cannot evict pod as it would violate the pod's disruption budget.
...
Error draining <node>: ... global timeout reached: 45m0s
Unable to cordon or drain <node>: ..., will release lock and retry cordon and drain before rebooting when lock is next acquired
Performing a best-effort uncordon after failed cordon and drain
```
— repeating indefinitely (kured retries on its own schedule, e.g. weekly,
and fails the same way every time), or a manual `kubectl drain <node>` hangs
on Longhorn's `instance-manager` pod specifically.

**Root cause**: Longhorn's `instance-manager` PodDisruptionBudget only
allows eviction when its own **node-drain-policy** setting says it's safe.
Check the live value — it may not match what's declared in
`system/storage/longhorn/values.yaml`:
```bash
kubectl get settings.longhorn.io -n longhorn-system node-drain-policy -o jsonpath='{.value}{"\n"}'
```
If this doesn't match the repo's `defaultSettings.nodeDrainPolicy`, the
declared value is probably not a real Longhorn enum (valid values are
`block-if-contains-last-replica`, `allow-if-replica-is-stopped`,
`always-allow` — anything else is silently ignored, and Longhorn keeps the
`block-if-contains-last-replica` default). This is exactly what happened
here: the repo had `allow-if-healthy`, which isn't a valid value, so it
never actually applied.

Separately, check for an under-replicated volume with its only copy on the
node you're draining — this alone can trip
`block-if-contains-last-replica` even when the rest of the node's volumes
are fully redundant elsewhere:
```bash
kubectl get replicas.longhorn.io -n longhorn-system -o jsonpath='{range .items[?(@.spec.nodeID=="<node>")]}{.spec.volumeName}{"\n"}{end}' | sort -u
# for each volume, check replica count/state across all nodes:
kubectl get replicas.longhorn.io -n longhorn-system -o jsonpath='{range .items[?(@.spec.volumeName=="<volume>")]}{.spec.nodeID}{" "}{.status.currentState}{"\n"}{end}'
```

**Fast fix**: correct the setting to a real value (`allow-if-replica-is-stopped`
is the right choice for a cluster using `kured`/unattended-upgrades — it
permits eviction when a volume's only local replica is already
stopped/detached, which is the common case for planned reboots):
```bash
kubectl patch settings.longhorn.io -n longhorn-system node-drain-policy \
  --type merge -p '{"value":"allow-if-replica-is-stopped"}'
```
Also fix `system/storage/longhorn/values.yaml`'s
`defaultSettings.nodeDrainPolicy` to the same value and land it via Fleet —
otherwise the next Longhorn Helm reconcile could silently reset it back to
whatever the (broken) declared value was.

Note this may not clear a block caused by a volume whose replica is
**actively running** (not stopped) and genuinely has no other copy — that's
a real single-point-of-failure and `allow-if-replica-is-stopped` correctly
still blocks it. Fix the under-replication itself (get a second healthy
replica onto another node) rather than loosening the policy further.

### NFS mount failed

**STALE (corrected 2026-07-06)**: this section previously referenced an
`nfs-subdir-external-provisioner` in an `nfs-provisioner` namespace and an
`nfs-client` StorageClass at `10.0.0.30` -- none of this exists in the
cluster (confirmed live: no `nfs-provisioner` namespace, no `nfs-client`
StorageClass; `kubectl get storageclass` shows only `fast-scratch`,
`local-path`, `longhorn`, `longhorn-fast`, `longhorn-overcommit`,
`longhorn-static`). This was either a planned-but-never-deployed setup or
removed long ago without updating this doc. All persistent storage on
this cluster goes through Longhorn or local-path -- there is no
general-purpose NFS storage class. If a manifest references
`storageClassName: nfs-client`, that's the bug, not the cluster (this
exact mistake caused `jhub-shared-rwx`/`jhub-userdir-rwx` PVCs on the
`non-production-testing` branch to be stuck Pending for 7+ months -- see
below).

The only real NFS dependency in this cluster is Longhorn's own **backup
target** (see the next section) -- an external NFS export used for
off-cluster backups, unrelated to any StorageClass or provisioner.

### Longhorn backup target NFS mount failing (recurring backups silently broken)

**Symptom**: `kubectl get backuptarget.longhorn.io default -n longhorn-system`
shows `available: false`, with a condition message ending in `mount failed:
exit status 32`. Recurring backup jobs (`backup-all`, cron `0 22 * * *`)
silently fail to create off-cluster backups; Longhorn's snapshot
auto-cleanup (which only fires after a *successful* backup) stops
pruning, and local snapshots accumulate unbounded.

**Found live 2026-07-06**: target is
`nfs://193.170.30.58:/mnt/persistent1/proxmox_backups/cit-gpu-01/longhorn`
(configured out-of-band via the Longhorn UI/kubectl -- not tracked
anywhere in this repo's GitOps manifests, so there's no version-controlled
record of when or why it was set up this way).

**This is a genuinely recent break, not old neglect** -- initially assumed
otherwise, but checking `kubectl get backups.longhorn.io -n longhorn-system`
showed 1048 completed backups, the most recent at **2026-07-05T22:00:36Z**
(the night before this was noticed), and the backup-target's own
`lastSyncedAt` shows it went unavailable at **2026-07-06T12:22:15Z** --
roughly a 14-hour window. So this broke sometime that morning, not months
ago. The ~2158 local snapshots (~463GB) found during this same
investigation are consistent with **normal** retention accumulation given
regular daily backups were working until the day before, not runaway
failure -- don't re-derive alarm from that number alone.

**Diagnosis so far**: TCP port 2049 (nfsd) on `193.170.30.58` is reachable
from both the Proxmox host and a cluster node directly (`nc -zv` succeeds
from both). But `showmount -e 193.170.30.58` from inside the cluster hangs
indefinitely -- suggesting the NFS **mount protocol/rpcbind (port 111) or
mountd** is unreachable or filtered, even though the main NFS data port
isn't. This is consistent with `mount failed: exit status 32` (a very
common `mount.nfs` failure mode when the MOUNT protocol can't complete),
though the export path itself (`/mnt/persistent1/proxmox_backups/...`)
could also simply be missing or reconfigured on the server side --
without access to `193.170.30.58` itself this can't be narrowed further
from the cluster side.

**Needs**: whoever administers `193.170.30.58` to check the NFS export
config and firewall rules for port 111/rpcbind specifically, and confirm
the export path still exists. This also has no documented owner/runbook
in this repo -- worth adding one once resolved, including moving the
backup target config into GitOps (a `BackupTarget` custom resource can be
applied declaratively) so future changes are tracked.

**Verify it's fixed**:
```bash
kubectl get backuptarget.longhorn.io default -n longhorn-system -o jsonpath='{.status.available}'
# should print "true"; then confirm a new backup completes at the next 22:00 cron run
```

### PVC stuck in Pending

**Symptom**: `kubectl get pvc` shows Pending status

**Solutions**:

1. Check PVC events:
```bash
kubectl describe pvc <pvc-name>
```

2. Verify StorageClass:
```bash
kubectl get sc
kubectl describe sc <storage-class>
```

3. Check provisioner logs:
```bash
kubectl logs -n kube-system -l app=local-path-provisioner
```

### Fast-scratch not working

**Symptom**: PVCs using fast-scratch SC fail

**Solutions**:

1. Verify NVMe mount on workers:
```bash
# On GPU workers
df -h | grep nvme
ls -la /mnt/nvme/scratch
```

2. Check StorageClass:
```bash
kubectl get sc fast-scratch -o yaml
```

3. Verify node selector:
```bash
kubectl get nodes -l scratch=nvme
```

### Longhorn upgrade skipped (2026-07-06): capacity/eviction state too unstable

**Context**: a routine version-bump pass considered upgrading Longhorn
from v1.9.2 towards v1.10.x/v1.11.3. This was intentionally SKIPPED.

**Why**: this cluster has an unresolved Longhorn capacity problem --
`default-disk` is mid-eviction-adjacent on all 4 GPU nodes and
`nvme-scratch` is scheduled beyond 100% capacity on 3/4 nodes. Checking
live volume state (`kubectl get volumes.longhorn.io -n longhorn-system`)
at the time confirmed the risk is not theoretical:

- 1 volume `degraded`/`attached` (rebuild-in-progress signature)
- 2 volumes `faulted`
- 33 volumes `unknown`/`detached` (expected for currently-unmounted PVCs,
  not itself a problem)

Longhorn upgrades replace the manager/engine images cluster-wide and can
trigger engine live-upgrades on attached volumes; doing that while a
volume is already mid-rebuild or faulted, on top of disks already at/over
capacity, risks turning a recoverable degraded-volume situation into data
loss. Per the standing guidance for this pass ("any risk -> skip"), the
upgrade was not attempted.

**Before attempting this upgrade in the future**:
1. Resolve the underlying capacity/eviction problem first (rebalance or
   add capacity so no disk is over 100% scheduled).
2. Re-check `kubectl get volumes.longhorn.io -n longhorn-system` and
   confirm zero volumes are `degraded`/`faulted`/rebuilding.
3. Take/verify recent backups of any volume holding non-reproducible data
   before upgrading.
4. Only then proceed with the v1.9.2 -> v1.10.x/v1.11.3 bump, following
   Longhorn's official upgrade path (no version-skipping across major
   minors per their docs).

---

## Fleet/GitOps Issues

### Pausing Fleet during live incident remediation

When fixing a live cluster problem with direct `kubectl`/`helm` changes
(acceptable only as an immediate, temporary fix — see repo conventions in
`CLAUDE.md`), pause the production GitRepo first so a Fleet reconcile can't
land mid-incident and interact unpredictably with in-progress manual
changes, especially if the matching fix hasn't been merged to `main` yet:
```bash
kubectl patch gitrepo cluster-maintenance -n fleet-local --type merge -p '{"spec":{"paused":true}}'
```
Check whether the relevant Bundle has `correctDrift` enabled — if not
(`kubectl get bundle <name> -n fleet-local -o jsonpath='{.spec.correctDrift}'`
returns empty), Fleet won't actively revert manual changes on its own
between reconciles; it only flags the Bundle as `Modified`. The real risk is
a *future* reconcile applying stale values from `main` if your fix hasn't
landed there yet, not Fleet's normal polling silently undoing things.

**Always unpause once the durable fix is merged to `main`** — don't leave
production GitOps paused indefinitely:
```bash
kubectl patch gitrepo cluster-maintenance -n fleet-local --type merge -p '{"spec":{"paused":false}}'
```

### GitRepo not syncing

**Symptom**: Fleet shows old commit or not syncing

**Solutions**:

1. Check GitRepo status:
```bash
kubectl get gitrepo -n fleet-local cluster-maintenance -o yaml
```

2. Force sync:
```bash
kubectl annotate gitrepo cluster-maintenance -n fleet-local \
  force-sync="$(date +%s)" --overwrite
```

3. Check Fleet agent logs:
```bash
kubectl logs -n cattle-fleet-system -l app=fleet-agent
```

### Bundle stuck in NotReady

**Symptom**: `kubectl get bundles` shows NotReady

**Solutions**:

1. Check bundle status:
```bash
kubectl describe bundle <bundle-name> -n fleet-local
```

2. Check target cluster:
```bash
kubectl get clusters -n fleet-local
```

3. Verify bundle deployment:
```bash
kubectl get bundledeployments -A
```

### Helm release failed

**Symptom**: Fleet shows Helm release error

**Solutions**:

1. Check Helm releases:
```bash
helm list -A
```

2. View Helm history:
```bash
helm history <release-name> -n <namespace>
```

3. Manual rollback:
```bash
helm rollback <release-name> -n <namespace>
```

---

## JupyterHub Issues

### Hub pod not starting

**Symptom**: JupyterHub hub pod in CrashLoopBackOff

**Solutions**:

1. Check logs:
```bash
kubectl logs -n jupyterhub -l component=hub
```

2. Verify database:
```bash
kubectl get pvc -n jupyterhub
```

3. Check secrets:
```bash
kubectl get secret -n jupyterhub hub-secret -o yaml
```

### User pods not spawning

**Symptom**: Users can't start notebooks

**Solutions**:

1. Check JupyterHub logs:
```bash
kubectl logs -n jupyterhub -l component=hub --tail=100
```

2. Verify resources available:
```bash
kubectl top nodes
kubectl describe nodes
```

3. Check quotas:
```bash
kubectl get resourcequota -n jupyterhub
```

### GPUs not available in notebooks

**Symptom**: `nvidia-smi` fails in notebook

**Solutions**:

1. Verify profile configuration:
```bash
kubectl get configmap -n jupyterhub hub -o yaml | grep -A 20 profileList
```

2. Check pod GPU requests:
```bash
kubectl describe pod -n jupyterhub jupyter-<username>
```

3. Verify node has GPUs:
```bash
kubectl get nodes -o json | jq '.items[] | select(.metadata.labels.accelerator=="nvidia")'
```

### Persistent storage issues

**Symptom**: User notebooks lose data

**Solutions**:

1. Check PVCs:
```bash
kubectl get pvc -n jupyterhub
```

2. Verify storage class:
```bash
kubectl get sc nfs-client -o yaml
```

3. Check NFS mounts:
```bash
kubectl exec -n jupyterhub jupyter-<username> -- df -h
```

---

---

## Knative Issues

### Kourier Gateway failing to start

**Symptom**: `kourier-gateway` pods restarting, liveness probes failing with `connection refused`.
Logs show: `StreamAggregatedResources gRPC config stream to xds_cluster closed: 13`.

**Cause**: Version incompatibility between the Kourier Controller (e.g. v1.20.0) and newer Envoy Proxy versions (e.g. v1.34+). The xDS protocol version or configuration format changed in newer Envoy versions.

**Solution**:
Downgrade the Envoy image in the Kourier deployment to a compatible version (e.g., `v1.30-latest`).

```bash
# In kourier.yaml
image: docker.io/envoyproxy/envoy:v1.30-latest
```

---

### Knative Serving 1.22.x upgrade blocked by Kubernetes version requirement (2026-07-06)

**Symptom**: after applying `knative-v1.22.1` serving-core.yaml/serving-crds.yaml
and matching `net-kourier` v1.22.1 kourier.yaml, the `controller` and `webhook`
Deployments crashloop immediately with:

```
{"severity":"EMERGENCY", ... "message":"Version check failed", ...
"error":"kubernetes version \"1.33.5+k3s1\" is not compatible, need at least
\"1.34.0-0\" (this can be overridden with the env var \"KUBERNETES_MIN_VERSION\")"}
```

**Cause**: Knative Serving 1.22 raised its minimum supported Kubernetes
version to 1.34.0. This cluster runs K3s v1.33.5 (control-plane upgrades
are out of scope for this pass -- handled separately due to higher risk).
1.22 is therefore not installable here without also bumping K3s.

**Resolution taken**: rolled back live (`kubectl apply -k` with the
previous 1.20.1 `serving-crds.yaml`/`serving-core.yaml`/`kourier.yaml`
restored via `git checkout`). All `knative-serving` and `kourier-system`
pods returned to `Running`/healthy on 1.20.1, and the `ollama` `ksvc`
in `llm` reported `READY=True` again post-rollback. One follow-up quirk
during rollback: the `config.webhook.serving.knative.dev` validating
webhook rejected re-applying the old `config-gc` ConfigMap ("the update
modifies a key in \"_example\" ... probably not what you want") because
the 1.22.1 apply had already rewritten its `_example` text/checksum
annotation; deleting the ConfigMap and recreating it via `kubectl apply`
**without** the `knative.dev/example-checksum` annotation resolved it
(Knative recomputes/validates that annotation itself; it isn't required
on create).

**Do not retry this bump** until K3s is upgraded to >= 1.34 (`KUBERNETES_MIN_VERSION`
env var override was deliberately not used here to sidestep this, since
that masks an unsupported combination rather than fixing it). Once K3s
is >= 1.34, knative-v1.22.1 / net-kourier v1.22.1 should be revisited.

---

## General Debugging Commands

### Check cluster health

```bash
# Node status
kubectl get nodes -o wide

# All pods
kubectl get pods -A

# Events
kubectl get events -A --sort-by='.lastTimestamp'

# Logs from all containers
kubectl logs -n <namespace> <pod> --all-containers=true
```

### Resource usage

```bash
# Node resources
kubectl top nodes

# Pod resources
kubectl top pods -A

# Describe node for allocated resources
kubectl describe node <node-name>
```

### Network debugging

```bash
# DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup kubernetes.default

# Network connectivity
kubectl run -it --rm debug --image=nicolaka/netshoot --restart=Never -- bash

# Service endpoints
kubectl get endpoints -A
```

### Storage debugging

```bash
# PV/PVC status
kubectl get pv,pvc -A

# Storage class
kubectl get sc

# CSI drivers
kubectl get csidrivers
```

---

## Getting Help

If issues persist:

1. **Check logs systematically** from bottom of stack up
2. **Search GitHub issues** for similar problems
3. **Rancher Forums**: https://forums.rancher.com/
4. **K3s Issues**: https://github.com/k3s-io/k3s/issues
5. **NVIDIA GPU Operator**: https://github.com/NVIDIA/gpu-operator/issues

### Collecting Debug Info

```bash
# K3s check
sudo k3s check-config

# System info
kubectl cluster-info dump > cluster-dump.txt

# GPU operator info
kubectl logs -n gpu-operator --all-containers=true --tail=-1 > gpu-operator.log

# Fleet info
kubectl get gitrepo,bundles,bundledeployments -A -o yaml > fleet-debug.yaml
```

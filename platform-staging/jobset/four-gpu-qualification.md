# Four-GPU JobSet runtime qualification

On 2026-10-06, a trusted operator fixture completed a four-rank NCCL collective
on four distinct A100-PCIE-40GB GPUs, forced one child Job to fail, repeated the
collective after one JobSet restart, and removed its child workloads. See
[four-gpu-report.json](four-gpu-report.json) for exact evidence and scope.

The generated JobSet uses the compute launcher application source at
`5771df5e3db86a59b20fcf965cc3ce273df0c503`, the deployed JobSet 0.12.0 controller
and KAI 0.18.1. Its fixed image is:

```
ghcr.io/mul-cps/cps-jupyter-notebook@sha256:6a0fc97f17ac13f70c06b834a37641116407a0d134ea23ed3d67eac0f55fc0ab
```

Each worker requests/limits one exclusive GPU, one CPU and 4GiB RAM. Both attempts
use four ranks across three nodes; two workers on one node use distinct device
UUIDs. A read-only CUDA property probe confirmed four distinct physical devices
in the replacement attempt, each visible as its worker's sole CUDA device.

The worker uses PyTorch 2.11.0+cu129 and NCCL over the Pod Ethernet interface.
InfiniBand and NCCL shared-memory transport are disabled for this bounded fixture;
no host networking, hostPath, IPC sharing or added privileges are used. Ten
reductions of 1024-element CUDA tensors per attempt sum rank values 1+2+3+4 to 10
on every rank. This is a functional communication test, not training-throughput
or model-scale memory qualification.

JobSet's [stable Pod DNS](https://jobset.sigs.k8s.io/docs/concepts/) identifies rank
zero for rendezvous. The worker derives its rank from its generated hostname.
IPv6 resolution warnings occurred while rank zero was not yet available; IPv4
rendezvous and both four-rank collectives succeeded. Cold image pulls delayed
three workers but finished within the 120-second distributed rendezvous timeout.
The 900-second per-child deadline bounds the operator test; these observations
do not qualify the teaching startup-burst targets.

A unique namespace uses restricted Pod Security, token mounts disabled, no
workload credentials, and a NetworkPolicy permitting only peers in that namespace
and cluster DNS. A fixture-specific copy of the live admission policy/binding
uses its own image parameters and namespace selectors/match condition. Production
catalog, admission parameters and distributed/GPU qualification remain unchanged.
The fixture marks only its private in-memory exclusive profile eligible for this
controlled job; it does not approve production GPU profiles.

After all initial ranks report successful collectives, the operator shortens
one observed UID-owned child Job's active deadline. JobSet recreates workers;
all replacement ranks repeat the collective and complete. Launcher termination
and cleanup sweeps remove Jobs, Pods and KAI PodGroups while retaining the parent
idempotency tombstone. Cross-owner SDK inspection is denied. Finally, the
namespace and its admission objects are deleted. The existing one-GPU resource
reservation for interactive use remains running; no human workload is stopped.

Private evidence and the executable operator fixture are in
`cps-platform-evidence/2026-10-06/jobset-four-gpu/`. The report includes the
fixture and eight collective-log hashes. Raw Pod/JobSet snapshots additionally
record resource requests, node placement and runtime image IDs.

Remaining gates:

- Checkpoint persistence and actual model/optimizer restore across retries.
- Eight-GPU communication/retry: all eight devices must be safely available;
  the current interactive reservation leaves only seven unreserved GPUs.
- Authenticated gateway authorization and qualified production launcher/storage.
- Scheduling/fairness, protected sessions, startup bursts and throughput.
- Shared GPU hard isolation, which this exclusive-GPU test does not address.

Production distributed and group GPU access remain disabled.

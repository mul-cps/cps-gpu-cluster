# Variable MPS profile qualification

Status: candidate / not deployed. Do not apply the DaemonSet patch as a complete
replacement manifest: merge it into the existing standalone daemon specification.
The ConfigMap affects that daemon only, never the physical GPU device plugin.

The production daemon reads `device-plugin-config/mps-sharing` with replicas=8.
On the nominal 40 GiB A100, live MPS commands reported a 5 GiB memory ceiling and
12% thread ceiling. A client environment can only reduce daemon/server ceilings,
so setting 10/20 GiB or 25/50% inside a Pod cannot restore the larger budget.
The existing replica-count comment claiming it only bounds concurrency is wrong.
See [NVIDIA MPS environment semantics](https://docs.nvidia.com/deploy/mps/appendix-environment-variables.html).

The candidate daemon uses a separate replicas=1 configuration to provide a full
device server ceiling. Fixed trusted client settings supply each profile's memory
and SM fraction, while KAI/HAMi schedule and enforce the memory budget. Client
settings alone are not a security boundary: user code can change its environment.
Qualify the combined runtime and admission rules before enabling any shared profile.

In controlled tests on 2026-10-06, seven 5 GiB clients allocated 4.5 GiB each on one
A100 (32,785 MiB measured physical usage). Three 10 GiB clients initially failed
under the 5 GiB server cap. With a temporary existing-server override, three 10 GiB
clients allocated 9.5 GiB each, executed a CUDA memset, and completed on one A100
(29,593 MiB physical usage). Their 25% compute setting reported 26 visible SMs.
The mixed20/10/5 GiB clients also completed together on one A100 and executed
CUDA memset; the20 GiB client reported54 visible SMs at50%. Its peak physical
memory usage was not sampled. The temporary server override was restored to
5 GiB and12% after all clients exited.

These checks do not qualify hostile CUDA bypass, workload throughput, teaching
reclaim, maximum-load startup, all-node runtime behavior or protected sessions.

Before daemon rollout, prevent new GPU starts in the controlled maintenance scope,
confirm no active MPS clients or physical GPU workloads, and preserve CPU servers.
A daemon restart interrupts its clients. Restore scheduling access after checking
all nodes and clear any temporary qualification overrides. The main device plugin
must keep its plain configuration and continue reporting two physical GPUs per node.

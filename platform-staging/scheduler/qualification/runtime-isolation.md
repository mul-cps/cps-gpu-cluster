# Runtime GPU isolation qualification

Status: failed runtime override gate; GPU policy remains disabled.

On 2026-10-06, a trusted operator probe on idle `k3s-wk-gpu2` demonstrated:

| Check | Result |
|---|---|
| Ordinary 6 GiB allocation with nominal 5 GiB assignment | Denied |
| Unsetting `LD_PRELOAD` (system preload still mounted) | Denied |
| Raising the environment limit with existing cache | Denied |
| Debug disable flag with existing cache | Denied |
| Raising limit after removing writable local cache | **6 GiB allocation succeeds** |
| Peer on the same physical GPU continues through all attempts | Passed |

The failing subprocess reports a total of 42,405,855,232 bytes rather than
5,582,618,624 bytes. The nominal limit is therefore not authoritative against
arbitrary notebook code. The probe freed the allocation, kept the peer working,
used a pinned trusted image, and deleted only its own ephemeral pods. It did not
change MPS server configuration, teaching sessions, quotas or grants.

### Combined-stack evidence boundary

A follow-up read-only inspection confirmed that the source fixture
`hami-20g-peer` has neither an MPS socket mount nor an MPS connection environment.
The runtime probe therefore exercises **HAMi alone**, not a qualified HAMi/MPS
combination. Its failure remains valid evidence for that scope.

The live standalone MPS daemon explicitly runs `nvidia-smi -c DEFAULT` every
five seconds. Both GPUs on the inspected idle node report Default mode. This
does not enforce MPS as the sole CUDA arbiter. NVIDIA recommends
`EXCLUSIVE_PROCESS` for that purpose, and documents that client memory limits
can only further constrain the server's limit:
[MPS deployment guidance](https://docs.nvidia.com/deploy/mps/latest/when-to-use-mps.html),
[MPS memory-limit hierarchy](https://docs.nvidia.com/deploy/mps/appendix-environment-variables.html).

A subsequent controlled combined-stack probe mounted the actual MPS pipe and
shared-memory directory. The MPS controller confirmed a participating client.
With the fresh HAMi cache and enlarged environment limit, MPS still denied the
6 GiB allocation. Setting the client pipe to a nonexistent path, while resetting
the writable HAMi cache, allowed the same 6 GiB allocation. The peer continued
on the same physical GPU through all six attempts. No daemon limits or compute
modes were changed, and the probe removed its own pods.

Thus the current **combined HAMi/MPS stack also fails the runtime override gate**.
Evidence is retained in the operator archive as
`2026-10-06/gpu-runtime/combined-mps.json`; the report records actual MPS clients,
CUDA return values, GPU identities and peer progress.

Remaining qualification must prove an authoritative enforcement path, distinct
5/10/20 GiB profile limits and compatibility with exclusive batch jobs. A single
daemon-wide ceiling does not establish those distinct per-profile limits.
Do not change production compute modes while existing sessions are active.

The probe runner is `scripts/compute-platform/qualify-gpu-runtime.py`. It refuses
nodes with an active GPU workload/reservation, requires the scoped qualification
namespace, bounds allocations and pod lifetimes, and records negative evidence.
Its safety guards have dedicated tests. Never run it from a public PR runner.

The live resource-isolator webhook was also missing its reviewed scheduler
condition; it now applies only to namespaces labeled
`compute.cps.unileoben.ac.at/isolation=required` and Pods using `kai-scheduler`.
Only the operator qualification namespace currently has this isolation label.

## Deployment boundary

The existing KAI/HAMi/MPS stack has ordinary OOM and packing evidence, but that
cannot prove tamper-resistant quotas. HAMi describes its in-container enforcement
as cooperative sharing on a trusted cluster:
[HAMi security model](https://github.com/Project-HAMi/HAMi/security).
The core also documents environment-controlled limits and resetting the local
cache when changing them:
[HAMi-core usage](https://github.com/Project-HAMi/HAMi-core).

If quotas must survive arbitrary notebook code, qualify the complete enforcement
path rather than merely suppressing one environment override. MIG offers dedicated
compute and memory paths, but changes packing/reconfiguration and exclusive-job
behavior; it needs a reviewed policy/scheduling migration:
[NVIDIA MIG introduction](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/introduction.html).

Do not declare the eight-GPU pool qualified or enable GPU profiles from the
ordinary allocation tests alone. The runtime trust requirement is awaiting user
clarification while independent platform implementation continues.

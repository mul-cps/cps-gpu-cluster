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

If quotas must survive arbitrary notebook code, qualify a hardware-backed design
rather than merely suppressing one environment override. MIG offers dedicated
compute and memory paths, but changes packing/reconfiguration and exclusive-job
behavior; it needs a reviewed policy/scheduling migration:
[NVIDIA MIG introduction](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/introduction.html).

Do not declare the eight-GPU pool qualified or enable GPU profiles from the
ordinary allocation tests alone. The runtime trust requirement is awaiting user
clarification while independent platform implementation continues.

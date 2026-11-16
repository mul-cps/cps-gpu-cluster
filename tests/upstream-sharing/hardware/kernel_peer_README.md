# Bounded kernel and peer-memory witness

`kernel_peer_probe.py` uses only Python ctypes and libcuda. It loads embedded
PTX 7.0, launches a 256-thread integer affine kernel on both exact GPU2 UUIDs,
and compares all 256 output values against a CPU reference. Two 1024-byte
ordinary device allocations per card are the only explicit device allocations;
CUDA context/module overhead is driver-managed and is not claimed as 2 KiB.

Each direction queries `cuDeviceCanAccessPeer`. A supported direction must
enable access, copy with `cuMemcpyPeer`, and execute a kernel that directly
reads the other GPU's allocation. Both results must match CPU references.
An unsupported direction records **UNSUPPORTED direct P2P** and checks a
separate explicit host-staged copy; it cannot produce a direct-P2P pass.
All unexpected API/module/kernel errors fail. Contexts, modules and allocations
are explicitly released. See the [CUDA peer access contract](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__PEER__ACCESS.html).

`kernel_peer_run.py` renders without cluster calls unless `--execute` is given.
Execution is only authorized inside the root's explicitly released hardware
window. It uses an ordinary nonroot admin Pod requesting `nvidia.com/gpu: 2`,
runtime `nvidia`, RuntimeDefault AppArmor/seccomp, no extra capabilities, and no
service-account token. It does not weaken or replace the NRI configuration.
The Pod deadline is 240 seconds; probe execution timeout is 90 seconds.
Delete uses exact Pod UID/resourceVersion preconditions with normal grace.
Host observations require the exact candidate boot, source SHA, loaded UVM
srcversion and both managed-memory guard settings Y; idle clients are checked
before execution and after deletion. This is a diagnostic witness, not a
cluster promotion or general framework.

```sh
python3 -B tests/upstream-sharing/hardware/kernel_peer_run.py \
  --execute --output NEW_EVIDENCE_DIRECTORY
```

2026-11-16 result: both kernels and both direct-P2P directions passed on actual
candidate image `c3b71557aa17df43faad5a2661d81f1025ba355ac3adf784096de12cd2ef3e73`.
Evidence: `docs/operations/evidence/upstream-sharing-20261116/managed-policy-load/kernel-peer/retry-stdin/`.
The first attempt in the parent evidence directory failed at HTTP 414 before
Python/CUDA execution because inline `kubectl exec -c` arguments exceeded the
ingress URI limit. It was cleaned normally. Root explicitly re-released the
window for the corrected stdin transport. That failure remains recorded as
fixture transport, not a CUDA result.

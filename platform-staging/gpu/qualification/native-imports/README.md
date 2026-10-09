This is an inert, trusted qualification probe for no-MIG R615 native memory accounting. It does not configure caps, enforce policy, start MPS, modify drivers or authorize production access. CUDA IPC/VMM and retained backing remain **hardware-unqualified** until the operator records actual owner/importer/native/physical accounting.

The source includes the official CUDA13.4.92 `cuda.h`, verifies its hash before CPU compilation, and dynamically resolves the declared API types from `libcuda.so.1`. There is no nvcc, CUDA stub library, guessed VMM ctypes structure, preload shim, GPU reset or MIG operation. The header is obtained by extracting, without installing, [NVIDIA's cuda-cudart-dev13.4.92 package](https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-cudart-dev-13-4_13.4.92-1_amd64.deb).

Package SHA256: `71bf3d001f2560a4710bdaba9297fcd3f775a50e3b320ec1c5fcc880d458b0df`.
Header SHA256: `7a79d67ca888061b1dfbe4739b51ad64f85a2f3ad874947ce09b2c635b4c7072`.
Compile in an Ubuntu24.04 environment compatible with the qualification Pods, using:

```sh
python3 compile_probe.py --headers /approved/cuda/include --output /approved/output/native-imports --compile
/approved/output/native-imports
CPS_CUDA_HEADER_DIR=/approved/cuda/include python3 -m unittest discover -s . -p 'test_*.py' -v
```

The default invocation reports inert state without loading CUDA. Executable invocation requires `--execute`, the exact physical `--gpu-uuid`, UID1000/GID100, no `LD_PRELOAD`, driver API13.4+, pageable-memory attributes88/100 bothzero, and a process memory-info total matching `--cap-mib 512` or `5120`. Root must additionally verify exact Pod/cgroup/native cap/backend/module/source identities before releasing the CUDA gate. The binary only checks the process-visible cap; it cannot replace native cgroup accounting observations.

All successfully touched payload allocations are fixed64MiB. Device granularity must divide64MiB. `vmm-direct` checks create/map/access/fill19/free, requests the entire configured cap while positive context overhead is already charged, requires numeric CUDA OOM2, then checks64MiB recovery/fill37. An unexpectedly successful over-cap allocation is released immediately and is **never mapped or touched**. Other error codes are inconclusive, not OOM success.

```sh
native-imports --execute --mode vmm-direct --gpu-uuid GPU-16128952-b438-556a-00bb-93039ee24e56 --cap-mib 5120
```

`ipc-export` / `ipc-import` use the official64-byte `CUipcMemHandle`; `vmm-export` / `vmm-import` use `cuMemExportToShareableHandle` / `cuMemImportFromShareableHandle` and exactlyone POSIX FD through SCM_RIGHTS. They exchange framed Linux Unix SEQPACKET messages with fixed protocol version, exact GPU bytes and64MiB size. Parent directory must already be an operator-approved UID1000-owned0700 directory; socket is0600 and peers must have UID1000/GID100. Exporter refuses an existing socket. Start exporter first; start importer after socket exists. Separate Pod fixtures need an explicitly approved temporary exchange volume; production Pods must not inherit that mount. Using opaque IPC handles means private IPC namespaces alone are not an import policy.

```sh
native-imports --execute --mode ipc-export --socket /exchange/private/probe.sock --gpu-uuid GPU-16128952-b438-556a-00bb-93039ee24e56 --cap-mib 5120
native-imports --execute --mode ipc-import --socket /exchange/private/probe.sock --gpu-uuid GPU-16128952-b438-556a-00bb-93039ee24e56 --cap-mib 5120
```

VMM uses the same command pair with `vmm-export` / `vmm-import`. The importer checks exporter byte19, fills37 and acknowledges successful import. Exporter then unmaps/releases/closes all its backing references and signals the importer. Importer holds its reference for `--retain-seconds`1–9(default3), verifies the backing remains usable, then unmaps/releases/closes and sends final acknowledgement. Exporter context exits after this acknowledgement. This tests **explicit exporter reference release**, not exporter-process-exit accounting; the latter is a separate future controlled fixture. Ordinary IPC exporter retains its allocation until importer closure, avoiding undefined exporter-free-before-import-close behavior.

Optional `--importer-fill-mib 64` allocates/touches64MiB in the importer before importing. At a512MiB parent with measured ordinary context overhead, this can exercise near-cap import behavior; use0(default) first. The correct near-cap amount must be selected from actual free/headroom and overhead, not inferred from nominal capacity. If the import fails, record its numeric result and cleanup; the overall process remains inconclusive because denial may be an expected policy outcome, an unsupported ABI or another error.

The operator must observe all participant Pod-parent native usage/limits, physical GPU memory, CPU memory.current, exact host process identities and independent GPU heartbeat timestamps throughout allocation/import/exporter release/importer release. Same-Pod children must aggregate under one parent; separatePods require separate cap/charge observations. Importer-accessible bytes may exceed its budget when memory is exporter-accounted; do not call this new physical allocation or claim importer-cap enforcement. If retained backing remains after exporter termination, reservations must remain until that backing is actually released. One passing64MiB case does not qualify arbitrary external-memory, DMA-BUF, arrays, asynchronous pools, managed globals or every MPS path.

Protocol waits are bounded at120seconds per operation and finite GPU operations are synchronized before ordinary cleanup. No SIGKILL, alarm, reset or external-kill helper is provided. In legacy IPC, a disconnected or hung importer cannot prove that mappings have closed; exporter timeout/exit can invalidate those mappings. This fixture is restricted to isolated trusted participants. Root must reconcile and stop both participants before releasing capacity; never run the failure protocol against production clients. Driver/kernel hangs are not recoverable inside this probe; any test job timeout/recovery remains under the root operator's controlled canary procedure. Malformed frames, unexpected FDs, bad GPU identity, peer disconnect and allocation failures cause cleanup and nonzero status. Every final receipt keeps production, managed imports and automatic caps unqualified.

The CPU tests compile the real probe against the pinned header, execute inert/bad-argument paths, exercise real SCM_RIGHTS FD lifetime/validation, and run synthetic driver functions for allocation/error/cleanup control flow. Those synthetic CUDA results are **not hardware evidence**. No test loads or invokes the GPU driver.

Canonical semantics: [CUDA IPC](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__MEM.html), [CUDA VMM](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__VA.html), [native accounting limitations](https://docs.nvidia.com/deploy/mps/mpsv3-memory-partitioning.html), [MPS termination/containment](https://docs.nvidia.com/deploy/mps/latest/when-to-use-mps.html).

This is an experimental global R615 UVM guard candidate. It is default off and has no production or hostile workload qualification. The scripts are inert unless an operator explicitly requests compile or GPU execution. They contain no install, load, GPU cap setter, Kubernetes mutation, or runtime restart operation.

The pinned patch adds a load-time `0444` boolean in `uvm_va_range.c`. When enabled, the constructor checks existing overlap before HMM reclaim or managed allocation. It returns the original collision status when an existing range overlaps, preserving the upstream caller's exact semaphore and P2P fallback. Otherwise it returns `NV_ERR_NOT_SUPPORTED`. Partial overlaps and managed overlaps remain denied. The CPU harness compiles the actual patched constructor and the actual upstream collision block; external kernel allocation/tree operations are mocked.

The complete pinned original source, patch and resulting source hashes are in [source-manifest.json](source-manifest.json). Primary source: [NVIDIA 615.71.09 uvm_va_range.c](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/kernel-open/nvidia-uvm/uvm_va_range.c), [caller](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/kernel-open/nvidia-uvm/uvm.c), [ATS load parameter](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/kernel-open/nvidia-uvm/uvm_ats.c).

The operator must use a fresh module and fresh independent CUDA VAspaces, with no existing managed allocations, MPS state or shared/imported VAspace. Actual module parameters must read `uvm_deny_managed_mmap=Y`, `uvm_disable_hmm=Y` (load argument `1`), `uvm_ats_mode=0`, and `uvm_enable_builtin_tests=0`. Actual CUDA attributes 88 and 100 must both read zero. These are runtime checks, not conclusions from compilation. The guard does not change reported managed-memory capability attribute 83. Shared/imported allocations, external pools, managed globals, inherited initialized CUDA contexts and hostile workload isolation remain unqualified.

An operator may execute the compile-only helper on the reviewed 6.8.0-134-generic canary:

```sh
python3 build_candidate.py --output /var/tmp/cps-r615-uvm-guard-build-20261008 --jobs 2 --compile
```

The helper requires the pinned installed source and original module hashes, kernel headers and original symbol CRC baseline. It creates a new private source copy bounded to 256 MiB/10,000 files, then runs `make ... NV_KERNEL_MODULES='nvidia nvidia-uvm' modules` with at most two CPUs and a 900-second deadline. No installed NVIDIA core `Module.symvers` was found, so both modules are compiled in that copy. The built core must never be installed or loaded. Only the UVM candidate may be considered later by the root operator after independent review and rollback readiness. The helper verifies unchanged installed hashes afterwards and requires the UVM candidate's version, vermagic and complete symbol CRC section to match the installed original. Compile output and logs are private. The CRC digest hashes the complete hexadecimal section bytes and handles the original final one-byte `00` row; the earlier four-column awk form incorrectly included its ASCII dot.

The canary driver container has no Python. Root verified host Python 3.12.3 can run with `PYTHONHOME=/proc/1/root/usr`; no host-wide `LD_LIBRARY_PATH` is allowed. Root may instead apply the pinned `.patch` only in its reviewed owned copy and use the same compile-only make command. This package does not run either operation itself.

The raw probe uses the existing reviewed driver/NVML ABI support files without changing them:

| Source | SHA256 |
| --- | --- |
| `platform-staging/scheduler/qualification/r615-pod-cap/cuda_probe.py` at fd90fc2 | `e0a3e28c00336d9dd5bc2c6267eb2b0792ef467940fd96c86aa11cd1c180e2eb` |
| `platform-staging/scheduler/qualification/r615-pod-cap/pod_cap.py` | `5c84ab668dd276b0216199a964f42886712af9225f9fc702740bfa9bb361a39f` |

Put these two unchanged files alongside `runtime_probe.py` in the immutable ConfigMap, or specify `--support-dir`. Root owns namespace/fixtures, native parent cap application and sealed first-init release. The parent observer must point to the actual host Pod-parent cgroup mounted read-only. The main process must be UID1000/GID100 without `LD_PRELOAD`; root supplies physical GPU UUID, exact Pod UID and CDI GPU libraries. The only read-only host mounts are the cgroup filesystem and UVM parameters. GPU libraries come from CDI; no driver-root mount, pull secret or host glibc path is used. All cached images use `Never` pull policy.

```sh
python /qa/runtime_probe.py --mode raw --execute \
  --device-uuid GPU-16128952-b438-556a-00bb-93039ee24e56 \
  --pod-uid EXACT_ROOT_REVIEWED_POD_UID \
  --parent-cgroup /host/sys/fs/cgroup/EXACT_ROOT_REVIEWED_POD_PARENT
```

The fixed parent cap is 512 MiB. The raw probe verifies a positive context baseline which leaves room for 64 MiB and places an additional 256 MiB above the cap. It performs raw device 64 MiB allocation/GPU touch/free, device 256 MiB OOM, 64 MiB recovery, then managed 64 MiB allocation denial and a heartbeat. Successful unexpected allocations are explicitly freed and cause failure. Managed denial records the actual CUDA result; a generic failure alone does not establish its causal mechanism. Root must combine candidate/loaded-module provenance, actual parameters, physical memory and peer coverage.

`--mode managed-only` checks a fresh independent process. With `--launch fork-before-cuda`, an uninitialized launcher forks before any CUDA call; the child creates its own CUDA VAspace. This does not qualify fork after CUDA initialization or a shared VAspace. `--mode heartbeat` runs the independent peer for 120 seconds with 200 ms ticks. Root must confirm its actual log interval covers the entire main phase.

`--mode torch` runs separately after raw processes exit, requires the same exact physical UUID/parameters/attributes/native cap, and measures Torch 64 MiB success, 256 MiB OOM and 64 MiB recovery. The pinned SDK b380 image was CPU-checked with read-only filesystem, no network, no capabilities and UID1000/GID100: Python 3.12.15, no Torch package. It reports unavailable rather than qualifying Torch. Root identified cached CPS notebook digest `6b6a8d6a225df1b938fe98bcdad9e547aef249347392ce8f29adb3fedda512ae` as a separately reviewed Torch fixture image; no GPU image was built or changed by this worker. `--mode all` runs fresh raw, managed, fork-before-CUDA and Torch subprocesses and fails if any phase is absent or unsuccessful.

CPU tests require a C compiler and three SHA-checked pinned source files (`uvm_va_range.c`, `uvm.c`, `nvstatuscodes.h`) in `CPS_UVM_GUARD_TEST_SOURCE`; default is `/tmp/cps-r615-uvm-guard-primary`. They do not load CUDA, NVML or kernel modules.

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover \
  -s platform-staging/gpu/qualification/r615-uvm-guard -v
```

16 tests pass. The old 512 MiB managed-bypass hardware receipts and source remain unchanged. This directory currently contains only CPU qualification and an inert future hardware probe. Root owns any canary load, actual CUDA test, rollback and node cleanup.

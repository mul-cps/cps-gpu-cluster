# Native parent aggregate qualification, 17 October 2026

The trusted, default-inert probe passed against one automatically capped 5 GiB
shared workspace. It uses direct libcuda allocation, full writes, synchronization
and readback. Two distinct processes shared the notebook container cgroup.
Typed driver OOM occurred near the parent cap; freeing sibling allocations
restored headroom while the sibling continued making CUDA progress.

The receipt records the reviewed probe hash, six independent host cap/physical
memory samples and successful cleanup. Raw stdout is retained privately; its hash
is recorded here. All samples confirmed physical free memory above 6 GiB.

Run only as a controlled operator qualification after independently verifying Pod
UID, GPU UUID, parent cgroup and finite cap. Default invocation makes no GPU/API
calls. Execution requires `--execute --pod-uid <actual-uid> --gpu-uuid <actual-uuid>`.
Independently sample host cap and physical memory during every held checkpoint.
Require final exit 0 and successful `children-cleaned`, not just `probe-passed`.
Public pull requests must not execute arbitrary code on cluster GPU runners.

This qualifies ordinary same-Pod allocation aggregation only. VMM, managed memory,
imports, cross-Pod isolation, MPS and broader production acceptance remain open.

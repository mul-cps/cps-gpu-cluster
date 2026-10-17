# Managed-memory denial and MPS qualification

On 17 October 2026, the normally started 5 GiB shared workspace passed:

- 64 MiB managed allocation denied with CUDA error 801 (NOT_SUPPORTED), with
  working ordinary kernels before and after, followed by explicit cleanup.
- Two actual clients registered with a private non-root MPS server. Aggregate
  ordinary allocation reached 4096 MiB before typed OOM on the next 256 MiB.
  Both clients recovered and verified kernels; clients and daemon exited cleanly.

The receipt includes nine independent host samples: the cap stayed sealed at
5 GiB, physical free memory stayed above 34 GiB, and charged usage returned to
zero after daemon cleanup. Neither test changed driver caps or host runtime.

The managed probe is default-inert and embeds the reviewed, hash-pinned Native
endpoint. MPS uses the existing frozen
[probe](../../platform-staging/gpu/qualification/native-mps/mps_probe.py), whose
source and binary hashes are recorded in the receipt. Actual Pod/cap/driver epoch
must be verified independently before execution; declared CLI identities alone
are insufficient. Run only as trusted operator qualification, never arbitrary PR
code on cluster GPU runners.

These are scoped 5 GiB results. Cross-Pod isolation, VMM/import paths, other profile
sizes and broader production acceptance remain open.

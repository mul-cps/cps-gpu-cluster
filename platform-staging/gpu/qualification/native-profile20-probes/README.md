# Trusted 20 GiB probes

Status: source and CPU preparation only. General GPU group sharing remains disabled.

`prepare_profile20.py` keeps the existing `cps5-cit10` default and accepts the
explicit `cps5-cit20` operator preset: CPS `native-group-b` at 5120 MiB, CIT
`native-group-a` at 20480 MiB, a 25600 MiB pool and another 1024 MiB of measured
headroom. The source templates are checksummed copies of the passed 5/10 GiB
cycle; no controller, GPU driver, workload image or user permission changes are
performed here.

The preparer requires full Root-captured policy/config, baseline ledger and
terminal history, current ledger, protected journal snapshot, Ready Pods,
immutable enrollment authorities, and genuine owning-Source Start receipts and
requests. The baseline cardinalities are derived from the complete inputs;
every old allocation and raw/canonical journal must remain exact, and only two
new finite sealed lifetimes may be added. Preparation is local and inert until
`--prepare` and the exact preparer/index hashes are supplied. That flag prepares
sources; it does not execute an operator recipe.

The 20 GiB probe uses 256 MiB steps, at least 19456 MiB held, an untouched
20736 MiB direct OOM attempt and typed CUDA OOM for exhaustion. Two MPS clients
retain the payload while repeatedly verifying real kernels for at least 120
seconds; the wrapper requires a healthy 5 GiB peer, protected native charge
samples, a 20480 MiB per-parent cap, a 25600 MiB aggregate pool, recovery,
identity-fenced private daemon cleanup and final zero charges. Its per-client
allocation guard allows at most 40 previous blocks, bounding the next attempt
to the forty-first. The unchanged ten-cap MPS template remains replayable.

The historical reader sibling adds only `20480` to the finite retirement cap
allowlist. It retains the exact old journal hashes, recovery exception,
enrollment, cleanup, audit, cgroup and epoch predicates. Use that same reader
in the new harness, strict Stop collection and future inverse proof. An expired
grant or an absent Pod is insufficient evidence to release physical capacity.

`--emit-native-import-source` emits the fixed-cap C parser and unchanged
compiler source. Root builds the resulting ELF with the existing pinned,
network-free GCC container recipe; no NVCC or GPU is needed for this CPU build.
The actual compiler exit/output, ELF digest and ABI, inert runtime output and
build receipt must pass the original guards before preparing a real harness.
The Python snippets and recipes do not manufacture build or hardware receipts.

The local CPU qualification suite is:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/tmp/cps-native-authority-test-deps-20261009:/home/bjoern/git/cps-compute-worktrees/cleared-offline-recovery-20261011/src:/tmp/e2x-native-platform-status-20261009 \
/home/bjoern/git/cps-compute/.venv/bin/python -m unittest discover \
  -s platform-staging/gpu/qualification/native-profile20-probes \
  -p test_prepare_profile20.py -v
```

These tests include synthetic future shapes and a read-only replay of the full
actual 31-allocation/25-journal baseline. They make no API, GPU, credentials,
driver, module, reset, configuration, grant or publication changes. They do not
constitute actual 20 GiB qualification.

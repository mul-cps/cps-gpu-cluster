# Single-process VMM cap qualification

The trusted probe passed on the normally started, automatically capped 5 GiB
workspace on 17 October 2026. It created distinct 64 MiB physical VMM allocations,
fully wrote them and checked first/last-byte readback. CUDA cuMemCreate returned
typed OOM at 4,898,947,072 bytes held. Same-process FD import produced a coherent
alias. Explicit mapping/handle/FD/context cleanup and fresh-context recovery passed.

Independent host samples confirmed a sealed 5 GiB cap, charged usage of
5,333,191,360 bytes during OOM, more than 34 GiB physical free memory, and zero
charged usage after cleanup. Normal Stop removed the Pod and released all 99
native claims; reservation tables were empty and the test token was revoked.

The included source is frozen and default-inert. Actual Pod identity, finite cap
and physical headroom must be verified independently before controlled execution.
Require exit 0, a passing receipt, explicit cleanup and before/during/after host
samples. Never execute arbitrary pull-request code on GPU cluster runners.

This tests VMM accounting and same-process import only. It does not prove
cross-Pod or distinct-process import isolation, other profile sizes, or production
readiness. Raw stdout remains private; its hash is recorded in result.json.

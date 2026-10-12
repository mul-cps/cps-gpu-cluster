# LIMITED CPS5/CIT10 measured results — 2026-10-12

Fresh notebook measurements passed for the two approved shared5/shared10
workspaces on the selected A100. This is a dated measurement receipt. General
group access, production release and full-fleet qualification remain false.
The bounded normal target-profile Start/Stop/restart/Stop cycle also passed;
both fixtures are stopped and all native allocations are released.

The [measured receipt](measured-receipt.json) is separate from the unchanged
[offline preparation record](record.json). It preserves the source preparation
boundary while recording the later live results. The
[evidence manifest](measured-evidence-manifest.json) pins the exact private
artifacts and their protected local locator. Raw probe streams, full native
inventories and source journals are not copied into this repository. Probe
source pins and MPS binary hashes are recorded in the retained receipts; this
publication does not include their executable bytes or import source custody
outside the stated evidence boundary.

| Workspace | Fresh Pod UID | Native cgroup inode | Exact soft/hard limit |
| --- | --- | ---: | ---: |
| `cps:native-group-b`, `interactive-shared-5` | `8c92fb62-5f64-4995-8ac2-870a72e71a46` | 1407303 | 5,368,709,120 bytes (5120 MiB) |
| `cit:native-group-a`, `interactive-shared-10` | `533ba8d5-2a8a-4e56-9ad0-b13231cda3fd` | 1407698 | 10,737,418,240 bytes (10240 MiB) |

Both identities bind to policy
`sha256:4f1dff1a92aba5cd7376dfb897612b7e6f2e6f15a09515dbdf29efa4c522359d`,
node `k3s-wk-gpu2`, GPU `GPU-16128952-b438-556a-00bb-93039ee24e56`,
boot `209f8bc9-a478-48e4-925a-6e07ffa56f7a` and driver generation
`b10498fc-9153-4394-875a-ea7cfb498625`. The fresh sealed journals record these
exact limits. Independent native inventory reads from
`/proc/driver/nvidia/gpus/0000:06:10.0/cps_native_caps` match the original
inode/kernfs/cgroup identities and retain active, pinned, default-hierarchy
rows. The probe's declared cap alone is not the accounting proof.

| Measurement | Actual result |
| --- | --- |
| CPS5 typed OOM and recovery beside CIT10 | 4608 MiB held; typed `torch.OutOfMemoryError` at an attempted 4864 MiB; the untouched 5376 MiB request was also denied. Ordinary kernel readback was 19 and post-OOM recovery readback was 37. Both processes exited 0 with unchanged Pod UIDs. |
| Independent CIT10 peer | 212 verified kernel ticks across 108.0013 seconds. Consecutive ticks bracket the CPS OOM and completed recovery. |
| CIT10 private two-client MPS | 9216 MiB (9 GiB) held; typed CUDA error 2 at 9472 MiB; 479 verified two-client kernel ticks over 120.081026302 seconds. Both recovery clients passed, client exits were `[0, 0]`, and private daemon cleanup was confirmed. |
| Independent CPS5 peer during MPS | 332 verified kernel ticks across 168.0032 seconds. Its first tick followed registration by 0.6907 seconds; subsequent ticks bracket OOM, recovery and daemon cleanup. |
| Native charge bounds | All 35 pair-test and 53 MPS-test samples retained the exact 5/10 GiB limits and stayed within each finite cap and the combined 15 GiB budget. Pair maxima: CPS 5,077,548,736 bytes, CIT 581,307,072 bytes, combined 5,658,855,808 bytes. MPS maxima: CPS 581,254,848 bytes, CIT 10,563,832,192 bytes, combined 11,145,087,040 bytes. |
| Same-parent IPC/VMM positive controls in CIT10 | Both 64 MiB exporter/importer pairs completed, with all 39 IPC and 56 VMM CUDA event results equal to 0. VMM backing remained usable for 9.000299966 seconds after exporter references were released. Participant cleanup and temporary-file cleanup passed; both stderr files were empty. |
| Normal target-profile lifecycle | Start/Stop/restart/Stop passed for both workspaces. Both replacement Pod UIDs received their automatic exact caps and verified 33 kernel ticks each. Final normal workspace states were `stopped`, native reservations were inactive, attempts were null, and all 35 ledger allocations were released. |

The MPS transport's original result selector omitted the final
`qualification-mps` kind, leaving its CIT receipt null despite process exit 0.
The accepted receipt exactly matches the retained final probe event; the
independent peer receipt and both original exit statuses are retained. This
publication uses that correction and does not rerun GPU work.

The last pair/MPS native samples still include peer or context charge and do
not prove post-exit zero charge. The separate
[sanitized lifecycle receipt](lifecycle-acceptance.json), observed at
`2026-10-12T14:06:36.833227+00:00`, establishes that cleanup: all four original
and replacement Pods are absent, and their original finite native rows are
offline, pinned and charged exactly zero bytes. Their original exact limits
remain retained. The restarted CPS inode is 1408273 and CIT inode is 1408668;
the receipt preserves both replacement Pod UIDs and admitted spec hashes.

CPS actions used authenticated console HTTP. CIT actions used the trusted
normal console manager; human CIT OAuth and browser collaboration were not
tested. Both public selector assets returned HTTP 200 with SHA256
`7e6e230c0309aca94ce3410ef7b8df7b7ff1d3c4f004d71b3ad2f62ac104d53b`.
Public asset retrieval alone does not establish an interactive browser flow.

Fresh cross-Pod IPC and VMM import denial was not run for these Pod lifetimes.
Same-parent import success does not establish cross-Pod isolation. Earlier
host5/20 import checks and earlier notebook lifetimes remain separate evidence.
These results do not qualify additional workspaces, profiles, GPUs, arbitrary
workloads, human browser collaboration or simultaneous cross-Hub starts.
Offline publication checks passed: all 105 retained artifact size/SHA256
bindings, the manifest-to-receipt binding, the byte-identical sanitized
lifecycle copy, local documentation links and unchanged preparation bytes.
The compute-policy suite passed 48 tests, compute-platform passed 103 tests,
and `scripts/compile_compute_policy.py --check` passed. These used the existing
course-hub interpreter and SDK/admin source paths; platform fixtures used the
private temporary directory to avoid this host's `/tmp/.git` marker.

The native-pilot suite is not passing: the existing SDK interpreter ran 279
tests with one failure and one error. The service-loop test
`test_pending_sealed_restart_terminal_absent_then_busy_peer_tombstone`
reproduces alone at `test_service_loop.py:104`: journal state remains `sealed`
where the test expects `cleaned`. The transport test
`test_stale_or_missing_rpc_proof_rejects_and_closes` raised
`BrokenPipeError: [Errno 32] Broken pipe` while closing after the expected
Root-fence EOF rejection. Neither source path was changed by this receipt
publication. The full run and focused trace remain in the protected test-log
directory alongside the qualification inputs.

The focused service-loop reproduction, from the repository root, is:

```sh
TMPDIR=/tmp \
PYTHONPATH=platform-staging/gpu/native-group-pilot:/home/bjoern/git/cps-compute-worktrees/reservation-batch-acceptance-20261012/src:/tmp/e2x-workspace-profile-ui-20261012 \
/home/bjoern/git/cps-compute/.venv/bin/python -m unittest \
  test_service_loop.ServiceLoopTest.test_pending_sealed_restart_terminal_absent_then_busy_peer_tombstone -v
```

The private temporary filesystem reports a different device number through
`fstat` and `/proc/locks`, so the native lock-ownership fixtures were rerun under
`/tmp`, where those identities agree. The final 279-test result above uses that
host context and complete existing dependencies; it is not a full-suite pass.

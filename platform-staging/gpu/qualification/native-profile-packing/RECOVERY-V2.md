This sibling recognizes one authenticated historical recovery. It does not
perform recovery, qualify hardware, renew grants, or change a Stop result.
The failed CPS lifetime remains `8066366f-6e7e-42ea-83b2-86a58e9c3bad`, binding
`16d264e00ee6778319a8961f9da510147c3bebc925e674bf95880689cd25`, original inode
1390814. The original archive remains b1fb3366… raw / 24fb181b… canonical.
The other sixteen original journal bodies remain pinned verbatim. The original
history contains eleven finite retirements, five cleaned records, and this one
exception. Every future target must have a normal finite retirement.

The required SDK is commit 9d6f4680d7af040cc1eceef6e34ed65d089545be: controller
630d43cc… and cleanup codec babeb6ee…. The reviewed node/helper are commit
6da0214b66d6e86028a8b83e7715859136832bae, source 05a6ca95… / 25c9514f…. The
active runtime node now uses the separately reviewed journal-contention fix
34ce5b9b… (Root integrated commit5236000). The historical operation validator
remains frozen05a6ca95… with helper25c9514f…; changing the active poller does
not change the archived operation's proof or validator source. The version2
adapter review binds node_source_sha256 to34ce and explicitly binds
historical_node_source_sha256 to05a6. `--node-source NODE05A6` still supplies
only that historical codec; the live fence requires actual mounted34ce bytes.
The actual gateway image, node Pod UID/spec/CM UID/data hashes, operator token/UID
and all fresh runtime observations are Root inputs. A source pin does not
substitute for an installed-module or Ready-process receipt.

Root first completes explicit operator recovery and authentic publication.
There is no executable recovery authority in this package. Until the genuine
terminal, immutable audit, cleanup receipt and protected published-cleanup
marker exist, assembly fails. No pending object is represented as successful.

1. Capture full current protected journal envelopes (owner UID0, directory0700,
   files0600/single-link), all seventeen original bodies, original raw archive,
   protected plan/review/marker raw bytes, and complete actual enrollment/audit/
   cleanup ConfigMaps. Preserve the failed original and its failed Stop receipt.
   Capture the current physical inventory and absence of all original cgroups
   and gates under the existing reviewed host transport. API objects must include
   actual immutable metadata, UIDs and full bodies. Store captures separately;
   do not update old v1 input files.

2. Assemble locally with pinned actual captures. Each `--NAME-sha256` below is
   the bare SHA256 of the corresponding full raw file. Inputs are private600
   files in owned0700 directories; the output directory must be new.

   ```sh
   python assemble_recovery_history.py --prepare \
     --host-capture HOST --host-capture-sha256 HOST_SHA \
     --original-archive ARCHIVE --original-archive-sha256 ARCHIVE_SHA \
     --plan PLAN --plan-sha256 PLAN_RAW_SHA \
     --review REVIEW --review-sha256 REVIEW_RAW_SHA \
     --marker MARKER --marker-sha256 MARKER_RAW_SHA \
     --enrollment ENROLLMENT --enrollment-sha256 ENROLLMENT_RAW_SHA \
     --audit AUDIT --audit-sha256 AUDIT_RAW_SHA \
     --cleanup CLEANUP --cleanup-sha256 CLEANUP_RAW_SHA \
     --model-source MODEL630 --control-source CONTROLBABE \
     --node-source NODE05A6 --recovery-source HELPER25C \
     --source-root OCT9_PRIVATE_GROUP_PROBES \
     --health-sha256 REVIEWED_HEALTH_SHA \
     --core-sha256 REVIEWED_CORE_ELF_SHA --uvm-sha256 REVIEWED_UVM_ELF_SHA \
     --output NEW_PRIVATE_OUTPUT
   ```

   This writes `terminal-history-v2.json`, a preparation receipt, a read-only
   `historical-observer-source.py` and `historical-host-request.json` with zero
   active targets. Root alone invokes the source with that JSON as `sys.argv[1]`
   through the existing pinned host-observer transport. Before and after exec,
   Root checks its actual observer UID/spec/node and preserves raw stdout. The
   source enforces Linux UID0, exact hostname/boot/driver health/module pins,
   full current selected-device inventory, cgroup2 device, absence, protected
   raw journal/archive/plan/review/marker reads twice. It performs no setter,
   allocation, GPU kernel, recovery or API operation. Its returned twelve rows
   classify eleven as finite and one as recovered; they never claim all finite.

3. For a new qualification pair, use `prepare_recovery_harness.py --prepare`
   with the same arguments as `prepare_harness.py`, plus exact model/control/
   node/helper sources and node/helper SHA flags. The binding still needs real
   newly captured Pod UIDs/specs, approved cap/init/device gates, actual measured
   pool and existing CPU-built native-import binary/build receipt. Its
   `retired_capture` input is the pinned v2 history file. Initial preparation rejects
   the historical recovered UID as either target. All old kernel/control
   implementations and the generated `inspect_stop.py` remain unchanged.

4. After genuine new Stop and physical cleanup, capture all original plus new
   protected journals and reassemble v2 history. Its historical recovery plan,
   archive, review, audit and cleanup remain unchanged. Additional records are
   finite only and bounded by total journal count32. Root invokes the generated
   `run_retirement_witness.py --execute` with its own source/preflight/binding/
   history raw pins, actual new binding and new output directory. It requires
   both new target UIDs to be finite. Run unchanged `inspect_stop.py` with actual
   new enrollment/cleanup/Pod404/ledger/host/Root-review inputs. The authenticated
   historical exception is carried as prior history, never a new Stop witness.

5. The expiry inverse uses the same actual 3c807 cycle before/after/receipt,
   original21 ledger and registration/handover provenance. Genuine close must
   leave Source stopped and all native claims released. Root reviews current
   physical observation and fills `physical-history-review.template.json` with
   exact raw file pins, ledger UID/full canonical digest and fresh UTC time.
   This distinct review explicitly keeps normal_stop_passed and hardware false.
   Stage a new private UID10001 source directory containing these siblings,
   frozen3c807/792/360 and the reviewed SDK9d6f overlay. The operator's actual
   scoped kubeconfig/token/PVC/config/image/security/freeze guards are unchanged.

   Add exact named ConfigMap GET permission only for original enrollment,
   `cps-native-recovery-16d264e00ee6778319a8961f9da510147c3bebc92`, and cleanup
   to its existing authority Role; preserve every other rule. No new CREATE,
   UPDATE, LIST, recovery endpoint or cluster-admin credential is required.
   Fill the disabled adapter review with current immutable gateway image and
   raw history/reader/loader/adapter pins. Root alone enables it after review.

   ```sh
   python qualified_recovery_expiry_adapter.py --execute \
     --adapter-sha256 ADAPTER_SHA \
     --adapter-review ROOT_ADAPTER_REVIEW --adapter-review-sha256 REVIEW_RAW_SHA \
     --history TERMINAL_HISTORY_V2 --history-sha256 HISTORY_RAW_SHA \
     --window-source FROZEN_3C807 \
     --model-source MODEL630 --control-source CONTROLBABE \
     --node-source NODE05A6 --recovery-source HELPER25C \
     --capture REMAINING_EXACT_3C807_INVERSE_ARGUMENTS
   ```

   The remaining arguments are the existing own-cycle restore CLI, including
   `--source-sha256 3c807348b85139ac90ae83d253019a242da344febcfe106e1ca32eb9a83697c3`,
   current runtime review, current v2 physical review, genuine close and protected
   physical observation, original21/full baseline, current mode/policy/config,
   own actual cycle receipt/before/after, full registration and Source provenance.
   Use operation `restore-expiry` only. First capture with reviewed current_full
   digest null; inspect full readback, then enable the exact canonical digest in
   a separate fresh request and invoke without `--capture`. Use fresh output
   directories. This restores only selected existing membership/grant expiries
   through normal audited APIs; profiles, CIT10 ceiling, identities/storage,
   released history and v2 runtime remain unchanged. Preserve incomplete receipts
   and use the same own-cycle inverse for guarded partial resumption.

   The adapter executes genuine792 context in the same globals and retains
   3c807's actual initialization hook, original19 then original21 ledger guards,
   current count21–32/all-released/full checksum, scoped credentials, writers0,
   both Ready qualified Hubs, Ready gateway/node plus mounted immutable CM hashes,
   named Pod404 and actual registration before loading Source. It additionally
   matches every immutable enrollment field to the recovered released allocation
   and GET-validates full actual enrollment/audit/cleanup UID/body closure before
   Source and every subsequent fence. The old792/360/3c807 files are unmodified.

CPU validation uses actual recorded original captures with explicitly synthetic
future recovery publication for schema tests; it is not a live acceptance:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/tmp/cps-native-authority-test-deps-20261009:/home/bjoern/git/cps-compute-worktrees/cleared-offline-recovery-20261011/src:/tmp/e2x-native-platform-status-20261009 \
/home/bjoern/git/cps-compute/.venv/bin/python -m unittest discover \
  -s platform-staging/gpu/qualification/native-profile-packing -q
```

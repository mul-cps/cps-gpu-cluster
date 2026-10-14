The retained-v2 executor is `handover_cli.py`, copied byte-for-byte to the private
`O/native-kai-node-epoch-handover-preparation-20261014/execute.py`. It is inert
without a mode. Worker preparation has not invoked a mutation stage. The image
is the qualified derivative `ghcr.io/mul-cps/cps-compute@sha256:8c2c456b90330622645d509f94882a11a465ac208a6fa7fc824900d6320e5c0b`.
This handover installs no Core or Hub wheel and enables no KAI/operator mode.

Root reviews the frozen private `run-*/plan.json` and `operator-code.json`, then
uses the same exact directory and canonical plan SHA for each stage:

```sh
NODE_HANDOVER_PYTHON=/home/bjoern/git/cps-compute/.venv/bin/python
"$NODE_HANDOVER_PYTHON" execute.py --mode refresh
"$NODE_HANDOVER_PYTHON" execute.py --mode begin --directory /exact/private/run-ID --reviewed-plan-sha256 sha256:EXACT --execute
"$NODE_HANDOVER_PYTHON" execute.py --mode finish --directory /exact/private/run-ID --reviewed-plan-sha256 sha256:EXACT --execute
# On failure before delivery activation has begun:
"$NODE_HANDOVER_PYTHON" execute.py --mode restore --directory /exact/private/run-ID --reviewed-plan-sha256 sha256:EXACT --execute
# If the Gateway rollout itself never becomes Ready, restore only its known
# config/seed preimages while Node's actual absence barrier remains held:
"$NODE_HANDOVER_PYTHON" execute.py --mode recover-gateway --directory /exact/private/run-ID --reviewed-plan-sha256 sha256:EXACT --execute
# Then use ordinary restore; it still requires genuine fresh Source,
# reservations, ledger and protected fd-zero proof before resuming Node.
```

`refresh` performs only actual authenticated reads. It checks the completed
a715 sealed delivery history, all four current ACKs, current policy/Source hash,
physical epoch, exact Source87 console UIDs, stopped same-group writers,
inactive member reservation attempts, released global native ledger and actual
protected kernel inventory zero. It retains the complete private preimages and
hashes the new observers, executor, adapter and fixed historical dependencies.

`begin` reuses the existing paused-controller/stable-journal protocol. Its
freshly regenerated plan must have the identical reviewed target, historical
lineage, physical epoch, Source hash, policy, qualification and complete specs.
Status churn can refresh RVs only under original UID/full-preimage guards.
It pauses Node replicas, waits for the actual old Pod and every matching Pod
to disappear, then repeats Source/reservation/ledger checks and observes the
real protected native inventory through a bounded read-only probe. Replicas0
with an old Ready Pod is insufficient. GPU preview can remain successful;
decisive acquire/register requires the missing current Node process, including
an already prepared request. CPU admission is not excluded. Any earlier
in-flight Source/native custody must close through genuine normal Source Close
and existing cleanup before continuation. The executor does not synthesize a
release or cleanup receipt.

`finish` repeats the absence/quiescence observation and uses the exact current
Node UID plus actual boot/driver/GPU fd readback for its independent fresh
physical epoch. While Node is absent, only the authenticated Source `/capture`
request is reused; the old `/epoch` route requires the Node process. The live
capture042 configuration also has a fixed 507 Node image pin. Its immutable
Secret therefore requires an explicit companion delta:

- Create the exact derived immutable capture input. Existing export token and
  qualification bytes remain byte-exact; only `config.node_process.image`
  changes to 8c2.
- Create the derived immutable Node bootstrap. Retain the original code CM,
  bootstrap, native config, driver/cap histories and original delivery inputs.
- CAS the existing Gateway runtime Secret's complete data under its UID/RV;
  only the existing Node trusted-image string changes.
- CAS the complete Gateway Deployment spec under its UID/RV; only
  `capture-seed.secretName` changes. Its image remains 440. Wait for actual old
  Gateway Pod absence and a structurally verified replacement.
- CAS the complete paused Node Deployment spec under its UID/RV to the exact
 8c2 image, new bootstrap and removal of the masking code volume/mount. All
  other Node fields remain exact.
- Verify the actual new capture Secret UID/full data and the Gateway's real
  init-materialized capture config hash. Discover the actual Node/Gateway Pod
  and ReplicaSet owners, then apply existing seven singleton Roles with exact
  UID/RV/full-rules CAS. Before that RoleCAS only, operator observation uses
  authenticated Source export plus the actual Node fd/UID physical epoch.
- Restore the ordinary authenticated `/epoch` observer, require genuine fresh
  all-four ACKs and actual mounted runtime, then invoke the existing sealed
  new-empty-journal activation. Preserve the original Secret/PVC/journal bytes
  and all prior immutable pairs. No Role is created or broadened.

The existing `qualified-hub-package-handover` kind is reused by a narrow
Node adapter; it does not install a Hub package. Both Hub full specs/images and
all policy/native-scope/profile/approval fields remain exact. Gateway's one
seed-volume field is explicitly changed. Capture input custody is original
Secret UID `c575bd98-0137-44d9-b27a-b306be394b75`, RV368234908,
full-data SHA `63e6858d19cffad8910d9ddc63836f9265eaebeee22f3eb1b7e4e37cfe551a6c`.

`restore` is an executable pre-activation inverse. It requires the original
delivery Deployment still exactly paused, zero controller Pods, and both
forward delivery names unused. It accepts only known original/candidate Node,
Gateway, runtime and Role states, establishes actual Node-process absence and
fresh Source/ledger/protected inventory zero, then restores the original
complete Node/Gateway specs, runtime data and original immutable bootstrap and
capture-input bindings. It obtains genuine replacement processes, exact
singleton permission CAS, fresh all-four ACKs and a new empty delivery journal
for the restored state. It never resumes or overwrites a historical journal.
Any completed or uncertain delivery activation requires a separately captured,
reviewed sealed successor; the pre-activation inverse refuses it. Unknown
mutation outcomes are held and are not automatically replayed.

`recover-gateway` is the narrow failed-rollout prerequisite. It requires the
exact known paused Node UID/full spec and actual absence of the original and
every matching Pod, retained paused delivery controller/history and unused
forward lineage names. It requires the original immutable capture input still
exact, and accepts only the known original or prospective Gateway full spec
and runtime complete data under their original UIDs. It restores only runtime
data and the Gateway capture-seed binding by fresh UID/RV/full-preimage CAS,
rechecking the barrier between writes. It needs no failed Gateway HTTP
interface. It cannot resume Node, release custody, change Roles or activate
delivery. Genuine HTTP/custody/fd proofs remain required by ordinary `restore`.

Only Root may execute the reviewed writes. No Source records, grants, aliases,
native ledger/caps/driver, Hub Deployment, GPU Pod or external repository is
written by this packet. The read-only probe has no token, GPU/device request,
privilege or writable host mount; exact created UID/current-RV deletion and
actual absence are required even after inspection failure. This is a
retained-v2 handover proposal. Actual execution, fresh post-barrier hardware
readback and all-four restored readiness remain live acceptance gates. KAI
operator/cap/CRI/CDI qualification is a separate gate.

Focused offline tests cover the sealed actual captured frame, exact Node and
Gateway deltas, capture opaque-byte preservation, forged peer/image/Role
rejection, independent inverse reproduction, absent-process barrier, privilege
and extra-field denial, API false-bool defaulting, actual pinned activation
loader/software, default inert behavior, failed-probe exact cleanup and
observer byte binding. The independent maintenance review additionally
established five ASGI scenarios /47 assertions for admission and genuine
intent-null Close; these are fixture evidence, not live GPU placement.

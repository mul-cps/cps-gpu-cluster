# Two ordinary CPS Source 5 GiB workspaces

Prepared only; Root owns execution. No live mutation was made by preparation.
The actual owning administrator is `bjoern`; targets are the existing approved
`native-group-a`/`native-group-b` and their reviewed neutral accounts. There is
no CIT actor, fixture person, new grant, account, approval or workspace.

The read-only exact Source capture on 2026-10-14 found two canonical members in
each group and **zero overlap**. Both were stopped, reviewed/ready and approved
for `interactive-shared-5` at revision `832e841b…`; current pool is max2/15360 MiB.
The SQL reservation and native authority each reject a shared canonical person
independently of allowance. No authoritative fixture change is needed for this
pair. A later overlap makes this harness refuse: review group ownership/membership
through its normal authority, not a wider allowance or direct ledger edit.

`pair.py` reuses the exact private normal-Source runtime SHA256
`8152fa84fff04e0dfc2cd1543fc2175fc7d84024cd4b1fd0732bdc53d7cce780` and its
host wrapper `b3a08f0a…` under `~/.local/state/cps-full-project-20261013`.
It adapts only the fixed hold to a common **180 seconds after both Ready**, and
requires confirmed Stop before restoring permission windows. The two starts use
the ordinary WorkspaceService APIs concurrently; preimages for both are verified
before either may mutate. Each invocation writes its own new private evidence
directory using the original filesystem/foreign-edit guards.

The first paired execution was refused before either Start: a later Source
fsGroup pass had widened the historical `/data/normal-source-gpu-acceptance`
parent to02770, correctly failing the original0700 guard. Its failed JSONL/plan
are preserved. This packet now uses a fresh parent
`/data/normal-source-gpu-acceptance-<canonical-subplan-run-UUID>` for each ordinary
invocation. Only new owned inodes may have inherited setgid cleared; existing
historical/widened/symlink paths are never chmodded, replaced or reused. Changed
runtime bytes invalidate previous plan metadata: generate and review a fresh plan.
Early exceptions now retain exact private tracebacks and emit only recognized
bounded guard codes through the host's output filter.

## Commands

From this directory, first generate and review a fresh private plan:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 host.py plan
```

Preflight reads the actual Ready components, cordoned GPU2 UID, exact immutable
node config, protected current driver inventory and boot/driver generation. It
requires no active native entry or charge; retired zero-charge entries remain.
Both real Source captures enforce reviewed accounts, stopped servers/reservations,
empty Shares, course/storage binding, explicit member mappings and existing
source-owned 5 GiB grants. It never infers physical freedom from VRAM/utilization.
Plan files and metadata are mode0600 under the new owned mode0700 directory
`~/.local/state/cps-concurrent-source5-20261014`. The plan expires after five minutes.

After reviewing exact preimages, component custody and temporary window changes:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 host.py execute \
  --plan /home/bjoern/.local/state/cps-concurrent-source5-20261014/pair-plan-<id>.json \
  --plan-sha256 <emitted-reviewed-sha256>
```

During `both-ready-for-root-hardware-readback`, use a separate terminal:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 readback.py \
  --plan /home/bjoern/.local/state/cps-concurrent-source5-20261014/pair-plan-<id>.json \
  --plan-sha256 <emitted-reviewed-sha256>
```

This reads both actual Ready Pods, protected sealed journals and root0400 driver
inventory. It binds distinct Pod/cgroup identities, exact 5120 MiB hard/soft caps,
common epoch and aggregate charge <=15360 MiB, preserving prior terminal entries.
It writes a private receipt; this observation alone is not GPU execution evidence.
Root must record actual concurrent kernels/OOM and peer continuation while both
ordinary lifetimes exist, with before/after cap and process readbacks.

## Existing bounded probes and restart

Readback includes argv recipes for the existing 5120 MiB `native-imports` ELF,
same-parent IPC/VMM helper and private same-parent MPS probe. Recipes deliberately
leave binary/source/MPS ELF pins and staging paths unresolved until Root checks
the exact bytes in the current ordinary workload. They execute nothing. Original
sources are under `~/.local/state/cps-group-native-20261009/group-probes/{imports,mps}`.
`native-imports` supports vmm-direct/ipc-export/ipc-import/vmm-export/vmm-import;
the unchanged same-parent helper accepts vmm-direct/ipc/vmm. MPS supports an
OOM/peer case with exact source/control/server hashes, actual Pod UID and driver
generation; its private daemon/control/two clients require fresh Root cgroup/PID
attribution and cleanup observations. Keep all activity within the common hold.

The older full import/MPS host wrappers hardcode CPS/CIT targets. Do **not** pass
a CPS UID as a CIT identity to those wrappers. This packet prepares the current
same-parent recipes and native observations, not a cross-parent exchange mount,
kernel denial witness or MPS attribution rewrite. Those additional gates remain
false unless separately collected and reviewed.

For restart, wait for both successful ordinary Stops/restoration, keep both
original full protected terminal journals, generate a fresh plan and run again.
The second readback additionally takes:

```sh
  --previous /home/bjoern/.local/state/cps-concurrent-source5-20261014/pair-readback-<first>.json \
  --previous-sha256 <first-readback-sha256>
```

It requires new actual UIDs and reads both original journals as retired-inert
with unchanged identities. Root still validates complete typed cleanup/retirement
proofs, absence of original Pod/cgroup/processes, preserved storage/PVC/PV and data
sentinels. A new UID by itself is not a complete restart/recovery gate.

## Exact restoration requirements

Keep policy/approval generation, Hub config, component images, pool/driver/MIG,
workspaces, canonical mappings and storage paths stable throughout the run.
Only starts/expires on the existing eligible grants/memberships may be temporarily
extended; future permissions cannot activate and active longer windows cannot
shorten. Do not interrupt the operator process while its finally blocks run.

Each normal Close must prove actual Hub shutdown, stopped workspace, inactive
reservation/no attempt, empty Shares and unchanged retained storage registration.
No forced reservation release, TTL inference, direct database deletion, driver
reload, MIG operation, uncordon or KAI qualification is performed. Restore each
changed record only if its full current bytes equal original or this invocation's
target, then compare every original member grant and membership. Restore Hub
group users only after shutdown, with original roles and original-or-expected
users; preserve any foreign edit and fail. If Stop is unresolved, preserve changed
windows and private evidence for reviewed normal Close/recovery; never erase the
active reservation or approval. Old/new native journals and terminal custody stay.

## Offline checks

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s . -v
PYTHONDONTWRITEBYTECODE=1 python3 /tmp/test-normal-source-gpu-acceptance-20261013.py
```

The packet keeps human OAuth, MPS/import execution, hostile isolation, physical
packing and production/KAI flags false. Root's actual two-parent kernel and
lifecycle receipts provide the eventual acceptance evidence.

# Prospective CPS531 pair: finite Node source successor

This directory contains the byte-exact published Node8c source and a pure source
transformer for its historical validator. The protected operator-epoch path is
still blocked by a separate qualification10-only guard described below.
It creates no accounts, registrations, Pods, driver allocations,
images, configuration or live authority. No real future target capture or Root
contract is included. The current D48 qualified-group behavior remains intact.

The actual Node8c validator rejects a prospective operator-qualification config
when reading retained39ef terminal history: its current-policy predicate permits
only D48 with the original CPS5/CIT10 scopes. The regression first reproduced
that rejection against `node8c.py`. The successor permits one additional finite
configuration bound to an independently reviewed raw contract SHA256. It changes
only `validate_historical_configuration`; every other definition and all source
bytes outside that definition remain unchanged.

The contract is a closed JSON object with these fields:

| Field | Required value |
| --- | --- |
| `version` | Integer 1 |
| `policy_hash` | Nonzero canonical SHA256, distinct from D48 and 39ef |
| `workspaces` | Exactly two bounded `cps:operator-qualification-531-*` scopes; qualification5/5120MiB and qualification20/20480MiB |
| `terminal_history_sha256` | Canonical SHA256 of the complete unchanged current terminal-history mapping |
| `operator_people` | Independent Root allowlist of canonical nonstudent UUIDs |
| `operator_members` | Exact scope keys; nonempty disjoint UUID lists whose union equals that allowlist |

The prospective configuration must additionally be enabled version 2,
`operator-qualification`, with max 2 workspaces, budget 25600 MiB, headroom
1024 MiB and measured free memory at least 26624 MiB. The original immutable 39ef
configuration, its raw data reference, original5/20 scopes, nonrecursive history,
physical node/device/boot/driver epoch and original25GiB budget are still checked.
The unchanged enrollment path still verifies retained enrollment/completion UIDs,
full hashes, released ledgers, inert journals and absent historical Pods.

The Node config itself has no people or workload-image fields. Contract membership
is provenance for this finite source output; it does not establish Directory or
Source identity. Before any runtime use, Root must independently review the real
two Source snapshots, disabled531 catalog/policy, complete current authority and
history, dedicated neutral owners/PVCs, disjoint actual operator people and
matching Gateway/Hub approvals. The historical916 evidence is retained as
historical evidence; this transformation establishes no new hardware gate.

Default invocation is inert and reads no files:

```sh
python3 node_successor.py
```

Only after an independently reviewed real contract exists may Root emit source:

```sh
python3 node_successor.py --emit --contract /reviewed/root-contract.json \
  --contract-sha256 <independently-reviewed-bare-64-character-raw-sha256> \
  > /reviewed/candidate-node-agent.py
```

The raw SHA256 must be supplied before any input file is opened. Duplicate keys,
nonfinite JSON, unknown fields, students, overlapping people, arbitrary source
bytes and unknown historical/pair configurations fail closed. The transformer
does not run the emitted source. A later separately reviewed runtime release must
also account for the unchanged operator-epoch bundle/process pins; no approval
consumer upgrade is implied by this source-only result.

## Remaining protected-epoch blocker

The same published image's `opt/native/native_operator_epoch.py`, SHA256
`890cebd7c1903a680e4dc836ec6f81f097198c2fed438ade6b2fa62157864bbd`,
has an independent guard at lines 75–96: `node_configuration` permits only
qualification10/cap 10240 and a budget at most 15360 MiB. Its
`OperatorNodeEpochPublisher._actual` (166–170) calls that guard;
`build_installed` (273–303) immediately calls the publisher. Thus this historical
transformer alone cannot run the protected prospective pair. A separately reviewed
finite change to that helper and the Node's exact helper pin is still required.
No such change, image build or runtime adoption is included here.

The coordinator-side `cps_compute.native_scheduler_node_epoch` observer also
requires the qualification10 profile in its constructor and a 10240 MiB cap in
`observe`; `native_scheduler_coordinator_server` selects it for operator-only
configuration. Future work must qualify both the selected Node publisher and
matching coordinator observer. These history-transformer tests qualify neither
protected execution path.

The selected Node publisher does not invoke `NativeGroupQualification.from_config`.
The separate `OperatorNodeEpochObserver` (119–155) imports that type only inside
its constructor. The Node's operator branch (1040–1043) constructs the publisher,
and its main guard (1010–1011) forbids overlapping dynamic approval inputs. This
supports retaining old Core modules on this path; it does not qualify arbitrary
future caller changes.

Offline regression command:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/bjoern/git/cps-compute/.venv/bin/python -m pytest \
  -q -p no:cacheprovider \
  platform-staging/gpu/native-group-pilot/prospective-pair/test_node_successor.py
```

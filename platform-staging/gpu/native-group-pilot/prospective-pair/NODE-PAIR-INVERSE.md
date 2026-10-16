# Fresh CPS pair Node restoration

`configuration_inverse.py` is a separate offline path for the two dedicated
CPS operator qualification workspaces. The legacy CPS+CIT inverse is unchanged.
Neither entrypoint performs an API call, reads credentials, touches the GPU or
applies an artifact.

`derive_node_inverse` requires the original and actual created immutable Node
configurations, complete baseline/final ledger/authority/journal/physical captures,
an unpaginated final PodList, the original pinned Node8c/epoch source bytes, an
explicit current timestamp, and two independently reviewed raw documents:

- The same exact Root contract used by `node_successor`: prospective policy,
  workspace/profile/cap pairs, disjoint nonstudent people and baseline history hash.
- A closed restoration approval containing `version=1`, canonical original/current
  configuration data hashes, the raw complete baseline ledger hash and two full
  Source claim identities (`qualification_configuration_inverse.IDENTITY`).

Each document is supplied as bytes alongside its independently reviewed raw SHA256.
The restoration approval must come from the actual reviewed Source-owned identities;
constructing an approval from arbitrary final ledger contents does not review them.
The final claims must match these identities, the Root contract and the native
ledger's own immutable claim checksums. Fresh workspaces do not need an invented
previous claim to satisfy the legacy CPS+CIT assumption.

The derivation requires all previous claims, protected envelopes, journal records
and physical retirements to survive unchanged, with exactly two new enrolled,
released lifetimes. Both new lifetimes require finite retired caps and zero-charge
physical witnesses in the unchanged driver epoch. The physical observation must
be no older than 60 seconds; lease expiry is not cleanup evidence. Both actual Pod
UIDs and replacements using their names must be absent.

The output restores the exact original Node configuration except for retained
terminal-history additions, stages a new immutable configuration, retains the
full authority archive and replays that archive under the restored policy. It
retains the generated Node/epoch code needed to interpret the new immutable
historical configuration. It does not revert to Node8c and lose that interpretation.

`derive_node_handover_inverse` additionally requires original/current full Node
Deployments and immutable code ConfigMaps. It verifies that the forward handover
changed only the exact configuration/code references, preserves every other
source byte and Deployment field, and returns a UID/resource-version/spec-tested
Node Deployment patch. Changed images, mounts, ownership, helpers or configuration
references fail validation.

All results have `enabled=false`, `live_applied=false` and
`hardware_qualified=false`. These artifacts cover Node restoration only. A complete
execution still requires coordinated Gateway policy/runtime and Source inverses,
reviewed forward configuration adoption, real post-stop captures and hardware
qualification. Do not apply a Node patch independently of that coordinated plan.

The synthetic CPU tests include retained prior history, a fresh pair, finite
retirements, round-trip replay, configuration/code CAS, and deliberate authority,
charge, Pod, freshness, ownership, code, image and mount faults. They do not
represent a completed hardware run or a deployed production release.

Validation on 16 October 2026: **27 new tests passed**; the complete native-group
pilot suite passed **658 tests and 851 subtests**, with 14 skips. No live or
hardware acceptance is inferred from these CPU tests.

## Baseline mapping and failure phases

The Root history hash binds the **complete verified baseline authority mapping**,
not merely the original D48 active configuration's `terminal_history` field.
That active field excludes D48 lifetimes because D48 is its current policy.
Those lifetimes must become retained history under the prospective policy, so
the inverse verifies them against the full baseline ledger, journal and immutable
completion objects before accepting the prospective mapping. Every original
historical configuration reference must remain unchanged.

`derive_unstarted_node_inverse` requires zero added claims and unchanged complete
custody. `derive_partial_node_inverse` requires exactly one reviewed new lifetime
to have been released and retired; `derive_node_inverse` requires both. The three
paths reject captures from the wrong phase. All require fresh zero-charge physical
evidence and absence of both prospective workspace Pod names.

`derive_node_handover_inverse(phase=...)` accepts exactly `unstarted`, `partial`
or `complete` (the default). The unstarted path restores the original Node code;
the other paths retain the reviewed generated code because new lifetime references
need its finite historical interpretation.

The [Gateway transition planner](GATEWAY-TRANSITION.md) separately produces exact
forward and reverse policy/runtime/Deployment CAS artifacts. Source and Hub
handover/restoration still require integration before execution.

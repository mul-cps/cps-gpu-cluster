# Single-scope prospective531 proposal

This is an offline operator proposal, never hardware evidence or an apply
packet. It requires the reviewed `efa3c8ab9c9e7cfffa223a7ae3577e3fe368901c`
Core qualification validator. The legacy5/10 and current-approved20 renderers
retain their existing contracts. Production image916, registry, historical
evidence, Source records and runtime configurations are unchanged.

Root first creates a dedicated operator account/course/group/workspace through
normal Source APIs. The workspace must be stopped on `interactive-cpu`, have
active provisioned storage, a neutral computed `cps-ws-<32hex>` owner, named
server `rtc`, and only explicit canonical operator members. Student workspace
`shared-gpu-lab`, its owner, Mikasa and Armin cannot be qualification targets.
This proposal creates no accounts, grants, Pods or storage.

The existing input, NVML observation, health and complete terminal-authority
formats remain. Every ledger claim must be released; all immutable enrollment,
completion, protected journal and finite historical configuration references
must match. The candidate mapper reuses the existing finite D48/39ef historical
validator without starting or patching a node agent. No historical policy,
image, journal or evidence is relabelled as candidate qualification.

Supply the unchanged full source closure format from
`source_qualification_handover.verify_source_closure`: `{version:1,modules:{...}}`
with exactly its sixteen application/Core module hashes. The renderer validates
that schema, its independently pinned raw bytes and the loaded candidate
qualification module hash. The Source lifecycle CLI must run the existing
loader to verify **every** loaded module before opening the configured app.
The historical checked-in closure is not a current deployment closure.

The separate Root-pinned `target_snapshot` has exactly:

* `version:1`, `source:"cps"`, `workspace:"operator-qualification-531-..."`,
  `profile:"interactive-native-qualification-5"`, and `workload_image` equal to
  `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:531027c8e330d4ce818598e998a29d502433e9064f06a32dfc208a06ef2d0ba4`.
* `operator_members`, `source_policy_hash`, `source_closure_sha256`,
  `current_authority_sha256`, `state:"stopped"`, and UTC `observed_at`.
* `source_instance:{namespace:"cps-compute",deployment_uid,pod_uid,image}`,
  binding actual nonzero UIDs and exact Source51f image.
* `registration`: the full existing Gateway GET record, including all twelve
  approval fields plus `workspace`, `policy_hash`, `workspace_label` and
  `workspace_hash`. Its storage retains `state:"active"`. Derived labels must
  match the source policy. Course, term and group IDs start with `operator-`.

Raw target/closure SHA arguments and `source_closure_sha256` are **bare64hex**.
Canonical authority/history/policy hashes use `sha256:<64hex>`.
`current_authority_sha256` is the canonical hash of
`{ledger:input.ledger,previous_node:input.node_config,...terminal_authority}`.
Target, capacity and protected host observations must be within fifteen minutes
and in UTC. The target is a supplied capture, not a live observer or substitute
for the later actual Source/Hub/isolation checks.

Default invocation is inert. Root reviews all concrete inputs and raw pins
before rendering into a new directory:

```sh
python qualification_proposal.py --render --source-mode prospective-candidate \
  --input ROOT/input.json --observation ROOT/nvml.json --health ROOT/health.json \
  --terminal-authority ROOT/terminal-authority.json \
  --target-snapshot ROOT/target-snapshot.json --target-snapshot-sha256 TARGET_RAW_SHA \
  --source-closure ROOT/source-closure.json --source-closure-sha256 CLOSURE_RAW_SHA \
  --output ROOT/new-offline-proposal
```

Output uses the existing policy/mode/node/registration/acceptance files, with
one disabled5GiB profile, one exact CPS scope, one claim slot and a5120MiB
budget. Gatebc5 remains exact. Acceptance records bind the target, full source
closure, current retired authority and complete terminal-history checksum.
`hardware_qualified` and `live_applied` remain false. Output snapshots are
canonical copies; preserve the original Root input files for their raw hashes.

No production activation is enabled. Before any hardware stage Root must
normally stop the current student workspace, verify actual Pod absence and
released/zero native custody, establish the existing writer/Start isolation,
review restoration and install the separately reviewed operator configuration.
All six candidate gates require fresh actual531 evidence.

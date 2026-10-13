# Reviewed Hub package image handover

This operator-only bridge upgrades the two existing Hub service containers from
`c22c7460ae3ddc3cac454a7f0fac41fc7308e4601e06162b91ca7af7ba301233` to the
reviewed immutable package image
`bc32b73d244738c3778560a1f48e701efd10f8c57ac4834f486b3f27a30d2623`.
Both images belong to `ghcr.io/mul-cps/cps-compute`. It is an offline intent
constructor, not an override API or an automatic rollout. With no arguments it
performs no network access or filesystem mutation.

The normal Source renderer remains unchanged: it must reject an image change
hidden in a Source revision or replay. This separate operation keeps the actual
Source registry, approval documents, references and their UIDs, policy,
qualification, driver epoch, acknowledgment identities, usernames, storage,
mounts, Hub configuration and all gateway/node Deployment fields unchanged.
Only the two Hub service images, their image-bound immutable publisher bootstrap
files and the corresponding bootstrap volume names change. The structural
permission step permits only actual singleton Pod and ReplicaSet GET names to
change. Publisher Roles never gain another verb, namespace or resource.

## Capture and pause

Use the already reviewed authenticated capture client against the private TLS
capture endpoint: `native_group_capture.py` from SDK commit `5b50e795` or its
corresponding immutable installed image. `/capture` supplies the closed v1
Source packet; independently call `/epoch` and record the observation time.
Use real API GET readbacks for all Kubernetes objects. Do not create examples,
edit acknowledgment JSON or label fixture tests as live evidence.

First confirm the existing delivery journal has completed: `transition=null`,
`process_refresh=null`, `structural_prior=false`, and every current process and
Role agrees with its publication. Pause its existing Deployment with a full
UID/resourceVersion/spec CAS; preserve its PVC and journal bytes. No Source
mutation may run concurrently with this software handover.

Create a mode-0600 packet in an owned private directory with these exact keys:

- `version: 1`, `previous_publication`, and its canonical
  `previous_publication_sha256`.
- Existing exact `policy` and `qualification` configuration.
- `reviewed_images`: exactly `hub:cps` and `hub:cit`, each containing exactly
  `previous` and `next` with the two full immutable image references above.
- `old_state`: exact previous `seed`, canonical `seed_sha256`, completed
  `journal`, canonical `journal_sha256`, paused actual `controller` Deployment,
  bound actual `journal_pvc`, and two distinct fresh object identities
  `next_journal` and `next_input_secret`, each `{namespace,name}` in
  `cps-compute`. Never reuse or edit the previous journal or input Secret.
- `observations`: exactly `documents`, `reference_maps`, `bootstrap_maps`,
  `acknowledgments`, `deployments`, `replicasets`, `pods`, `roles`, `source`,
  and `epoch`. The first seven maps contain all four component keys;
  `acknowledgments` contains actual ConfigMaps with `ack.json`, not only their
  data. `roles` is keyed by each of the seven `namespace/name` pairs.
  `source` is the actual closed v1 capture packet. `epoch` is exactly
  `{driver_epoch,captured_at}`, where `driver_epoch` is the actual four-field
  protected epoch result. Both captures and all genuine ACKs must be current
  within 30 seconds when planning.

Use canonical hashes from `native_group_approval_renderer.canonical_sha256`.
The original publication must already bind all actual document, reference and
bootstrap UIDs. The helper also checks the complete original journal baselines,
Role UIDs/rules, paused controller and preserved PVC lineage.

## Plan and apply the two guarded Deployment changes

Run with the reviewed SDK and cluster pilot helper directory on `PYTHONPATH`:

```bash
python qualified_hub_package_handover.py --phase plan \
  --input /private/hub-handover-request.json --output /private/hub-handover-plan
```

The output `/private/hub-handover-plan/intent.json` is private. It contains only
two `bootstrap_candidates` and two `deployment_patches`, plus the complete
reproducible request and previous seed/journal/PVC/controller lineage. Planning
requires fresh genuine readiness for all four existing processes. `ready=false`
is intentional.

Create the two immutable ConfigMap candidates through the operator's existing
API identity, then retain their actual create/readback UIDs. Preflight both
Deployment patches before applying either. Apply exactly each four-operation
JSON patch from `deployment_patches[component]`: test original UID, test
resourceVersion, test complete `/spec`, replace complete `/spec`. Apply to the
Deployment named by `projection.expected_deployments[component]`. Do not use
`kubectl set image`, regenerate publisher fields manually, change another
container, or alter an approval document. If a preimage conflicts, recapture and
review; do not remove its tests.

No helper phase contacts Kubernetes. The operator applies the reviewed create
and patch artifacts. An installation interrupted between Hubs is incomplete;
keep the delivery controller paused and finish the same exact reviewed targets.
Do not replace either newly created immutable bootstrap.

## Permit only the actual new process names

Capture the genuine new Hub Pods and their owning ReplicaSets, all four exact
Deployment specs and current ConfigMaps/Role readbacks, and fresh protected
Source and epoch results. Pending/Running Pods may be used for this structural
step before their acknowledgment publishers can read their own Pod. The full
owner chain and executable template must match the exact planned target.

Create a new mode-0600 packet with exactly `{version:1,plan,observations}`,
where `plan` is the complete plan output and `observations` uses the schema
above. Existing publisher Role rules must still match the old current-process
GET names, with the original Role UIDs.

```bash
python qualified_hub_package_handover.py --phase process-access \
  --input /private/hub-handover-process-request.json \
  --output /private/hub-handover-process-access
```

Preflight and apply the seven full UID/resourceVersion/rules CAS patches from
`role_patches`, including unchanged no-op targets. The result is still
`ready=false`; this stage proves structure and named read permission only.
Keep this exact output: it binds the actual new immutable bootstrap UIDs.

## Genuine readiness, final publication and new seed

After the two replacement Hub processes publish genuine successful ACKs,
recapture all four current processes, the original ACK ConfigMap identities,
the applied Role rules and fresh protected Source/epoch results. Never reuse an
old Pod receipt or an ACK from the previous image. Make a mode-0600 packet with
exactly `{version:1,plan,access,observations}`; `access` is the complete structural
permission output.

```bash
python qualified_hub_package_handover.py --phase finalize \
  --input /private/hub-handover-final-request.json \
  --output /private/hub-handover-final
```

Finalization verifies actual ready Deployment/ReplicaSet/Pod ownership,
executable image IDs, exact specs and mounted inputs, fresh successful ACKs from
all four current processes, original documents/reference/ACK identities and the
same driver epoch. It rejects replacement of any bootstrap since the structural
readback. The final artifact has `ready=true`, an actual UID-bound `publication`,
a closed compatible `seed`, and the old seed/journal/PVC/controller lineage.
This is software handover evidence; `production_qualified` remains false.

Create a separate empty journal PVC and separate immutable input Secret under
the planned fresh names. Render the existing delivery runtime with the new
closed `seed`; its named immutable-ConfigMap access must include the new Hub
bootstrap names. Preserve the old controller UID, full unchanged configuration
outside this reviewed seed/volume/input replacement, original Role UIDs and
admission protections. Apply those operator-reviewed full CAS artifacts with
replicas still zero. Do not edit the previous journal `config_hash`, publication
or Role receipts. Start the new controller only with the new empty journal,
then require its normal trusted Source capture, genuine four-process readiness
and durable journal replay to pass. Preserve the final artifact and old journal
for recovery.

If recovery is needed before the new seed is active, keep the controller
paused. Restoring the old images also requires their original immutable
bootstrap names, exact old specs and fresh actual process permissions/ACKs;
image rollback alone is insufficient. Never reset driver state or GPU caps to
repair this software upgrade.

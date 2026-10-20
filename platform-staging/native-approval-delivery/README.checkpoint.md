# Explicit checkpoint prerequisites

Checkpointing is an operator maintenance action. Preserve the original journal,
anchor, legacy files and all archives; independently review matching backups,
quiesced admission, current Source/epoch and all four actual component identities.
The installed SDK performs the authenticated readiness and custody checks.

`checkpoint_job.render(...)` returns only the one-attempt Job. Supply the actual
protected immutable checkpoint reference separately; it is never a delivery.json
field. The daemon and every subsequent rotation retain that same reference.

Before creating the Job, separately render and review:

```python
permissions = checkpoint_job.read_permissions(
    configuration, namespace='cps-compute', name='cps-native-head-checkpoint-reader')
```

This returns exactly four namespace-local Roles and four RoleBindings for the
existing delivery ServiceAccount: Pods LIST and GET of the seven fixed observer
Role targets derived by the SDK from the actual immutable NodeConfiguration.
There are no writes, Secret reads, wildcard grants or ServiceAccount creation.
Nothing is applied automatically, and Job rendering does not add these objects.
Verify the existing writer can also GET the exact checkpoint ConfigMap; this
helper does not grant arbitrary checkpoint namespaces or replace current Roles.

Create the separately approved eight objects with durable intent and actual
UID/fullspec readbacks. Before retrying a failed Job, reobserve the complete
journal and determine whether a commit happened; preserve failed Job evidence
and use an explicitly reviewed new Job name. Never blindly replay creation.
After successful checkpoint validation, remove only these temporary objects using
their recorded namespace/name/UID and exact current rules/subjects/roleRef checks.
A missing or changed identity is a stop condition, never permission to delete a
replacement. Retain all receipts and leave existing writer/observer Roles intact.

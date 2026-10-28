# Current-group readiness repair — 28 October 2026

The authenticated `/internal/v1/native-group-approvals` API changed from
`ready: false` to **`ready: true`** for profiles `interactive-shared-5` and
`interactive-shared-10`, revision
`sha256:992ae99b027bccef76a537ce91fd6f249f48df6f6263523652ae54fc8985b863`,
policy `sha256:9d86546fd3b9cc52eb92f030932c64600d352884f949c7d06b8b86a0f1f42620`.
The request used CIT's existing Source service credential over CA-verified
HTTPS; credentials were not printed or committed.

## Cause and exact repair

The Rino restoration and CPS compatibility image changes were not fully paired
with process identity declarations. CIT's publisher still named Hub image
`46ffa869...`; its acknowledgment was over three hours old. The gateway's
runtime expected-image declarations also still named `46ffa869...` for both
Hubs. Exact process observation correctly rejected those mismatches.

1. Created immutable `cit-jhub/cps-rino-publisher-5d6803af-20261028`, changing
   only the existing declaration's process image to the actual restored CIT
   image `sha256:5d6803af796bcac8b9487eafb87c3928d7279c958530a0b5ec1ae4640858f31b`.
2. Changed only CIT Hub's publisher volume reference using Deployment
   UID/resourceVersion/old-reference tests. The Hub rolled successfully and
   published a fresh acknowledgment for its actual image/Pod.
3. Created `cps-compute/cps-hub-image-readiness-20261028`, preserving every
   runtime field except the two Hub process image declarations. CPS now names
   `sha256:f00f8c5b63bdce6348153aab6e11c1fd5cbf638ed1b50ef27bdda346ad202b75`;
   CIT names the restored image above. Strict configuration validation passed.
4. Changed only Gateway's runtime Secret volume reference with the same CAS
   guards. It rolled successfully. Final readback verified the entire Pod spec
   unchanged except that reference, and the API returned `ready: true`.

All four acknowledgments agreed on revision/policy and were younger than
13 seconds at final observation. No acknowledgment was fabricated or freshness,
process-image, cap, policy, epoch or qualification check relaxed. Neither the
Node configuration nor GPU/workload image/caps were changed.

Rino, aditya, gottam and muslim retained their original notebook Pod UIDs,
Running phase and zero restarts. This repair restarted CIT Hub and Gateway,
not their notebooks. Rino's Hub activity logs separately report an expired Dex
login token requiring reauthentication; repairing group readiness does not
claim to resolve that distinct authentication condition.

## Qualification scope

The deployed current-group coordinator config is version 2 (`current-groups`),
using the v3 qualification contract on one GPU2 device, UUID
`GPU-16128952-b438-556a-00bb-93039ee24e56`. Its configured shared budget is
15360 MiB, maximum two workspaces, with 5120/10240 MiB caps and six passed gate
references. This readiness result is not eight-device, 20-GiB, burst, reclaim,
full lifecycle, restore or production-release qualification.

Private exact preimages, candidates, CAS patches and acknowledgment summary
are in `/tmp/cit-publisher-repair-20261028/` with restricted permissions.
For rollback, restore the saved runtime Secret and publisher volume references
only if their paired old Hub images are also restored; old declarations paired
with current images intentionally fail closed. No broad Fleet reconciliation
was performed. Runtime-preserving GitOps promotion remains necessary.

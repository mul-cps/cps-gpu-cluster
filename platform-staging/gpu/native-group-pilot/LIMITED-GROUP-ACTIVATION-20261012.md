# LIMITED CPS5/CIT10 activation source recipe

This record persists the Root-accepted offline compatibility preparation from
`group-activation/ready-v2/ROOT-READY.md` on 2026-10-12. It is limited to the two
existing neutral group workspaces below. It does not establish production
qualification, full-fleet qualification, or target-profile Start/Stop success.
All three remain false in [record.json](qualification/limited-group-20261012/record.json).
This recipe performs no Kubernetes, credential, deployment, or live API action.

| Source/workspace | Namespace | Owner / server | Profile | Fixed cap |
| --- | --- | --- | --- | --- |
| `cps:native-group-b` | `jupyterhub` | `cpsnativegroupb` / `rtc` | `interactive-shared-5` | 5120 MiB |
| `cit:native-group-a` | `cit-jhub` | `citnativegroupa` / `rtc` | `interactive-shared-10` | 10240 MiB |

The full sanitized group, member and storage configuration is frozen in
[native-groups.json](qualification/limited-group-20261012/native-groups.json).
Each source settings file contains that same deployment and only its owning
workspace, owner, profile and writable PVC allowlist. No third workspace or
20 GiB profile is admitted. The selected pool is `k3s-wk-gpu2`, node UID
`3336cdd5-d245-436e-b57c-2f66c6dcaa41`, GPU
`GPU-16128952-b438-556a-00bb-93039ee24e56`, maximum two workspaces and a
15360 MiB budget. The captured boot and driver epoch are preserved exactly.

The target policy is version `0.1.1`, hash
`sha256:4f1dff1a92aba5cd7376dfb897612b7e6f2e6f15a09515dbdf29efa4c522359d`.
The gate remains
`ghcr.io/mul-cps/cps-compute@sha256:bc5b128f582641eae8395e1121d1fb248eddc39a56c9e863b7c564badd94b167`
and the notebook remains
`ghcr.io/mul-cps/cps-jupyter-notebook:qualification-native-group-980408a@sha256:9167861058c1364c58d1c2fca0d6f536c3ffb53a33800dcdb9a1560f14ca4dc0`.
These identify the gate and workload; they do not authorize replacing a
gateway or Hub image without checking its installed source independently.

## Offline verification and rendering

Use the existing compiler against the complete Root-reviewed package. The
seven reports establish only the reviewed fixed resource/image/node/member/
storage compatibility, using unchanged historical raw evidence plus the
matching epoch/capacity/importguard. Keep their historical policy/profile
values unchanged. Their checksums and `passed` fields do not create new live
target-profile acceptance. The compiler's general release lock stays
`unqualified`, and ordinary `gpuQualification.qualified` stays false.

From the repository root:

```bash
ready=/home/bjoern/.local/state/cps-platform-completion-20261012/group-activation/ready-v2
python3 scripts/compile_compute_policy.py \
  --catalog "$ready/catalog.json" \
  --native-group-evidence "$ready/native-group-evidence.json" \
  --native-group-artifacts "$ready/native-group-artifacts.json" \
  --output "$ready/compiled" --check
python3 -m unittest discover -s tests/compute_policy -v
python3 platform-staging/gpu/native-group-pilot/limited_group_recipe.py \
  --render --ready "$ready" --output /NEW/LOCAL/limited-group-recipe
```

The renderer reads only `native-groups.json`, `cps-settings.json` and
`cit-settings.json`, checking their raw hashes against the committed record.
The committed sanitized copies can also be used for `--ready`; this reproduces
the frozen source recipe without access to the state directory. The renderer
does not read a baseline runtime, Secret, environment token or kubeconfig, and
does not construct an SDK client. Its default invocation is inert. Changed
source bytes need a new reviewed record; they cannot silently expand this one.

The output contains only a four-field gateway runtime overlay, the two
unchanged source settings documents, two Hub hook documents and an offline
acceptance record. It contains no Secret or Deployment patch. The relevant
source-owned runtime fields are exactly:

```json
{
  "policy_hash": "sha256:4f1dff1a92aba5cd7376dfb897612b7e6f2e6f15a09515dbdf29efa4c522359d",
  "nativeGpuGroups": "the complete unchanged reviewed native-groups.json object",
  "nativeGpuQualification": {"enabled": false},
  "nativeGpuPilot": {"enabled": false}
}
```

The displayed `nativeGpuGroups` string is a documentation placeholder; the
rendered overlay contains the complete typed object. During the separate
Root-owned live update, replace these entire top-level fields in the freshly
captured existing runtime and preserve every unrelated field. Do not recursively
merge the disabled modes: the released schema requires disabled
`nativeGpuQualification` to be exactly `{"enabled":false}`. Old `node_pool`,
`workspaces`, evidence or other mode fields must be removed with the replacement.

Both Hub hooks call `install_native_group_hub_configuration(c, settings)` from
`cps_compute.native_hub_config`. Replace the previously installed mode hook
using the freshly captured current configuration; do not install multiple mode
hooks. Preserve the neutral login guard, source roles, canonical human mapping,
source token reference, trust files, personal configuration and other hooks.
The existing private machine pull wrapper delegates the released group hook
first and modifies only the exact neutral owner's image pull references.
The settings already use `groupDeployment`; prospective
`install_native_qualification_hub_configuration` and pilot
`install_native_hub_configuration` are not this mode's installer.

## Root-owned live handover boundary

The source record retires `interactive-native-qualification-5` and
`interactive-native-qualification-10`; no entitlement references remain in the
target catalog. It preserves all 31 historical allocations, 28 terminal Pod
histories and three released never-enrolled allocations. The existing
`ready-v2/node-config.json` has its own recorded hash and full terminal history;
it is not regenerated or trimmed by this helper. Preserve original historical
policy/profile values, finite limits, enrollment/completion UIDs, journals and
storage bytes. Existing cordon/device-plugin and unrelated driver/node state
are outside this overlay.

Root executes any later live changes with the owning source service identity
and existing controlled writer/start exclusion. The sanitized `ROOT-READY.md`
defines the audited API path; the sequence below records that boundary without
reading credentials or submitting requests:

1. Capture the existing source-owned workspace and grant records, and verify
   no active reservations before the policy/runtime change.
2. After the reviewed group runtime is installed, rebind the two existing
   workspaces with `cps-workspace-registration.json` and
   `cit-workspace-registration.json`. Preserve the original source/workspace/
   group/owner/server/member/principal/ceiling/course/term identity. The server
   retains storage; do not add storage, labels or status to the closed PUT body.
3. For exactly the two existing CPS and two existing CIT canonical members,
   replace each existing source-owned grant by its captured ID. Preserve
   person, projects, allowance, starts and other existing profiles. Migrate
   only retired profile references to the corresponding shared5/shared10
   profile and use Root's bounded timezone-aware expiry and controlled-cycle
   reason. Do not create new identities, grant IDs or larger allowances.
4. Read back effective policy, workspace-policy preview and source audit
   entries before normal Start. Do not use metrics credentials, actor headers
   or direct database edits for internal source authority.
5. End the cycle with normal Stop and confirmed cleanup before reversal.
   Under the new policy, end a temporary renewal by restoring the original
   expired expiry while retaining migrated shared profile names. Exact old
   grant bodies containing retired aliases require the complete old-policy
   rollback first; retain both change audits.

The remaining live acceptance is shared5/shared10 target-profile Start/Stop,
CPS5 typed OOM while CIT10 peer ticks, and exact CPS5/CIT10 cross-parent IPC and
VMM import checks. Historical MPS10 execution and host5/20 import results are
not those live results. Record later independently reviewed evidence separately;
this frozen source preparation keeps their acceptance flags false.

The separate [2026-10-12 measured receipt](qualification/limited-group-20261012/measured-results.md)
records fresh CPS5/CIT10 OOM, peer continuity, sustained MPS and same-parent
import controls. It does not change this frozen preparation record or establish
fresh cross-Pod import isolation, general access or production qualification.

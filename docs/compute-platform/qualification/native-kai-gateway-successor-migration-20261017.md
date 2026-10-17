# Gateway startup successor: publication and v4 migration contract

Status: read-only source audit, not an implemented migration or live acceptance.
The main goal remains actual Source-approved dynamic GPU sharing through KAI,
with no MIG/driver reconfiguration. The immediate prerequisite is a qualified
Gateway startup fix followed by a guarded v4-to-v4 trust/configuration rotation.
Root owns fresh captures, backups, maintenance fences, publication and rollout.

## Provenance and source covers

SDK baseline: `551379c6902791d0dd192596046669f1fe274562`, clean source at
`/home/bjoern/git/cps-compute-worktrees/native-dynamic-approval-delivery-20261017`.
The startup owner reports committed/pushed successor
`db9f453fc4289a95f6ef495be921fedd7bdb71b0` in
`/home/bjoern/git/cps-compute-worktrees/native-kai-current-head-startup-20261017`:
15 focused cases and3283 full cases pass (3 skips,49 subtests);72 source/wheel
modules match, with only the Coordinator server runtime module changed from551.
The regression extends `tests/test_native_head_empty_startup.py`. These are
source/package results; no successor image or live acceptance is claimed.
Cluster covers below were inspected at `89a9e86a19ea36b20e3aba8acff85d146b1cffb2`;
this report adds no implementation. Paths in this table are repository-relative
to the indicated repository; spans describe that baseline, not a future patch.

| Repository / covers | Relevant contract |
| --- | --- |
| SDK `src/cps_compute/runtime.py:491-496`; `src/cps_compute/native_scheduler_coordinator_server.py:113-157,246-306` | Gateway runtime installs the Coordinator; closed configuration, current context and head-aware epoch selection. The startup fix is a Gateway consumer change, not a Hub/Node protocol change. |
| SDK `src/cps_compute/native_approval_head.py:32-40,144-165` | Exact Binding2 and actual process/mount/epoch/current-head ACK2 proof remain required. |
| SDK `src/cps_compute/native_node/service.py:85-96,432-450`; `src/cps_compute/native_node/custody.py:204-271` | Node reads its protected six-key configuration reference; private antirollback custody is keyed by the head binding. Preserve that binding and custody rather than reanchor. |
| SDK `src/cps_compute/native_observer_permissions.py:80-122,229-281` | Release2 pins NodeConfig, four local heads and seven Role UID/static baselines. Held Node needs its complete template digest; Ready controller proof uses actual Deployment/RS/Pod specifications. |
| SDK `src/cps_compute/native_approval_delivery.py:34-97,126-198,254-325,327-345,415-425` | Delivery pins NodeConfig plus Release2, verifies actual process declarations, and binds both journal and anchor to the full configuration hash. Existing explicit adoption handles the old legacy journal, not v2-to-v2 rotation. |
| Cluster `platform-staging/gpu/native-group-pilot/current-group-kai/image_adoption.py:193-241,265-320,323-357` | Existing image composer reads v3 fixed approval/reference projections and `approval_ref`; it is not a current v4 image rotator. Its guarded actual-readback/full-spec patch style is reusable. |
| Cluster `platform-staging/gpu/native-group-pilot/current-group-kai/head_runtime_adoption.py:18-77`; `head_observer_adoption.py:44-56,130-174` | Existing helpers explicitly compose v3-to-v4 and Release1-to-Release2 migration, not v4-to-v4 image/config rotation. |

## Minimum artifact change and required trust rotation

If the reviewed runtime diff remains confined to
`native_scheduler_coordinator_server.py`, only a new **Gateway image** is
needed. Retain qualified551 Hub, Node, observer and binder images; record their
unchanged provenance explicitly. Do not describe this mixed component cohort
as all four images containing the new wheel. Source/wheel inventory must prove
that the other SDK modules and all Hub modules are unchanged.

That image is **not a drop-in rollout**. A guarded successor must:

1. Create immutable NodeConfiguration4 changing only the Gateway image
   declaration. Preserve qualification, driver epoch, terminal index/history,
   all four HeadBinding2 values, pointer UIDs, anchors, current references and
   retained immutable approval history. Do not reset generations or approvals.
2. Bind the actual new ConfigMap UID/RV/data hash into the Node bootstrap and
   Coordinator configuration. Preserve the Node image, `NODE_IMAGE`, service
   command and private state. Use the actual held bootstrap/template proof;
   restarting the same Node image to consume its new reference is separate
   from building a new Node image.
3. Update Gateway runtime/publisher process image declarations and the immutable
   Coordinator seed consistently. Preserve Source/DB/policy/auth/CA/storage
   settings and unrelated Secret bytes. Existing Hubs need no image/template
   change solely for this Gateway source delta.
4. Compose successor ObserverRelease2 with the new NodeRef and actual held Node
   template digest. Preserve seven Role UIDs and static rules; allow only the
   specifically reviewed named ConfigMap GET additions for the new authority
   objects. Preserve the separate four operator-own pregrant Role UIDs and
   baselines as well. Perform prospective
   and then actual observer rendering with fresh complete controller captures,
   followed by genuine current ACK2 proof for all four components.
5. Rotate the existing delivery v2 configuration/journal through a separately
   reviewed migration primitive. The old configuration retains the old Gateway
   process pin; the new configuration has a different `config_hash`. Either
   naive substitution therefore holds. Preserve old journal/anchor bytes,
   legacy archives and hashes, completed publications, highest/current heads,
   process provenance and crash/restart custody. No deletion, reset, fresh
   state directory, fabricated initial head or legacy-adoption shortcut is an
   acceptable substitute. That v2 rotation primitive is currently missing.

Root may explicitly keep automatic delivery paused during bounded coordinated
qualification. Paused delivery is not completed automatic production adoption.

## Required regression and acceptance evidence

- The startup worker's actual `create_runtime` regressions must cover a
  nonseed current scope while current ACK readiness is temporarily unavailable,
  then restored, without using fallback seed claims or bypassing authentication.
- Preserve SDK tests `test_native_head_empty_startup.py:156-245`,
  `test_native_head_coordinator.py:46-150`, `test_native_head_epoch.py:16-77`,
  current-group/server tests and the full source suite. Run the new startup
  regression against the installed candidate wheel/image, not source imports.
- New v4 rotation tests must prove exact allowed deltas and unchanged head,
  qualification/history, driver, other images and seven Role/static baselines;
  reject UID/RV/spec/data drift, broad grants and unrelated template changes.
- Delivery rotation requires interrupted-write/lost-reply/restart tests,
  old/new configuration mismatch holds, missing/tampered archive holds,
  stale ACK/process/Source/epoch denial, and continuation of the next genuine
  publication without resetting the existing journal or any pointer.
- Root's live acceptance requires fresh quiescent ledger/SQL fences, verified
  backups, actual created-object readbacks, guarded process adoption, observer
  permissions and four genuine ACK2 receipts before resuming delivery and
  attempting the bounded KAI GPU lifecycle. None is established by this report.

## Existing package and image path

The repository workflow is `.github/workflows/test.yml` (test/build only;
publication is a separate Root action). Its existing commands build all three
distributions, enforce equal versions/Hub SDK pin and one Lab asset owner,
rebuild wheels from sdists, and exercise installed SDK/Hub/Lab plus lean Node:

```sh
python -m build --outdir dist
python -m build packages/hub --outdir dist
python -m build jupyterlab-addon --outdir dist
python scripts/verify_extension_packages.py dist
```

Keep the workflow's sdist rebuild, `pip check`, installed extension checks,
Lab4.5.7/4.6.4 matrix and the three installed Node closure test files. No new
Lab image or broad dependency/SBOM campaign is required for this server delta.

The latest qualified baseline evidence is under
`/home/bjoern/.local/state/cps-full-project-20261013/dynamic-approval-delivery-source-20261017/`:
`final-package-verification.json`, `installed-verification.json` and their
source/build/installed logs. These are551 evidence, not successor results.

Reuse the generic, independently reviewed private recipe at
`/home/bjoern/.local/state/cps-full-project-20261013/native-head-image-recipe-20261017/recipe.py`:

```sh
python -B recipe.py --prepare /absolute/reviewed-successor-inputs.json --out /absolute/fresh-successor-contexts
```

`prepare` (lines67-102) requires a clean exact committed source, actual SDK/Hub
wheel paths/hashes and four current immutable predecessor references. It
prepares four contexts but builds nothing. Use the actual qualified551 image
digests from fresh Root captures, not the older bases inside historical inputs.
Review the generated plan, then Root executes only its Gateway `build_command`
array (`podman build --pull=never --network=none`). For Gateway-only verification,
retain the complete revision/module/archive evidence and the reviewed Gateway
entry in a separate plan, then run:

```sh
python -B recipe.py --verify /absolute/reviewed-gateway-only-plan.json
```

`verify` (lines104-134) checks complete installed module bytes, unchanged
dependency distributions/runtime defaults, exact provenance labels and
`pip check` in read-only, network-disabled containers. Add the installed startup
functional regression with test fixtures/tools mounted read-only and no source
package import override. Root separately publishes and verifies immutable
registry manifest/config digests after review.

Do not run `build_one.py` unchanged: it selects `contexts-551379c` explicitly.
Do not reuse `docker/kai-reviewed-release/build_hub.sh` unchanged: its old wheel
hashes are hardcoded. Neither is a generic successor publication command.

### Revocation and restart regression closure

The first startup candidate (`db9f453`) is superseded by SDK `1f4d647`: a
normal approval/use/release/revocation cycle exposed a restart failure when
the captured startup PVC list contained a now-revoked workspace. The fix
accepts startup provenance only from current approvals or exact authenticated
retained registry-v2 history, with a fresh exact-head check. Request-time
leases, compilation and writable mounts remain current-approval-only.

The real-runtime regression verifies revoked requests remain denied and a
surviving approved peer can still lease and compile. Unknown, unretained,
tampered or missing historical evidence and source/head races fail closed.
Full source qualification passed 3,327 tests and 49 subtests; 29 focused
cases passed independently and from the installed wheel. The three host-only
skips passed in the actual candidate image in a disposable CPU container.

The published Gateway digest and package checksums are in
`qualification-artifacts/native-head-delivery-release-20261017/gateway-revoked-pvc-restart-image.json`.
Publication is not deployment: the old six inert successor objects still
reference the superseded Gateway candidate. Refresh actual successor refs,
finish exact-source CI, then perform the guarded maintenance and live GPU
acceptance gates. No journal rotation or live successor rollout is claimed.

### Live trust handover and rotation attempt

The fixed Gateway `1f4d647` is now deployed with its actual successor Node
reference and observer release. Gateway, both unchanged Hub applications,
Node and observer recovered; the observer reconciliation plan was empty and
four genuine current ACK2s passed. Original operator Roles and four protected
notebook Pod UIDs were preserved; GPU2 remains cordoned.

The explicit same-journal rotation Job then rejected Kubernetes' default
`configMap.defaultMode: 420` on the authenticated old Node bootstrap volume.
It failed before commit. A fresh read-only snapshot proved state and anchor
bytes, inode and device identities unchanged; the journal remains version2.
The writer is intentionally paused until the delivery validator fix is
qualified and rotation succeeds. Coordinator installation, Hub pending-path
activation and live shared-GPU acceptance remain open. See the separate
`gateway-fixed-successor-live-result.json` receipt; earlier staging receipts
remain historical observations.

### Journal recovery completed

The corrected delivery image `d66abdeb` passed all four CI jobs. Its
explicit same-PVC/subpath rotation Job succeeded; the journal is version3,
the original anchor bytes are unchanged, and five rotation archives remain.
The corrected continuous writer is Ready. Eight temporary read RBAC objects
and both terminal rotation Jobs were removed with UID/RV preconditions after
evidence capture. Four genuine acknowledgments passed after recovery.

Coordinator installation now reaches Ready, but signed service authorization
is not yet qualified. Kubernetes' projected-volume root mode03777 is rejected
by the strict credential reader even on its read-only mount. A controlled
CPU-only Pod proved a nested `credentials/token` projection has parent
mode02755 and is accepted by the existing reader. SDK and binder path
validators support this layout and reread credentials per request; deploy
the nested projection rather than weakening the reader.

### Coordinator and pending Hub paths activated

Deployment source `f905d39` uses nested projected credentials; no SDK token
reader change was promoted. The existing strict reader accepts the protected
nested parent and continues rereading kubelet-rotated tokens. Admission
proved the Gateway manifest changed only its token item path and immutable
seed name. Images, Node reference, epoch, policy and RBAC stayed unchanged.

Live TLS/authentication checks accepted both Hub identities and the binder
identity, while rejecting missing credentials, wrong audiences, unauthorized
actors and cross-role operations. Invalid request envelopes were used, so
these checks created no leases and do not prove a complete GPU start.

Both Hubs were upgraded sequentially to the pending-workspace hook after
fresh PostgreSQL backups. Each is Ready, has owner1000 mode0600 private
configuration in a mode0700 directory, and authenticated using its actual
mounted projected credential. Four genuine ACK2s passed after both updates;
four protected notebook Pod UIDs remained unchanged. The first CPS actor
attempt restored its original spec/Secret after a local argument-size limit;
the successful retry used patch files.

The binder's nested credential and pinned reservation image are staged and
Ready, with its bridge explicitly false. Its public trust bundle was copied
from the exact existing Gateway CA. Actual KAI placement remains unqualified
while GPU2 stays cordoned. Isolation/import/restart/MPS and broader production
acceptance gates remain open.

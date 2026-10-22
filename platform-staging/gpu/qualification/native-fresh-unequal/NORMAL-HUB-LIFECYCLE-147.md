# Normal Hub lifecycle qualification, 2026-10-22

Status: bounded two-workspace Start/CUDA/Stop/restart checks passed; remaining
production gates are open.

The isolated CPS/CIT path uses the canonical control/reservation databases and
normal service-authenticated APIs. No MIG, device reset, driver/module update,
or manual Pod creation was used for the notebook workloads.

## Verified in this run

- Both neutral accounts and central workspace registrations were created by their
  owning Source services. Fresh group storage was provisioned through the normal
  API, with NAS permission evidence and both PV/PVC pairs observed Bound.
- The storage Gateway permits provisioning only, for exactly the two reviewed
  source/workspace/group targets. Actual-service-account admission checks accepted
  four intended dry-run objects and rejected 26 altered objects. No dry-run object
  persisted. The temporary parent PV admission exception was restored afterward.
- Both Hubs run the owner-scoped adapter image
  `sha256:6dd145ada0670c2217f5ef89bba35bf88252a74a0dbc1e09c76a79a269e45c5d`.
  TLS from each Hub to the isolated Gateway and active storage/owner bindings passed.
- Normal Source-console service requests started both named servers. The node
  controller automatically programmed, read back and sealed 5120 MiB per cgroup;
  each notebook became Ready. PyTorch reported exactly 5368709120 usable bytes.
- CPS rejected a 6442450944-byte CUDA allocation and subsequently executed CUDA
  successfully. Concurrent CIT CUDA completed 100 checks over 25 seconds.
- CIT normal Hub Stop returned HTTP 204; its Pod disappeared and the controller
  published `cleanup-confirmed`. CPS executed CUDA successfully during that stop.
- CIT restarted through the same normal API with new Pod UID
  `5be16447-a9ce-4b9d-b7df-387c78a769fd`, a fresh sealed 5120 MiB allocation,
  successful CUDA and an unchanged saved-file SHA-256.
- Final normal stops returned HTTP 204 for both workspaces. Both Pods were absent,
  all three allocation records were `released`, both member reservations were
  inactive, and all three journals were terminal `retired-inert-cap`. These inert
  records were preserved, not erased through a GPU reset.

The two first-start Pod UIDs were
`aa72af7b-66a4-4235-b53e-6ec686decf99` (CIT) and
`c0faef49-9fc7-4573-83af-fe3b957fb5a9` (CPS).

## Runtime integration findings

The host's k3s `data/current` is an absolute symlink. Under a `/host` mount,
`/host/var/lib/rancher/k3s/data/current/bin/crictl` does not resolve to the host
binary. This run selected and tested the actual versioned host path instead:
`/host/var/lib/rancher/k3s/data/65415f7708224bbfc7865f032e84da4a5123a3acebef70c8ee40fa991aa68555/bin/crictl`.
Production deployment must resolve and verify its own current version; this hash
is evidence for this host, not a portable default.

The node image also requires the host driver's read-only `usr/bin` directory on
PATH for `nvidia-smi`. This run used `/host/run/nvidia/driver/usr/bin` and the
separately mounted NVML library, without adding the whole driver library directory
to LD_LIBRARY_PATH. CRI version and both GPU UUID/driver queries passed.

The journal context currently wraps nested OS errors as a journal-lock error.
Error-chain diagnosis distinguished the missing binaries from lock permissions.
A transient stop-time error was followed by successful cleanup on reconciliation;
its exact cause has not been established and must not be represented as a lock
failure or ignored as a passed robustness test.

## Remaining acceptance

- Membership removal, access revocation and cross-Hub reservation conflicts.
- Persist and qualify runtime-tool discovery in the deployment configuration.
- 20 GiB, memory import, MPS, broader packing/scheduling and all remaining original
  production/recovery/release gates. The two 5 GiB results do not close those gates.

Private evidence is held under the operator lifecycle preflight directory:
`normal-hub-two5-oom-peer-recovery.actual.private.json`,
`cit-first-normal-start-cuda-storage.actual.private.json`,
`cit-first-normal-hub-stop.actual.private.json`,
`node-stop-cleanup-diagnostic.actual.private.json`,
`cit-normal-restart-cuda-storage.actual.private.json`,
`post-stop-gpu-ledger-all-released.actual.private.json`,
`post-stop-member-reservations.actual.private.json`, and
`fresh-storage-bindings-verified.actual.private.json`.
Credentials and raw Secret captures are deliberately excluded from Git.

## Follow-up: runtime tools and delayed release

The generated launcher now resolves and preflights the host tools before loading
SDK code or opening native GPU authority (cluster commit `63e7eeb`). Its generated
SHA-256 is `9a87e66de29627a97fb6d780a0d6090a959b1ee3843346d4b34bf96b9ed384b3`.
The materialized launcher passed read-only host checks and a further normal CIT
Start/CUDA/Stop cycle without operator PATH or versioned-CRI arguments. The
qualification suite passed 251 tests plus 118 subtests.

This fourth Pod was `a1c17154-9ea2-44e2-a07a-d582059ceca8`. Expanded error logging
did not reproduce the earlier cleanup OS error; that finding remains unresolved.
It did establish a separate automatic-release failure: the Hub finalizer abandoned
its attempt after 30 seconds, before the controller's later cleanup confirmation.
The ledger stayed `releasing` until an explicit retry of the normal release API.
After that proof-backed retry all four test allocations were released and test
Pods were absent. No release was forced without cleanup evidence.

Compute commit `4ffe956` fixes the deadline failure by retaining one deduplicated
finalizer task across bounded polling windows and keeping its original generation
fences. Request/stop-future errors remain held. 102 focused compatibility and
lifecycle tests passed, including late confirmation, new-generation protection,
failed stop futures and request timeouts; independent source review was clear.
The Hub fix is now deployed and live-qualified as recorded below.

At that stage the fresh CIT group had an empty Hub roster and no native Share. It was
a fixture awaiting the normal console assignment/sharing flow, not evidence
that student collaboration permissions have passed. This needs qualification
before promoting the new workspace path.

Additional private evidence: `node-runtime-tools-readonly.actual.private.json`,
`cit-tool-fixed-launcher-cuda.actual.private.json`,
`node-stop-race-controller.private.log`,
`cit-current-native-shares.actual.private.json`, and
`tool-fixed-post-stop-ledger-all-released.actual.private.json`.


## Delayed cleanup retry: live qualification passed

Both Hubs now run the source-verified Hub-only image
`ghcr.io/mul-cps/cps-compute@sha256:b3cd140fb9cb57f5746152389dfc46e9de97220ae364b1b39aa9d7d6af5470d3`.
Its Hub wheel SHA-256 is
`7dee65777e6d7095a5346536eda35d75cc460fcdf5f1d36683639b820c795694`
(source `4ffe956`). Image checks preserved all 136 other distributions, SDK
module bytes, runtime configuration and base layers. An in-image Python 3.12.14
probe verified delayed retry and transport-timeout handling. Both actual Hub
processes expose the exact reviewed module bytes.

The normal CIT service started a further 5 GiB workspace, observed it Ready in
the Hub API and successfully executed CUDA. For this stop, the owned test node
poller was deliberately stopped between iterations after sealing the allocation.
The Pod was then stopped through the normal Hub API. For over 102 seconds without
cleanup confirmation, the allocation stayed `releasing` and its member
reservation remained active; three Hub retry-window messages were observed.

After restarting the bounded node controller, cleanup was confirmed and the Hub
released the allocation automatically. No operator release API call was made.
Gateway access logs identify the successful release request as originating from
the actual CIT Hub Pod. The member reservation became inactive. A PostgreSQL
transaction explicitly set read-only verified that the stopped Hub row persisted
null attempt, workspace, profile and native state.

The resumed node controller completed all 30 iterations with exit code zero.
All five test allocation records are now released and test Pods are absent.
The earlier transient cleanup OS error was not reproduced in this delayed test;
this result closes the 30-second finalizer abandonment defect, not its separate
diagnostic finding. Collaboration roster/Shares, cross-Hub conflict and the
remaining original production gates remain open.

Private evidence: `delayed-cleanup-held-past-window.actual.private.json`,
`delayed-cleanup-member-hold.actual.private.json`,
`delayed-cleanup-automatic-native-release.actual.private.json`,
`delayed-cleanup-hub-origin-release-proof.actual.private.json`,
`delayed-cleanup-member-auto-release.actual.private.json`,
`delayed-cleanup-hub-persisted-state-readonly.actual.private.json`, and
`node-finalizer-delayed-cleanup-resume.private.log`.

## Console service roster, Shares and removal qualification

On 2026-10-22 the installed CIT console application service was invoked with its
actual provider/database, owning Hub credential and verified administrator actor,
using the isolated lifecycle147 gateway with its verified TLS CA. The running
browser console's production endpoint was not changed. This qualifies the normal
application service methods, not browser OAuth, RTC or assignment UI interaction.

The fresh local group and two expiring memberships were created through validated,
audited provider operations; `WorkspaceService.create` accepted the matching
central canonical identities. The stopped qualification course ceiling was set
to 5 GiB and its exact fresh owner/server binding appended; the old workspace and
expired memberships were retained. The first normal service Start exposed a real
repeat-provision defect: Kubernetes admission rejects CREATE on the existing PV
before the API can return AlreadyExists. An actual service-account server-side
dry run confirmed the parent-PV policy rejection.

Compute commit `ad260820cc0355de4168b2417afca96cbe5baf25` reads and validates existing
PV/PVC bindings before creating missing ones. Only a 404 permits creation; a
concurrent create conflict is read back and validated. Foreign bindings and
forbidden reads remain rejected. Six focused regression scenarios pass; the
storage regression set passed 184 tests. Existing creation-only test doubles were
changed to return the Kubernetes missing-object response on reads.

The isolated gateway now runs
`ghcr.io/mul-cps/cps-compute@sha256:9a9a99bdc2963b6dfbb99176ee68f309133fc4ec1eb4f033d0cbaa6a95ff8edf`.
Wheel SHA-256:
`aa72417b0a15d76c74b801a1976506fa403e12c07c36cd831302d86e954cc0f3`.
Image verification confirmed exactly one SDK module changed (`storage.py`),
other distribution files/metadata were unchanged, and runtime UID remained 10001.
Registry manifest/config digests were independently verified. Only the isolated
Deployment image field changed under UID/resource-version/full-spec comparisons.

Normal service Start then completed with both students in the actual Hub group.
The native group Share granted only the exact server's `access:servers` scope.
Read-only PostgreSQL transactions using JupyterHub's installed scope resolver
confirmed both non-admin users had access without server lifecycle or sharing
administration. Pod UID: `bb026eab-d1b8-468b-9420-934b0f394433`.

Normal `remove_member` stopped the workspace and retained the reconciliation
barrier while native cleanup was pending. The node controller emitted one transient
wrapped cleanup OS error, then confirmed cleanup on a later iteration; this is a
reproduction of the separate diagnostic finding, not evidence that it is fixed.
The Hub automatically released the reservation. Retrying the same normal removal
operation completed the membership/group update and cleared the barrier.
The removed student's effective server access disappeared; the survivor retained
only the exact shared-server access. No direct group/Share mutation was used to
substitute for the service flow.

The survivor's normal service restart revalidated the one-member allowance,
returned Running with Pod UID `16902be7-7cf0-42a2-ba88-f23ee4aaf51b`, and exposed
5368709120 CUDA bytes. The preserved workspace file still matched SHA-256
`771626f9e2fc708860f25296af05e3f3aa69756351099ff6a6216d5fd6ebae2e`.
Normal service Stop completed. All seven lifecycle allocations are released,
test notebook Pods are absent, and the protected running user Pod UID is unchanged.
The finite controller was deliberately interrupted only after cleanup (exit 130);
the final read-only inventory preflight passed. No controller loop remains running.

Repository-wide pytest collection was blocked by missing `oauthenticator` in the
local test environment. A broader SDK test run was interrupted after 345 seconds:
748 tests passed and `test_upstream_71_patience_messages_are_preserved` failed
because the installed KubeSpawner module lacks the expected `time` attribute.
That same failure was reproduced on the unchanged `d00390b` base. These runs do
not constitute a green full-suite gate.

Still open: actual browser/OAuth/RTC visitor flows; assignment/group allocation;
cross-Hub canonical-person conflicts and rollback; automatic console completion
or clear retry UX for pending cleanup; review of duplicated group roster fields;
the separate transient cleanup diagnostic; and all remaining original production
gates. This result does not activate the production GPU approval gates.

Private evidence: `cit-console-local-records-prepare.actual.private.jsonl`,
`cit-console147-normal-start-after-storage-fix.actual.private.jsonl`,
`cit-console147-remove-member.actual.private.jsonl`,
`cit-console147-resume-removal.actual.private.jsonl`,
`cit-console147-effective-access-after-removal.actual.private.jsonl`,
`cit-console147-survivor-restart.actual.private.jsonl`,
`cit-console147-normal-close.actual.private.jsonl`,
`console147-final-all-released.actual.private.json`,
`node-console-sharing-after-storage-fix.private.log`, and
`storage-read-before-create/registry-verification.private.json`.

## Cross-Hub member conflict and rollback: live service qualification passed

The normal CPS console service now has its fresh lifecycle147 group, audited local
memberships and owned course binding. Its roster contains the existing QA person
and the reviewed CPS alias of the CIT test person; no username/email matching was
used. The two CPS canonical members are ordered so the uncontested member is
processed before the shared member. Both Source service methods use their actual
local database and Hub credentials against the same isolated TLS gateway and
shared canonical reservation database. Browser/OAuth interaction is not covered.

The two normal Start calls were issued 1.153 milliseconds apart. CIT acquired the
shared member and reached Running. CPS received a durable `reservation_conflict`
audit record, returned its local workspace to stopped and created no notebook Pod.
Read-only SQLite inspection proved that only the CIT member/binding existed:
CPS's earlier uncontested member was rolled back, and CPS's failure cleanup did
not release the CIT member. The persisted conflict contains the exact two-member
CPS payload and attempt, rather than an unrelated authorization failure.
CIT winner Pod UID: `6ec77c18-b292-4130-8aa7-9e6f2ac05075`.

After normal CIT Stop and confirmed release, normal CPS Start reached Running
with both members reserved. A subsequent normal CIT Start was denied with its
own durable reservation-conflict audit record. The CPS binding and both member
reservations remained intact; CIT had no binding or notebook Pod. A CUDA operation
in the surviving CPS notebook passed after the denial and still reported
5368709120 bytes. Its pre-existing workspace marker checksum was unchanged.
CPS winner Pod UID: `25845393-1c06-4b0d-be55-2002a19bb973`.

An additional bounded CPS grant for the shared person was written through the
owning policy API, expiring at the original pilot deadline. With grants from both
consoles, the single-person policy preview still reported 5 GiB pooled allowance,
not 10 GiB. This grant also prepares separately entitled CPU/batch profiles for
future independence tests; those actual launches have not yet been qualified.

Normal CPS Stop completed. All nine accumulated native allocation records are
released. Both test notebook Pods, both workspace reservation bindings and the
test members' reservation rows are absent. The final read-only native inventory
preflight passed. The finite diagnostic controller was deliberately interrupted
only after cleanup with PID/start-time verification (exit 130); no loop remains.
Its additional exception-cause logging did not reproduce the transient cleanup
error on this required CPS stop, so that separate diagnostic finding stays open.

The final protected-user check found its Pod absent. Hub logs attribute this to
an authenticated `muslim` request: successful
`204 DELETE /hub/api/users/muslim/server (muslim@193.170.30.58)` at
2026-10-22T20:31:29 UTC. Kubernetes records the matching notebook stop event on
GPU1 for the original protected UID. No recreation was attempted. This supersedes
the earlier statement that this Pod was still Running; it does not indicate a
test-controller cleanup of that Pod.

This closes the bounded normal-service cross-Hub conflict, rollback and recovery
scenarios. It does not activate production GPU gates or qualify personal CPU and
batch independence, stale callback races beyond existing coverage, browser/RTC,
assignments, broader scheduling/packing, recovery or the other original gates.

Private evidence: `cps-console147-prepare-race.actual.private.jsonl`,
`cross-hub147-race-cps.actual.private.jsonl`,
`cross-hub147-race-cit.actual.private.jsonl`,
`cross-hub147-race-atomic-rollback.actual.private.json`,
`cross-hub147-reverse-cps-start.actual.private.jsonl`,
`cross-hub147-reverse-cit-denied.actual.private.jsonl`,
`cross-hub147-reverse-conflict.actual.private.json`,
`cross-hub147-cps-cuda-after-conflict.actual.private.json`,
`cross-hub147-duplicate-grants.actual.private.json`,
`cross-hub147-close-cit.actual.private.jsonl`,
`cross-hub147-close-cps.actual.private.jsonl`,
`cross-hub147-final-all-released.actual.private.json`,
`cross-hub147-protected-user-own-stop.actual.private.log`, and
`cross-hub147-receipt.actual.private.json`.

## Student CPU/batch independence and HTTP access revocation

A CPS non-admin qualification user's real Hub API token authenticated as canonical
person `386feebb-df1a-4f3c-9ef9-6d9c026d5aea`. Short-lived test tokens inherited
existing roles only; no roles, authentication state or refresh policy were altered.
A bounded local project and project grant were created through validated/audited
application/provider and owning policy APIs. All four temporary tokens were revoked
and their private plaintext files removed after testing.

Ordinary batch used the unchanged production gateway image
`sha256:5f1dd4f55710f1cdf97d24a1165b265681c61c67578680b8f5ef8bd67a34fc3c`
and policy hash
`sha256:332d14fb9e510b9810feffb8d40b408743f9679ebd13ca1ba0e1077d666e9281`.
The isolated native gateway remains excluded from Argo ingress by network policy:
its workload-list request fails, whereas production access with its configured
CA works. No network policy, credential, deployment image or production GPU gate
was weakened to route batch through the isolated gateway.

While the same person was reserved in the running CPS shared 5 GiB GPU workspace,
the student requested a personal `cpu-default` server through their own Hub API.
The observed Pod requested 2 CPUs, 8 GiB and no GPU. The first cold-image trial
exceeded the fixed 180-second test budget and was normally stopped; it is retained
as a failed trial. Events show attachment in about 14 seconds, followed by a
158.373-second pull of the 10,475,847,925-byte notebook image
`sha256:a2159bf12d79069ab7eae9075a95dfeaf95e2c7980103701eea595745967bba1`.
The unchanged retry used the same profile and 180-second budget, reached Ready in
39.294 seconds, and was normally stopped. Both trials scheduled on GPU3. The warm
image check took 118 milliseconds. This is one warm startup observation, not a
burst/p95 qualification; cold-image coverage and pre-pulling still need work.

Independently, the student's production `/v1/workflows` request ran an approved
2-CPU/8-GiB `batch-cpu` workflow while the GPU member reservation stayed held.
Workflow `cps-ca43da85c75ecae68021912975100988094cbb40a4c5d438`, UID
`6531d382-161b-4c93-917b-bd7acc2432de`, reached Succeeded in 29 seconds and its
personal log endpoint returned the unique marker. Repeated submissions returned
the same UID and the personal list contained one copy. The warm CPU test later
inspected that same completed workflow; it did not execute another batch run.
Read-only reservation checks and the GPU workspace's audit interval show no
release during the successful CPU case. The completed workflow is retained under
normal lifecycle policy, with no active orphan batch job.

Actual shared-server HTTP authorization was checked with two existing non-admin
CPS users, using tokens issued before the membership change. Both authenticated
as themselves and received 200 from the shared server's protected Contents API;
a request without credentials received 403. The normal console service then
removed `cpsgpumembera`, stopping the workspace and waiting for native cleanup
before completing removal. The normal service restarted with the remaining QA
member and revalidated its fixed profile. With the same still-authenticated
tokens, the removed user received 403 and the survivor received 200. This proves
server access revocation beyond a database-only scope inspection. It does not
prove browser OAuth cookies, RTC synchronization or the addon UI's full flow.
The same-origin addon service redirected the token-only probe to login, so that
probe is not counted as a browser authentication pass.

The synthetic CIT user's token did not provide a corresponding positive case:
its Hub row has no default user role or prior auth state, and CIT requires a
fresh login. The fixture must go through genuine directory authentication before
it can represent an authenticated CIT student. No role or auth-state bypass was
introduced to make the test pass.

After normal final Stop, all eleven accumulated native allocations are released;
all test notebook Pods are absent. The node loop completed its 180 iterations
but exited 1 because iteration 96 recorded one wrapped journal-lock cleanup
error for Pod `d06b0883-ff62-4c6b-8689-af69b422dfaf`; subsequent cleanup recovered.
This is not a clean controller qualification. Its underlying cause remains open.
The final read-only inventory/physical-retirement preflight passed. No controller
loop remains running and no driver, kernel, MIG or NFS address was changed.

The CPS fixture now contains only canonical QA member
`0949db38-7f66-4524-a3f4-cd38a3e6db69`; the CIT fixture retains
`386feebb-df1a-4f3c-9ef9-6d9c026d5aea`. Do not reuse the earlier two-member CPS
start guard without reconciling this deliberate membership removal.
Next priority is automatic unequal 5/20 GiB qualification with exception-cause
logging, not another repetition of the passed two5 lifecycle.

Private evidence is under `student-independence/`: `receipt.actual.private.json`,
`student-independence.actual.private.jsonl` (failed cold trial),
`student-independence-warm.actual.private.jsonl`,
`parallel-student-batch.actual.private.jsonl`,
`cpu-cold-and-warm-pod-events.actual.private.json`,
`gpu-reservation-after-batch.actual.private.json`,
`gpu-reservation-warm-interval-audit.actual.private.json`,
`visitor-http-before-removal.actual.private.json`,
`visitor-http-after-removal.actual.private.json`,
`remove-shared-member.actual.private.jsonl`,
`survivor-normal-start.actual.private.jsonl`,
`final-gpu-close.actual.private.jsonl`,
`all-eleven-allocations-released.actual.private.json`,
the four `*-token-revoked.actual.private.json` receipts, and
`node-controller.private.log`.

### Measured five/twenty wrapper preparation (not hardware qualification)

The node wrapper now accepts a separate operator-only V2 configuration with
exact 5/20 GiB profiles, a 25 GiB aggregate budget, two slots and the pinned
147 boot/driver epoch. The underlying closed configuration and measured-pool
validators still run first. Legacy two-5-GiB configuration remains separate.

Current inventory checks require each intent's cap and policy to match its
original protected enrollment and configured workspace. Legacy terminal entries
under a new policy require explicit original enrollment UID, payload hash,
binding and policy pins. Fresh cleanup publication reads them using their
original policy scope; the underlying terminal-history verifier still checks
published completion, released ledger and protected journal proofs. No history,
journal or receipt is deleted or synthesized by this change.

Verification: 206 tests passed in the native-fresh-unequal qualification directory,
including generated-runner packaging and rejection of altered history pins,
profile/cap mismatches, wrong mode, epoch or budget. This is source preparation:
the isolated gateway and node deployment have not yet been migrated to V2, and
no automatic 5/20 GiB hardware pass is claimed.

### Measured configuration and candidate gateway image

A read-only live capture found all eleven lifecycle allocations released, all
corresponding protected journals `retired-inert-cap`, and the selected GPU with
40960 MiB total / 40471 MiB free on driver 615.71.09. A private, non-applied V2
proposal was validated with the SDK operator qualification factory and original
node configuration validator. It contains eleven explicit history pins and a
5/20 GiB pair under policy
`sha256:abb8ce7430087ca7a73e812a4d21a1a3777650b14540e226949d5c3081e18897`.
The proposed roster/course/grants and node configuration are not yet applied.
Fresh authenticated node-side history and physical partition checks remain
required; local structural validation is not that proof.

Gateway SDK revision `4ba8c8daa78f8c978c8ec747b1efea3574e294ac` was built into
`ghcr.io/mul-cps/cps-compute@sha256:2701165c10ed941016ad110bf02195de41ef000cd58efc111cb569ac611889d9`.
Wheel SHA256: `c71281d30adf51906627094987049a6240df98ceaae1da0f220aebf556c606c5`.
Build verification found all 79 SDK modules exact, only
`native_qualification.py` changed, and all 43 other distributions unchanged.
Dependency checks and unprivileged runtime admission smoke passed.
The digest was verified against the registry and deployed only to
`cps-compute/native-lifecycle147-gateway` with resourceVersion/image preconditions.
Rollout completed; the running module hash was
`26b9008db5e2902a9d03b678b1f553a2f81fa4b58b7ec79c8413474cca81378f`
and UID 10001. The runtime configuration remains the legacy five-GiB pilot.
Neither production gateway nor production GPU access was changed. No automatic
five/twenty hardware qualification is claimed by this image rollout.

### Measured-mode live preflight and isolated runtime activation

The expired, terminal owned node helper was replaced with a UID-preconditioned
DELETE and a bounded inert helper using immutable ConfigMap
`native-lifecycle147-measured-90d12bde934d782f`. Generated agent SHA256:
`2e52d1c63b8b3f35b2322936a68abf456992239fe0626691cd69662213d1f2a1`.
No controller loop was launched. A real node-side preflight used the original
authenticated enrollment reader, protected journal/mirror, completion and ledger
validators, followed by the complete physical-inventory guard. All eleven
historical enrollments and twelve prior physical retirement rows passed. All
nine installed SDK source pins and current CDI verified. Native SET and Pod
DELETE were explicitly forbidden in this preflight.

The isolated gateway was then switched from `nativeGpuPilot` to the separate
`nativeGpuQualification` mode using new immutable policy/runtime objects and
resourceVersion/old-reference tests. Rollout succeeded. Running policy hash
`sha256:abb8ce7430087ca7a73e812a4d21a1a3777650b14540e226949d5c3081e18897`
and caps 5120/20480 MiB were verified from the running container. Both profiles
remain disabled for ordinary access. The production gateway is unchanged.
Hub settings/policy and controlled QA course/roster/grants have not yet migrated;
normal Source Start, CUDA measurements and terminal cleanup of the measured pair
remain pending. This is not a hardware pass or production approval.

### First measured starts: reproduced blockers and corrections

Both Hub owner overlays and controlled console fixtures were migrated through the
installed applications. CPS uses four reviewed QA canonical members and a 20 GiB
ceiling; CIT uses one reviewed QA member and a 5 GiB ceiling. Grants and local
memberships expire after two hours. Profile changes used the normal audited
`WorkspaceService.change_profile` path with stopped-writer and reservation checks.

The first starts failed before notebook Pod creation: CPS's exact approval list
had noncanonical member ordering; CIT's Hub reverse lookup used dictionary value
equality, selecting the equal but unauthorized legacy five-GiB alias. CPS roster
ordering was corrected without changing member identities. Hub revision
`6dc240b547fc5239c3518c40ca04f6323c697218` changes lookup to catalog object identity;
the reproducer failed before the fix and 88 focused tests passed afterward.
The Hub-only wheel `f44b202a270156455614769e91d87ccd3fbb6fc252de86998d901c8bac800588`
was packaged as
`ghcr.io/mul-cps/cps-compute@sha256:f8495d31d663a1662b5153ca60c18040a4192651f35da08244e46fd9b607399b`.
All 20 Hub modules matched, only `hub.py` changed, all 136 other distributions
and the preserved SDK were unchanged. Registry digest and both Hub rollouts
verified; the alias regression also passed inside the running CIT Hub.

A subsequent start created both Pods but exposed two remaining legacy wrapper
assumptions: active reconciliation excludes pinned historical intents, and the
physical partition checker still required two five-GiB caps and a ten-GiB budget.
Revision `c10818b` restores explicitly pinned finite historical intents to physical
accounting and validates exact five/twenty caps under a maximum 25 GiB aggregate
budget. It preserves all original retirement rows and per-inode cap checks.
Regressions failed before these changes; all 208 qualification directory tests
then passed. Generated source
`ed6aa0e16a6d57c796a774694503ba490e43f5889c535c94b8abdc3c2ea8432b`
passed fresh node-side read-only history/CDI/physical-inventory checks with both
new enrolled Pods present. The failed diagnostic controller was stopped using
its exact PID/start-time identity, its exit 130 verified, and the corrected
bounded diagnostic controller started without replacing the node helper Pod.

CIT Pod `cfe205e5-96fe-4f7c-83d9-74743fec724f` completed normal Start and passed CUDA:
a 6 GiB allocation was rejected under its 5 GiB cap, and the same process
continued using its original 512 MiB tensor. CPS Pod
`d20d0668-c605-4d8f-a2a3-1d4b86b905d1` had an original sealed journal with
21474836480-byte soft/hard readback, but the console deadline elapsed during the
wrapper corrections and normal rollback stopped it. The attempted CPS CUDA exec
therefore returned Pod NotFound and is NOT a pass. Normal console Close completed
with inactive pooled reservation. A fresh normal CPS Start was requested only
after that cleanup; its result and the twenty-GiB CUDA test remain to be recorded.

### Automatic measured pair CUDA result and confirmed cleanup

Fresh CPS Pod `2f2a98a8-dfc5-415b-bd1d-39c3b6c8d344` completed normal console
Start under the corrected implementation while CIT's five-GiB workspace remained
running. In CPS, CUDA successfully allocated and touched 18 GiB, then released
that probe before requesting 21 GiB. The 21 GiB allocation was rejected and the
same process continued operating on its original 512 MiB tensor. Device count
was one. Concurrently CIT held a tensor and completed 200 checked GPU updates.
This establishes automatic unequal five/twenty provisioning and this bounded
CUDA over-cap/recovery/peer case on image 542 with the pinned 147 epoch; it is
not a pass for all production gates or all allocation/import/MPS paths.

Both workspaces were stopped through normal console Close. CIT completed;
CPS exceeded the console cleanup wait and required normal Stop retries. During
Pod disappearance, one conservative identity-stability check reported
`Replacement identity changed across original terminal proof`; it retained
protection and the next stable observation completed cleanup. All fourteen
allocations were subsequently verified released, both console workspaces stopped
with inactive pooled reservations, and both notebook Pods absent. No manual
reservation release or journal/receipt deletion was used. Only after that ledger
verification was the identified diagnostic controller interrupted (observed exit
130). Its earlier recovered blocked observation remains in the log; this is not
claimed as a clean finite 300-iteration controller pass. Final read-only original
history/CDI/physical-inventory preflight passed with native SET and Pod DELETE
forbidden.

The diagnostic helper was CPU throttled: `cpu.max=50000 100000`, 4302 throttled
periods of 5217 and 69034526 throttled microseconds at capture, with `kubectl top`
showing 501m CPU. Subsequent diagnostic runs should request adequate CPU after
confirming all allocations released; do not change live GPU/user limits to
shorten verification. Current-image ten-GiB/restart/import/MPS coverage and
ordinary qualified-group activation remain separate unfinished work. Production
access and qualification flags remain unchanged.

### Subsequent evidence reconciliation and diagnostic CPU allocation

The retained five/ten MPS/import measurements were audited against actual raw
probes, preflight imageIDs/boot/generation/caps, kernel witness capture hashes and
cleanup measurements. See `CLOSURE-147.md` and
`results/current-image-component-reconciliation-20261022.json` for the 29-file
hash index and exact coverage boundaries. These cases are measured component
passes, not wholly untested gaps; they are not silently relabeled as an
ordinary qualified-group production release or general cross-parent MPS proof.

After all fourteen allocations were again verified released and absence of any
stdin controller process was checked, only the inert diagnostic helper was
replaced with UID-preconditioned deletion. Its new immutable code ConfigMap is
`native-lifecycle147-measured-4713545c88394119`, still generated source
`ed6aa0e16a6d57c796a774694503ba490e43f5889c535c94b8abdc3c2ea8432b`.
New helper Pod UID: `cb2bc9c9-27a9-4344-933e-9f8fde5fe9e1`. CPU request/limit
are now 1/2 cores instead of 100m/500m; memory, authority, mounts and bounded inert
main remain unchanged. The node has 48 allocatable cores. No user workload,
GPU limit, driver or kernel was changed. The helper became Ready and its new
node-side read-only history/CDI/full-inventory preflight passed with native SET
and Pod DELETE forbidden. No controller loop or workload was launched.

### Automatic ten-GiB integration completed

Revision `6e2d2b435232c9453e6fc254829f54fbd0c617d3` adds a bounded five/ten
operator pair and exact measured terminal-history support while preserving the
previous five/twenty case. Regressions failed before implementation; 236 tests
and 82 subtests passed. All fourteen original released enrollments, including
their prior twenty-GiB caps, were captured with original enrollment/completion/
ledger/journal pins. A new immutable helper configuration with generated source
`cd64be430bd7b072af4e2de8a9087abf5b197a7154aed727c88a62f3aa157271`
passed read-only original-history, CDI and full-inventory preflight. Only then
were isolated gateway and exact neutral-owner Hub overlays migrated to policy
`sha256:5c900f6503991d1c9514b028be71939f29bb30c0423f6b5de59214ac47675d92`.
Both Hub rollouts succeeded. The stopped controlled CPS fixture was changed to
two reviewed members and ten GiB through audited local provider operations and
normal `change_profile`; CIT retained one member and five GiB. Ordinary profiles
remain disabled.

Normal Starts succeeded for CPS Pod `a4e98e0f-172e-456c-8f91-792c1f971286` and CIT
Pod `3564bf8f-8558-4bf8-9d11-7e757a461c13`. Request-to-Pod-ready observations were
90.696 and 55.689 seconds respectively, not a burst/p95 qualification. Both
workspace marker hashes matched their earlier five/twenty lifecycle records.
CPS allocated/touched eight GiB, freed that probe, rejected eleven GiB under its
ten-GiB cap, and recovered in the same process. CIT completed 200 concurrent
checked GPU updates. Actual imageIDs and init exits were captured separately.

CIT normal Close completed; CPS exceeded the console cleanup wait and a normal
Stop retry completed after trusted cleanup. All sixteen allocations were then
verified released and both console workspaces stopped with inactive pooled
reservations. No manual release was used. The diagnostic log contained no
blocked-error observations. After release verification, only the identified
controller was interrupted (observed exit 130), and final read-only complete
history/CDI/inventory checks passed. This closes automatic five/ten/twenty sizing
integration across the two measured runs; ordinary qualified-group promotion,
cleanup latency and broader production acceptance remain open. The checked
artifact index is `results/automatic-five-ten-147-20261023.json`.

### Read-only cleanup cost and nested-read guard candidate

With all sixteen allocations released, a native-SET/Pod-DELETE-forbidden
preflight instrumented the unchanged live helper. One complete inventory guard
made 338 authenticated API calls and took 2.042 seconds (1.278 process CPU
seconds); 282 protected file reads took 0.026 seconds. Timings are nested,
inclusive observations and must not be added together. This identifies guard
cost, not a complete explanation or resolution of the console cleanup timeout.
See `results/cleanup-readonly-guard-profile-20261023.json`.

The wrapper previously repeated the full guard for nested read-only backend
calls inside an already guarded read action. A candidate scopes only those
nested reads to the current synchronous backend action using ContextVar.
Every top-level operation still performs a fresh complete check. `read_limit`
is explicitly treated as mutating because it can bootstrap native state;
`set_limit`, `seal_gate`, `revoke_gate` and their nested observation sequences
retain fresh checks. Cleanup publication's separate fresh guard is unchanged.
The candidate uses no cross-operation inventory/authority cache. Regressions
cover late foreign inventory before mutations, bootstrap classification,
exception reset and concurrent threads. 296 tests and 211 subtests passed,
including original full-inventory, cleanup and emergency-stop cases. This
candidate is not yet deployed and no live cleanup speedup is claimed. Ordinary
qualified-group activation remains the next primary integration step.

### Current-epoch bounded qualification and actual SDK compatibility blocker

Live inspection found production `nativeGpuGroups.enabled=true`, qualified
five/ten profiles and notebook image 542 already declared under policy 332.
Effective access remains readiness-held: the installed qualification pins boot
`209f8bc9-a478-48e4-925a-6e07ffa56f7a` and generation
`b10498fc-9153-4394-875a-ea7cfb498625`, not the current attested epoch. The production
node and observer deployments are paused at zero replicas. The old production
ledger has 197 released records; the separate lifecycle ledger has 16 released.
No live claim was discarded or rewritten.

Checked actual cap-assignment, both-direction OOM/aggregate, import, bounded MPS,
and normal restart/cleanup artifacts were composed into a current-epoch bounded
five/ten qualification record, retaining explicit component scope differences
and no production-readiness claim. Current free memory was measured again; the
pool stays two slots with 15360 MiB budget and 1024 MiB extra headroom. Immutable
ConfigMap `cps-native147-qualification-6a129169a6afef2d` was created in
`cps-native-system`, actual UID `4de5b8de-e18d-4275-9421-7629efb165aa`,
resourceVersion `380259107`, data SHA256
`613e8f9554ee222b362002fab6c107be819455e9cccd5c62a9433083cea710f6`.
The actual API-bound qualification and deployment factories accepted it. No
runtime consumer reference was changed; object creation did not activate access.

Testing the same actual object inside installed packages exposed a concrete
software mismatch: the node SDK accepted it, while gateway and both Hubs rejected
its current core/UVM/health fingerprints. Their metadata modules match SDK2f13
exactly. Bridge revision `221906b` changes only those two SDK metadata modules
on the 2f13 baseline. It recognizes the current measured build; historical v3
readback is limited to the exact old immutable qualification reference/data hash.
Unknown/mixed builds and self-reissued historical proofs remain denied; legacy
v1/v2 checks are unchanged. Actual new qualification validation and the actual
old qualification's complete policy-transition chain both passed with the bridge.
271 regressions passed, plus the final four bridge tests. Full-suite collection
still fails for missing `oauthenticator` in `test_login_guard.py`; no full-suite
pass is claimed. The bridge is pushed but not packaged/deployed yet. Coordinated
Node/gateway/Hub/publisher/observer adoption, genuine readiness acknowledgments
and normal qualified-group lifecycle tests remain pending. See
`results/current-epoch-qualification-renewal-20261023.json`.

### Qualification metadata bridge deployed on preserved component baselines

The Hub SDK wheel from `221906b` built successfully on the actual SDK2f13 Hub
baseline. The first Gateway build refused to overwrite ten newer installed SDK
modules: live Gateway is Source53b7174, not SDK2f13. The bridge was cherry-picked
onto that exact baseline as `dbf52dbf8d750dbcaf151578c377261205979ec9`;
272 qualification/policy/node-config regressions passed. Its wheel changes the
same two metadata modules while preserving those ten fixes. The failed initial
build remains retained; it made no deployment change.

Both published images passed exact 78-module wheel/RECORD checks and dependency
checks. All 136 non-target Hub distributions, including the Hub extension, and
43 non-target Gateway distributions were unchanged. With networking disabled,
both images validated the actual historical qualification/policy-transition
chain and new actual current-epoch record under their normal UIDs 1000/10001.
Registry digests were verified before UID/resourceVersion/image-guarded rollout:

- Hubs: `ghcr.io/mul-cps/cps-compute@sha256:837cbdb0400a3c23157c54fabc820d9fdc0b2345f4785bd241196896a84d2208`
- Gateway: `ghcr.io/mul-cps/cps-compute@sha256:0e11ec258e3e04eeb37512679b5059a189849b555fea2f882c70730cdad1fc0f`

Initial Gateway rescheduling to GPU4 hit Multi-Attach because isolated Gateway
still holds the shared canonical `compute-state` RWO PVC on GPU1. Gateway
unavailability caused both Hubs to retry startup with connection refused.
Production Gateway was then explicitly colocated on GPU1 using a guarded
nodeSelector patch. No force detach, volume address/export change or notebook
Pod patch was used. Gateway rollout completed and both Hubs recovered to Ready.
Keep this placement while both gateways share RWO state; reassess it when the
isolated gateway is retired rather than silently keeping a permanent GPU1
availability constraint. Future image rollout preflight must check shared RWO
attachment topology before rescheduling the control-plane services.

All three running packages now validate the actual current qualification record;
their unchanged historical configuration also loaded successfully on startup.
This removes the verified metadata compatibility blocker. Qualification/policy
references, grants, credentials, permissions and paused Node/Observer replicas
were not advanced. Genuine coordinated current-epoch acknowledgments and normal
qualified-group lifecycle remain pending; GPU access is still readiness-held.
See `results/driver-qualification-bridge-rollout-20261023.json`.

## Current-epoch adoption: production custody recovery prerequisite

A fresh read-only preflight confirms that the paused production node service still
uses `/run/cps-native-gpu`. Its required enrollment, intent, journal and completion
directories are absent on the current boot. The original ledger remains unchanged
in identity and contains 197 released records; the mounted immutable terminal index
inventories 82 records. The SDK verifies original private bytes in addition to API
records, so neither a qualification-reference swap nor a released ledger alone
proves safe service resumption. No historical receipts were reconstructed.

This is separate from the passed current-boot CUDA tests and the deployed reader
compatibility bridge. The previously staged `cps-native-runtime` authority and
durable `/var/lib/cps-native-gpu/domains/.../custody` path must be evaluated as the
explicit successor rather than creating another staging path. Activation needs
reviewed predecessor preservation and current physical retirement accounting,
followed by genuine component acknowledgments. The old ledger must stay intact.

Evidence: `results/production-custody-renewal-preflight-20261023.json`.

### Durable successor: predecessor preserved, offline codec checked

The existing offline disaster-loss proposal codec (`b4fb0ea`) passed all 72
focused tests in the project virtual environment. It checks proposal consistency
and explicitly provides no activation authorization. The initial base-Python run
failed because Kubernetes dependencies were absent; no implementation change or
weakened assertion was needed.

The staged runtime namespace now holds an immutable capture of the original
197-record released ledger. The original UID, resourceVersion and exact data
remained unchanged across capture. This is a predecessor preimage, not substituted
private custody or a terminal acceptance. No new ledger or writer was created.
The capture reference was verified with the SDK immutable ConfigMap parser; its
data hash covers the complete data map, separately from the raw payload hash.

Fresh read-only host queries confirm the same qualified kernel/boot/generation;
both GPUs reported zero used memory and no compute applications. These are
instantaneous NVML observations, not a full cap-table/device-holder attestation.
The current qualification's exact immutable reference passed SDK validation.

Evidence: `results/predecessor-ledger-preservation-20261023.json` and
`results/durable-successor-preparation-20261023.json`.

### Current physical retirement accounting passed

Two fresh read-only host snapshots accounted for all 28 current selected-GPU cap
entries using original durable journals: 27 finite `retired-inert-cap` records and
one `cleanup-offline-unlimited` record. The SDK parsed each original CapRecord and
validated its current physical inventory proof. All entries were offline and zero
charge, all recorded Pod UIDs were absent from the current API list, and there were
no unmatched cap entries. This closes the earlier instantaneous-NVML-only evidence
gap for these snapshots.

The device holder scan found one PID with nine NVIDIA device descriptors; separate
executable observation identified root-owned `/usr/bin/nvidia-persistenced`. No
node-service or MPS-server candidate was found. One process-exit race occurred in
each scan, with no permission errors; this is not a continuous writer-exclusion
claim. The physical and exclusion checks must be repeated immediately before
activation. No cap write, device reset, driver change or historical reconstruction
was performed.

Evidence: `results/successor-physical-accounting-20261023.json`. Full original
journals and the collector remain private; public evidence contains counts and
the capture digest only. The old 197-row ledger is still preserved separately.

### Durable successor authority objects staged and SDK-validated

The existing `cps-native-runtime` namespace now contains an exact copy of the
current measured qualification proof, an authority-local deployment document, a
fresh empty allocation ledger and its immutable empty terminal index. Actual API
identities passed the SDK qualification, deployment, ledger and terminal-index
readers. The copied hardware proof is unchanged; this does not broaden its two-slot
5/10 GiB qualification or add 20 GiB ordinary access.

The new empty ledger is a distinct authority with UID
`89c1c55e-31e8-4af8-a3c0-306a86142f48`. It does not replace or import the historical
ledger: all 197 released predecessor records remain byte-for-byte unchanged at
the original UID/resourceVersion and have the separately pinned immutable capture.
Lost private receipts have not been reconstructed or represented as accepted
terminal history. Root-created staging objects alone do not authorize activation.

No consumers were switched and no writer started. Remaining work includes binding
predecessor preservation and current physical accounting into the reviewed
successor handover, packaged node/controller configuration with durable state,
least-privilege permissions, genuine readiness and ordinary Start/Stop checks.

Evidence: `results/durable-successor-deployment-staged-20261023.json` and
`results/durable-successor-ledger-staged-20261023.json`.

### Packaged successor controller and dynamic configuration staged

Created the successor ServiceAccount and a zero-replica Recreate Deployment,
using the previously validated Node image `9d998baa...` and the durable authority
state directory. The original production controller was untouched. All four
component declarations use actual current Deployment and ServiceAccount UIDs and
image digests. Four new dynamic initial approval heads, immutable anchors and
empty acknowledgment targets were created without changing consumers or granting
RBAC. Their generation-zero registry approves no workspaces.

The SDK loaded the actual immutable version4 NodeConfiguration and all four
HeadSnapshots successfully. Its CDI/runtime pins were taken from the passed
5/10 GiB lifecycle run and independently checked against every current CDI
provider and four runtime files. This corrects stale original pins that named
`management.nvidia.com-native-pilot-r615.json`; the tested current provider is
`cps-native-selected-147.json`. No host files were changed.

The actual bootstrap input now binds the reviewed configuration and policy with
`release=false`. Approval and anchor volumes bind actual staged objects. Three
host runtime binary hashes embedded in the packaged initializer were independently
verified. Replicas remain zero and no successor Pods exist.

The namespace still enforces restricted Pod Security. Its warnings correctly
identify the trusted node controller's required host privileges; no namespace
exception has been enabled. Least-privilege RBAC, narrow trusted host-access
admission, private authority bootstrap, observer/consumer adoption and genuine
readiness remain prerequisites to activation. Empty acknowledgments are not
qualification or readiness evidence.

Evidence: `results/durable-node-controller-staged-20261023.json`,
`results/durable-successor-node-config-staged-20261023.json` and
`results/durable-successor-bootstrap-held-20261023.json`.

### Successor read-only RBAC applied and authorization checked

Applied four namespaced read Roles/bindings and one single-node ClusterRole/binding
for the new stopped node principal. Current component Deployment and ServiceAccount
reads are name-scoped; cross-namespace ConfigMap reads include only the staged
heads, anchors, approval documents and acknowledgment targets. Authority-local
ConfigMap listing supports complete custody inventory. Node GET is limited to
`k3s-wk-gpu2`. No historical object-name lists were copied.

43 live SubjectAccessReviews used the exact service-account username and standard
service-account/authenticated groups. All 14 intended reads were allowed and all
29 negative cases denied, including Pod create/delete, ConfigMap create/ACK patch,
Secrets, Roles, another node, node patch, foreign-namespace listing, Pod exec and
ServiceAccount token creation. Exec/token checks used explicit SAR subresource
fields. These are authorization results, not admission or runtime qualification.

No Pod was created, bootstrap remains held, and all mutation permissions required
for service operation remain deliberately absent until their admission rules are
in place. Evidence and applied manifests are in
`results/durable-successor-read-rbac-20261023.json` and
`results/durable-successor-read-rbac-manifests-20261023.json`.

### Narrow trusted controller Pod admission and real held-image preflight

Installed a fail-closed ValidatingAdmissionPolicy scoped only to
`cps-native-runtime`, bound to the actual current ReplicaSet UID and approved node
Pod template. The dedicated namespace's PSA enforcement is now privileged, with
restricted audit/warnings retained; the custom policy is installed before that
change and constrains images, commands, environment, security fields, host paths,
credentials projection, physical node and ancestry. No general host-access
exception was added to either Hub namespace.

18 server dry-runs passed: the intended Pod was accepted and 17 modified Pods
were denied by the policy. In addition to image/command/owner/mount cases, these
include health-probe command injection, init privilege escalation and extra GPU
resources. The exec-probe case first demonstrated a real gap in the initial policy
and was denied after hardening. CEL type-checking reports no warnings. CEL resource
field checks use dynamic access because this server's static type view omits
quantity-map members; altered CPU/memory/GPU cases validate those checks live.

The controller now uses an explicit standard-path projected API token/CA/namespace
volume with automatic mounting disabled. Its pulling credential was copied
namespace-locally without disclosure. One actual Pod reached the running packaged
initializer with no restarts and `release=false`; the node main did not start.
The actual Node image loaded the complete successor configuration using exact
Root-supplied current API objects, without live API calls or private authority
initialization. The held Pod was then normally stopped and replicas are zero.

This proves admission and held-image integration, not native writer readiness.
Guarded mutation permissions, private authority bootstrap, consumer/observer
adoption, genuine acknowledgments and ordinary group lifecycle remain pending.
Evidence: `results/durable-node-pod-admission-20261023.json`, its manifests, and
`results/durable-node-held-image-preflight-20261023.json`.

### Guarded writes and genuine successor Node readiness passed

Added successor-specific fail-closed admission for immutable completion CREATEs
and exact own-ACK updates before granting ConfigMap CREATE and own-target PATCH.
No ledger PATCH, enrollment publication, foreign ACK PATCH, Pod creation/deletion
or Secret privileges were granted to the node principal. These are provider/wire
constraints; SDK custody and physical verification remain required for acceptance.

15 direct service-account server dry-runs passed. Cleanup wire and clearing the
own ACK were accepted; enrollment/ledger/arbitrary creation, altered completion
forms, foreign component data, metadata injection and ledger/foreign ACK patches
were denied. Fixtures were never persisted. All four initial empty acknowledgment
ConfigMaps were corrected from absent data to `ack.json: {}` without changing
UIDs; the real publisher's preimage validator accepted each.

An authentication issue was caught by the negative tests: Rancher's proxy ignored
`kubectl --as` and retained the administrator identity. Those initial attempts
were rejected as evidence. Final tests used a verified actual node-service-account
identity against Kubernetes via temporary loopback-only SSH forwarding, with TLS
CA/server-name checks and a ten-minute token bound to a temporary Secret. The
binding and private kubeconfig were deleted and forwarding terminated afterward.
The earlier 43 SubjectAccessReviews are unaffected: their identities were explicit
in request bodies, not delegated through impersonation.

Released the bootstrap after verifying the new ledger, enrollment set and initial
approval set were empty and the old writer remained stopped. The packaged service
is now running on the durable state root. Two separately refreshed readiness
receipts passed SDK head/process/driver-epoch validation and authenticated both
custody and pending-generation annotations. Renewal was observed with zero
restarts. The current ledger has zero records; no workspace is yet approved.
The original 197-record ledger retains its exact UID/resourceVersion.

Gateway/Hub configuration and observer adoption, genuine four-component readiness
and ordinary group Start/Stop remain pending. Node readiness is not a claim of
production readiness or active user GPU access.

Evidence: `results/durable-node-guarded-writes-20261023.json`, its manifests and
`results/durable-successor-genuine-node-readiness-20261023.json`.

### Authority-scoped registry implementation and actual database-copy rehearsal

SDK commit `88cbf365559c454ad9fba5403bcd7ab8575f4742` adds an explicit,
validated authority namespace to the approval registry, runtime and read-only
capture/export paths. Defaults retain legacy behavior. The new authority starts
with no approvals; normal audited Source operations must approve workspaces.
Grants, workspaces, audit and global reservations retain their existing storage.

A fresh read-only online backup of the actual Gateway control database was tested
on a private copy. All six existing tables and 6,002 rows retained identical
schema/row digests. Exactly two new tables were created, and the initial revision
matched all four staged heads. Scoped read-only export passed. No live database
was changed. Independent review found no blocking issues; 220 focused tests pass.
Fifteen legacy transport-migration tests fail while constructing their old fixture
on both this change and the untouched baseline; they are not reported as passing.

The source is published; replacement images and coordinated Gateway/Hub adoption
are still pending. This rehearsal does not activate workspace approvals.
Evidence: `results/authority-scoped-registry-rehearsal-20261023.json`.

The reviewed wheel and both immutable Gateway/capture images are now built and
published. Each image was checked against its own live-container package baseline:
78 SDK modules match the wheel and all 43 other distributions retain identical
owned files/metadata. Dependency checks and nonroot, read-only, networkless import
smokes passed. Published registry digests were independently checked. Deployment
remains pending coordinated consumer configuration and readiness validation.
Image evidence: `results/authority-scoped-registry-images-20261023.json`.

### Scoped-registry images deployed with existing configuration

Gateway and approval capture now run the published scoped-registry images. The
rollout completed with both containers ready, zero restarts and runtime UID
10001. All 78 installed SDK module digests match the reviewed wheel. Comparing
Deployment specs proves only the two container images changed; all mounts,
credentials, runtime settings and authority references were retained. All three
GPU ledgers had no active allocations before rollout.

An immutable service-image successor Node configuration was staged and loaded
through the SDK, linking its exact predecessor and changing only Gateway's image
declaration. It is not activated. Gateway/Hub authority adoption, genuine
four-component readiness and ordinary group lifecycle remain pending.
Evidence: `results/authority-scoped-registry-image-rollout-20261023.json`.

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

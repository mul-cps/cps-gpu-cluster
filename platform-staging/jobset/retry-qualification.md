# JobSet retry and cleanup qualification

This gate exercises the deployed JobSet 0.12.0 controller and KAI with the
`cps-compute` launcher at `5771df5e3db86a59b20fcf965cc3ce273df0c503`.
It uses two 250m CPU / 128Mi workers per attempt, no GPU requests, the pinned
compute image, restricted Pod Security, disabled service-account token mounts,
and a deny-all ingress/egress NetworkPolicy.

The operator fixture creates a unique namespace, its own admission parameters,
and clones the live workload policy and binding. Both namespace selectors and
the dedicated-namespace match condition are redirected to the fixture. The
production policy, parameters, catalog and distributed qualification flag are
unchanged. A negative automatic-token server dry-run must be denied by the
fixture policy before any worker runs; a valid generated Pod must pass.

Failure injection shortens only an observed, UID-owned child Job's active
deadline. It selects a running, non-terminating Pod whose JobSet restart-attempt
matches the current parent status. Resource-version and UID preconditions protect
the patch. This tests controller failure recovery; it does not simulate a
checkpointable training application's own failure or restore a checkpoint.

Both live scenarios passed on 2026-10-06; see [retry-report.json](retry-report.json).
The 24 targeted launcher/lifecycle tests also passed, including regression
coverage for late KAI PodGroup recreation. Application source and the pinned
image remain unchanged; the regression commit only adds a test.

The two scenarios are:

- One injected failure: both replacement workers complete, with one restart.
- Repeated failures: the parent reaches Failed after two permitted restarts.

Each scenario also checks submission idempotency, cross-owner read denial,
launcher termination plus periodic cleanup sweeps, absence of child
Jobs/Pods/KAI PodGroups, and retention of
the suspended parent as an idempotency tombstone. Finally, the fixture admission
policy/binding and namespace are deleted. These are operator SDK checks, not an
authenticated user HTTP acceptance test.

Private operator evidence and the executable fixture are under
`cps-platform-evidence/2026-10-06/jobset-retry/`. The report records exact parent
states, restart counts, injected child UIDs and cleanup assertions. Failed
fixture setup attempts ran no workers; an initial exhaustion attempt exposed a
fixture race selecting a terminating Pod from the previous restart, corrected
by the attempt/deletion checks above. A further attempt omitted the periodic
cleanup sweep and observed KAI recreate a UID-owned PodGroup after termination.
The corrected fixture includes the existing sweep, which retries child cleanup
while retaining the tombstone. Production defaults to a 60-second sweep; the
fixture invokes it during observation, so this does not establish a production
cleanup latency bound. Termination acknowledges a request, rather than promising
that all resources are already absent.

The controller's default Recreate strategy and bounded `maxRestarts` behavior
are documented in the official [failure policy guide](https://jobset.sigs.k8s.io/docs/tasks/failure_policy/).

Remaining gates: actual four/eight-GPU collective communication, checkpoint
restore across attempts, real gateway authorization, concurrent scheduling and
retry cleanup under those GPU workloads. This CPU test does not qualify GPU
profiles or enable distributed production access.

# Source maintenance executor scaffold

`source_maintenance.maintenance_pod` copies the actual CPS Source configuration,
environment, trust and existing PVC bindings from the reviewed dbaad531 consumer.
It uses the original Source node so the existing RWO volume is not moved. The
new label does not select the ordinary console Service. It serves no HTTP port,
has no probes or lifecycle callbacks, and starts only a one-hour sleep. It runs
as10001 with a readonly root filesystem, no host namespace/path mounts and no
capabilities. Only an empty control directory is writable in addition to the
original application data mount. No application/provider/database is opened by
its command or by the module-closure validation.

The dedicated service account initially has no added RoleBindings. Actual
in-cluster SelfSubjectAccessReview using its own mounted token denied Deployment
patch, Pod create, Secret get and Pod exec. Administrator-context `--as` checks
returned misleading yes answers; they are not used as service-account evidence.
SDK exec transport is installed in the existing image, avoiding a new kubectl
binary or another application image build. Scoped reader permissions and genuine
application callbacks still need wiring before this scaffold may be armed.

`verify_freeze` is a pure verifier of fresh API observations, not a scale-down or
network-isolation implementation. It checks both original Deployment UIDs and
complete specs with only replicas changed to zero, an unpaginated actual PodList,
absence of original/in-flight consoles and every other live/terminating writer
of either database PVC. Fully terminated completed containers may remain as
history; uncertain status fails. The exact operator must occur once and its full
spec hash must match the protected review. Its runtime/entrypoint/security are
also checked. Root's separate active authorization/start-exclusion and exclusive
service-token-custody review binds the exact current Gateway Pod/policy and pair
contract, with expiry600seconds. No static config or fabricated boolean is live
evidence. All observations and the review are trusted Root inputs; never expose
this function as a browser accepting caller-supplied Pod or freeze assertions.
Only after the verifier succeeds may the genuine application factory open the
existing SQLite provider. Existing strict Source migration guards remain in use.

15 tests cover the restricted idle spec, positive frozen snapshots and refusal
for active/changed frontends, old console Pods, foreign or terminating PVC
writers, pagination, changed operator image/host settings/environment, mismatched
Gateway binding and absent/stale Root review. Actual preparation created only a
UID-recorded idle Pod, helper ConfigMap and unbound service account. It verified
all16 image modules and the SDK transport while both consoles stayed Ready1/1.
The full pilot suite passed804 tests plus851 subtests (14 skipped).

This is preparation. No freeze, database migration, policy rollout, GPU Start or
hardware qualification occurred. The idle Pod has a one-hour active deadline;
Root must inspect its live UID/state before reuse and clean only recorded owned
resources when done. Never restart a possibly still-running operation solely
because an observation timed out.

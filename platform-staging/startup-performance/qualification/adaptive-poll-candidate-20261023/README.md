# Pending Node reconciliation candidate — 23 October 2026

The 184.86-second baseline includes a registered-snapshot refresh followed by
a successful 37.11-second Prepare. Enrollment publication accounts for 22.51
seconds across two nested steps. Context checks account for 9.97 seconds within
the same request; nested spans must not be summed. The final execution fence
opened 24.79 seconds into Prepare and completed Binding after another 18.46.
Unused per-user PVC creation is already disabled for shared workspaces.

Source `7486ea8` changes only the Node daemon's successful pending-work cadence:
awaiting registration, placement or first gate polls again after at most one
second. An explicitly shorter interval stays shorter. Idle and sealed work
retain the configured interval; error backoff, retry budget, snapshot checks,
readiness withdrawal and driver/seal authorization are unchanged.

Real pending-service fixtures first failed on the old five-second delay. All
109 focused Node service and pending-group tests now pass, including return to
normal cadence after sealing and no premature CRI/CDI/driver activation.
The complete repository suite is running; its result is not yet known.

The Node image is published with a verified registry digest and source/wheel
labels. Its installed service matches the source; protected driver-manifest,
kernel, driver-health source and current policy graph preflight pass.
The image is not deployed. Startup improvement and API/CPU cost remain unproven
until a controlled comparison. Snapshot identities are still checked afresh;
this change does not cache authorization.

The full suite subsequently finished with 5178 passed and one failure in
post-CAS grant withdrawal. A deterministic test reproduced the ordering gap:
permissions could be revoked during external approval/ledger observations after
the preceding local grant read. Source `e837d76` ends the final acquisition
observation with another current local Source/permission check. Two regression
boundaries and the focused acquisition/authorization/pooling suites pass
(111 tests). A new full suite is running against that source.

This polling-only candidate was never deployed. Its eight inactive configuration
objects were deleted with UID preconditions after verifying all deployed
specifications remained unchanged. The next candidate must include the grant
check correction as well as the polling change.

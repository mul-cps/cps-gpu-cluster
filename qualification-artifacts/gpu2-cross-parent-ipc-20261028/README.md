# GPU2 second-card cross-parent IPC measurement

Both directions of the missing CUDA IPC case passed on 28 October 2026, using
one fresh, controlled 5/10 GiB pair on the second A100. Each cross-parent import
returned `CUDA_ERROR_NOT_PERMITTED` (800), correlated to the exact importer PID
lifetime and a kernel status 27/reason 6/client-kind 4 denial. The same exported
handle succeeded inside its owning parent. Exporter kernel continuity, recovery,
importer survival and unchanged native authority checks passed.

The adjacent receipts and summary pin the actual trials, capture hashes, tuple
and raw receipt bytes. Full kernel captures, source closures, attribution and
before/after host observations remain in the private qualification directory;
they are not published as general cluster logs.

The original controller set and sealed both caps but failed its post-reconcile
empty-accounting assertion. The failing instantaneous inventory was not saved;
a startup-charge race is plausible, not proven. The original failed result was
retained. An independent read-only continuation verified the original protected
journals, seals, exact actual Pod/CRI/epoch identities and current empty charges
without rerunning cap assignment. Actual preflight then passed.

Two harness attempts were inconclusive before the marked import: the first
Root exec transport did not enter the host UTS namespace; the second lacked the
required protected sessions directory. Both failed attempts were retained and
their endpoints proved absent before retry. The passing third attempt retained
the original witness checks and used the host UTS namespace plus a root-owned
0700 sessions directory. No driver, kernel, device mode or cap threshold changed.

Cleanup UID-deleted only the two owned QA Pods, proved process/cgroup absence,
and retired both original records through the existing controller. All twelve
retained rows are offline, pinned and charged zero; both GPU2 cards have no
compute clients and the QA namespace is empty. Aditya, Gottam, Muslim and Rino
retain their original Pod UIDs with zero restarts.

This closes the bounded cross-parent IPC measurement gap for this tuple. It
does not promote fleet-wide production qualification, complete scheduling or
cross-Hub acceptance, or deploy the pending two-device placement implementation.
Receipt qualification flags remain unchanged.

# Retention runtime qualification — 23 October 2026

The current released Gateway image also runs the unchanged mounted retention
controller successfully. It conditionally expired only the failed cross-Hub QA
notebook's two disposable artifacts with a per-call 91-day test clock. Real-clock
reconciliation preserved both beforehand. The current image separately preserved
the existing explicitly retained successful output under the same aged clock,
with no mutation methods exposed in that read-only retained-object test.

The values overlay enables qualified reconciliation and conditional deletion,
initially suspended for full-template validation. It must be combined with the
owning deployment's policy/image/OAuth values; it is not a standalone deployment.
The default chart remains disabled and unqualified. Prior active-input, owner
retain/foreign denial, ambiguity, conditional conflict and identity fencing
receipts remain linked from the current-state and qualification records.

Missing Argo proof continues to preserve data and fail the run visibly; the
seven historical proof failures are not authorization for orphan deletion.

## Full-template activation result

The aligned current-image, current-policy full-template real-clock run reconciled
45 objects and conditionally expired one eligible snapshot. It reported 42 errors.
A separate read-only diagnostic with write methods suppressed classified these
as 28 missing-workflow HTTP 404s and 14 unmanaged key formats. The unmanaged-key
bug was reproduced by four regression cases and fixed in `f0a8773`: objects
outside the fixed notebook-artifact schema are now skipped before any read,
reconciliation or proof lookup. All 21 tests and eight subtests pass.

A new immutable corrected controller ConfigMap was selected with a resourceVersion
and exact-spec compare-and-swap while suspended. Its actual full-template run
reconciled 44 objects, skipped the 14 unmanaged objects, made no deletions, and
reported only the 28 remaining missing-workflow proof errors. These objects are
preserved; the schedule remains suspended pending reviewed legacy/orphan handling.
The qualified mutation configuration is prepared and exercised, not automatically
scheduled. No missing-proof error was ignored or converted into deletion authority.

# Pooled-budget gateway candidate — 23 October 2026

Source `8bdacc4395300e445e4bb9170e664f6c98dba4c9` corrects qualified
member budget pooling independently of the selected shared-workspace profile.
Seven regression cases pass inside the built gateway image with networking
disabled, real SQLite and the installed package. These are synthetic CPU
contract tests, not new GPU or cross-Hub hardware qualification.

The installed package also validates the current protected driver manifest and
kernel, matches the deployed driver-health source and loads the current policy
configuration graph. The registry digest and source/wheel labels were verified.

The complete repository suite passed: 5173 tests and 68 subtests, with 6 skipped
and 593 warnings. The gateway candidate is now deployed; this is not a production
release. All four service templates and current component acknowledgments were
verified. The normal writer is Ready. Its sixth rotation preserves the original
anchor and all five predecessors, with no pending transition. Both maintenance
Pods were deleted with UID preconditions.

Admission dry-runs caught a handover-helper assumption that an image uniquely
identifies the successor Node ReplicaSet. The unchanged Node image also matched
the predecessor. Selection now includes the exact new bootstrap reference; the
approved Pod passes, while wrong bootstrap, wrong owner and extra host mount
requests fail. No incorrect Node Pod was launched.

The Node image, policy, driver, kernel, GPU mode and storage paths were preserved.
Live pooled-workspace acceptance and startup improvement remain unproven. See
the machine-readable activation, software, admission, rotation and cleanup receipts.

# Pooled-budget gateway candidate — 23 October 2026

Source `8bdacc4395300e445e4bb9170e664f6c98dba4c9` corrects qualified
member budget pooling independently of the selected shared-workspace profile.
Seven regression cases pass inside the built gateway image with networking
disabled, real SQLite and the installed package. These are synthetic CPU
contract tests, not new GPU or cross-Hub hardware qualification.

The installed package also validates the current protected driver manifest and
kernel, matches the deployed driver-health source and loads the current policy
configuration graph. The registry digest and source/wheel labels were verified.

The complete repository suite is still running. This candidate is published,
not deployed or released for production. The read-only rollout capture found
five preserved journal rotations, no pending transition, and unchanged policy.
No controller, driver, kernel, GPU mode, storage path or research notebook was
changed. See the three machine-readable receipts in this directory.

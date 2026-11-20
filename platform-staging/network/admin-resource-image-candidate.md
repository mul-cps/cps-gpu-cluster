# Admin console with bounded-verifier SDK candidate — 2026-10-07

Admin source cdbc1d7 is rebuilt with the same 6bb6a57 compute wheel as the latest gateway candidate. The wheel SHA-256 is `05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`. All 42 installed admin modules and 21 compute modules match source. The runtime is UID/GID 10001, pip check passes, and the installed Hub 5.5.2 / RBAC 0.3.0 dependency with reviewed RBAC commit 4683d1a remains verified. The explicit JobSet route allowlist and frontend hashes match the previous qualified admin build.

Network-disabled installed-image tests pass: 58 tests plus four subtests, with one existing Tornado warning. The first collection lacked the verifier fixture; adding test-only fixtures allowed the complete run. Application source was not overlaid into the runtime. The test container exited zero and was removed.

The immutable image reference is in the adjacent JSON. Its OCI index and child manifests were independently rehashed against local build metadata. SPDX and SLSA v1 subjects bind to the Linux manifest. Builder dependency resolution used network access; the final runtime installs offline from the resolved wheelhouse.

Private evidence: 2026-10-07 `admin-resource-image/{build.log,metadata.json,image.tar,verify-oci.py,verify-installed.py,image-verification.json,installed-tests-verified.log,push.log,remote-index.json,report.json}`.

This is a published, undeployed qualification candidate. The matching notebook matrix, full authenticated integration, browser and remaining acceptance gates are incomplete. Neither production console was changed.

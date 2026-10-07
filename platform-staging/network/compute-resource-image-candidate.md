# Compute resource-bounded verifier candidate — 2026-10-07

Compute source 6bb6a57 was built into a new wheel and immutable gateway image. All 21 installed modules and five addon assets match current source by SHA-256. All 267 tests pass against the installed wheel outside the source checkout; the network-disabled gateway runtime passes pip check as UID 10001. The wheel SHA-256 is `05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`.

The candidate's exact image reference is in the adjacent JSON. Remote OCI index and both child manifest digests match local metadata. SPDX and SLSA v1 subjects bind to the Linux manifest; OCI index/manifests/config and attestation blobs were checksum verified. Container dependency installation used network access with constrained versions; this is not an offline gateway build.

The shared notebook wheelhouse was separately updated, replacing exactly one of 146 wheel files. Both Python 3.12 and 3.13 installed all 133 package versions offline with required hashes, passed dependency consistency/native imports and matched the 21 modules/five addon assets. The notebook release runner still passes 14 tests.

Private evidence is in 2026-10-07 `compute-6bb6a57-wheel`, `compute-6bb6a57-image` and `notebook-shared-wheelhouse-6bb6a57`. Earlier ecca902 candidates remain unchanged; they do not contain this later storage fix.

This is a published qualification candidate, not a production release or deployment. Matching admin and all notebook image builds, authenticated controller/gateway integration and the remaining full acceptance gates are incomplete.

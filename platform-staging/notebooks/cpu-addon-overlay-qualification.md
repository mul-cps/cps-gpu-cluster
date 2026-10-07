# CPU notebook addon overlay qualification — 2026-10-07

An offline overlay of the shared 146-wheel, 133-version wheelhouse onto the pinned standard CPU candidate passed package installation, pip dependency checks, compute/RTC imports and prebuilt addon presence. BuildKit completed successfully; runtime UID remains 1000.

Parent: `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:4dfb654d8f01f1b0818664ffa8a431afd53165deb08c4758b4a37d2907b4175c`. The compute wheel is the ecca902 candidate recorded in the shared wheelhouse qualification.

The first unnamed export produced empty in-toto subjects and was rejected. Re-exporting with an explicit registry name produced SPDX and SLSA v1 subjects matching the Linux manifest. The attestation JSON blobs and OCI index/manifests/config were checksum verified. Notebook revision `9f5d0a867b7ba0ce0e063ecca0038426888fd1b9` fixes both BuildKit and buildx exports; 14 release tests pass. Export naming does not publish the image.

Private evidence: `notebook-addon-standard-cpu/{inputs.json,build.log,named-build.log,metadata.json,image.tar,verify.py,report.json}` in the 2026-10-07 operator evidence directory. Digests are in the adjacent JSON report.

This is compatibility qualification against one existing parent, not a production release. No image was published or deployed. Notebook execution from this image, live browser behavior, all twelve variants from one tagged source, GPU isolation and production acceptance remain pending.

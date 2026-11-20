# CPU notebook addon overlay qualification — 2026-10-07

The corrected standard CPU overlay installs the complete shared 146-wheel, 133-version wheelhouse offline. All 21 installed compute modules and all five prebuilt addon assets match the ecca902 source candidate by SHA-256. Dependency checks pass; the runtime remains UID 1000.

Parent: `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:4dfb654d8f01f1b0818664ffa8a431afd53165deb08c4758b4a37d2907b4175c`. The new image digest and Linux manifest are in the adjacent JSON report.

Network-disabled runtime tests as UID 1000 executed fresh Papermill kernels with bool/int/float/string parameters, preserved the immutable input and retained the executed notebook after an intentional ValueError. Both successful and failed notebooks were inspected; the test container exited zero and was removed.

Two earlier exports were rejected. The first unnamed export had empty in-toto subjects. The next named export correctly bound attestations, but pip retained old SDK/addon content because both versions were 0.1.0. Version/import checks alone missed this. Source hashing exposed six module and three addon asset mismatches. Notebook revision `b95c700a12229ff1435d986e4722b80e39290a0f` forces reinstall from locked, hashed wheels; its 14 release tests pass. The corrected image has no mismatches. SPDX and SLSA v1 subjects match the Linux manifest; index, manifests, config and attestation JSON blobs were rehashed.

Private evidence: `notebook-addon-standard-cpu/{initial-report.json,initial-hash-check.log,fixed-build.log,metadata.json,image.tar,verify.py,hash-check.py,fixed-hash-check.log,fixed-runtime,report.json}` under the 2026-10-07 operator evidence directory.

This proves one existing CPU parent's compatibility with the requested compute candidate. It does not qualify all twelve variants from a common tag, GPU isolation, browser behavior, gateway-to-notebook execution or production release. No production workload/image was changed.

The corrected qualification candidate was published at `ghcr.io/mul-cps/cps-jupyter-notebook:qualification-addon-ecca902-cpu@sha256:8da5ec7bd43f791c677b44f42f9f16c5261cdf3834b5d7e3fed3b7782acb8fc6`. The remote OCI index and both child manifests were independently rehashed and match local build metadata. It was not deployed.

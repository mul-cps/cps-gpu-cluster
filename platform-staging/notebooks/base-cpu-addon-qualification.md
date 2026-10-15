# Base CPU addon qualification — 2026-10-07

The b95c700 offline overlay with forced installation of the shared 146-wheel wheelhouse passed against the existing base CPU image pinned at `ghcr.io/mul-cps/cps-jupyter-notebook-base-cpu@sha256:d5cfee0c5f8051406c6cfb976fa7fa28c1587513764699b52005a9684ba4fa8f`.

All 21 installed SDK modules and five addon assets match the ecca902 source candidate. Dependency checks, compute/RTC imports and prebuilt addon presence passed. SPDX and SLSA v1 subjects bind to the Linux manifest; OCI index/manifests/config and attestation JSON blobs were rehashed. Digests are recorded in the adjacent JSON.

With networking disabled as UID 1000, fresh Papermill kernels passed bool/int/float/string parameters, preserved the immutable input, executed successfully and retained an executed notebook after an intentional ValueError. The harness exited zero; its container was removed. Runtime Python is 3.13.13, JupyterLab 4.5.7 and RTC 4.4.1.

Private evidence: 2026-10-07 `notebook-addon-base-cpu/{inputs.json,build.log,metadata.json,image.tar,verify.py,hash-check.log,runtime,report.json}`.

This is existing-parent compatibility qualification only. The image is local, unpublished and undeployed. The common-tag twelve-variant release, gateway submission flow, browser and GPU gates remain incomplete.

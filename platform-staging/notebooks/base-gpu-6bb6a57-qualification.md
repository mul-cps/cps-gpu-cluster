# Base GPU notebook candidate compatibility — 2026-10-07

The existing immutable base GPU parent at `ghcr.io/mul-cps/cps-jupyter-notebook-base-gpu@sha256:7672b3b4c8efa60bb41e6b614254c7cf834e77033690c94c4844feef83835966` now consumes the same 6bb6a57 compute wheel as the gateway/admin/CPU candidates, checksum `05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`. Forced offline wheelhouse installation and dependency checks pass. All 21 installed compute modules and five addon assets match source hashes.

As UID 1000 with networking disabled and no GPU devices supplied, fresh Papermill kernels passed typed parameters, immutable input, successful execution and retention of the executed notebook after an intentional ValueError. The test container exited zero and was removed. Python 3.13.14, JupyterLab 4.5.7 and RTC 4.4.1 were recorded. This is notebook CPU execution inside a GPU-capable image, not GPU execution or isolation qualification.

OCI index/manifests/config and attestation JSON blobs were rehashed; SPDX and SLSA v1 subjects bind to the Linux manifest. Exact digests are in the adjacent JSON. Build output was streamed directly to the existing NFS scratch mount; no cluster storage address/configuration changed. Source evidence is `/mnt/cps_scratch1_tmp/bjoern/cps-platform-builds/2026-10-07/notebook-base-gpu-6bb6a57/`.

Image publication is in progress and remote verification remains pending. Nothing was deployed. Common-tag construction for all twelve variants, GPU execution/isolation, browser and full gateway notebook submission acceptance remain incomplete; GPU sharing stays disabled.

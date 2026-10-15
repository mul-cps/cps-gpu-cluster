# PyTorch runtime base compatibility — 2026-10-07

The immutable parent now consumes compute source 6bb6a57 and wheel checksum `05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`. Parent index and child manifests were independently rehashed. Forced offline installation and dependency checks passed; 21 SDK modules and five addon assets match both in the container and its fresh notebook kernel.

As UID 1000 with networking disabled and no GPU devices, Papermill passed typed parameters, immutable input, successful execution, intentional failure with retained executed notebook, and PyTorch CPU matrix multiplication. Recorded Python 3.13.12, PyTorch 2.10.0+cu128, JupyterLab 4.5.7 and RTC 4.4.1. This does not qualify CUDA execution or GPU isolation.

Publication and independent registry index/child digest verification passed. SPDX and SLSA provenance subjects bind the Linux manifest. Exact parent/image digests are in the adjacent JSON. Temporary GHCR-only authentication remained outside the build context and was removed from the host and builder. Private evidence: `/mnt/cps_scratch1_tmp/bjoern/cps-platform-builds/2026-10-07/notebook-pytorch-runtime-base-6bb6a57/`.

Nothing was deployed. Common source-tag construction, GPU and browser execution, authenticated gateway notebook submission and remaining platform acceptance gates are incomplete.

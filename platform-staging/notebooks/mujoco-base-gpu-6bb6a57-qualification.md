# MuJoCo base GPU parent compatibility — 2026-10-07

The minimal CUDA/PyTorch parent now consumes compute source 6bb6a57 and wheel checksum `05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`. Forced offline installation and dependency checks passed. All 21 SDK modules and five addon assets match in both the container and its fresh notebook kernel.

UID 1000, networking disabled and no GPU devices: Papermill passed typed parameters, immutable input, successful execution, intentional failure with retained executed notebook, and PyTorch CPU matrix multiplication. Recorded Python 3.13.12, JupyterLab 4.5.7 and RTC 4.4.1. The first harness incorrectly required MuJoCo in this minimal parent and failed; its harness, logs and executed notebook are retained. The source installs MuJoCo in the mujoco-xpra descendant. MuJoCo physics/rendering acceptance remains incomplete.

Publication and independent registry index/child manifest digest verification passed. SPDX and SLSA provenance subjects bind the Linux manifest. Exact digests are in the adjacent JSON. Registry authentication used a temporary GHCR-only configuration outside the build context; host and builder cleanup were verified. Private evidence: `/mnt/cps_scratch1_tmp/bjoern/cps-platform-builds/2026-10-07/notebook-mujoco-base-gpu-6bb6a57/`.

Nothing was deployed. This is parent compatibility evidence, not GPU execution, GPU isolation, browser acceptance or production release qualification.

# MuJoCo Xpra compatibility — 2026-10-07

The immutable MuJoCo desktop parent now consumes compute source 6bb6a57 and wheel checksum `05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`. Parent index and child manifests were independently rehashed. Forced offline installation and dependency checks passed; 21 SDK modules and five addon assets match both in the container and its fresh notebook kernel.

UID 1000, networking disabled, no GPU devices: Papermill passed typed parameters, immutable input, successful execution and intentional failure with retained executed notebook. MuJoCo advanced a free-body model for 100 timesteps; finite positions, elapsed simulated time and gravity-driven displacement were verified. Gymnasium import passed. Recorded MuJoCo 3.15.0, Gymnasium 1.4.0, Python 3.13.12, PyTorch 2.10.0+cu128, JupyterLab 4.5.7 and RTC 4.4.1. Desktop commands, the CPU wrapper fallback and denial of passwordless sudo also passed.

A separate owned container started an Xpra desktop on isolated loopback only. HTML returned HTTP 200; a live XFCE process and native server information were observed. Both test containers were removed. CPU physics and desktop server bootstrap are qualified at this scope; browser interaction, GPU/EGL rendering, isolation and Hub authentication remain separate gates.

Publication and independent registry index/child digest verification passed. SPDX and SLSA provenance subjects bind the Linux manifest. Temporary registry authentication stayed outside the build context and was removed. Private evidence: `/mnt/cps_scratch1_tmp/bjoern/cps-platform-builds/2026-10-07/notebook-mujoco-xpra-6bb6a57/`.

Nothing was deployed. Common source-tag construction and remaining platform acceptance gates stay open.

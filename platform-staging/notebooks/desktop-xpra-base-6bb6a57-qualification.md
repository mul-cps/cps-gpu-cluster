# Xpra desktop base compatibility — 2026-10-07

The immutable desktop parent now consumes compute source 6bb6a57 and wheel checksum `05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`. Parent index and child manifests were independently rehashed. Forced offline installation and dependency checks passed; 21 SDK modules and five addon assets match both in the container and its fresh notebook kernel.

UID 1000, networking disabled, no GPU devices: Papermill passed typed parameters, immutable input, successful execution, intentional failure with retained executed notebook and PyTorch CPU operations. Xpra, DBus and XFCE commands were present, Xpra CLI execution passed, the VirtualGL wrapper's CPU fallback passed, and passwordless sudo was denied. Recorded Python 3.13.12, PyTorch 2.10.0+cu128, JupyterLab 4.5.7, RTC 4.4.1 and jupyter-server-proxy 4.6.0.

A separate owned container started an Xpra desktop bound only to its isolated loopback interface. The HTML connection page returned HTTP 200; a live XFCE process and native Xpra server information were observed. The server was stopped and both test containers were removed. This follows the upstream [HTML5 usage boundary](https://github.com/Xpra-org/xpra-html5/blob/master/README.md), narrowed to loopback. It does not qualify browser interaction, WebSocket desktop streaming, GPU rendering or Hub authentication. Exact HTTP body checksum and scope are in the adjacent JSON.

Publication and independent registry index/child digest verification passed. SPDX and SLSA provenance subjects bind the Linux manifest. Temporary registry authentication remained outside the build context and was removed. Private evidence: `/mnt/cps_scratch1_tmp/bjoern/cps-platform-builds/2026-10-07/notebook-desktop-xpra-base-6bb6a57/`.

Nothing was deployed. Common source-tag construction and the remaining platform acceptance gates stay open.

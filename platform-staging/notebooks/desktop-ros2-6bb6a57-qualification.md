# ROS desktop compatibility — 2026-10-07

The immutable ROS desktop parent now consumes compute source 6bb6a57 and wheel checksum `05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`. Parent index and child manifests were independently rehashed. Forced offline installation and dependency checks passed; 21 SDK modules and five addon assets match both in the container and its fresh notebook kernel.

UID 1000, networking disabled, no GPU devices: Papermill passed typed parameters, immutable input, successful execution and intentional failure with retained executed notebook. PyTorch CPU execution passed. From the fresh kernel, the ROS Jazzy environment was sourced and `/usr/bin/python3` exchanged a std_msgs String between a local publisher and subscriber using Cyclone DDS. This validates the separate ROS interpreter; it does not claim that Conda's notebook interpreter directly imports rclpy. Recorded notebook Python 3.13.14, PyTorch 2.11.0+cu129, JupyterLab 4.5.7 and RTC 4.4.1.

Embedded SLSA provenance binds the Linux image manifest. The reviewed Syft executable generated full standalone SPDX and native inventories because the earlier ROS embedded attestations exceeded BuildKit's 80 MiB limit. The verifier bound inventory to the image configuration, checked 5,444 package entries and 161,546 file entries, and required the SDK, Hera, Papermill, RTC, PyTorch, ROS desktop/rclpy, XFCE, VirtualGL and TurboVNC packages. Neither inventory was reduced to fit the embedded limit.

Publication passed for the image and its SBOM referrer. The remote image index/children were rehashed, the referrer manifest subject matched the exact image index, and both downloaded inventory checksums matched local outputs. Exact image, referrer and inventory hashes are in the adjacent JSON. Temporary build authentication stayed outside the context and was removed. Private evidence: `/mnt/cps_scratch1_tmp/bjoern/cps-platform-builds/2026-10-07/notebook-desktop-ros2-6bb6a57/`.

Nothing was deployed. GPU execution, desktop/browser interaction, common source-tag construction and remaining platform acceptance gates stay open.

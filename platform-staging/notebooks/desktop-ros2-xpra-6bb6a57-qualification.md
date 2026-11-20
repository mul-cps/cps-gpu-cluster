# ROS Xpra compatibility — 2026-10-07

The immutable ROS Xpra parent consumes compute source 6bb6a57 and wheel checksum `05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`. Parent index and children were rehashed. Offline forced installation and dependency checks passed; 21 SDK modules and five addon assets matched in the image and fresh kernel.

UID 1000, networking disabled, no GPU devices: Papermill passed typed parameters, immutable input, success and intentional failure with the executed notebook retained. PyTorch CPU execution passed. ROS Jazzy pub/sub passed in the separate `/usr/bin/python3` interpreter invoked from the notebook kernel; this does not establish direct rclpy import in Conda. The isolated Xpra HTML endpoint returned HTTP 200, a live XFCE session was observed and native server information verified.

Reviewed Syft generated full SPDX and native inventories, bound to the image configuration: 5,522 packages and 165,802 file entries. Required coverage includes SDK, Hera, Papermill, RTC, PyTorch, ROS desktop/rclpy, XFCE, VirtualGL, Xpra server and HTML client. The initial verifier incorrectly required TurboVNC from the other ROS desktop variant; its failure is retained in private scan.log. The corrected verifier reused the complete inventories and checked Xpra packages without rescanning or reducing inventory.

Publication and remote verification passed for the image index/children and the SBOM referrer subject. Both downloaded inventories matched their local hashes. Exact immutable references and hashes are in the adjacent JSON. Temporary build credentials were outside the context and removed. Private evidence: `/mnt/cps_scratch1_tmp/bjoern/cps-platform-builds/2026-10-07/notebook-desktop-ros2-xpra-6bb6a57/`.

Nothing was deployed. GPU execution, browser interaction, model rendering, common source-tag construction and remaining platform acceptance gates remain open.

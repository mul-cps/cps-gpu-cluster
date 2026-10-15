# ComfyUI compatibility — 2026-10-07

The immutable startup-repaired ComfyUI parent consumes compute source 6bb6a57 and wheel checksum `05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`. Parent index and children were rehashed. Forced offline installation and dependency checks passed; 21 SDK modules and five addon assets matched in the image and fresh kernel.

UID 1000, networking disabled, no GPU devices: Papermill passed typed parameters, immutable input, successful execution and intentional failure with the executed notebook retained. PyTorch CPU execution passed. Recorded Python 3.13.14, PyTorch 2.11.0+cu129, JupyterLab 4.5.7 and RTC 4.4.1.

The isolated ComfyUI CPU server returned HTTP 200 for system statistics and 827 node definitions. Its input/output/temp/user directories and SQLite database were created beneath the selected user data directory. A real EmptyLatentImage → SaveLatent workflow completed; the saved tensor was finite, zero-filled and shaped [1,4,8,8]. This uses no downloaded models and does not qualify GPU model inference or browser interaction.

Embedded SLSA provenance binds the Linux image manifest. Reviewed Syft produced full SPDX and native inventories, bound to the exact image configuration: 5,043 package entries and 78,612 file entries. Required SDK, Hera, Papermill, RTC and PyTorch package coverage passed. The image index/children were rehashed remotely; the SBOM referrer subject matched the exact image index and both downloaded inventories matched local checksums. Exact references and hashes are in the adjacent JSON.

The startup script matches its reviewed repaired source. The bundled ComfyUI checkout revision and main-module checksum are recorded in the JSON. Temporary build credentials were outside the context and removed. Private evidence: `/mnt/cps_scratch1_tmp/bjoern/cps-platform-builds/2026-10-07/notebook-comfyui-6bb6a57/`. Nothing was deployed. GPU execution, model inference, browser interaction, common source-tag construction and all remaining platform acceptance/migration gates remain open.

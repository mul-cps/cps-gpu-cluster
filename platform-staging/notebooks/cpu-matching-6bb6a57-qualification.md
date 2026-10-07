# Matching CPU notebook candidates — 2026-10-07

Standard CPU and base CPU existing-parent overlays now use the same 6bb6a57 compute wheel as the updated gateway and admin candidates, SHA-256 `05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`. Both install the shared 146-wheel/133-version wheelhouse offline with forced replacement, pass dependency checks and match all 21 installed compute modules and five addon assets. Exact image and Linux manifest digests are in the adjacent JSON.

Both images were exercised as UID 1000 with networking disabled: fresh Papermill success/failure kernels, bool/int/float/string parameters, immutable input and retained failed executed notebook. Both runtime harnesses exited zero and their containers were removed. The OCI indexes/manifests/configs and attestation JSON blobs were rehashed; SPDX and SLSA v1 subjects bind to each Linux manifest. Runtime Python 3.13.13, JupyterLab 4.5.7 and RTC 4.4.1 were recorded.

Private evidence is 2026-10-07 `notebook-cpu-6bb6a57/{standard-cpu,base-cpu}` and the reusable `verify-runtime.py`. Verified evidence copies of each OCI archive remain; duplicate builder archives were removed to recover disk space.

These two candidates are local, unpublished and undeployed. This qualifies existing CPU parents only, not twelve variants built from one common source tag, GPU isolation, real user-browser behavior or the full gateway notebook submission path. Those gates remain incomplete.

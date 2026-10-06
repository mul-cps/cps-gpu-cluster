# Python 3.13 notebook package qualification

Status: offline package and execution smoke passed; notebook image matrix and production release remain unqualified.

The candidate wheelhouse contains 131 hash-pinned wheels, including `cps-compute` from source `d87dd25ceb11f16b11b1d5cdcefe39accc8cfb4f`. Its wheel SHA-256 is `204ce7c606697a253e2ce624950239209cfa8e8be7dfa3cfcd8a343b19a5d25b`. The compatibility hook and prebuilt JupyterLab addon are present. A separate wheelhouse was created so running builds keep their original inputs.

A fresh Python 3.13.12 virtual environment installed all packages offline using `--no-index --find-links --require-hashes`. Dependency checking passed. Installed versions were JupyterLab 4.6.4, Jupyter collaboration 5.0.4 and Papermill 2.7.0. These are the candidate package versions, not a claim about currently deployed notebook images.

Papermill executed success and intentional-failure notebooks with integer, boolean and list parameters and a selected local Python import. Both runs used a fresh Python 3.13 kernel and retained their executed notebook, including error output on failure. The submitted notebook's hash remained unchanged. JupyterLab reported the compute addon enabled and compatible; rendered UI and RTC behavior were not covered by this smoke.

Private operator evidence is under `/home/bjoern/cps-platform-evidence/2026-10-06/notebook-sdk-d87dd25-qualification/`: `report.json`, `smoke.py`, `smoke.log`, and the executed fixture notebooks. The separate candidate lock is `notebook-candidate-lock-d87dd25.json`; every wheel hash was rechecked. It has no source tag and remains `qualified=false`.

The existing CPU and Xpra builds still use their recorded original inputs. Their completion does not qualify the new SDK revision. Final overlays must use this reviewed wheelhouse, pin their parent and output digests, retain checksums/SBOMs/provenance and pass all twelve variant runtime checks. Production RTC, Hub integration and the platform acceptance scenarios remain separate gates.

## JupyterLab server asset smoke

A separate loopback JupyterLab server using the installed Python 3.13 candidate returned HTTP 200 for `/lab`. Its federated-extension configuration included `@cps/compute-jupyterlab`, and the referenced remote-entry JavaScript returned HTTP 200 (6,492 bytes). Evidence: `lab-http-report.json` in the same private evidence directory. The owned server was stopped after the check. This proves server registration and asset delivery; browser activation, panel interactions, authenticated gateway calls and RTC synchronization still require qualification.

## Corrected container compatibility qualification

The earlier standalone wheel smoke omitted packages already present in the notebook base. Actual container dependency checking rejected JupyterLab 4.6.4 because Notebook 7.5.6 requires JupyterLab <4.6. RTC 5.x simultaneously requires Lab >=4.6, so the full compatibility group was resolved together. The shared overlay now runs `python -m pip check` during every variant build (notebook source `7e8a42b51e7db43072fd67e4908d3728b16b07fa`). Failed candidates were not published.

The corrected 133-wheel group pins Notebook 7.5.6, JupyterLab 4.5.7, RTC 4.4.1, collaboration UI/docprovider/server-ydoc 2.4.1, YDoc 3.5.0, CRDT 0.13.0, CRDT store 0.1.4, CRDT websocket 0.16.2 and setuptools 80.9.0. Compute source is `5771df5e3db86a59b20fcf965cc3ce273df0c503`. All wheels are hash-locked.

Published CPU qualification artifact: `ghcr.io/mul-cps/cps-jupyter-notebook:qualification-cpu-7e8a42b-5771df5@sha256:4dfb654d8f01f1b0818664ffa8a431afd53165deb08c4758b4a37d2907b4175c`. Remote digest matches the built OCI index. All 53 blob hashes and SPDX/SLSA attestations verified. The final container passed offline tests as UID 1000: dependency checking, addon registration, typed parameters, selected local imports, fresh Python 3.13 kernels, unchanged submitted notebook and retained success/failure executed notebooks.

Evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/notebook-cpu-resolved/` (`inputs.json`, `oci-report.json`, `runtime-report.json`, `publication-report.json`), with the matrix candidate lock in `notebook-candidate-lock-resolved.json`. This qualifies one variant's bounded offline runtime smoke. It does not qualify production RTC, rendered addon interactions, Hub startup bursts or the twelve-variant release matrix. The candidate lock has no source tag and remains unqualified.

Base CPU also passed the same bounded offline container checks as UID 1000. Artifact: `ghcr.io/mul-cps/cps-jupyter-notebook-base-cpu:qualification-7e8a42b-5771df5@sha256:d5cfee0c5f8051406c6cfb976fa7fa28c1587513764699b52005a9684ba4fa8f`. All 53 OCI blob hashes, SPDX/SLSA statements and the published index digest verified. Evidence is under `notebook-matrix-resolved/base-cpu/` in the operator evidence root above. The candidate inventory now contains standard CPU and base CPU; other variants and platform acceptance gates remain incomplete.

## Restricted cluster runtime qualification

The standard CPU candidate also passed a Kubernetes Job with Pod Security restricted, UID 1000, a read-only root filesystem, all capabilities dropped, no service-account token, a bounded memory-backed `/tmp`, and default-deny ingress/egress. The namespace is dedicated to operator-controlled image qualification; no user homes or GPU devices were mounted.

Base GPU candidate `ghcr.io/mul-cps/cps-jupyter-notebook-base-gpu@sha256:7672b3b4c8efa60bb41e6b614254c7cf834e77033690c94c4844feef83835966` passed the same notebook execution checks under those restrictions. Its 73 OCI blob hashes, SPDX/SLSA statements and published index digest verified. Python was 3.13.14, with Lab 4.5.7, RTC 4.4.1 and Papermill 2.7.0. This validates the installed notebook runtime without granting a GPU: CUDA execution, memory isolation, specialized libraries, production RTC and the full release matrix remain separate incomplete gates.

Private evidence: `notebook-cluster-runtime/{standard-cpu,base-gpu}-report.json`, exact Job manifests and runtime logs, plus `notebook-matrix-resolved/base-gpu/oci-report.json`. Completed Jobs were removed after collecting evidence. The candidate inventory now has three final overlay images and remains `qualified=false`, without a source tag.

## Xpra and MuJoCo/Xpra backend checks

Final Xpra overlay `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:d1a89ef183373c254b10522ed171aec8e6ca6e8dc0e6b6711f8b2a07ea0513eb` passed the restricted notebook runtime and a headless non-root Xpra/XFCE test. Its local control socket responded and the VirtualGL wrapper's CPU fallback worked. The test explicitly placed all Xpra sockets under writable `/tmp`; initial attempts exposed Xpra's default additional socket directory under the read-only home. No rendered browser or GPU graphics were qualified.

Final MuJoCo/Xpra overlay `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:a7fbf377c7fa077ed1ce3330a898e9ba4f32a6ebbfca6ec5710ebb47063ffe7d` passed the same checks and compiled a small MuJoCo model, advanced 100 physics steps and verified finite state and gravity-induced movement. Versions were MuJoCo 3.15.0 and Gymnasium 1.4.0. GPU EGL rendering remains unqualified. All 44 OCI blob hashes, SPDX/SLSA statements and the published index digest verified.

Evidence is under `notebook-cluster-runtime/`: `desktop-xpra-report.json`, `mujoco-xpra-report.json`, Pod snapshots, exact Jobs, scripts and logs. Completed Jobs were removed. There are now five final overlay candidates; the full twelve-image matrix and production release remain incomplete.

## Minimal CUDA/PyTorch root qualification

`mujoco-base-gpu` is deliberately the minimal CUDA/PyTorch parent; its Dockerfile installs no MuJoCo. The first assigned physics test therefore failed with an absent module after all notebook checks passed. That failed test and Job snapshot are retained. MuJoCo physics belongs to the derived `mujoco-xpra` runtime, which passed it above.

Final base artifact `ghcr.io/mul-cps/cps-jupyter-notebook-mujoco-base-gpu@sha256:5b5898a5f1dfb98a8dde2f313b923f8532267dffb1c1670b19ae56c6b35875b2` passed the restricted notebook tests plus CPU matrix multiplication, autograd and TorchVision import with Torch 2.10.0+cu128 / TorchVision 0.25.0+cu128. Its CUDA build is 12.8; no GPU kernels were run. All 36 OCI blob hashes, SPDX/SLSA statements and the remote index digest verified. Evidence: `notebook-cluster-runtime/mujoco-base-report.json` and `notebook-matrix-resolved/mujoco-base-gpu/`. Six final overlay candidates now have bounded runtime checks; full matrix, hardware and release qualification remain incomplete.

Final PyTorch runtime artifact `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:9be24416bf45c17762df4aee824423b0b27656aea1b1c2963a11b7be452643b1` passed the same restricted notebook and CPU framework checks, using Torch 2.10.0+cu128 and TorchVision 0.25.0+cu128. All 37 OCI blobs and SPDX/SLSA statements verified; the published index matches the build. Evidence: `notebook-cluster-runtime/pytorch-runtime-report.json` and `notebook-matrix-resolved/pytorch-runtime-base/`. Seven final overlay candidates now have bounded runtime checks. CUDA kernel execution and full matrix/release qualification remain open.

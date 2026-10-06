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

## PyTorch tooling runtime

Final `pytorch-code` artifact `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:6a0fc97f17ac13f70c06b834a37641116407a0d134ea23ed3d67eac0f55fc0ab` passed restricted notebook execution, matrix multiplication/autograd and all declared tooling imports. TorchVision's compiled CPU NMS operator also ran successfully. Installed Torch was 2.11.0+cu129 and TorchVision 0.26.0+cu129; declared CUDA build was 12.9. The report records Transformers, Datasets, Accelerate, Lightning, timm, OpenCV, scikit-image, scikit-learn, pandas, matplotlib, seaborn and torchaudio versions. No external models were downloaded and no GPU kernels ran.

All 75 OCI blobs, SPDX/SLSA statements and the published index digest verified. Evidence: `notebook-cluster-runtime/pytorch-tooling-report.json`, exact Job/Pod snapshots and logs, plus `notebook-matrix-resolved/pytorch-code/`. The completed Job was removed. Eight final overlay candidates now have bounded runtime checks; the remaining four variants, GPU execution/isolation and platform release gates remain incomplete.

## TensorFlow parent dependency repair

The initial TensorFlow candidate failed `pip check`: inherited Torch 2.9.1 required NCCL 2.27.5, while TensorFlow 2.21 requires NCCL >=2.27.7. The repaired parent uses Torch 2.11 / TorchVision 0.26 / torchaudio 2.11 from the CUDA 12.9 index with NCCL 2.28.9. Notebook 7.5.6 is pinned to retain compatibility with JupyterLab 4.5.7. Notebook repository commit `62b0baf0c8ff0251e55e11f8e08202e8c44c579d` records the repair.

The parent build passed dependency validation. Its OCI index is `sha256:3fe6e83ca6118785bdf5632c0f6d059aa7f32d431c81765048e647e2bba86575`; all 73 blobs and SPDX/SLSA statements verified locally. Evidence: `notebook-tensorflow-parent-v2/inputs.json`, `build.log`, `metadata.json` and `oci-report.json`. This is a root intermediate parent, not a qualified final notebook image. Registry publication, the final nonroot offline overlay, framework execution and GPU kernels remain separate gates. The final runtime candidate count remains eight.

Final TensorFlow candidate `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:bfa7d83af8752390c616b6632e9854e24064895dc504916be7b9a58ceef978d4` passed all restricted notebook checks, Torch 2.11.0+cu129 / TorchVision 0.26.0+cu129 CPU matrix multiplication and autograd, and TensorFlow 2.21.0 CPU differentiation plus a Keras training step. TensorFlow Datasets, Keras, tf-keras, scikit-learn, pandas, seaborn and matplotlib imports passed. No GPU was mounted; the CUDA initialization warning does not establish GPU execution.

All 75 OCI blob hashes, SPDX/SLSA statements, UID 1000 configuration and the published index verified. Evidence: `notebook-matrix-resolved/tf-code-v2/`, `notebook-cluster-runtime/tensorflow-report.json`, exact Job/Pod snapshots and runtime logs. The completed Job was removed. Nine of twelve final overlay candidates now have bounded runtime checks; ROS/ComfyUI, GPU hardware/isolation and full production release qualification remain open.

## ROS desktop runtime and large SBOMs

Final `desktop-ros2` candidate `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:e8c0e956fd441c97e75523c5fac142e11be0f01c4cf80298238f47d53329bf8b` passed restricted notebook execution, Torch 2.11.0+cu129 CPU matrix multiplication/autograd, TurboVNC protocol readiness, XFCE window-manager startup and ROS 2 Jazzy local DDS publisher/subscriber exchange. The first fixture failed because ROS logging targeted the read-only home; its failure is retained. The corrected fixture uses a temporary log directory. GPU graphics, robot connectivity and production RTC remain unqualified.

All 96 OCI blobs, provenance, UID 1000 and the published index verified. BuildKit's 80 MiB attestation limit rejected the full SBOM, including a package-selection retry. A separate full Syft 1.54.1 scan retained package/file cataloging, with a bounded 16 GiB entry limit for measured layers above 2 GiB. Its SPDX document is 143,020,174 bytes and covers 5,444 packages; its source configuration digest matches the verified OCI image. SPDX SHA-256 is `b74e67f34392b762605e10739ad919e02fd8ac2cad1ac49023e2ffbb24d472d6`. Release tooling must publish this separate SBOM with the image and checksums; embedding remains unsuitable for this image.

Evidence: `notebook-matrix-resolved/desktop-ros2-standalone-sbom/` and `notebook-cluster-runtime/desktop-ros2-report.json`, exact Job/Pod snapshots and logs. Both terminal Jobs were removed after evidence capture. Ten of twelve final overlay candidates now have bounded runtime checks; ROS/Xpra, ComfyUI, GPU and production release gates remain open.

## ROS/Xpra runtime

Final `desktop-ros2-xpra` candidate `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:af54f9a7b2d4ec521350d9a5fbb3d1efeca74d78edd8ee0ff62cb45e480a4b35` passed restricted notebook execution, Torch CPU matrix multiplication/autograd, nonroot Xpra control-socket readiness, XFCE session startup, VirtualGL CPU fallback and ROS 2 Jazzy local DDS exchange. The successful Job and Pod and all four runtime reports were captured before Job deletion. Rendered desktop behavior, GPU graphics and production RTC remain unqualified.

All 97 OCI blobs, SLSA provenance, UID 1000 and the published index verified. The full standalone SPDX SBOM covers 5,522 packages, is bound to the OCI runtime configuration and has SHA-256 `24e619b85da9f8beeb912924941b6ebbfd609e555048bfd3ded26c64e10adec4`. The release verifier also checked native-package coverage and manifest binding. The SBOM remains a local paired artifact requiring release publication.

Evidence: `notebook-matrix-resolved/desktop-ros2-xpra-standalone-sbom/` and `notebook-cluster-runtime/desktop-ros2-xpra-report.json`, final Job/Pod snapshots and runtime log. Eleven of twelve overlay candidates have bounded runtime checks. ComfyUI, actual GPU execution/isolation, production collaboration and final release qualification remain open.

## ComfyUI artifact verification

ComfyUI's final offline overlay build completed at OCI index `sha256:87055416cb30d04f26b93a8912d6cbfa7f612bdecb709bc4097ab409f6662eb5`. All 89 blobs, SLSA provenance, UID 1000 and core notebook/framework package coverage verified. The full standalone SPDX SBOM contains 5,043 packages and has SHA-256 `afbfb247b67fa0ec328f99d928ec6b623440c44ee91de9cc87914acb9357b862`. Release tooling verified native-package coverage and image configuration/manifest binding, using checksum-verified Syft 1.54.1. Evidence: `notebook-matrix-resolved/comfyui-standalone-sbom/`.

Registry publication and runtime execution remain separate gates. This artifact verification does not increase the eleven runtime-tested candidates or qualify GPU/model execution, proxy startup, production RTC or a final tagged release. Standalone SBOM publication remains required with the eventual release.

ComfyUI's published digest matched the locally verified index. Its restricted runtime Job passed notebook execution, Torch CPU matrix multiplication/autograd and a model-free ComfyUI API graph (load an 8x8 red image, invert and save, verifying cyan output). No models were downloaded and no GPU was mounted. The server emitted a database initialization warning, retained in the log; this graph test does not establish persistence or proxy startup. The successful Job/Pod and all three reports were captured before Job deletion. Evidence: `notebook-cluster-runtime/comfyui-report.json`, final Job/Pod snapshots and runtime log.

All twelve final overlay candidates now have bounded runtime checks. The candidate lock retains `qualified: false` and no source tag. Actual GPU kernels/graphics/model execution, production RTC, application startup/proxy behavior and same-tag final release artifacts remain open. Six full standalone SBOM documents for the two ROS variants and ComfyUI have a verified local bundle manifest and checksums; remote SBOM release publication remains pending.

## ComfyUI startup and synthetic proxy repair

Notebook source commit `c087852acc142b5f2a5b1270241d4edb3d52d1b3` gives ComfyUI explicit writable input/output/temp/user directories and SQLite URL under the persistent home (or `COMFYUI_DATA_DIR`), with a loopback listener for Jupyter Server Proxy. The prior database warning arose because the application defaults SQLite to `/opt/comfyui/user/comfyui.db` independently of its user-directory option.

Restricted tests of the mounted source script passed SQLite initialization/migration and the CPU image graph, both directly and through token-authenticated Jupyter Server Proxy HTTP requests. The first proxy fixture asserted the override directory without passing it to the proxy child; the failure is retained and the corrected fixture passed. Evidence: `notebook-cluster-runtime/comfyui-startup-report.json`, `comfyui-proxy-report.json`, terminal Job/Pod snapshots and logs. Test Jobs were removed after capture. No human Hub session or browser was accessed. The startup repair is rebuilding into a new candidate; embedded-script artifact verification, production Hub proxy behavior, persistence across restarts and GPU/model execution remain open.

Repaired ComfyUI candidate `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:0f251eff4c49c5381c3b31db1ac19baa5c85b5ec33150ec031afd3040d13a0c3` passed all 90 blob hashes, SLSA provenance, UID 1000 and embedded startup-script checksum/ownership/executable checks against notebook commit `c087852`. Its new full SPDX SBOM contains 5,043 packages, is bound to the repaired runtime image and has SHA-256 `8aff9acaf23787d84fc1aa3bd7744cc5fa061aa4667c8c894373350111611cbb`. The published index digest matched the verified artifact.

The repaired image then passed restricted notebook and Torch CPU checks and two token-authenticated Jupyter Server Proxy image graphs. Anonymous requests redirected to login. A SQLite marker created after the first start survived the second server start. The startup script was embedded in the image, with no replacement script mount; CPU and custom-node/API-node qualification overrides were explicit. Evidence: `notebook-matrix-resolved/comfyui-startup-v2/`, `notebook-cluster-runtime/comfyui-embedded-proxy-report.json`, final Job/Pod snapshots and log. The completed Job was removed after capture. The candidate lock and local SBOM bundle now reference this repaired image and retain the superseded digest. This verifies persistence across process restart on the same test volume, not NFS/Pod disaster recovery, production Hub proxy behavior or GPU/model execution. Full release qualification remains false.

## Controlled PyTorch CUDA execution

The `pytorch-code` candidate `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:6a0fc97f17ac13f70c06b834a37641116407a0d134ea23ed3d67eac0f55fc0ab` passed actual CUDA matrix multiplication and autograd on one device-plugin-allocated NVIDIA A100-PCIE-40GB on quiescent worker 3. Torch 2.11.0+cu129 used CUDA 12.9 with peak Torch tensor allocation 42,206,208 bytes. The restricted nonroot Job had no host mounts or service credentials, a 180-second deadline and one GPU resource request/limit. Successful Job/Pod and logs were captured before deletion. Evidence: `notebook-cluster-runtime/pytorch-cuda-report.json`, exact Job/Pod snapshots and runtime log. This verifies bounded CUDA execution for this candidate, not GPU isolation, fractional scheduling, the remaining variants or production Hub behavior. Shared profiles remain disabled.

## Standalone SBOM registry publication

The full SPDX/native Syft pairs for `desktop-ros2`, `desktop-ros2-xpra` and repaired `comfyui` are now published as OCI referrers to their exact qualification image index digests. Each referrer manifest's subject was checked against the image, then both documents were pulled by referrer digest into separate verification directories and hash-compared with the verified local SBOMs. Evidence: each variant's `sbom-publication.json`, `sbom-referrer-manifest.json` and `sbom-remote-verification-report.json`. ORAS 1.3.4's archive was verified against the official release checksum over HTTPS; its release signature was not independently verified. This completes remote SBOM publication for these qualification candidates, without creating a release tag or qualifying the platform. Final same-tag release assets and checksum/SBOM archival remain required.

## TensorFlow CUDA cold-pull deadline

The first controlled TensorFlow CUDA Job reached its 180-second deadline during image pull, before container creation. Its `DeadlineExceeded` Job/Pod/events are preserved in `notebook-cluster-runtime/tensorflow-cuda-coldpull-failure-*`. Normal Job deletion left the Pod terminating while containerd continued a slow download. Read-only diagnostics matched active layer `sha256:f6e3171afd3db551f89dd4f09c6b5d0ece49b8e9caa8313d52b45866610f0ddf` to the TensorFlow candidate: 4,200,244,382 bytes total, with observed progress from 1.845 GB through 2.296 GB. Node health and free disk were adequate; no container ID or running qualification container existed. Evidence: `tensorflow-active-layer.json`, `tensorflow-containerd-active-download.txt`, node stats and `tensorflow-pull-progress-report.json`.

No force deletion or node/runtime restart was used, and no overlapping GPU retry was launched. Framework execution remains untested by this attempt. A follow-up uses the established 900-second image qualification deadline after confirmed old-Pod removal; the small GPU kernel/gradient checks remain bounded. This cold pull is separate from the required pre-pulled startup burst qualification, which remains open.

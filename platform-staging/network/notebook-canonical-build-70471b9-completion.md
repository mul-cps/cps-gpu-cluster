# Canonical twelve-image build completed: historical 70471b9 candidate

The offline canonical build completed with exit code **0** and produced all twelve requested OCI images, standalone SPDX and native Syft SBOMs, metadata files, `release.json` and `SHA256SUMS`. The [terminal audit receipt](notebook-canonical-build-70471b9-completion.json) records each image index, Linux amd64 manifest, config, provenance and SBOM digest. No new image was pushed or release published during this audit.

All twelve saved SPDX inventories passed `release/build.py::verify_standalone_sbom`: package inventories contain `cps-compute` and agree with native SBOM inventories; source image IDs and manifests match the OCI archive. Image labels bind notebook source revision `b95c700a12229ff1435d986e4722b80e39290a0f`, version `0.1.0` and the locked policy hash. SLSA provenance subjects bind the actual amd64 manifests, and build parameters bind the exact locked base digest, source labels and disabled build network. Metadata blob SHA-256 checks passed. Five earlier SBOM receipts still match; all twelve were checked without rescanning.

User, WorkingDir, Entrypoint, Cmd and Healthcheck equal the corresponding saved locked-base configs for every variant. Every base report identifies the exact locked image reference, and config bytes hash to its recorded source image ID. This checks saved base evidence; it is not a fresh registry verification. The checksum inventory has exactly **49** expected entries. All **37** non-archive file hashes were independently checked; the compiler recorded the twelve large OCI archive checksums, which this audit did not independently rehash. Layer payloads were not revalidated.

| Variant | SPDX packages |
| --- | ---: |
| standard-cpu | 4087 |
| base-cpu | 4087 |
| base-gpu | 3916 |
| mujoco-base-gpu | 818 |
| pytorch-runtime-base | 818 |
| pytorch-code | 3941 |
| tf-code | 3933 |
| desktop-xpra-base | 964 |
| desktop-ros2 | 5444 |
| desktop-ros2-xpra | 5522 |
| mujoco-xpra | 984 |
| comfyui | 5043 |

This is a **historical qualification candidate**, using the `70471b9` compute wheel (`86a0fa74cb6e15dd408fcfe36945ca1f614af14ff3bda555f49aaf4e85408d37`). It does not contain later SDK/addon fixes. The notebook `v0.1.0` source tag exists only in a clean private build clone; it was not published. The private source tag, input lock and compute-wheel checksum were reverified. Updated SDK artifacts need a new locked build and qualification.

Build completion does **not** establish runtime qualification. `release.json` has `qualified=false` and every image has `qualification=not-run`; the completion receipt records `productionQualified=false` and `releasePublished=false`. Browser, RTC, notebooks through Argo, GPU applications, and other per-image runtime gates remain separate. This audit ran no images, hardware workloads, scans, image pulls or publishing.

Private reproducible evidence: `2026-10-07/canonical-12-build-terminal-audit/{audit.py,verify_source.py,report.json}`. The public receipt includes its script/report hashes and the hashes of canonical `release.json`, `SHA256SUMS`, the verifier and the input lock. Original complete build outputs remain in the private `tagged-source-70471b9/outputs` evidence directory.

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

# Python 3.13 notebook package qualification

Status: offline package and execution smoke passed; notebook image matrix and production release remain unqualified.

The candidate wheelhouse contains 131 hash-pinned wheels, including `cps-compute` from source `d87dd25ceb11f16b11b1d5cdcefe39accc8cfb4f`. Its wheel SHA-256 is `204ce7c606697a253e2ce624950239209cfa8e8be7dfa3cfcd8a343b19a5d25b`. The compatibility hook and prebuilt JupyterLab addon are present. A separate wheelhouse was created so running builds keep their original inputs.

A fresh Python 3.13.12 virtual environment installed all packages offline using `--no-index --find-links --require-hashes`. Dependency checking passed. Installed versions were JupyterLab 4.6.4, Jupyter collaboration 5.0.4 and Papermill 2.7.0. These are the candidate package versions, not a claim about currently deployed notebook images.

Papermill executed success and intentional-failure notebooks with integer, boolean and list parameters and a selected local Python import. Both runs used a fresh Python 3.13 kernel and retained their executed notebook, including error output on failure. The submitted notebook's hash remained unchanged. JupyterLab reported the compute addon enabled and compatible; rendered UI and RTC behavior were not covered by this smoke.

Private operator evidence is under `/home/bjoern/cps-platform-evidence/2026-10-06/notebook-sdk-d87dd25-qualification/`: `report.json`, `smoke.py`, `smoke.log`, and the executed fixture notebooks. The separate candidate lock is `notebook-candidate-lock-d87dd25.json`; every wheel hash was rechecked. It has no source tag and remains `qualified=false`.

The existing CPU and Xpra builds still use their recorded original inputs. Their completion does not qualify the new SDK revision. Final overlays must use this reviewed wheelhouse, pin their parent and output digests, retain checksums/SBOMs/provenance and pass all twelve variant runtime checks. Production RTC, Hub integration and the platform acceptance scenarios remain separate gates.

## JupyterLab server asset smoke

A separate loopback JupyterLab server using the installed Python 3.13 candidate returned HTTP 200 for `/lab`. Its federated-extension configuration included `@cps/compute-jupyterlab`, and the referenced remote-entry JavaScript returned HTTP 200 (6,492 bytes). Evidence: `lab-http-report.json` in the same private evidence directory. The owned server was stopped after the check. This proves server registration and asset delivery; browser activation, panel interactions, authenticated gateway calls and RTC synchronization still require qualification.

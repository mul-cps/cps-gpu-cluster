# Held PyTorch OOM with independent peer progress

This is an inert-by-default qualification harness, not a production approval.
Root must first roll out the reviewed `47d8e532409337c864d02fc608600b4aecea650075573690b4f17dcb7a670c7f` Node image, verify current four-process readiness, and start the two approved CPS 5 GiB workspaces through the normal administration API. The notebook runtime remains exact `9167861058c1364c58d1c2fca0d6f536c3ffb53a33800dcdb9a1560f14ca4dc0`. No 20 GiB profile is covered.

`peer_probe.py` derives from the frozen trusted private `group_probe.py` (SHA256 `02ce478a4543b3d971585add60c6314605a0f120eea3e8a6adb014c5ba527cbd`). Its only behavior addition is retaining the successful allocations for eight seconds after a typed OOM, with explicit start/end events. The original private source is unchanged. `ProbeRun` reuses the bounded stdin transport from that probe's supervisor, with isolated Python (`-I`) to exclude notebook working-directory and `PYTHONPATH` import shadowing and a bounded kill-wait; the obsolete supervisor's policy, historical inventory and workspace assumptions are not reused. `current_preflight.py` derives from the reviewed VMM qualification adapter in the adjacent artifact directory, with only the required Node image updated.

The pressure child allocates and touches 256 MiB increments, requires a typed Torch OOM after 4–5 GiB has been held, and never touches an unexpected over-cap allocation. It verifies ordinary and recovered CUDA kernels. The other Pod repeatedly fills, synchronizes and reads its own CUDA tensor. Success requires multiple peer kernels strictly inside the eight-second retained-pressure window, plus peer kernels before the OOM and after recovery, without a gap exceeding five seconds.

Independent physical samples run as Root in the existing observer's host namespaces. The exact SHA-pinned host `nvidia-smi` and NVML query only the reviewed GPU. Four observations must fall strictly inside the retained-pressure window and show physical total greater than 30 GiB and physical free greater than 6 GiB. Capped `torch.cuda`/CUDA memory totals cannot provide this evidence. All processes run on the same host, so their Linux monotonic timestamps share a clock. The host boot ID is checked.

Before and after, the adapter reads the actual packaged Node's typed sealed records, exact receipts, Pod spec hashes, parent identities and NVML limits. It requires unchanged full Pod/process observations, journals, gates and identities; per-parent charged bytes must return to no more than the initial baseline. It never writes a cap, gate, ledger, Pod, runtime, driver, or MIG setting.

## Root execution

Run CPU checks first:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s qualification-artifacts/native-peer-oom-20261017 -p 'test_*.py' -q
python -B qualification-artifacts/native-peer-oom-20261017/run_peer_oom.py
```

Prepare a **fresh, separately reviewed, owned regular 0600 manifest** with exactly this shape, using the actual current UIDs after normal starts (never copy old workload UIDs):

```json
{"pods":{"a":{"namespace":"jupyterhub","name":"ACTUAL-LAB-POD","uid":"ACTUAL-UUID","cap_mib":5120},"b":{"namespace":"jupyterhub","name":"ACTUAL-SECOND-POD","uid":"ACTUAL-UUID","cap_mib":5120}},"node":{"namespace":"cps-native-system","name":"ACTUAL-NODE-POD","uid":"ACTUAL-UUID"},"observer":{"namespace":"gpu-operator","name":"cps-native-driver-control","uid":"ACTUAL-UUID"}}
```

The manifest has the same closed schema as the current VMM harness. Supply the independently reviewed manifest SHA256 and the three source SHA256 values in `source-pins.json`; those flags are mandatory with `--execute`. The output directory must not exist. For example, from this directory:

```sh
python -B run_peer_oom.py --execute \
  --manifest /absolute/private/current-targets.json --manifest-sha256 REVIEWED_MANIFEST_SHA256 \
  --runner-sha256 REVIEWED_RUNNER_SHA256 --probe-sha256 REVIEWED_PROBE_SHA256 \
  --preflight-sha256 REVIEWED_PREFLIGHT_SHA256 \
  --direction a-to-b --output /absolute/private/new-peer-oom-a-to-b
```

Repeat with `--direction b-to-a` and a different fresh output directory if Root requires both directions. Each probe has a remote watchdog (peer 60 seconds, pressure 45 seconds); source transfer, API observation and local child waits are bounded separately. Failure is nonzero and never retries hardware work or stops a workspace. Local transport cleanup is attempted for every child even after another cleanup fails. On an interrupted/failed run, a remote child can remain until its own watchdog; inspect and wait for it to finish before normal workspace Stop. A missing `assessment.json` means inconclusive. Do not infer successful restoration from a failed run; inspect final Pod/cap state through the existing read-only controls.

Normal workspace Stop, expiry restoration, four-process readiness and physical/kernel interpretation remain Root's separate protocol. This harness does not mutate or approve those states.

## Current authority refresh

The adapter now pins packaged Node image `7e319bf…08bb0`. The installed typed loader authenticated NodeConfig, deployment and qualification; read-only observations confirmed the current boot, driver generation and non-MIG physical GPU. The GPU workload remains the qualified `916786…14ca4dc0` image; CPU notebook image `9444a0…df7f` is not a substitute. See `current-cohort-authority.json`.

This refresh does not repeat or extend historical hardware results. The current cohort still needs actual placement, sealed cap and CDI/CRI provenance before CUDA. GPU2 remains cordoned and the native binder bridge disabled.

## Jupyter kernel transport helper

`kernel_transport.py` provides a one-request Jupyter protocol exchange and generates code that runs the SHA-checked probe in an isolated Python child of an owned kernel. Child stdout streams in real time; deadlines and output limits apply, stderr is bounded, and failure kills and reaps only that child. The caller must authenticate the socket, create and pin its own kernel UUID, and clean up that kernel.

`run_peer_oom.py --mode kernel` uses the owned normal-user kernel lifecycle. It requires `--kernel-manifest`, its separately reviewed `--kernel-manifest-sha256`, and the exact `--kernel-transport-sha256` / `--kernel-lifecycle-sha256` from `source-pins.json`. The legacy default `--mode kubectl` remains available. The kernel mode has CPU lifecycle and containment tests, but has not yet qualified a live normal-user GPU run. No browser, shared-workspace authorization or current-cohort hardware qualification is claimed. These CPU tests run on the hosted CI runner without GPU or cluster access.

The private kernel manifest has exactly `a` and `b` rows. Each row contains `hub_origin` (the fixed CPS HTTPS origin), `operator` (an existing non-admin user), `owner`, `server`, `pod_uid` (the selected actual Pod UID) and `token_file` (an absolute, owned regular 0600 token-file path). Never put token values in the manifest or Git. The actual Pod must expose the matching literal JupyterHub user, server and service-prefix environment. Ambiguous kernel creation is a manual cleanup hold; the runner never adopts or deletes an unproven kernel.

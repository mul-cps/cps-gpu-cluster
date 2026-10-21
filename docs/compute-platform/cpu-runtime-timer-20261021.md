# CPS CPU runtime timer image

The CPS `cpu-default` profile and its `datascience` pre-puller now select
`ghcr.io/mul-cps/cps-jupyter-notebook@sha256:16ed0a2c9c3d8e6d3942b515fc3a32ec750b3c506323326c050370566b595497`.
The pre-puller retains the chart's `name:tag` representation with the same digest.
This is the addon-only runtime timer overlay on the deployed CPU image
`sha256:9444a023984ffe792ba6588b5f54d459edae1c69b13399597498a659b591df7f`.
The canonical values previously contained `ff0c30d9…`; that older source pin
was not the deployed CPU9444 baseline.

The publication receipt is
`O/jupyterlab-server-runtime-20261021-image-preparation/cpu.publication.verified.private.json`,
where `O=/home/bjoern/.local/state/cps-full-project-20261013`.
It binds config `sha256:6ceb8aab062c23285d11262712085e8def92ea4b3238b9aa93d5eb7a9a14e90d`,
addon source `5d15d2db497b2d96e16e981348cabe94910b9ae6`, and wheel
`a90b63abfa3fa64f64a4ec3f37edf54875cc0c08ad07d698904f231595c02eed`.
Installed verification retained all 43 core modules, 315 other distributions,
runtime configuration, base layers, and UID1000/GID100; all 10 addon wheel files
matched. The source addon suite passed 70 tests. The image's Node18 diagnostic
harness passed 61 and failed nine because modern mock timers and development
fixtures were unavailable; this is not an installed 70-test pass.
The isolated authenticated Jupyter Server API probe passed, with stable server
start and no polling-induced activity updates. Browser display acceptance is
still separate.

## Verified deployment

CPS standard CPU now uses this image. An ordinary student completed normal
Start and authenticated timer API checks in 76.74 seconds. Normal Stop,
Pod absence, temporary grant expiry, unchanged preexisting grants and token
revocation were verified. The original control-plane specs/routes, four genuine
acknowledgments and journal60/12/300/checkpoint48 were preserved.

The existing PyTorch session received the same prebuilt wheel in its user
extension environment. Its Python backend was byte-identical; the actual Lab
page serves the new timer bundle with the same Pod/container and no additional
restarts. Browser display remains user-observed. Other PyTorch image consumers
still require their persistent image overlay.

[Acceptance receipt](qualification/runtime-timer-20261021.json) separates these
checks from the remaining CIT deployment and other profile image work.

## Deployment handover procedure

`registered_cpu.configured_image` in the released Hub package captures the
operator-owned `PROFILE_CONFIGS['cpu-default']` image before installing the
native wrapper. This serves ordinary CPS CPU selections and registered CPU
workspaces. The interactive CPU policy has no image allowlist; this change
does not require changing D48, GPU authority, batch image1fab, or any backend.

The existing pure consumer edit pattern is
`O/compute-runtime-consumer-deltas-20261015/consumer_deltas.py::hub_target`:
capture the current Hub Secret UID/resourceVersion and full data, replace only
the reviewed CPU image literals in decoded `values.yaml`, validate the complete
decoded mapping, and use a whole-preimage CAS plus inverse. Its historical
old/new constants and three-object payload are not a current executable plan.
Root must derive a fresh CPS-only proposal from actual CPU9444 data, preserving
all unrelated Secret keys and Hub settings. Do not apply this entire older
canonical Helm file over the separately maintained live configuration.
Restart the Hub only through the existing guarded maintenance path with fresh
process proofs; preserve existing notebook Pods. A newly started controlled CPU
server must prove image16ed, authenticated timer API, and normal Stop cleanup.
Existing notebook processes keep their old image until their normal restart.

## CIT and other images

CIT ordinary CPU Small/Large/XLarge use their own operator profile list and
`cit-jupyter-notebook` runtime. The reviewed current CIT base is
`ghcr.io/mul-cps/cit-jupyter-notebook@sha256:6acd8bfe2b56968f7db0f9a033cdec329888a0e90cc73d4fa1e511f2561b18f9`.
It requires a separately verified addon-only overlay on those bytes. CPS16ed
does not replace it. CIT, batch1fab, all GPU profiles, and all backend images
are unchanged by this source change. No deployment or browser acceptance is
claimed here.

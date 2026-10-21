# CPS PyTorch runtime image

The ten existing CPS PyTorch profiles now pin
`ghcr.io/mul-cps/cps-jupyter-notebook@sha256:3910644e2e541f9cde6bed75a01f1bbdcc293a2d57a3f8862cbc99c7eeca30f3`:
`gpu-pytorch-single`, `gpu-pytorch-dual`, `gpu-3gb`, `gpu-5gb`, `gpu-8gb`,
`gpu-10gb`, `gpu-12gb`, `gpu-20gb`, `gpu-student`, and `gpu-slurm`.
The matching `cps-pytorch` prepuller retains the Helm chart's
`latest-pytorch-code@sha256:...` representation with that exact digest.

This published image retains the original PyTorch base
`sha256:6b6a8d6a225df1b938fe98bcdad9e547aef249347392ce8f29adb3fedda512ae`.
Root verified the registry manifest and configuration, the 76-layer base prefix,
runtime configuration except three provenance labels, and all 400 existing
distribution versions. Thirteen previously missing distributions were added
for the reviewed SDK, Hera, RTC and addon requirements. All 76 SDK modules match
the reviewed `aa1f` source; the addon wheel hash is
`a90b63abfa3fa64f64a4ec3f37edf54875cc0c08ad07d698904f231595c02eed`.
Default Jupyter extension discovery and an isolated authenticated server-status
probe passed as normal UID/eUID1000 and GID/eGID100. Authenticated `/api/status`
returned 200, unauthenticated access was denied, server start remained stable,
and repeated status polling did not update idle activity. These CPU-only image
qualification results do not claim an actual Hub profile Start, GPU execution,
browser display, or live deployment of this persistent PyTorch image.

The source delta changes only ten profile image values and the matching
prepuller tag. CPU16ed, batch images, TensorFlow, desktop, ComfyUI, all resource
limits, scheduling settings, grants and policy declarations remain unchanged.
CIT images are maintained separately. Helm regression tests check both actual
rendered image pullers and the exact profile selection and resource values.

Deployment needs a fresh CPS-only configuration delta against actual Hub Secret
UID, resourceVersion and full data, using the established whole-preimage CAS and
inverse procedure. Do not apply this entire canonical values file over the
separately maintained live configuration. Existing notebook Pods retain their
current processes and image until their normal restart. This commit performs no
deployment, GPU operation or policy migration.

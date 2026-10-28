# Selected-node managed runtime activation preflight

Status: offline installation plan; no cluster resources were changed. This is a
source-linked preflight, not an activation approval or production qualification.

## Finding

The selected-node runtime is not enabled in either live Node agent. On
2026-10-28, the live `cps-native-node-agent` Deployments in namespaces
`cps-native-runtime` and `cps-native-system` both ran the ordinary bootstrap
arguments (`--execute`, `--config`, `--policy`, `--process`, …) without
`--selected-runtime`. Their declared mounts include `/run/cps-node-bootstrap`
and the existing approval/head-anchor inputs, but no selected-runtime config
file or selected-runtime history mount. The images were, respectively,
`ghcr.io/mul-cps/cps-native-node@sha256:27a7a0765797347b3d5353b50e05a60f142cf5d9893f0cdc7531142e32cc1dad` and
`ghcr.io/mul-cps/cps-native-node@sha256:ca1e903df21a6ed06fc7044e11b22935c8786fc372ef179507f1f9034d73a8a9`.

The source activates `SelectedNodeRuntime.from_protected(service, path)` only
when `args.selected_runtime` is set; otherwise it executes the ordinary
`service.run_once()` / `service.run_forever()` path. See candidate source
commit `5d67c132186ca01ac4853f259d60930b368c46f8`,
`compute/src/cps_compute/native_node/bootstrap.py` around the selected-runtime
branch and `compute/src/cps_compute/native_node/pool_factory.py`,
`SelectedNodeRuntime.from_protected` and `SelectedNodeRuntime.__init__`.

The constructor is the authoritative config parser. It requires the exact
closed document shape and checks the installed pool binding, boot epoch,
protected coordinator token path, maintenance roots, and existing local
history. It does not create or repair those paths. Do not generate a new
history to satisfy the constructor. The Hub-side managed installation also
requires an existing installed history owned by the original coordinator;
see `compute/src/cps_compute/native_hub_installation.py`,
`ManagedHubInstallation.__init__` and `.install` in the same commit.

## Activation proposal for review

Apply only to the specific Node agent whose retained installation has been
identified and verified. Mount its operator-prepared config file read-only at
an absolute path inside the agent, then add
`--selected-runtime <that-mounted-absolute-path>` to that agent's existing
container arguments. Keep every current argument, mount, volume, image pin,
policy, approval reference, head anchor, service account, and state root intact.
Do not roll both agents together or alter the other agent while establishing a
single-node canary.

The mounted file must be parsed by the candidate `SelectedNodeRuntime` itself.
Its required keys are defined in that source parser: `protocol`, `version`,
`pool_id`, `database_id`, `installation_id`, `coordinator`, `local_history`,
`authority_node_references`, and `maintenance`. The coordinator and maintenance
subdocuments have exact closed key sets in the same parser. Obtain every value
from the original installation records and currently trusted operator
references; this artifact intentionally supplies no values or generated
authority. Keep the file and its parent private and root-owned as required by
`from_protected` and `private_read`.

## Missing inputs that block a deployable config

No compatible per-node selected-runtime configuration or retained-history
identity was established by the read-only deployment inspection. Before
rendering a deployment delta, the owner must identify, for the chosen Node:

- the original installed `pool_id`, `database_id`, and `installation_id`,
  matching `installed_binding(service, pool_id)`;
- the existing protected `local_history` directory and proof that its retained
  history reopens against that exact peer binding;
- the trusted coordinator origin, CA file and projected token file paths;
- the authority-node references used for the selected pool;
- the original maintenance public root, state roots and boot ID matching the
  installed Node epoch; and
- an explicit compatibility/read-only preflight result for those existing
  histories and references, before a rollout is considered.

The actual live Deployment mounts show that a config mount is absent, but do
not establish whether an unmounted host history exists or whether it is
compatible. Treat both as unknown and deployment-blocking until verified from
the original retained records. Never initialize, copy, rotate, or replace a
history, token, CA, or authority reference as part of this preflight.

## Evidence and limits

Live evidence was limited to Kubernetes Deployment metadata: namespace,
container image, argument names/paths, volume names and mount paths. No Secret
data, token, private key, or certificate contents were read. The selected-node
I2 and factory results in `/tmp/cps-selected-runtime-i2-pass-freeze-20261028`
are controlled software evidence; they do not prove this live config exists or
that deployment wiring is compatible. The source freeze is recorded in
`/tmp/cps-platform-precommit-freeze-20261028/published.json`; its compute
candidate commit is `5d67c132186ca01ac4853f259d60930b368c46f8`.

Read-only inventory command used:

```sh
kubectl get deploy,ds,sts -A \
  -o custom-columns=NS:.metadata.namespace,KIND:.kind,NAME:.metadata.name
kubectl -n cps-native-runtime get deploy cps-native-node-agent -o jsonpath='...'
kubectl -n cps-native-system get deploy cps-native-node-agent -o jsonpath='...'
```

The JSONPath reads only image, args, mount paths, and referenced volume names;
it does not dereference Secret values.

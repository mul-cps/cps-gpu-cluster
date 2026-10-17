# Release-pinned observer permission operator

This staged renderer supports application commit `699c457f3e6f2a9c4bca777c7f594306f196c112`.
It does not install anything or contact Kubernetes. Its output defaults to
`replicas: 0` and omits the application's `--execute` flag.

Reviewed operator image:

```
ghcr.io/mul-cps/cps-native-observer@sha256:979567428e891b6861c55bba3eb746b7284fc5e7f82b7e31be4d8b3da2cb075e
```

Published wheel SHA256: `538b860deb2409c8470d3aa6e39fdac1cb1efe485883d02bcc1b2916afeebd31`.
The image was independently checked as UID 10001 with inert import/CLI and
Root-protected readable input paths. Publication is distinct from installation
and live rescheduling qualification.

## Inputs and trust

Use a Python environment containing the reviewed SDK and its node dependencies.
Supply three explicit JSON documents; keep actual release data out of Git:

* `release.reviewed.json`: closed application `ObserverRelease` version 1.
  It pins the exact immutable six-key NodeConfiguration reference and all seven
  target Role UIDs and **full independently reviewed baseline rules**. Supply
  its separately reviewed canonical SHA256 as an argument. The renderer never
  promotes current API Role privileges into this baseline.
* `policy.json`: the exact compiled policy used by that NodeConfiguration.
* `capture.json`: closed version 1 with `configmaps`, `deployments`, `roles`.
  Include the exact immutable NodeConfiguration/deployment/qualification proof
  ConfigMaps required by `NodeConfiguration.load`, the currently named Node
  bootstrap ConfigMap, exactly the four declared Deployments, and exactly the
  seven existing target Roles. Use real GET responses, not invented UIDs/RVs.

The renderer validates the actual immutable authority chain with the application
factories. Current Role UIDs must match the independent baseline. API-added
rules or changes to other privileges are rejected. Only the existing Pods GET
and ReplicaSets GET `resourceNames` surfaces may differ; their current contents
are not copied into the trusted input. At runtime those names become baseline
names plus freshly verified current chains. Release upgrades must update the
protected input coherently; old arbitrary API additions are not history.

`held_node_template_sha256` is null by default: held Node binding is prohibited.
An explicit nonzero canonical full Node Deployment template hash permits only
that reviewed template, a running exact-image packaged-bootstrap init, an exact
NodeConfig/policy bootstrap document and `release=false`. Ready rescheduling
continues to require actual Pod→ReplicaSet→the fixed Deployment UID, current
controller template, immutable imageID and actual ServiceAccount UID.

`synthetic-fixture.json` is derived solely from redacted application unit-test
fixtures. It is not deployable authority, an operator baseline or live evidence.

## Render and review

No arguments prints inert JSON without opening files or importing the SDK.
An explicit render only writes the JSON manifest to stdout:

```sh
python -I platform-staging/native-observer-operator/render.py
python -I platform-staging/native-observer-operator/render.py \
  --render --release /private/release.reviewed.json \
  --reviewed-sha256 'sha256:REVIEWED_CANONICAL_RELEASE_HASH' \
  --policy /private/policy.json --capture /private/capture.json \
  --image ghcr.io/mul-cps/cps-native-observer@sha256:979567428e891b6861c55bba3eb746b7284fc5e7f82b7e31be4d8b3da2cb075e \
  > /private/observer.inert.json
```

The hash placeholder is deliberately not an authority pin. Compute and review
it against the independent baseline before replacing it. A mismatched hash,
role UID/rules, target set, current controller identity/image/SA, policy,
immutable ConfigMap reference or held template blocks all output.

After Root review, `--activate-manifest` additionally sets replicas=1 and adds
`--execute`. Rendering still performs **no API writes**. Review/dry-run/apply is
a separate Root action. Do not apply the synthetic fixture or blindly reapply an
old capture over a newer release. Keep the exact preimages and install receipt;
stopping this dedicated Deployment removes its writer without changing target
Roles, policy, GPU state or component workloads.

## Least privilege and protected files

The dedicated ServiceAccount is in the Node authority namespace. Four
namespace-local Roles/Bindings grant only:

* `get`, `patch`, `escalate` on the exact seven existing target Role names.
  `escalate` is required to preserve their legitimate ACK PATCH rules without
  granting the operator those ACK write privileges itself. No `bind`, `create`,
  `update`, RoleBinding write, ClusterRole write or wildcard is granted.
* GET of each fixed Deployment and ServiceAccount name.
* GET of the exact immutable authority ConfigMaps actually resolved offline,
  plus the Node's exact **mutable bootstrap release-gate ConfigMap**.
* Pods GET/LIST and ReplicaSets GET in only the four controller namespaces.
  Dynamic Pod/RS names preclude `resourceNames` restrictions here. The
  application LISTs only the fixed Deployment's exact label selector; Kubernetes
  RBAC cannot enforce that selector. ReplicaSets LIST is not granted.

There is no Secret API access, GPU request, host mount or privileged container.
The Deployment uses Recreate, UID/GID 10001, drops all capabilities, forbids
privilege escalation and uses a read-only root filesystem. An immutable input
ConfigMap is mounted as two read-only regular `subPath` files at
`/etc/cps-observer/{release,policy}.json`, mode 0444, with Root-owned 0755 parents.
It must not be mounted through `..data` or `/var/run` symlink parents. No fsGroup
is set. Runtime Root-file validation remains enabled as nonroot.

Root must verify the actual mounted ownership/path closure, dedicated SA RBAC,
source/image pins and inert defaults before activation. Live acceptance needs
ordinary sanctioned rescheduling/new-RS recovery, exact named GET convergence,
all-four readiness and unchanged GPU/policy/workload state. This staged unit
does not claim those live gates have passed.

## CPU tests

With the reviewed SDK on PYTHONPATH or installed in the test environment:

```sh
python -m pytest -q platform-staging/native-observer-operator/test_render.py
```

Tests use the bundled synthetic API documents, never live access. They cover the
full explicit CLI, independent baseline hash, immutable refs, all seven Role
scopes, no extra privileges, image/controller drift, optional exact held pin,
nonroot mount layout and default-inert output.

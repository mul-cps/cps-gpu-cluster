# CPS fixed-launch remediation — 28 October 2026

## Installed scope

The CPS Hub Deployment (`jupyterhub/hub`, unchanged Deployment UID
`02fb8421-d323-4636-b006-2490cd6f5b63`) now runs the published compatibility image
`ghcr.io/mul-cps/cps-compute@sha256:f00f8c5b63bdce6348153aab6e11c1fd5cbf638ed1b50ef27bdda346ad202b75`.
The new Hub Pod is `hub-78f5698c64-d97bm`, UID
`a0af6346-9895-4fcd-a0cc-85bfb3044344`. It became Ready with no restarts.

The image is built from backport commit
`16fa7670601546ba7c1ec1bf58eb3e8b38c67619`, preserving the 20 existing Hub
modules, 84 SDK files and 137 installed package versions byte-for-byte. Only
the packaged directory-cache and fixed-request validation helpers were added.
Its Hub wheel SHA-256 is
`126d804a75e5a9029d5931a7b4dfc45e42910b3ce10ca31690a6e81ee3e55693`.

A targeted mounted-values update replaced exactly the four reviewed legacy
functions (`get_options_form`, `options_from_form`, `get_profile_list`,
`apply_profile_settings`), added the packaged directory cache, disabled default
optional network mounts, and selected the new `jupyter-notebook` ServiceAccount
with token automount disabled. Live function ASTs were first checked against
reviewed baseline `230b9b29`. Actual live profile images and all other Hub
configuration overlays were preserved. The proxy update replaced only the
allow-all predicate, preserving the remainder of the actual mounted notebook
configuration. Already running notebook processes do not reload that predicate.

The Hub image, values Secret reference and approval-publisher declaration were
updated together with Deployment UID/resourceVersion and prior-value tests.
The publisher declaration retains the actual Deployment identity and binds the
new image; a fresh `hub:cps` approval acknowledgment reports the new Hub Pod
UID and image. All other Hub Pod-spec fields were verified identical. There
was no Helm upgrade, Fleet reconciliation, driver change or notebook restart.

## Live checks

- A normal non-admin test account's authenticated REST request for
  `cpu-default` plus `custom_gpus=1` was rejected by the actual launch hook
  before Pod creation. The Hub log contained the fixed-profile rejection;
  no test-account Pod existed afterwards.
- An empty-options REST launch selected the server-owned CPU default and
  reached Jupyter readiness in **50.37 seconds**. This is one sample, not a
  p50/p95, warm/cold comparison or burst qualification.
- Its actual Pod UID was `cfa73545-4205-4328-a18d-ff15a37d0fea`, using
  `jupyter-notebook`, `automountServiceAccountToken: false`, no projected
  Kubernetes token and only its home PVC. It had no direct NFS volume or
  optional shared-storage PVC. The CPU image remained the existing live
  digest `efc3b485006f9d4e1e1b1eeacdd75c92bf00bfe02141f5d91ff28eaadb6eb72f`.
- Timeline: API request 09:24:25Z; LDAP timed out after approximately five
  seconds; Pod creation 09:24:33Z; KAI assignment 09:24:35Z; Longhorn attachment
  completed 09:25:00Z; image pulled in 381 ms and container started 09:25:01Z.
  Storage attachment dominated this sample. UID/GID cache does not cache the
  failed LDAP result and does not cache authorization/group membership.
- The controlled CPU server was stopped through the Hub API (HTTP 204) and
  its exact Pod deletion was confirmed. Its test account/home are retained.
- Research Pods for aditya, gottam and muslim retained their original UIDs,
  Running phase and zero restarts. Rino's CIT Pod retained UID
  `4e5aba5b-87f7-4755-b1c9-e90b127dab71`, Running phase and zero restarts.

Private backups and detailed logs are under
`/tmp/cps-fixed-launch-rollout-20261028/` on the operator host. They include
credentials-bearing values and are intentionally excluded from Git.

## Source checks and remaining boundary

The final combined launch/policy/proxy/pre-pull scope passed **86 tests plus
167 subtests**. The source Hub-image pairing test first failed on the default
chart Hub image and then passed on the exact published compatibility image. All Hub extraConfig blocks parse, Kustomize
renders, and the chart render includes the unprivileged ServiceAccount.

The source continuous/hook pullers now include every supported source fixed
profile reference, including the CPU digest, and exclude the unsupported Dask
image. This source correction was not applied to the live DaemonSets. Several
live notebook image overrides differ from the source profile table; those were
preserved, not silently promoted. Complete policy-catalog consolidation,
immutable pinning of the remaining tag references and measured pre-pull rollout
remain separate work.

CIT Xpra capability gating remains source-only. The production selected-Node
runtime assembly, complete shared lifecycle, all-device qualification,
coordinated restore and release gates remain open. This receipt proves the
named live CPS remediation and its controlled launch, not production readiness
for the full platform.

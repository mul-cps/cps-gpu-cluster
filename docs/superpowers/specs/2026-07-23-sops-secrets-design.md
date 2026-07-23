# Cluster-wide SOPS secrets encryption — design spec

Date: 2026-07-23
Status: proposed (not yet implemented)

## Problem

This repo currently has two secret-handling patterns, both flagged as
problems in prior incident docs (`docs/rancher-authentik-sso-plan.md`,
`docs/troubleshooting.md`):

1. **Plaintext secrets committed to git.** Confirmed live today:
   - `system/observability/monitoring/values.yaml:51` — Grafana `adminPassword: "admin"`
   - `user/jupyter/jupyterhub/postgresql.yaml` (`postgresql-secret`) and the
     duplicate in `values.yaml`'s `hub.db.url` — Postgres password
     (explicitly flagged "not addressed" in the SSO migration doc)
   - `user/jupyter/jupyterhub/values.yaml` — `LDAP_PASSWORD` hardcoded inside
     an inline Python `extraConfig` block
   - `user/jupyter/jupyterhub/values.yaml` — `proxy.secretToken` is a literal
     placeholder string (`"GENERATE_WITH_openssl_rand_-hex_32"`), not a real
     generated value
2. **Secrets applied out-of-band** via `kubectl create`/`kubectl patch`,
   documented in code comments but never version-controlled or
   Fleet-reconciled: Rancher's `genericoidc.yaml` `clientSecret`
   (`rancher-oidc-secret`/`cattle-system`), JupyterHub's
   `jupyterhub-oauth-secret`, and Open WebUI's OAuth client id/secret
   (referenced as "injected via patch" — the patch itself wasn't located
   during scoping and needs to be found during implementation).

Separately, `bootstrap-cluster/` (Terraform tfvars, Ansible group_vars)
keeps its real secrets *only* as local, gitignored files — never shared or
versioned, and a real credential (an OIDC `client_secret` and a weak
`rancher_bootstrap_password`) was previously committed in git history by
mistake (commit `5c16d55`, remediated in `2280a55` — but permanently
present in history since SOPS does not retroactively scrub git history).

## Constraint: don't duplicate the existing operator

A separate repo, `cit-teaching-platform`, already deploys
`sops-secrets-operator` (the `isindir/sops-secrets-operator`, watching
`SopsSecret` CRs) into this same `cit-cps-gpu` cluster via its own Fleet
GitRepo, using age recipient key
`age1h05qj66un22scwapuhyl76skls7ll235vlu27cjwkk5tpav6sqmsx3zp6a`.

This repo **must not** install a second operator instance — that would
create two controllers reconciling the same CRD/namespace and is a direct
ownership clash. Instead, this repo:

- Reuses the existing operator (assumed live in `sops-system`; verify with
  `kubectl get pods -n sops-system` and
  `kubectl get crd sopssecrets.isindir.io` before implementation — this
  could not be confirmed from a local session without cluster access).
- Encrypts to the **same age public key**, so the one already-mounted
  private key on that operator can decrypt secrets from both repos.
- Only ever adds `SopsSecret` manifests as ordinary Fleet bundle content —
  "just another Fleet bundle," never a second copy of the operator itself.

## Two encryption surfaces, one shared key

### 1. In-cluster K8s Secrets (`cluster-maintenance/`)

Existing plaintext `Secret` manifests and out-of-band `kubectl`-applied
secrets convert to `SopsSecret` CRs, co-located with the manifests that
already reference them (no new top-level directory — follows this repo's
existing "self-contained bundle" convention):

| Secret | New location | Notes |
|---|---|---|
| Grafana admin password | `system/observability/monitoring/` | replaces plaintext `adminPassword` |
| Postgres password | `user/jupyter/jupyterhub/` | fixes the two duplicated plaintext copies |
| LDAP bind password | `user/jupyter/jupyterhub/` | extracted out of the inline Python `extraConfig` block |
| JupyterHub proxy token | `user/jupyter/jupyterhub/` | replaces the placeholder string with a real generated + encrypted value |
| Rancher OIDC `clientSecret` | `rancher/` | see below — also the direct groundwork for the future Dex broker's client secrets |
| JupyterHub OAuth `client_secret` | `user/jupyter/jupyterhub/` | replaces the out-of-band `jupyterhub-oauth-secret` |
| Open WebUI OAuth client id/secret | `user/llm/open-webui/` | the existing "injected via patch" mechanism must be located during implementation before it can be converted |

`rancher/` currently has no `fleet.yaml` (a documented, deliberate
exception to the Fleet-only rule, because its secret had to be
hand-patched). Since secrets can now be committed encrypted, this spec
**ends that exception**: `rancher/` gets a `fleet.yaml` and becomes a
normal Fleet-reconciled bundle, with its `clientSecret` as a `SopsSecret`.

### 2. Local IaC secrets (`bootstrap-cluster/`)

`bootstrap-cluster/terraform/*.tfvars` (real, non-`example.tfvars` files)
and `bootstrap-cluster/ansible/group_vars/*.yml` real-value overrides get
SOPS-encrypted with the `sops` CLI directly (not the CRD mechanism — these
are local files consumed by `tofu`/`ansible-playbook` on an operator's
workstation, not Kubernetes objects). Same age recipient key as above.

Operators decrypt on demand rather than keeping a permanent plaintext copy:

```bash
sops exec-env terraform.tfvars 'tofu apply'
```

or equivalent for Ansible var files. This replaces the current
gitignore-only, never-shared pattern with encrypted-and-committed files,
while keeping the raw private age key itself off any machine that doesn't
need it (same handling as the SSH keys already gitignored today).

## `.sops.yaml`

One root-level `.sops.yaml`, mirroring `cit-teaching-platform`'s
regex-driven `creation_rules` style for consistency across the two repos
sharing an operator:

```yaml
creation_rules:
  - path_regex: cluster-maintenance/.*-sopssecret\.yaml$
    encrypted_regex: "^(stringData)$"
    age: age1h05qj66un22scwapuhyl76skls7ll235vlu27cjwkk5tpav6sqmsx3zp6a

  - path_regex: bootstrap-cluster/(terraform/.*\.tfvars|ansible/group_vars/.*\.ya?ml)$
    age: age1h05qj66un22scwapuhyl76skls7ll235vlu27cjwkk5tpav6sqmsx3zp6a
```

(`example.tfvars` stays out of scope — it's an intentional placeholder
template, not a real-secret file.)

## Explicit non-goals

- **Git-history-leaked credentials are not scrubbed.** The old Rancher OIDC
  `client_secret`, the old `rancher_bootstrap_password: "admin"`, and the
  old JupyterHub OAuth `client_secret` remain permanently readable via
  `git log`/`git show`. This spec's deliverable includes a rotation
  checklist (rotate each in Authentik) as a tracked follow-up action, not
  an automated fix — SOPS encrypts future state, not history.
- **TLS certificates are out of scope.** `dshl-wildcard`,
  `wildcard-cps-cert`, and `openwebui-tls` stay on their current
  cert-manager-issued / manually-copied path. They're not application
  secrets in the same sense, and folding them into SOPS+Reflector is a
  separate, later decision if wanted.
- **This spec does not touch Dex/Rancher IdP broker work.** That's a
  separate, subsequent spec that will build on top of this one (Dex's
  connector client secrets will use the `SopsSecret` pattern established
  here).

## Optional follow-up: git history rewrite

Rotating the git-history-leaked credentials (above) is mandatory and
sufficient to neutralize the exposure — a rotated credential is worthless
even if its old value stays visible in history. Scrubbing the values from
git history itself (e.g. `git filter-repo`) is a **separate, optional**
piece of cleanup, not required by this spec and not performed as part of
it. It is destructive and disruptive:

- Rewrites every commit hash from the point of introduction onward,
  breaking all existing clones, forks, and open branches/PRs — everyone
  must re-clone.
- Requires a force-push to `main`.
- Does not retroactively erase copies that already exist outside the
  canonical repo (forks, CI logs, local clones made before the rewrite) —
  it reduces future exposure, it does not undo past exposure.

If this is wanted, it should be a deliberate, explicitly-requested,
separately-scheduled operation performed only after rotation is confirmed
complete — never bundled into the SOPS migration itself.

## Documentation deliverable

`docs/sops-secrets-migration.md` (dated, following the
`rancher-authentik-sso-plan.md` style), covering:
- The shared-operator model and why a second operator instance was
  deliberately avoided.
- The local `sops` CLI workflow for `bootstrap-cluster/`.
- The full list of secrets migrated, old location → new `SopsSecret`
  location.
- The credential-rotation checklist for git-history-leaked values.

At implementation time, use parallel documentation-update agents (one per
affected area: `cluster-maintenance/system`, `cluster-maintenance/user`,
`bootstrap-cluster`, plus the new migration doc) rather than a single
serial pass, per user instruction.

## Verification before implementation

- Confirm `sops-secrets-operator` is actually live in `cit-cps-gpu`
  (`kubectl get pods -n sops-system`,
  `kubectl get crd sopssecrets.isindir.io`) and note its exact namespace —
  this spec assumes `sops-system` by analogy with `cit-teaching-platform`
  but that must be verified against the real cluster, not assumed.
- Confirm the shared age key is the correct one to encrypt to (i.e. that
  this is genuinely the operator instance serving `cit-cps-gpu`, not a
  namespace-scoped instance limited to `cit-teaching-platform`'s own
  resources).

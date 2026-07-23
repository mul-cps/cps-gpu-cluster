# SOPS Cluster-Wide Secrets Encryption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace plaintext/out-of-band secrets across `cluster-maintenance/` and `bootstrap-cluster/` with SOPS-encrypted equivalents, reusing the `sops-secrets-operator` already deployed to this cluster by `cit-teaching-platform`.

**Architecture:** One shared age keypair (recipient `age1h05qj66un22scwapuhyl76skls7ll235vlu27cjwkk5tpav6sqmsx3zp6a`, already held by the live operator) encrypts two kinds of content: `SopsSecret` CRs for in-cluster K8s Secrets (decrypted by the existing operator, delivered as Fleet bundle content), and directly `sops`-encrypted `.tfvars`/Ansible `group_vars` files for local IaC use (decrypted on demand via `sops exec-env`). No new operator is deployed.

**Tech Stack:** SOPS CLI, age, `isindir/sops-secrets-operator` CRD (`SopsSecret`), Rancher Fleet, Helm values, Ansible, Terraform/OpenTofu.

## Global Constraints

- Do **not** deploy a second `sops-secrets-operator` instance — reuse the one `cit-teaching-platform` already runs in this cluster (verify namespace before Task 1).
- Encrypt everything to the existing shared age public key `age1h05qj66un22scwapuhyl76skls7ll235vlu27cjwkk5tpav6sqmsx3zp6a` — do not generate a new keypair.
- `example.tfvars` stays a plaintext template — never encrypt it.
- Git-history-leaked credentials (old Rancher OIDC secret, old `rancher_bootstrap_password`, old JupyterHub OAuth secret) are rotated in Authentik as part of this plan, but git history itself is **not** rewritten — that's optional, separate, and out of scope (see spec's "Optional follow-up" section).
- TLS certs (`dshl-wildcard`, `wildcard-cps-cert`, `openwebui-tls`) are out of scope — leave their current cert-manager/manual handling untouched.
- Every manifest change in `cluster-maintenance/` must go through Fleet (edit + commit; Fleet reconciles) — never `kubectl apply` by hand, except where a task explicitly says to verify live cluster state read-only.
- Spec: `docs/superpowers/specs/2026-07-23-sops-secrets-design.md`

---

### Task 1: Verify the shared operator and record its details

**Files:**
- Create: `docs/sops-secrets-migration.md` (start the doc here; filled in further by later tasks)

**Interfaces:**
- Produces: confirmed facts (operator namespace, CRD group/version, age public key in use) that every later task's `SopsSecret` manifests depend on.

- [ ] **Step 1: Check the operator is live**

Run: `kubectl get pods -n sops-system`
Expected: at least one `sops-secrets-operator` pod in `Running` state. If the namespace doesn't exist or is empty, STOP — do not proceed with this plan until the operator's actual location is confirmed with whoever manages `cit-teaching-platform`'s Fleet deployment (it may be a different namespace than assumed).

- [ ] **Step 2: Confirm the CRD and its API group**

Run: `kubectl get crd sopssecrets.isindir.github.com -o jsonpath='{.spec.group}/{.spec.versions[0].name}'`
Expected: output like `isindir.github.com/v1alpha3` (record the exact version — later `SopsSecret` manifests must use it).

- [ ] **Step 3: Confirm the operator's age public key matches the design assumption**

Run: `kubectl get secret sops-age-key -n sops-system -o jsonpath='{.data.age\.agekey}' | base64 -d | age-keygen -y`
Expected: `age1h05qj66un22scwapuhyl76skls7ll235vlu27cjwkk5tpav6sqmsx3zp6a`. If it differs, STOP and update the spec/plan with the real key before continuing — every later task encrypts to whatever key this step confirms.

- [ ] **Step 4: Start the migration doc with these confirmed facts**

Write `docs/sops-secrets-migration.md`:

```markdown
# SOPS secrets migration

Date: 2026-07-23
Spec: docs/superpowers/specs/2026-07-23-sops-secrets-design.md

## Shared operator

This repo reuses the `sops-secrets-operator` deployed by the
`cit-teaching-platform` repo into this cluster. This repo never deploys
its own instance.

- Namespace: `sops-system`
- CRD: `sopssecrets.isindir.github.com` (`<version from Step 2>`)
- Age recipient key: `age1h05qj66un22scwapuhyl76skls7ll235vlu27cjwkk5tpav6sqmsx3zp6a`

Verified live 2026-07-23 via `kubectl get pods -n sops-system` and
`kubectl get crd sopssecrets.isindir.github.com`.

## Secrets migrated

(filled in as each is migrated — see table below)

| Secret | Old location | New location | Status |
|---|---|---|---|
```

- [ ] **Step 5: Commit**

```bash
git add docs/sops-secrets-migration.md
git commit -m "docs(sops): start migration doc, confirm shared operator details

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NwvkBV9MrW8jBTiTprtsgb"
```

---

### Task 2: Add root `.sops.yaml`

**Files:**
- Create: `.sops.yaml`

**Interfaces:**
- Consumes: age public key confirmed in Task 1 Step 3.
- Produces: `creation_rules` that every subsequent `sops -e` call in this plan relies on.

- [ ] **Step 1: Write `.sops.yaml`**

```yaml
# SOPS configuration for cps-gpu-cluster.
# Shares an age keypair with the cit-teaching-platform repo's
# sops-secrets-operator, already deployed into this cluster — see
# docs/sops-secrets-migration.md. Do not generate a new keypair here.

creation_rules:
  # In-cluster K8s Secrets, decrypted by the shared sops-secrets-operator.
  - path_regex: cluster-maintenance/.*-sopssecret\.yaml$
    encrypted_regex: "^(stringData)$"
    age: age1h05qj66un22scwapuhyl76skls7ll235vlu27cjwkk5tpav6sqmsx3zp6a

  # Local IaC secrets, decrypted on demand via `sops exec-env`.
  - path_regex: bootstrap-cluster/(terraform/.*\.tfvars|ansible/group_vars/.*\.ya?ml)$
    age: age1h05qj66un22scwapuhyl76skls7ll235vlu27cjwkk5tpav6sqmsx3zp6a
```

- [ ] **Step 2: Verify sops can read the config**

Run: `sops --config .sops.yaml -e --output-type yaml /dev/null 2>&1 | head -5 || true`

This is a smoke test that `.sops.yaml` parses — a real encrypt happens in later tasks against real files. Expected: no YAML parse error from `sops` (an error about missing input is fine and expected here).

- [ ] **Step 3: Commit**

```bash
git add .sops.yaml
git commit -m "feat(sops): add root .sops.yaml, share age key with cit-teaching-platform's operator

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NwvkBV9MrW8jBTiTprtsgb"
```

---

### Task 3: Migrate Grafana admin password to a `SopsSecret`

**Files:**
- Create: `cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring/grafana-sopssecret.yaml`
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring/values.yaml:51`
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring/README.md` (remove "Password: admin" / default-password language)

**Interfaces:**
- Consumes: `.sops.yaml` rule from Task 2 (`*-sopssecret.yaml$` path match), operator/CRD version from Task 1.
- Produces: K8s Secret `grafana-admin-credentials` in the monitoring namespace, key `admin-password`, for the `values.yaml` change in this task to reference.

- [ ] **Step 1: Generate a real random password**

Run: `openssl rand -base64 24`
Record the output — used in the next step, then discard from your shell history (`history -d` or equivalent) once encrypted.

- [ ] **Step 2: Write the plaintext `SopsSecret`, matching the CRD version from Task 1**

```yaml
apiVersion: isindir.github.com/v1alpha3
kind: SopsSecret
metadata:
  name: grafana-admin-credentials
  namespace: monitoring
spec:
  secretTemplates:
    - name: grafana-admin-credentials
      stringData:
        admin-password: "PASTE_GENERATED_PASSWORD_HERE"
```

Save this to `cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring/grafana-sopssecret.yaml`. Replace `apiVersion` with whatever Task 1 Step 2 actually confirmed if it differs from `isindir.github.com/v1alpha3`.

- [ ] **Step 3: Encrypt the file in place**

Run: `sops -e -i cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring/grafana-sopssecret.yaml`
Expected: `stringData.admin-password` is now a `sops`-encrypted blob (ENC[AES256_GCM,...]); everything else in the file stays readable YAML.

- [ ] **Step 4: Point Grafana at the new Secret instead of a literal password**

In `cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring/values.yaml`, replace line 51:

```yaml
# before
adminPassword: "admin"  # Change this in production!
```

```yaml
# after
admissionExistingSecret: grafana-admin-credentials  # verify against the chart's exact key name below
```

Check the actual Helm chart's key for "use an existing Secret for the admin password" (`helm show values <grafana chart> | grep -i existingsecret`, or the upstream `kube-prometheus-stack`/`grafana` chart docs) — the common key is `grafana.admin.existingSecret` with `userKey`/`passwordKey` set to `admin-user`/`admin-password`. Use whatever the chart in this repo actually exposes; do not guess blindly, confirm against `helm show values` output for the pinned chart version in `fleet.yaml`.

- [ ] **Step 5: Update the README to remove the default-password language**

Edit `system/observability/monitoring/README.md` lines ~92 and ~247 — remove "Password: `admin`" and replace with a pointer: "Admin password is SOPS-encrypted in `grafana-sopssecret.yaml`; retrieve with `sops -d grafana-sopssecret.yaml` if you have decrypt access."

- [ ] **Step 6: Commit**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring/
git commit -m "fix(monitoring): replace plaintext Grafana admin password with SopsSecret

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NwvkBV9MrW8jBTiTprtsgb"
```

- [ ] **Step 7: Verify after Fleet reconciles**

Run: `kubectl get secret grafana-admin-credentials -n monitoring -o jsonpath='{.data.admin-password}' | base64 -d | wc -c`
Expected: a non-zero byte count matching the generated password length (confirms the operator decrypted it into a real Secret). Then confirm Grafana login works with the new password via port-forward or ingress.

- [ ] **Step 8: Record in the migration doc**

Append a row to the table in `docs/sops-secrets-migration.md`:
`| Grafana admin password | system/observability/monitoring/values.yaml:51 (plaintext) | system/observability/monitoring/grafana-sopssecret.yaml | done |`

Commit: `git add docs/sops-secrets-migration.md && git commit -m "docs(sops): record Grafana password migration"`

---

### Task 4: Migrate JupyterHub Postgres password to a `SopsSecret`

**Files:**
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/postgresql.yaml` (remove the plaintext `Secret`, keep the rest)
- Create: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/postgres-sopssecret.yaml`
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml:44` (remove duplicated plaintext password from `db_url`)

**Interfaces:**
- Consumes: `.sops.yaml` rule from Task 2, CRD version from Task 1.
- Produces: K8s Secret `postgresql-secret` (same name as before, so the existing `secretKeyRef`s in `postgresql.yaml`'s Deployment env keep working unmodified) with the same three keys (`postgres-db`, `postgres-user`, `postgres-password`).

- [ ] **Step 1: Generate a new random password (rotating the old, now-compromised one)**

Run: `openssl rand -base64 24`
The old value `jhub-secure-db-password-2025` is being retired, not reused — it was committed in plaintext and must be treated as burned.

- [ ] **Step 2: Write the `SopsSecret`, preserving the exact Secret name and keys the Deployment already references**

```yaml
apiVersion: isindir.github.com/v1alpha3
kind: SopsSecret
metadata:
  name: postgresql-secret
  namespace: jupyterhub
spec:
  secretTemplates:
    - name: postgresql-secret
      labels:
        app.kubernetes.io/name: postgresql
        app.kubernetes.io/component: database
      stringData:
        postgres-password: "PASTE_NEW_GENERATED_PASSWORD_HERE"
        postgres-user: "jhub"
        postgres-db: "jhub"
```

Save to `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/postgres-sopssecret.yaml`.

- [ ] **Step 3: Encrypt in place**

Run: `sops -e -i cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/postgres-sopssecret.yaml`

- [ ] **Step 4: Remove the plaintext `Secret` block from `postgresql.yaml`**

In `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/postgresql.yaml`, delete lines 9-20 (the whole `kind: Secret` document, from `apiVersion: v1` through `postgres-db: "jhub"`, including its trailing `---` separator) — the `SopsSecret` from Step 2 now produces the same Secret object. Leave the `Deployment`, `PersistentVolumeClaim`, and `Service` documents untouched; their `secretKeyRef`s already point at `postgresql-secret` by name and need no changes.

- [ ] **Step 5: Fix the duplicated plaintext password in `values.yaml`**

In `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml` line 44, replace:

```yaml
# before
db_url: postgresql://jhub:jhub-secure-db-password-2025@postgresql:5432/jhub
```

Check what JupyterHub's Helm chart actually supports for this — `hub.db.url` typically also accepts a `$(POSTGRES_PASSWORD)`-style env substitution if `hub.extraEnv` sources it from a `secretKeyRef`, or a separate `hub.db.password` values key that reads from an existing secret. Confirm via `helm show values <jupyterhub chart>` for the pinned version. Use whichever mechanism the chart supports to reference `postgresql-secret`/`postgres-password` instead of a literal value — do not leave a plaintext password in `values.yaml` under any key.

- [ ] **Step 6: Commit**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/
git commit -m "fix(jupyterhub): replace plaintext Postgres password with SopsSecret

Also fixes the duplicated plaintext copy in values.yaml's db_url —
this was the exposure explicitly flagged as 'not addressed' in
docs/rancher-authentik-sso-plan.md.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NwvkBV9MrW8jBTiTprtsgb"
```

- [ ] **Step 7: Verify after Fleet reconciles**

Run: `kubectl get secret postgresql-secret -n jupyterhub -o jsonpath='{.data.postgres-password}' | base64 -d`
Expected: the new generated password, not the old `jhub-secure-db-password-2025`.

Run: `kubectl logs -n jupyterhub deploy/hub --tail=50 | grep -i "database\|postgres"`
Expected: no auth failures against Postgres (confirms the hub picked up the new password consistently).

- [ ] **Step 8: Record in the migration doc and note the rotation**

Append to `docs/sops-secrets-migration.md`'s table:
`| Postgres password | postgresql.yaml (plaintext) + values.yaml db_url (duplicate) | postgres-sopssecret.yaml | done, rotated |`

Also add to a new "## Credential rotation checklist" section (create if it doesn't exist yet):
`- [x] JupyterHub Postgres password — rotated 2026-07-23 (was jhub-secure-db-password-2025, plaintext in git)`

Commit: `git add docs/sops-secrets-migration.md && git commit -m "docs(sops): record Postgres password migration and rotation"`

---

### Task 5: Extract and migrate the hardcoded LDAP password

**Files:**
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml` (lines ~274, ~280 — the `02-profiles` `extraConfig` block)
- Create: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/ldap-sopssecret.yaml`

**Interfaces:**
- Consumes: `.sops.yaml` rule from Task 2.
- Produces: K8s Secret `jupyterhub-ldap-credentials`, key `bind-password`, injected into the hub pod as env var `LDAP_BIND_PASSWORD` for the `extraConfig` Python to read.

- [ ] **Step 1: Read the current `extraConfig` block to see exact surrounding code**

Read `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml` around lines 260-290 in full before editing — the plan can't show a diff against code it hasn't loaded fresh; confirm the exact current indentation and variable names (`LDAP_PASSWORD` per the inventory) before changing anything.

- [ ] **Step 2: Write the `SopsSecret`**

Generate nothing new here — this is an existing service-account credential (`ldapservice`'s password), not something to regenerate blindly, since rotating an LDAP bind account may need coordination with whoever administers that directory. Use the existing value `ldapservice` as a placeholder to encrypt for now, and flag rotation as a manual follow-up (LDAP bind accounts are typically centrally managed, unlike an app-generated Postgres password).

```yaml
apiVersion: isindir.github.com/v1alpha3
kind: SopsSecret
metadata:
  name: jupyterhub-ldap-credentials
  namespace: jupyterhub
spec:
  secretTemplates:
    - name: jupyterhub-ldap-credentials
      stringData:
        bind-password: "ldapservice"
```

Save to `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/ldap-sopssecret.yaml`, then `sops -e -i` it.

- [ ] **Step 3: Add an env var sourcing it, alongside the existing OAuth env var pattern**

In `values.yaml`'s `hub.extraEnv` list (same list already used for `OAUTH_CLIENT_SECRET` per the existing `jupyterhub-oauth-secret` pattern — find and match that list's exact YAML shape), add:

```yaml
- name: LDAP_BIND_PASSWORD
  valueFrom:
    secretKeyRef:
      name: jupyterhub-ldap-credentials
      key: bind-password
```

- [ ] **Step 4: Replace the hardcoded value in the `extraConfig` Python block**

Change the line(s) around 274/280 from:

```python
LDAP_PASSWORD = 'ldapservice'
```

to:

```python
LDAP_PASSWORD = os.environ['LDAP_BIND_PASSWORD']
```

(matching however `os` is already imported/used elsewhere in that same `extraConfig` block, per the existing `OAUTH_CLIENT_SECRET` handling.)

- [ ] **Step 5: Commit**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/
git commit -m "fix(jupyterhub): move hardcoded LDAP bind password out of values.yaml into SopsSecret

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NwvkBV9MrW8jBTiTprtsgb"
```

- [ ] **Step 6: Verify**

Run: `kubectl logs -n jupyterhub deploy/hub --tail=100 | grep -i ldap`
Expected: no LDAP auth errors, no `KeyError: 'LDAP_BIND_PASSWORD'`.

- [ ] **Step 7: Record in migration doc + rotation checklist**

Add row + rotation checklist item (mark as "flagged for manual rotation, coordinate with directory admin" rather than done, since this plan reuses the existing value).

---

### Task 6: Generate a real JupyterHub proxy token and encrypt it

**Files:**
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml:2`
- Create: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/proxy-sopssecret.yaml`

**Interfaces:**
- Consumes: `.sops.yaml` rule from Task 2.
- Produces: K8s Secret `jupyterhub-proxy-token`, key `proxy-token`.

- [ ] **Step 1: Generate a real token**

Run: `openssl rand -hex 32`

- [ ] **Step 2: Write and encrypt the `SopsSecret`**

```yaml
apiVersion: isindir.github.com/v1alpha3
kind: SopsSecret
metadata:
  name: jupyterhub-proxy-token
  namespace: jupyterhub
spec:
  secretTemplates:
    - name: jupyterhub-proxy-token
      stringData:
        proxy-token: "PASTE_GENERATED_HEX_TOKEN"
```

Save to `proxy-sopssecret.yaml`, then `sops -e -i` it.

- [ ] **Step 3: Point `values.yaml` at the Secret instead of the placeholder string**

Check the JupyterHub chart's exact key for sourcing `proxy.secretToken` from an existing Secret (`helm show values <chart>` — commonly `proxy.secretToken` accepts a literal only, and the existing-Secret approach is instead `hub.extraEnv` + `CONFIGPROXY_AUTH_TOKEN` env var, which the chart's proxy and hub both read directly, making `proxy.secretToken` itself unnecessary). Replace line 2's placeholder accordingly — do not leave `"GENERATE_WITH_openssl_rand_-hex_32"` in the file.

- [ ] **Step 4: Commit**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/
git commit -m "fix(jupyterhub): replace proxy secretToken placeholder with real generated SopsSecret

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NwvkBV9MrW8jBTiTprtsgb"
```

- [ ] **Step 5: Verify**

Run: `kubectl logs -n jupyterhub deploy/proxy --tail=50`
Expected: proxy starts cleanly, no auth-token mismatch errors between hub and proxy pods.

- [ ] **Step 6: Record in migration doc**

---

### Task 7: Bring `rancher/` into Fleet and SOPS-encrypt its `clientSecret`

**Files:**
- Create: `cluster-maintenance/clusters/cit-cps-gpu/rancher/fleet.yaml`
- Create: `cluster-maintenance/clusters/cit-cps-gpu/rancher/oidc-sopssecret.yaml`
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/rancher/genericoidc.yaml` (remove the "applied by hand" comment block; reference the new Secret instead of the `kubectl patch` workflow)
- Modify: `docs/rancher-authentik-sso-plan.md` (update to reflect Fleet management, since it currently documents the hand-apply exception as permanent)

**Interfaces:**
- Consumes: `.sops.yaml` rule, CRD version from Task 1.
- Produces: K8s Secret `rancher-oidc-secret` in `cattle-system`, key `clientSecret` — this is also what the future Dex spec will point Dex's connector config at, so keep this exact name/namespace/key stable.

- [ ] **Step 1: Confirm the AuthConfig CRD does NOT support `secretKeyRef` (it doesn't — verified in the existing SSO doc: fields are set directly on the object, not via K8s Secret references)**

This means we can't just point `genericoidc.yaml` at a Secret the way Deployments do. Read `docs/rancher-authentik-sso-plan.md` in full before this task — Rancher's `AuthConfig` requires `clientSecret` to be a literal field on the object itself, patched in after apply. The `SopsSecret` here holds the value; a small controller-free mechanism is still needed to get it from the Secret into the `AuthConfig` object, since Rancher doesn't read Secrets for this field.

- [ ] **Step 2: Decide the sync mechanism — Fleet cannot patch a value from one object into another's spec field. Use a Fleet Helm chart with a post-render, or a small in-repo Job**

Simplest option consistent with existing repo patterns (no new tooling): a Kubernetes `Job` in the `rancher/` bundle that runs on every Fleet reconcile, reads the Secret, and `kubectl patch`es the `AuthConfig` — same operation as the manual step today, just automated and idempotent instead of a human running it once.

Write `cluster-maintenance/clusters/cit-cps-gpu/rancher/oidc-sync-job.yaml`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: rancher-oidc-sync
  namespace: cattle-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: rancher-oidc-sync
rules:
  - apiGroups: ["management.cattle.io"]
    resources: ["authconfigs"]
    verbs: ["get", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: rancher-oidc-sync
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: rancher-oidc-sync
subjects:
  - kind: ServiceAccount
    name: rancher-oidc-sync
    namespace: cattle-system
---
apiVersion: batch/v1
kind: Job
metadata:
  name: rancher-oidc-sync
  namespace: cattle-system
  annotations:
    fleet.cattle.io/apply-once: "false"
spec:
  backoffLimit: 3
  template:
    spec:
      serviceAccountName: rancher-oidc-sync
      restartPolicy: OnFailure
      containers:
        - name: sync
          image: bitnami/kubectl:1.30
          command:
            - sh
            - -c
            - |
              set -eu
              SECRET=$(kubectl get secret rancher-oidc-secret -n cattle-system -o jsonpath='{.data.clientSecret}' | base64 -d)
              kubectl patch authconfig genericoidc --type merge -p "{\"clientSecret\":\"$SECRET\"}"
```

Note: Fleet's default Job handling only runs a Job once per unique manifest content unless `fleet.cattle.io/apply-once: "false"` or the Job is given a content-derived name suffix — verify this against Fleet's actual Job re-run semantics for the deployed Fleet version before relying on it (`kubectl get bundle rancher -n fleet-local -o yaml` after first apply, confirm the Job actually reruns when the Secret's content changes — if it doesn't, switch to a `CronJob` on a modest interval, e.g. hourly, instead).

- [ ] **Step 3: Write the `fleet.yaml`**

```yaml
defaultNamespace: cattle-system
```

Save to `cluster-maintenance/clusters/cit-cps-gpu/rancher/fleet.yaml`. Keep it minimal — this bundle has no chart, just raw manifests (`genericoidc.yaml`, `oidc-sopssecret.yaml`, `oidc-sync-job.yaml`), matching how other raw-manifest bundles in this repo are structured (check an existing raw-manifest `system/` bundle for the exact convention before finalizing).

- [ ] **Step 4: Write and encrypt the `SopsSecret`**

Use the actual current live `clientSecret` value (retrieve it from the running cluster — do NOT invent a new one, this would break the existing Authentik OAuth provider registration unless also rotated there):

Run: `kubectl get secret rancher-oidc-secret -n cattle-system -o jsonpath='{.data.clientSecret}' | base64 -d`

```yaml
apiVersion: isindir.github.com/v1alpha3
kind: SopsSecret
metadata:
  name: rancher-oidc-secret
  namespace: cattle-system
spec:
  secretTemplates:
    - name: rancher-oidc-secret
      stringData:
        clientSecret: "PASTE_VALUE_RETRIEVED_ABOVE"
```

Save to `oidc-sopssecret.yaml`, then `sops -e -i` it.

- [ ] **Step 5: Update `genericoidc.yaml`'s comments to reflect the new Fleet-managed flow**

Remove the header comment block (lines 6-27 per the current file) describing manual `kubectl apply`/`kubectl patch` steps and the "bypasses Fleet entirely" note. Replace with a short comment: "Fleet-managed since 2026-07-23 — see rancher/oidc-sync-job.yaml, which patches clientSecret in from the rancher-oidc-secret SopsSecret. See docs/sops-secrets-migration.md."

Set `enabled: true` if not already (per the SSO doc, this is already live) — verify current live state first with `kubectl get authconfig genericoidc -o jsonpath='{.enabled}'` before changing anything in git, so this edit matches reality rather than assuming.

- [ ] **Step 6: Commit**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/rancher/
git commit -m "feat(rancher): bring rancher/ under Fleet management, SOPS-encrypt OIDC clientSecret

Ends the documented 'no Fleet' exception for this directory now that
secrets can be committed encrypted. Adds an in-cluster sync Job since
Rancher's AuthConfig CRD requires clientSecret as a literal field, not
a Secret reference.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NwvkBV9MrW8jBTiTprtsgb"
```

- [ ] **Step 7: Verify end-to-end**

Run: `kubectl get bundle rancher -n fleet-local` — expect `Active`/`Ready`.
Run: `kubectl get job rancher-oidc-sync -n cattle-system` — expect `Complete`.
Then do a real browser login through Rancher's OIDC flow to confirm the patched `clientSecret` still works.

- [ ] **Step 8: Update `docs/rancher-authentik-sso-plan.md`**

Edit the line stating `rancher/` "has no `fleet.yaml` — a documented exception to the Fleet-only rule" — update it to note this changed 2026-07-23, with a pointer to `docs/sops-secrets-migration.md`.

- [ ] **Step 9: Commit docs and record migration**

```bash
git add docs/rancher-authentik-sso-plan.md docs/sops-secrets-migration.md
git commit -m "docs: update SSO plan to reflect rancher/ joining Fleet management"
```

---

### Task 8: Migrate JupyterHub's OAuth `client_secret` to a `SopsSecret`

**Files:**
- Create: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/oauth-sopssecret.yaml`
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml` (comment update only — the `secretKeyRef` to `jupyterhub-oauth-secret` already exists and needs no code change, per the inventory)

**Interfaces:**
- Consumes: `.sops.yaml` rule.
- Produces: K8s Secret `jupyterhub-oauth-secret`, key `client-secret` (must match the existing `secretKeyRef` exactly — do not rename).

- [ ] **Step 1: Retrieve the current live value (do not invent a new one, or Authentik's registered client breaks)**

Run: `kubectl get secret jupyterhub-oauth-secret -n jupyterhub -o jsonpath='{.data.client-secret}' | base64 -d`

- [ ] **Step 2: Write and encrypt the `SopsSecret`**

```yaml
apiVersion: isindir.github.com/v1alpha3
kind: SopsSecret
metadata:
  name: jupyterhub-oauth-secret
  namespace: jupyterhub
spec:
  secretTemplates:
    - name: jupyterhub-oauth-secret
      stringData:
        client-secret: "PASTE_VALUE_RETRIEVED_ABOVE"
```

Save to `oauth-sopssecret.yaml`, then `sops -e -i` it.

- [ ] **Step 3: Add a comment in `values.yaml` near the existing `secretKeyRef` pointing to the new source of truth**

Add: `# client-secret sourced from jupyterhub-oauth-secret, now SOPS-managed — see oauth-sopssecret.yaml`

- [ ] **Step 4: Commit**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/
git commit -m "fix(jupyterhub): bring out-of-band OAuth client secret under SOPS/Fleet management

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NwvkBV9MrW8jBTiTprtsgb"
```

- [ ] **Step 5: Verify**

Test a real JupyterHub OAuth login through Authentik after Fleet reconciles — confirms the `SopsSecret`-produced Secret matches what Authentik has registered.

- [ ] **Step 6: Record in migration doc**

---

### Task 9: Locate and migrate Open WebUI's OAuth client secret

**Files:**
- Investigate first (see Step 1) — exact file to modify is not yet known.
- Likely create: `cluster-maintenance/clusters/cit-cps-gpu/user/llm/open-webui/oauth-sopssecret.yaml`

**Interfaces:**
- Consumes: `.sops.yaml` rule.
- Produces: K8s Secret with Open WebUI's OAuth client id/secret — exact name TBD by Step 1's findings.

- [ ] **Step 1: Find the "injected via patch" mechanism referenced in `values.yaml`'s comment**

Run: `grep -rn "OAUTH_CLIENT\|patch" cluster-maintenance/clusters/cit-cps-gpu/user/llm/ cluster-maintenance/clusters/cit-cps-gpu/.vcluster-ckf/ 2>/dev/null`
Also check for a Fleet `kustomize`/overlay patch mechanism: `find cluster-maintenance -iname "*patch*" -path "*open-webui*"`, and check live cluster state: `kubectl get deploy -n <open-webui namespace> -o yaml | grep -i oauth` to see what env vars/Secret refs are actually live, since the source manifest wasn't found in the original scoped search.

- [ ] **Step 2: Once located, apply the same pattern as Task 8** — retrieve the live value, write a `SopsSecret` preserving the existing Secret name/keys, encrypt, commit, verify with a real OAuth login test.

(This task's remaining steps mirror Task 8's Steps 1-6 exactly, applied to whatever Step 1 here finds — do not guess the file path or Secret name ahead of investigation.)

- [ ] **Step 3: Record in migration doc**

---

### Task 10: SOPS-encrypt real Terraform `tfvars` and Ansible `group_vars`

**Files:**
- Modify: `bootstrap-cluster/terraform/terraform.tfvars` (if it exists locally — this file is gitignored today; check with whoever holds it)
- Modify: `bootstrap-cluster/ansible/group_vars/all.yml` (only the real-value overrides, not the Jinja/lookup-based generated ones)
- Create: `bootstrap-cluster/README.md` addendum or new section documenting the `sops exec-env` workflow

**Interfaces:**
- Consumes: `.sops.yaml` rule from Task 2 (`bootstrap-cluster/(terraform/.*\.tfvars|ansible/group_vars/.*\.ya?ml)$`).
- Produces: encrypted, git-committed versions of files that were previously local-only/gitignored.

- [ ] **Step 1: Confirm what's actually in `group_vars/all.yml` today that's a real secret vs. a Jinja lookup**

Read `bootstrap-cluster/ansible/group_vars/all.yml` in full. Per the inventory: `k3s_token` and `rancher_bootstrap_password` are already runtime-generated via Ansible `lookup('password', ...)` — these don't need SOPS since nothing plaintext is committed. Only variables holding real static values (if any exist beyond what was found) are candidates. If none exist beyond the already-safe lookup-based ones, this half of the task is a no-op for `group_vars/` — do not invent secrets to encrypt where none exist.

- [ ] **Step 2: `terraform.tfvars` is confirmed LOST — recreate it, do not search further for a copy**

Confirmed 2026-07-23: the real `terraform.tfvars` no longer exists anywhere it was kept; it must be recreated from scratch rather than retrieved. This is a real credential-recreation task, not a file-hunt:

1. `pm_api_token_secret` — generate a **new** Proxmox API token (Datacenter → Permissions → API Tokens in the Proxmox web UI), since the old one's value is unrecoverable and should be treated as dead (revoke the old token ID if it still exists and is identifiable, to avoid an orphaned live credential). This step requires access to the Proxmox web UI — it cannot be done via this repo or kubectl; escalate to the human operator to perform it and hand back the new token value.
2. `vm_password` — regenerate via `scripts/generate-password-hash.sh` (interactive, prompts for a new password, prints a SHA-512 hash to stdout — never persists the plaintext).
3. `ssh_public_key` — reuse the existing public key if the corresponding private key (`~/.ssh/id_rsa` per `ansible.cfg`) is still available locally; otherwise generate a new keypair and redistribute the public key to existing VMs' `authorized_keys` (out of scope for this task — flag as a separate follow-up if a new keypair is needed).
4. Other non-secret `tfvars` values (VM counts, network ranges, etc.) — copy from `bootstrap-cluster/terraform/example.tfvars`'s structure and the "Key facts to keep straight" section of `CLAUDE.md` (network `10.21.0.0/16`, control planes `.35-37`, GPU workers `.38/.43/.40/.41`) as the source of truth for non-secret values, since there's no other copy to restore from.

Do not fabricate a plausible-looking `pm_api_token_secret` value — a wrong-but-real-looking token fails silently differently than a clearly-fake placeholder and is worse to debug. If the human operator hasn't provided the new token value yet, mark this task NEEDS_CONTEXT and stop rather than guessing.

- [ ] **Step 3: Encrypt and commit the real file, removing it from `.gitignore`'s exclusion for this specific filename**

Once the real `terraform.tfvars` is available locally:

Run: `sops -e -i bootstrap-cluster/terraform/terraform.tfvars`

Edit `.gitignore` and `bootstrap-cluster/terraform/.gitignore` to carve out an exception, matching the existing `!example.tfvars` pattern:

```
*.tfvars
!example.tfvars
!terraform.tfvars  # now SOPS-encrypted, safe to commit — see docs/sops-secrets-migration.md
```

- [ ] **Step 4: Document the decrypt-on-demand workflow**

Add to `bootstrap-cluster/ansible/README.md` (or create `bootstrap-cluster/README.md` if none exists at the root of that tree — check first):

```markdown
## Secrets (SOPS)

Real values for `terraform/terraform.tfvars` are SOPS-encrypted and
committed. Decrypt on demand rather than keeping a permanent plaintext
copy:

    cd bootstrap-cluster/terraform
    sops exec-env terraform.tfvars 'tofu apply -var-file=/dev/stdin' # adjust per actual tofu invocation needs

Requires the shared age private key (same one used by the
sops-secrets-operator in-cluster) — see docs/sops-secrets-migration.md
for how to obtain it if you don't already have it.
```

- [ ] **Step 5: Commit**

```bash
git add bootstrap-cluster/ .gitignore
git commit -m "feat(bootstrap): SOPS-encrypt terraform.tfvars, document decrypt-on-demand workflow

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NwvkBV9MrW8jBTiTprtsgb"
```

- [ ] **Step 6: Verify**

Run: `sops -d bootstrap-cluster/terraform/terraform.tfvars | grep pm_api_token_secret`
Expected: the real value prints (confirms decrypt works with the local age key), and `git show HEAD:bootstrap-cluster/terraform/terraform.tfvars | grep pm_api_token_secret` shows only an `ENC[...]` blob (confirms what's committed is encrypted).

- [ ] **Step 7: Record in migration doc**

---

### Task 11: Credential rotation for git-history-leaked secrets

**Files:**
- Modify: `docs/sops-secrets-migration.md` (rotation checklist section, started in Task 4)

**Interfaces:**
- Consumes: Authentik admin access (external system, not this repo).
- Produces: a fully-checked rotation checklist confirming no git-history-leaked credential is still live.

- [ ] **Step 1: Rotate the old Rancher OIDC `client_secret`** (the one leaked in commit `5c16d55`, matching endpoints of the live Authentik provider per `docs/rancher-authentik-sso-plan.md`)

In Authentik: regenerate the client secret for the Rancher OAuth2/OIDC provider. Then update the live value:

Run: `sops -d --extract '["stringData"]["clientSecret"]' cluster-maintenance/clusters/cit-cps-gpu/rancher/oidc-sopssecret.yaml` to check the current value, edit with `sops cluster-maintenance/clusters/cit-cps-gpu/rancher/oidc-sopssecret.yaml` (opens decrypted in `$EDITOR`, re-encrypts on save) to put in the newly-rotated value, commit, let Fleet/the sync Job (Task 7) apply it.

- [ ] **Step 2: Confirm the old `rancher_bootstrap_password: "admin"` local-admin account no longer uses that password**

Run: `kubectl get user -n cattle-system` or check via Rancher UI for the bootstrap `admin` local user's last-changed state. If it's still set to the old weak value from before commit `2280a55`'s fix, change it now via Rancher's UI (Users & Authentication → local admin → reset password).

- [ ] **Step 3: Rotate the old JupyterHub OAuth `client_secret`** (leaked prior to the fix documented in `values.yaml`'s comment)

In Authentik: regenerate the client secret for the JupyterHub OAuth2/OIDC provider. Update `oauth-sopssecret.yaml` from Task 8 the same way as Step 1 above, commit, verify login.

- [ ] **Step 4: Mark the checklist complete**

In `docs/sops-secrets-migration.md`:

```markdown
## Credential rotation checklist

- [x] Rancher OIDC client_secret — rotated 2026-07-23 (was leaked in commit 5c16d55)
- [x] Rancher bootstrap admin password — confirmed no longer "admin" (was leaked in commit 5c16d55)
- [x] JupyterHub OAuth client_secret — rotated 2026-07-23 (was leaked prior to the values.yaml fix)
- [x] JupyterHub Postgres password — rotated 2026-07-23 (Task 4)
- [ ] LDAP bind password — flagged, not rotated (coordinate with directory admin; not a repo-introduced leak, existing value reused in Task 5)

Git history itself is not rewritten — see the spec's "Optional follow-up"
section. All values above are rotated, so the historical git blobs are
inert.
```

- [ ] **Step 5: Commit**

```bash
git add docs/sops-secrets-migration.md
git commit -m "docs(sops): complete credential rotation for git-history-leaked secrets

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NwvkBV9MrW8jBTiTprtsgb"
```

---

### Task 12: Final documentation pass (parallel agents)

**Files:**
- Modify: `docs/sops-secrets-migration.md` (final polish pass)
- Modify: `CLAUDE.md` (the "Secrets are never stored in Git" line under "Key facts to keep straight" is now inaccurate — must be corrected)
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring/README.md`, `user/jupyter/jupyterhub/README.md` if one exists, `bootstrap-cluster/ansible/README.md` — cross-link the migration doc from each touched area

**Interfaces:**
- Consumes: the completed migration doc table and rotation checklist from Tasks 1-11.
- Produces: a consistent, cross-linked documentation set with no stale claims.

- [ ] **Step 1: Dispatch parallel documentation-update agents, one per affected area**

Per the user's explicit instruction to run documentation-update agents rather than a single serial pass, dispatch four agents in parallel (one message, multiple Agent tool calls), each scoped to a specific area:

- Agent A: update `cluster-maintenance/clusters/cit-cps-gpu/system/` READMEs (monitoring) to cross-reference `docs/sops-secrets-migration.md` wherever secret-handling is mentioned.
- Agent B: update `cluster-maintenance/clusters/cit-cps-gpu/user/` READMEs (jupyterhub, jupyterhub-ssh, open-webui) the same way, plus confirm no stale "plaintext password" language remains anywhere in those trees.
- Agent C: update `bootstrap-cluster/ansible/README.md` and `bootstrap-cluster/terraform/` docs (e.g. `TEMPLATE_CREATION.md` if it references `tfvars` handling) to describe the new `sops exec-env` workflow from Task 10.
- Agent D: update root `CLAUDE.md`'s "Key facts to keep straight" section — the line "Secrets are never stored in Git; cross-namespace secret distribution goes through Reflector annotations... not copy-pasted manifests" is now inaccurate; replace with an accurate statement covering both Reflector (still used for TLS certs) and SOPS (`SopsSecret`, shared operator with `cit-teaching-platform`) as the two live mechanisms, pointing to `docs/sops-secrets-migration.md` for details.

Each agent's prompt must include: the exact files in its scope, the fact that `docs/sops-secrets-migration.md` is the canonical source of truth to link to (not to duplicate), and an instruction to report back exactly which files it changed.

- [ ] **Step 2: Review each agent's diff for accuracy against what Tasks 1-11 actually did**

Do not trust an agent's self-report — read the actual diffs (`git diff`) before committing, and cross-check specific claims (e.g. "Grafana password is now SOPS-managed") against the real state of the files changed in Task 3.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: cross-link SOPS migration across all affected areas, fix stale CLAUDE.md secrets claim

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01NwvkBV9MrW8jBTiTprtsgb"
```

- [ ] **Step 4: Final full verification pass**

Run `scripts/verify.sh` against the live cluster to confirm nothing broke. Manually re-test: Grafana login, JupyterHub login (both password-auth path via Postgres and OAuth path), Rancher OIDC login, Open WebUI OAuth login. Confirm `kubectl get sopssecrets -A` shows all new `SopsSecret` objects as successfully decrypted (no `Failed` status).

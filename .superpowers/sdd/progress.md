# SOPS migration — progress ledger

Plan: docs/superpowers/plans/2026-07-23-sops-secrets-migration.md
Branch: feat/sops-secrets-migration
Worktree: ../cps-gpu-cluster-sops

Pre-verified facts (controller, live cluster, 2026-07-23):
- sops-secrets-operator IS running in sops-system (confirmed via kubectl)
- CRD is sopssecrets.isindir.github.com, versions v1alpha1/v1alpha2/v1alpha3
- age public key confirmed: age1h05qj66un22scwapuhyl76skls7ll235vlu27cjwkk5tpav6sqmsx3zp6a
- sops v3.13.3 and age v1.3.1 installed to ~/.local/bin (not in base image)
- terraform.tfvars is CONFIRMED LOST — Task 10 recreates rather than retrieves

Task 1: complete (commit 2dbf94d, controller-executed — facts pre-verified live, no subagent needed for pure transcription)
Task 2: complete (commit 2dbf94d, controller-executed)

Task 3: complete (commits b302fa7..c124a9a, review approved)
  Note: system/observability/monitoring/ is applied manually via deploy.sh, NOT Fleet-reconciled (pre-existing, flagged by reviewer, not fixed by this task).
  Note: real namespace is cattle-monitoring-system, not "monitoring" as the plan assumed.

Task 4: complete (commits 649cdad..c79233e, review approved)
  Note: db_url user/db (jhub/jhub) still hardcoded literal (non-secret, pre-existing, not a regression) — flagged for future awareness if those ever rotate.

Task 5: complete (commit 7875ed9, review approved)
  Minor note: docs still echo the still-unrotated 'ldapservice' value in a code span — acceptable until rotation, flagged for later tightening.

Task 6: complete (commit 2cb46ba, review approved)
  IMPORTANT cross-cutting fix (commit after 2cb46ba): kustomization.yaml
  resources: lists in BOTH jupyterhub/ and system/observability/monitoring/
  were missing the new *-sopssecret.yaml files -- Fleet's kustomize build
  only includes explicitly listed resources, so Tasks 3/4/5/6's secrets
  would never have reached the cluster. Fixed and verified with
  `kubectl kustomize .` locally (confirmed SopsSecret objects now appear
  in the rendered output for both bundles). MUST check this same gap for
  every later task that adds a *-sopssecret.yaml file to an existing
  Fleet-kustomize bundle (rancher/ in Task 7, open-webui/ in Task 9).

Task 7: complete (commits f25b3d8..5877029 + fix 234deac, review: Changes Requested -> fixed -> effectively approved)
  Fix applied directly (trivial, one-line image pin): bitnami/kubectl:1.30 -> rancher/kubectl:v1.29.0 (unconfirmed-pullable tag risk).
  Deviations from brief, verified sound by reviewer: Helm post-install/post-upgrade hooks instead of fleet.cattle.io/apply-once (real in-repo precedent); added secrets:get RBAC (necessary, brief's RBAC was broken without it); added empty-value guard (necessary, brief's script had a silent-failure hole).
  True end-to-end verification (Fleet sync, Job Complete, real OIDC login) deferred to post-merge -- cannot test pre-merge since GitRepo tracks main.

Task 8: complete (commit 21eba72, review approved, kustomize wiring correctly included from the start)

Task 9: complete (commits 6787fad, 3220f5c, b2aff06 -- review found & fixed a Critical: the "new" Authentik client (pk 36, client_id 5PLqeFpglsR0YVcsZj6nQtBkzNG6EiGyjQOZAdGr) was actually the SAME client leaked in commit 9f9f8ff. Rotated secret in Authentik immediately (client_id unchanged), re-encrypted, docs corrected. Re-review approved.)
  Real Authentik infra changes made outside git: provider pk 36 redirect_uris set, client_secret rotated twice (once during setup believing it was fresh, once after discovering the leak).
  User-provided Authentik API token was pasted in this chat session -- recommended user revoke/rotate it since it's no longer needed and now sits in conversation history.
  Pre-existing, out of scope: open-webui/fleet.yaml Helm chart is unpinned (no version:).

Task 10: complete (commit 3b06a1b, review approved)
  group_vars/all.yml half: genuine no-op, k3s_token/rancher_bootstrap_password already Jinja-generated, nothing to migrate.
  terraform.tfvars half: real file was lost, recreated from LIVE Proxmox API queries (node cit-gpu-01, storage pools, 8x A100 PCI addresses, VLAN 633, gateway, existing SSH pubkey from k3s-cp1) using a fresh operator-provided API token. Fresh vm_password generated (hash committed, one-time plaintext in scratchpad for operator to save to a password manager -- NOT in git).
  Controller independently verified decrypt works for terraform.tfvars AND spot-checked Tasks 4/7's secrets too, using the real age private key extracted read-only from the live sops-age-key cluster Secret (then securely deleted locally) -- full pipeline confirmed end-to-end, not just structurally.
  User-provided Proxmox API token was also pasted in chat -- recommend revoking/rotating alongside the Authentik token.

Task 11: complete (commits e922a13 + docs-fix, review: Changes Requested -> fixed -> approved)
  Both rotations independently confirmed by controller to decrypt to exactly the new values.
  Fix applied directly: corrected a wrong citation (JupyterHub leak wrongly attributed to rancher-authentik-sso-plan.md; real commits are dfd3c3d leak / d96a8fa fix).
  rancher_bootstrap_password: confirmed no separate checklist item needed -- addressed as a code-level fix (random generation) already, not a SopsSecret; live Rancher admin account state still needs a human check.
  Both Authentik API tokens used during this session should be revoked by the user now that rotation work is done.

Task 12: complete (final commit above)
  4 parallel doc agents dispatched (system/, user/, bootstrap-cluster, CLAUDE.md). All diffs spot-checked before commit, all accurate.
  Agent D's dispatch prompt assumption (Reflector has "narrower remaining use" for TLS) was WRONG -- controller verified live via kubectl: Reflector IS active, but only for cit-teaching-platform's cit-auth/cit-jhub namespaces, unrelated to this repo. CLAUDE.md corrected to state this precisely rather than guess.
  All 12 tasks complete. Ready for final whole-branch review.

Final whole-branch review: complete. No Critical findings.
  Verdict: ready to merge, one Important doc-consistency fix applied (above) -- inventory table + Rancher sync-mechanism note said "not rotated" after Task 11 already rotated both. Checklist was always correct; this only fixed stale prose elsewhere in the same doc.
  Explicit PASS on all high-stakes checks: kustomize wiring (all 7 SopsSecrets render, verified live), no plaintext secrets anywhere in the 31-file diff, Task 7's Critical image-pin fix present, git history not rewritten, TLS certs untouched, scope matches spec.
  Residual, disclosed, unavoidable pre-merge: true end-to-end login verification (Fleet sync -> Job Complete -> real OIDC browser login for Rancher; JupyterHub Postgres/LDAP/OAuth/proxy login) can only happen AFTER merge, since the live GitRepo tracks main.

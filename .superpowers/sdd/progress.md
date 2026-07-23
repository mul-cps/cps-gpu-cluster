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

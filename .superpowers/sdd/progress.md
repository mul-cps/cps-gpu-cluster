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

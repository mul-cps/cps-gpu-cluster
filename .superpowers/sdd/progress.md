# Dex IdP broker — progress ledger

Plan: docs/superpowers/plans/2026-07-23-dex-idp-broker.md
Branch: feat/dex-idp-broker
Worktree: ../cps-gpu-cluster-dex

Context: built after two live incidents earlier this session (Fleet bundle
name collision took down Rancher; duplicate env-var name broke JupyterHub's
Fleet patch). Extra live-verification discipline required per plan's Global
Constraints. kubectl direct access is currently unauthorized (token expired);
using `ssh root@193.171.81.160 "qm guest exec 101 -- ..."` (KUBECONFIG=/etc/rancher/k3s/k3s.yaml)
as the reliable path, same as used to recover both incidents.

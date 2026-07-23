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

Task 1: complete (controller-executed, live-verified: chart 0.24.1, CRDs auto-created by Dex itself via RBAC not a separate manifest, genericoidc baseline confirmed matching git, local login confirmed by operator)

Task 2: complete (controller-executed, CPS provider pk 47, client_id iGjkHeZPoMrpWsw5TZ3RY368DDJa2d8TwOnR1EVS, live discovery confirmed)
Task 3: complete (controller-executed, CIT provider pk 3, client_id qlPmVf0I9embINVWrDqSjWIjoD6HrTwx6TbEUYXq, live discovery confirmed -- unblocked, user provided both CPS+CIT tokens together)
  Both client secrets in /tmp/.../scratchpad/secure/dex_cps.txt and dex_cit.txt for Task 4's SopsSecrets, not yet consumed.
  Recommend user revoke both Authentik API tokens now that registration is done.

Task 4: complete (commit 90a8545, review approved, controller independently verified all 3 decrypt to expected values via real age key)

Task 5: PR #7 merged successfully. Post-merge collision discovered live: a genuinely separate ~6mo-old orphaned Dex deployment (ClusterRole/ClusterRoleBinding "dex", CRDs dex.coreos.com/* dated Jan 2026, namespace "auth" long gone) blocked install with an ownership-metadata error. User directed: delete the old orphans rather than rename our release. Deleted stale ClusterRole+ClusterRoleBinding "dex" (confirmed genuinely orphaned: no namespace, no pods, 6mo old). Forced resync (forceSyncGeneration, NOT bundledeployment delete). Dex now fully live and verified:
  - Job dex-rancher-secret-sync: Complete
  - Pod dex-*: 1/1 Running, clean startup logs (reused old CRDs gracefully, "already available, skipping create")
  - Config Secret's staticClients[0].secret contains the REAL value, not placeholder (confirmed via decode)
  - https://dex.dshl.unileoben.ac.at/.well-known/openid-configuration resolves correctly
  - Bundle status "Modified" is expected/intentional (same pattern as Rancher AuthConfig drift)
Starting Task 6 (repoint Rancher genericoidc at Dex) on branch feat/dex-task6-rancher-repoint.

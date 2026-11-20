# Isolated Argo admission qualification

Status: admission preparation passed; gateway-to-Argo notebook execution remains unqualified for the current candidate.

The current production allowlist contains only the pinned Argo executor. Rather than widen it, this qualification cloned the live workload policy into a temporary namespace. Only the namespace selectors/match condition and the separate parameter reference changed; validation expressions were identical. The separate parameter object added the pinned 6bb6a57 standard CPU notebook runner. A tokenless workflow service account satisfied normal Pod admission.

Server dry-run accepted the candidate runner and rejected mutable images, host networking, automatic tokens and secret environment injection. The same runner remained rejected in production. Production policy, binding and parameter identities/content were checked unchanged. The temporary namespace, service account, parameter, policy and binding were removed and absence verified. Exact results are in `argo-isolated-admission-report.json`.

Two setup failures were preserved privately: the initial missing service account and admission-binding propagation delay. Type-check readiness alone did not prove enforcement. The corrected qualification waits until a prohibited host-network dry-run is denied by the isolated policy before collecting cases.

No execution Pod or Workflow was created. This establishes a controlled admission path for the next runtime test; it does not qualify controller-generated executor credentials, artifact connectivity, immutable notebook execution, gateway HTTP authentication, ownership or production promotion. Those gates still require the real current gateway/runner and Argo/S3 lifecycle.

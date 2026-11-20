# Current CPU runner under real Argo

Status: controlled runtime passed; full gateway notebook submission remains incomplete.

A temporary namespace used the same workload admission validation expressions with its own namespace match and approved image parameter. The real Argo controller created a Pod, KAI scheduled it, and the pinned 6bb6a57 CPU image executed a fresh Papermill kernel. Assertions verified stripped old outputs, unchanged submitted notebook bytes, typed parameters and an explicitly selected helper import. Workflow and Pod both succeeded. See `argo-isolated-runtime-report.json`.

The first runtime exposed a real launcher defect: UID 10001 could not access the notebook image's interactive home working directory, causing Papermill to fail when restoring its original directory. The trusted launcher now injects `workingDir: /tmp` after policy validation. The successful runtime used that exact Pod setting with the existing runner digest. This does not claim that a newly packaged gateway containing the fix has been deployed.

The fixture required executor-only artifact credentials and CA references plus a temporary namespace-scoped relay ingress allowance on TCP 8333. No user-container credential mount was added. The generated executor still attempted S3 log archival despite the template's archiveLogs setting; an unauthorized namespace therefore failed before the allowance. This run does not qualify S3 notebook snapshot transfers or retained executed-notebook artifacts. Initial setup/quoting/directory failures and the result-parser correction are preserved privately.

All temporary namespace resources and the separate cluster admission policy/binding and relay ingress allowance were removed, with absence verified. Production policy and approved image parameters were unchanged; production still denies the runner. Source regression tests passed: 262 general tests plus five Hub integration tests in the Hub-equipped environment. Full gateway HTTP authentication/submission, ownership and notebook S3 artifact lifecycle remain required.

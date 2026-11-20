# Packaged gateway, real Argo and S3 notebook qualification

Status: controlled submission/runtime passed; production integration remains incomplete.

The remotely verified 70471b9 gateway image served authenticated loopback HTTP requests using synthetic operator fixture identities. Its installed notebook submission and S3 launcher code created workflows through the real Argo API in a temporary namespace. The namespace used a copy of production workload validation expressions, its own runner allowlist and executor credentials, and narrowly scoped temporary ingress to Argo/S3. Production image approvals and Service selectors were unchanged. The pinned CPU runner used the launcher's `/tmp` working-directory fix.

Both a successful notebook and an intentionally failing notebook completed with the expected workflow phase. Each preserved the immutable S3 snapshot, stripped old outputs, imported the selected helper, accepted typed parameters, reused the same workflow UID on retry and rejected changed input under the same idempotency key. Each produced a downloadable executed notebook; the failed notebook contained the expected RuntimeError. Object metadata bound the snapshot/output to the server UID. Another fixture identity received 403 for inspection, logs, artifacts, termination and retention. Exact hashes and results are in `gateway-70471b9-argo-report.json`.

The test namespace, gateway Pod, separate admission policy/binding and both temporary ingress policies were removed; six explicit NotFound checks verified cleanup. Synthetic S3 inputs, intent/binding records and outputs are preserved as evidence, without broad deletion. Earlier ingress and fixture event-loop failures are retained privately.

This does not qualify real Hub/Dex/Authentik login, canonical person linkage, browser/addon submission, production HTTPS, the full release compatibility set or owner retention/CAS in the fixed `cps-workflows` namespace. The lifecycle namespace restriction was preserved, and the owner retention endpoint was deliberately not replaced by a fake implementation. Production promotion remains disabled.

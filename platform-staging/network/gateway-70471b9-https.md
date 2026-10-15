# Packaged gateway HTTPS notebook qualification

Status: controlled certificate-verified HTTPS and notebook runtime passed; production identity, Service routing and owner retention remain incomplete.

The installed 70471b9 gateway served its real application using the deployment TLS certificate/key references. The client used `ssl.create_default_context` with the deployment CA and verified `compute-gateway.cps-compute.svc.cluster.local`; only the TCP dial address changed to loopback. Certificate and hostname verification were not disabled. Missing and invalid Bearer credentials returned 401, and the synthetic owner identity reached `/v1/me`. This does not claim a production Service or ingress request.

Over this HTTPS transport, success and deliberate-failure notebook submissions passed through real Argo and S3 in an isolated namespace. Assertions verified immutable snapshots, stripped outputs, supporting imports, typed parameters, same-UID retry, changed-input rejection, executed-notebook availability and UID-bound artifact metadata. Another identity was denied inspection, logs, artifacts, termination and retention with 403. Failed execution retained the expected error in its downloadable executed notebook. Exact results are in `gateway-70471b9-https-report.json`.

The separate namespace, gateway Pod, cloned admission policy/binding and temporary Argo/S3 ingress policies were removed; six explicit absence checks passed. Synthetic S3 evidence remains preserved. Production image approvals, Service selectors and deployments were not promoted.

Real Dex/Authentik identities, canonical linkage, browser/addon submission, production Service routing, owner retention/CAS in the fixed lifecycle namespace and coordinated release qualification remain required. The fixed lifecycle namespace restriction was preserved.

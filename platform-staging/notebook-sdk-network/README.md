# Notebook SDK Gateway egress

The Hub chart allows notebook egress to Hub services and public destinations,
but excludes private cluster ranges. The SDK intentionally uses the private TLS
Gateway address; without this explicit rule it receives connection refused.

These additive policies select only single-user notebook Pods in the CPS and CIT
namespaces and permit only TCP 8000 to `app=compute-gateway` Pods in `cps-compute`.
Existing DNS and Hub rules remain owned by the chart. No capture-port or other
private service access is added. Gateway authentication and profile authorization
remain required.

Both policies were server-dry-run checked, applied, and read back against the
rendered specs. The installed CIT SDK submitted a real notebook successfully;
unauthenticated API requests remained 401 and private capture port 8001 remained
unreachable. CPS SDK execution still requires its own live acceptance.

This overlay is staged and live-applied; inclusion in the final Fleet release is
still required. Render with `kubectl kustomize platform-staging/notebook-sdk-network`.

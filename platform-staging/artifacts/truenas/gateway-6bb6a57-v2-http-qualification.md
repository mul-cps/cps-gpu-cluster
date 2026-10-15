# Current gateway V2 HTTPS lifecycle — 2026-10-07

Status: bounded current-package lifecycle passed; production promotion remains unqualified.

The matching 6bb6a57 gateway candidate ran under the real controller service account with an isolated JupyterHub 5.5.2 fixture, production TLS/CA and service credential references, temporary state and V2 selected only inside the fixture. It did not match the production Service selector. A temporary relay ingress rule allowed only that fixture label on TCP 8022; the rule and fixture Pod/ConfigMap/Secret were removed afterwards. No public endpoint or production configuration was changed.

For CPS and CIT, authenticated HTTPS registration, forced SSH/TrueNAS provisioning, idempotent reprovisioning, cross-source denial, archive and archived-reprovision rejection passed. Certificate and hostname verification were enabled. Missing/invalid credentials returned 401; metrics credentials returned 403. The sibling root had no active ancestor mount in the pre-test inventory. The earlier refusal probe was specifically V1: its legacy shared parent is mounted by an existing notebook. That notebook was not stopped or changed.

Both archive verifier Jobs completed with container exit 0, UID/GID 1000 and the current packaged resource contract: requests 100m/64Mi, limits 500m/256Mi. Each attempted a real write through a writable NFS client mount and required server EROFS. Their exact Job/Pod identities and resources are recorded in the JSON. The admission-approved verifier image remains the reviewed fa48334 digest; the gateway/controller package is the matching 6bb6a57 candidate.

SQLite backup captures contain both archived storage states and 14 audit records with actor, target, previous/new values, time and outcome. This is disposable fixture state capture, not production backup/restore qualification. Verifier Jobs and synthetic PV/PVC objects were removed only after exact namespace/path/group-hash/Retain/claim UID checks. The two synthetic NAS datasets remain read-only; no dataset or user data was deleted. Private evidence: `/home/bjoern/cps-platform-evidence/2026-10-07/gateway-6bb6a57-v2-http/`.

These empty synthetic workspace tests do not qualify production identity linkage, grants, real visitor/browser authorization, user spawn/RTC, cross-group privacy, permanent parent-mount prevention, legacy handover, data-bearing crash/recovery, off-host restore or GPU pooling. Production storage stays V1 and its gateway remains on the previous image.

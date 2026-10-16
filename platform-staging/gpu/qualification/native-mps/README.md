# Bounded native MPS qualification

This is a qualification probe for the reviewed GPU2 target, not a daemon or
application launcher. Its foundation is the previously qualified MPS probe
SHA256 `a235f486239056bedf2afd6e48536c5024da5efa62340a6e7d3545dd0a1b4a8e`.
It never sets a cap, creates a Pod, changes a driver, or accesses Kubernetes.

Without `--execute`, it reports an inert plan and opens no CUDA device. The only
supported caps are 5120 and 20480 MiB. Execution requires the actual reviewed
source/binary hashes, GPU UUID, Pod UID and driver generation, ordinary
UID1000/GID100, and a previously sealed native parent. The owning operator must
independently observe parent limits, server attribution and peer progress.

Two private MPS clients alternate 256 MiB allocations. Requests are bounded at
cap+256 MiB, and an unexpectedly successful over-cap request is never touched.
Only CUDA error2 proves OOM; both clients must recover. The control/server use
private `/tmp` directories. Cleanup signals only PID-lifetime-fenced processes
belonging to that private session.

The cleanup scan does not interpret permission loss as absence. For a process
whose identity was already established, it accepts a missing environment only
when a kernel PID descriptor confirms exit of the same lifetime. Unreadable live
processes, unknown identities, or reused PIDs fail closed. The selected cap is
forwarded to both child processes.

CPU checks:

```sh
python -m pytest -q platform-staging/gpu/qualification/native-mps/test_mps_probe.py
python platform-staging/gpu/qualification/native-mps/mps_probe.py --cap-mib 20480
```

Public pull requests must run only inert/CPU checks. Live execution belongs to a
trusted, controlled qualification session. These CPU tests do not qualify the
new cleanup observer on hardware; that live rerun remains required.

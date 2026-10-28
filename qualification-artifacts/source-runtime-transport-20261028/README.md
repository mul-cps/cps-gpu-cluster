# Source/coordinator transport qualification — 28 October 2026

This is application-boundary and local package evidence. No Source, Gateway,
Node, driver or workload was changed by this work. The full platform remains a
pilot; production coordinator owner/history assembly is still incomplete.

## Implemented application boundary

- Admin source `2e620b1b1cce6886d551d0666671004d40aa3d3d` registers the real
  service-prefix `GET /internal/v1/runtime-observation` route. It requires the
  exact private console service credential and matching Source header; browser
  identities cannot substitute. Actual local Source guard/schema/binding and
  bounded retained references are read in one SQLite transaction. No schema
  migration, write, secret disclosure or coordinator callback occurs.
- Compute source `05c3d7399c0b65bb4914bbd1501f8235bf7ee419` adds the matching
  SourceRuntimeClient. It pins the HTTPS service origin, CA, console, database
  UUID and Source path hash; reloads a private credential file per request;
  rejects redirects/encoded paths, compressed/oversized replies, duplicate JSON
  keys and foreign/unknown response fields. Independent review findings were
  reproduced with failing tests and fixed before packaging.
- A real CA-verified HTTPS test connects this client to the actual Tornado
  Source handler, including cross-console denial and a Source-side client that
  raises if a coordinator callback is attempted. This is a controlled Source
  database fixture, not a running-cluster or complete-history proof.

The response returns at most 32 receipt and 32 operation references, with an
explicit truncation flag. This is not evidence of complete backup custody,
stopped Pods or freed GPU capacity, and cannot authorize activation alone.
Canonical contracts live in the application repositories:
`cps-compute/docs/production-source-observations.md` and
`e2x-course-hub/docs/cps-runtime-observation.md`.

## Clean, unreleased wheels

Both wheels were built from clean Git archives at the exact revisions above.
These are local qualification artifacts, not new releases or registry uploads.

| Artifact | SHA-256 | Verified RECORD hashes |
|---|---|---:|
| cps_compute-0.1.0-py3-none-any.whl | `96eb95e2bcd6bc1fa6fbb53344324969dac539dc0bc7a4873a3defb692462a60` | 141 |
| e2x_course_hub-0.1.1-py3-none-any.whl | `7622feacddbd1f3f1722c4efe020c0f5771f193107f8e20631fe05167ec90dde` | 60 |

The new implementation files match archive bytes. The SDK wheel does not own
Hub-package or JupyterLab extension files. Admin frontend compilation passed.
The existing npm build reported two high-severity dependency advisories; these
were not triaged or automatically changed by this transport qualification.

A fresh verification environment installed these exact wheels without
resolving dependencies again, reusing the dependency-complete qualification
environment as a dependency-only site. Module paths were asserted inside the
new environment. With PYTHONPATH unset and pytest's pythonpath override empty:

- Compute client, real HTTPS and selected-peer scope: **36 passed**.
- Source observation and Source guard scope: **15 passed, 20 subtests passed**.

Suites run in separate processes because the repositories have colliding bare
fixture-module names. No implementation source checkout is used for imports.
Artifacts and verification environment are under
`/tmp/cps-source-transport-packages-20261028/` on the operator host.

## Remaining production boundary

This transport is not yet wired into `create_runtime`. The current activation
owner assumes in-process console providers and SQLite paths; production has
separate CPS/CIT Source processes. Remaining work is production remote
process/storage binding, complete retained-history/backup custody, managed
owner/history construction and complete logical/device consumer assembly.
Do not enable selected-node mode or weaken existing ownership/history checks
on the strength of this receipt.

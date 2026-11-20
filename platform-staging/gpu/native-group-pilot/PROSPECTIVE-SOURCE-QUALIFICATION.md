# Single-scope531 Source lifecycle CLI

`prospective_source_qualification_workspace.py` is a separate, default-inert
copy of the small normal-lifecycle CLI. The original CLI and historical
qualification paths stay byte exact. This increment makes no live claim.

The only candidate is notebook531, the only profile is
`interactive-native-qualification-5` (5120 MiB), and the source is CPS. The gate
remains exact `bc5b128f…`. The target must be a new
`operator-qualification-531-*` scope, with its own existing `cps-ws-<32hex>`
neutral owner, exact RTC server/Pod/PVC, and explicitly reviewed canonical
operator members (at most eight). Course, term and group IDs all start with
`operator-`. The node pool permits exactly one workspace and 5120 MiB total
budget. Mikasa, Armin, their shared GPU owner, `shared-gpu-lab`, and
legacy native-group scopes are rejected. No directory identity is invented.

Root must create the operator-only course/group/workspace/account through the
normal Source console/API first, provision its CPU storage, and capture its
actual stopped registration. A missing local workspace produces a clear pending
normal-creation error before Hub/Gateway calls. This CLI does not directly create
accounts, members, records, grants, registration, profiles, PVCs, or Pods. Root
must perform any required profile change through the existing normal API before
this CLI's get/start/stop operation. The service's normal Start/Stop retain their
own registration, filesystem, Hub, Share, audit and shutdown/cleanup behavior.

## Root inputs

The renderer and CLI share `target_snapshot`: a closed version1 document with
`source`, `workspace`, `profile`, `workload_image`, `operator_members`,
`source_policy_hash`, `source_closure_sha256`, `current_authority_sha256`,
`source_instance`, `registration`, `state`, and `observed_at`. It must be a UTC
capture no older than fifteen minutes. The source instance binds the actual
Source51f image and captured Deployment/Pod UIDs in `cps-compute`; the owning
Hub and registration remain in `jupyterhub`. The full CPU registration
includes the gateway-derived `workspace_label` and `workspace_hash`, plus active
storage. Its members and all storage fields remain exact in the target mode;
only profile, ceiling and policy binding change through the reviewed proposal.

Every file has an independent Root-reviewed raw SHA256 argument. The CLI also
requires the canonical current-authority hash and complete terminal-history
hash from the reviewed renderer output. It checks these against the target and
node configuration without rewriting, filtering, retiring or promoting history.
It does not replace Root's independent full-history/authority review.

Required pinned files are:

- `--source-closure`: existing closed sixteen-module source closure, unchanged
  format. The original `verify_source_closure` verifies installed source bytes.
- `--source-policy` and `--policy`: old and prospective policy documents.
- `--qualification-config`: actual typed `NativeGroupQualification`, exact531,
  retained gate, one CPS scope and disabled matching profile.
- `--target-snapshot`: the independently reviewed existing Source target.
- `--node-config`: exact operator node configuration and full terminal history.
- `--config-file`: actual existing CPS console configuration.
- `--handover-file`: unchanged `source_qualification_handover.py`, fixed SHA256
  `53c5ed41ad95729a6f4248cf9d3f384c4c5c834b0bbef92134fe25c9ede8f870`.

Each file flag requires its corresponding `--<name>-sha256`. Execution also
requires `--source-sha256` for this CLI, `--current-authority-sha256`,
`--terminal-history-sha256`, `--source cps`, and an explicit
`--operation get|start|stop`. No pin or path has an active default.

Without `--execute`, invocation prints an inert result and imports neither
Source nor Core. With execution selected, malformed/missing pins are rejected
before private file reads. Target scope, member and Source identity checks then
precede other private inputs. The exact source closure and all typed
configuration/history checks precede construction of the real configured app.
The existing loader requires preexisting `/data/courses.sqlite` and
`/data/config.yml`; it is not a database migration or record repair path.

The operator must run as trusted UID10001 with private regular inputs (0400 or
0600); the unchanged loader separately verifies the original console config.
The returned service must be the actual released `WorkspaceService`, sharing
the configured provider/client objects and original CPS Hub/Gateway endpoints.
An actual fresh `bjoern` administrator read is required. Central registration
must exactly match the reviewed target before and after the normal operation.
Output contains only bounded operation metadata, never credentials or raw
configuration/history. There is no automatic retry or replay.

Root must separately establish the drained/fenced GPU2 qualification environment
and review any configuration activation. This CLI supplies no driver, cap,
hardware, production916 admission, or evidence promotion authority. Default
inert authoring and synthetic tests do not qualify a real Start or device.

## Offline validation

Use the reviewed efa3 Core source and its test fixtures; the Hub source path is
needed only by those fixtures. For example, from this directory, with
`CPS_CORE_TEST_ROOT` pointing to that reviewed checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$CPS_CORE_TEST_ROOT/src:$CPS_CORE_TEST_ROOT/tests:$CPS_CORE_TEST_ROOT/packages/hub/src" \
/home/bjoern/git/cps-compute/.venv/bin/python -m pytest -q -p no:cacheprovider \
  test_source_qualification_workspace.py test_prospective_source_qualification_workspace.py
```

These paths select source only for offline tests. Runtime execution instead
uses installed modules verified by the Root-pinned closure. Fixtures contain
synthetic target/history objects and mocked service boundaries; tests do not
read captured credentials, Source data, live configuration or hardware.

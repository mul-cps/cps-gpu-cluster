# Unequal cross-Hub peer-OOM qualification — prepared, not run

This derivative of the frozen [5/5 GiB harness](../native-peer-oom-20261017/README.md)
tests the existing approved **CPS 5 GiB + CIT 10 GiB** pair on GPU2 without MIG.
The combined 15 GiB fits the unchanged two-slot pilot budget. It creates no
approval and writes no cap, driver, gate, ledger or workload configuration.
A prepared harness or passing CPU checks do not qualify the hardware.

The manifest is closed: `a` must be a current CPS Pod in `jupyterhub` at 5120 MiB;
`b` must be a current CIT Pod in `cit-jhub` at 10240 MiB. Other namespaces,
swapped caps and 20 GiB are refused. Exact current Pod UIDs, Node/observer UIDs,
notebook and Node image pins, and unchanged driver boot/epoch are required.
The Node read checks each sealed record and that parent's exact soft/hard limits
against 5 or 10 GiB independently, before and after the run.

The runner sends each manifest cap to isolated remote Python. The pressure
sequence must hold at least **cap minus 1024 MiB** before typed OOM, retain it
for eight seconds, then recover. A 5 GiB result cannot qualify a 10 GiB test.
Both probe receipts must match the independently supplied manifest caps.
Independent peer kernels and host physical-memory samples must overlap the
hold; the original time, physical headroom, typed-error, recovery, custody and
transport/watchdog checks remain. `a-to-b` pressures CIT10 with CPS5 as peer;
`b-to-a` pressures CPS5 with CIT10 as peer.

## Execution prerequisites

[Read-only preflight](approval-preflight.json) verified CPS membership/grants,
stopped state and absence of its Hub server. CIT API authorization currently
fails because `akadmin`'s upstream Dex authentication expired. Sign in at
<https://jhub.dshl.unileoben.ac.at>, then repeat current permission checks.
All temporary test token rows are confirmed absent, local plaintext removed,
and loopback port-forwards stopped. No workload was started or grant changed.

Before execution, verify both consoles' current grants, exact approved roster,
stopped state, absence, and fresh four-component readiness. Start sequentially
through the normal console APIs. Do not bypass upstream authentication or
change approvals just to make a test pass. Prepare an owned regular 0600 target
manifest using actual post-start UIDs, with the same schema as the frozen
harness but the namespace/cap pair above. Separately review its SHA256.

```sh
python -B -m unittest discover -s qualification-artifacts/native-unequal-peer-oom-20261017 -p 'test_*.py' -v
python -B qualification-artifacts/native-unequal-peer-oom-20261017/run_peer_oom.py
```

From this directory, use the exact three digests in `source-pins.json`:

```sh
python -B run_peer_oom.py --execute \
  --manifest /absolute/private/current-unequal-targets.json --manifest-sha256 REVIEWED_MANIFEST_SHA256 \
  --runner-sha256 REVIEWED_RUNNER_SHA256 --probe-sha256 REVIEWED_PROBE_SHA256 \
  --preflight-sha256 REVIEWED_PREFLIGHT_SHA256 \
  --direction a-to-b --output /absolute/private/new-unequal-a-to-b
```

Repeat in reverse with a fresh output path only after the first run is terminal.
Missing assessments are inconclusive. Then perform normal Stops and independently
verify complete reservation release, permission restoration if any, credential
revocation, personal Pod preservation and fresh readiness. No automatic replay.

MPS, 20 GiB, concurrent starts, whole-fleet isolation and production readiness
remain separate gates. The original 5/5 GiB source pins and results are unchanged.

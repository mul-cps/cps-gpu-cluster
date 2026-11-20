# Shared compute policy

`catalog.json` owns CPS/CIT profiles, entitlement bundles, priorities and labels.
Compile with `python3 scripts/compile_compute_policy.py`; CI runs `--check`.
All consumers must record `version` and `policyHash` from `generated/policy.json`.
The hash is SHA256 of sorted, compact UTF-8 catalog JSON, excluding the derived
hash field. Deployment consumers verify artifact bytes before use.

Generated files are **outside Fleet's watched deployment trees**. They are review
artifacts, not a deployment. Targets in `release-lock.json` are not qualified
versions. Existing production Hubs and queues are unchanged.

GPU profiles remain disabled. Nominal 5/10/20 GiB does not imply safe packing;
the live node product labels identify nominal 40 GiB A100s. Fractions use that
nominal denominator; usable device memory, runtime overhead and peer-isolation
need measured evidence.
Images remain empty until released immutable digests have been reviewed. Consumers
must reject submission when no permitted approved image exists, including CPU jobs.
Entitlement catalog entries define bundles; they grant nobody membership themselves.
Shared workspaces reserve each canonical member globally, and release only after
confirmed shutdown. Batch grants do not consume interactive allowance.

KAI manifest conversion follows the [v0.18.1 Queue CRD](https://github.com/NVIDIA/KAI-Scheduler/blob/v0.18.1/deployments/kai-scheduler/crds/scheduling.run.ai_queues.yaml):
catalog CPU cores become millicpu; catalog MiB becomes decimal MB. CPU and memory
ceilings are explicit provisional targets and require capacity qualification.
Project/user descendants remain controller-owned. PriorityClasses alone do not
implement teaching protection, reclamation, fairness or consolidation policy.

`--qualification-evidence FILE` checks independent evidence against the exact
compiled policy hash. It requires all twelve acceptance scenarios, `passed: true`
and nonempty artifact entries `{path, sha256}` whose local bytes match. This is a
mechanical integrity gate, not a claim that scenario results are valid. Operator
review remains necessary; the gate never enables GPU profiles or deploys artifacts.
The evidence file uses `policyHash`, `passed`, `scenarios` (identifiers in the
compiler) and `artifacts`; artifacts must be available at verification time.

Moodle is planned / not deployed. The catalog keeps it disabled with no credentials.
The application provider boundary must fail startup if enabled. Local course
management remains active. Temporary artifacts default to 14 days, run artifacts
to 90 days, preserving active inputs and explicitly retained outputs. Notebook
snapshots default to 50 MiB and stripped outputs.

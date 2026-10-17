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

## Runtime limits — policy 0.2.0

| Use | Maximum runtime | Idle timeout |
| --- | ---: | ---: |
| CPU batch | 72 hours | Not applicable |
| GPU batch, shared or exclusive | 24 hours | Not applicable |
| Interactive CPU | 8 hours | 1 hour |
| Interactive shared GPU | 4 hours | 30 minutes |
| Administrative exclusive GPU debugging | 1 hour | 15 minutes |

These are the revised **staged** limits. GPU profiles retain their independent
qualification gates; changing a time limit does not enable them. A batch maximum
is a ceiling, not a guarantee against reclamation. Jobs may request a shorter
walltime and must remain checkpointable where required.

The live CPS generic culler was read on 16 October: `--timeout=172800`, interval
600 seconds, no `--max-age`, administrators excluded. The CIT culler was also read: idle24h, max-age24h, interval300s and named-server
removal enabled. Advertised CPU profile limits therefore do not prove consistent
live enforcement across the two Hubs. `interactive-culler-values.yaml`
provides the reviewed CPU/default ceiling for both stable Hub releases. The
profile-aware GPU loop must additionally enforce tighter GPU limits. Verify
installation, invocation and actual stopped/cleanup behavior before promotion.
The overlay preserves the existing administrator exemption; policy cards must
not imply that the generic culler enforces limits on exempt administrator servers.

Promotion requires a coordinated policy revision in Gateway, both Hubs, approval
readers and native history references, together with the culler overlay. Preserve
existing qualified runtime image/storage/identity bindings and archive historical
policy references. Do not replace the live qualified catalog with this unqualified
base catalog or re-stamp old isolation evidence for the new hash. No live limits
changed when this artifact was generated.


## Distributed JobSet contract — staged, unqualified

The catalog now includes `trusted.jobsets`: the same bounded namespace and
service account as normal batch workflows, `python` as the fixed worker command,
at most eight workers, two retries, and a ten-minute termination tombstone
retention. Checkpoint claims start empty; callers cannot supply PVCs or Pod
configuration through the distributed descriptor. Retry and cleanup settings
are administrator policy, separate from a job's requested walltime.

`distributedQualification.qualified` remains explicitly false. The compiler
rejects a bare true assertion, unsupported fields and malformed launcher bounds.
The launcher configuration and qualification marker must be provided together;
historical catalogs with neither remain compilable without rewriting their
contents. The installed Gateway's actual `JobSetLauncher` accepts this staged
contract and rejects generation before any Kubernetes call while unqualified.

This supplies the missing configuration artifact, not a deployment or a completed
distributed-runtime qualification. The live D48 policy and runtime remain
unchanged; `/v1/jobsets` still reports that its launcher is unconfigured. Do not
replace live D48 with this base catalog: it intentionally lacks approved runtime
images and keeps GPU profiles disabled. A coordinated, evidence-preserving
policy/consumer handover must retain current image, identity, storage and
qualification bindings. Four/eight-GPU execution and checkpoint/cleanup
qualification remain separate acceptance gates before submission is enabled.

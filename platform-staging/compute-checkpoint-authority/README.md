# Compute-state operator delivery record

This directory is an **operator-owned desired-state record**, not a Fleet bundle or SDK controller. Do not recursively apply this directory. It deliberately contains both current and future manifests. No automatic reconciler, execution authorization or rollback is introduced.

`current-delivery.json` remains `BASELINE-current`: Gateway444, native35 and backup Cron12 use original PVC `compute-state` UID `d791faac-9c82-42dc-87ad-541ae9edc89a`. The candidate is **not active**. Root must review/commit this record before a cutover, then publish a separate successful cutover receipt and explicit pointer update afterward. Do not update the current pointer merely because candidate manifests exist.

## Exact candidate delta

The three `baseline/` manifests reproduce the captured specs. All raw last-applied annotations, API status, managedFields and resource versions are removed; object UIDs and preservation hashes are in the delivery record. Secrets are references only. Inline env values are paths, a component name, `1`, image digest or policy hash; init programs copy existing mounted files without embedded credentials. No Secret payload, bootstrap token or database data is committed here.

The two `candidate/` Deployment specs change only `data.persistentVolumeClaim.claimName` to `compute-state-checkpoint-20261118` and hostname selector GPU2 to GPU3. The candidate Cron changes only its `source` claim; its separate `backup` destination remains `compute-state-backup`, schedule/command/image/affinity remain exact. Existing required pod affinity follows `app=compute-gateway`, so it follows the target controller without adding a fixed-node Cron selector.

Candidate PVC UID: `bfe673db-6d32-4ddd-a8a7-94cf9b86890e`; PV UID: `63513db8-9ec4-48f9-947d-8faf5ba0ccea`. The volume is an empty independently provisioned 1Gi target, not a VM or PV clone. This record does not claim completed copying or new authoritative data. Full native checkpoint verification and actual target volume health remain separate cutover gates.

Before every subsequent controller image/config or backup change:

```sh
python3 platform-staging/compute-checkpoint-authority/assert_delivery.py --live-check
```

This performs GET-only current PVC UID/PV-name, original controller UID, fullspec and manifest-hash comparisons. Any drift requires a reviewed successor delivery record. It does not grant mutation authority. Preserve the current declared claim through later updates. After target writes begin, never use `rollout undo`, historical maintenance manifests, old ReplicaSet scale-up or automatic old-store failback. Old store is stale; reverse movement requires its own complete checkpoint protocol.

## Native stale-writer admission fence — UNARMED

`admission/policy.json` is a native Kubernetes v1 ValidatingAdmissionPolicy. It matches **CREATE core/v1 Pods only**, namespaced scope, with exact `request.namespace == 'cps-compute'`. For each PVC volume naming `compute-state`, `persistentVolumeClaim.readOnly` must explicitly be true. Missing/false readOnly is refused by validation. Container-only readOnly is intentionally insufficient; the whole PVC source must be read-only. The actual staged source audit helper already has volume-level readOnly true. New target, backup and unrelated PVCs remain permitted.

`binding-warn-audit.json` has **Warn + Audit only**. No Deny binding is prepared for direct application. `release.UNARMED.json` retains null Root release, policy/binding UIDs, stopped-writer receipt and operation clock. The policy does not alter existing Pods, deployments, scale, status, exec or PVC APIs. It is a narrowly scoped stale ordinary-Pod writer fence, not protection against a privileged hostPath/NFS alias, static Pod or a principal allowed to remove admission policies.

Sequence, each step separately released by Root:

1. Outside the measured outage, create only the reviewed policy and Warn/Audit binding, retaining actual UIDs. Wait for observed policy generation/type-check diagnostics; test all `admission/proposals/` with **server dry-run only**. Old RW must yield the expected warning; all other cases must succeed without that warning. API object dry-run acceptance alone does not prove live admission evaluation or audit-sink delivery.
2. Begin the original Service-fence clock and gracefully stop both old authorities. Prove both original API Pod UIDs and **all actual CRI CIDs** stopped, no other RW old-claim consumer anywhere, Cron suspended and callers quiescent. Existing Pods are unaffected by CREATE-only policy, so Deny cannot substitute for these facts.
3. Only after that proof, fill the separate Root release envelope. Fresh policy/binding UID/resourceVersion/fullspec tests; change binding actions from `[Warn, Audit]` to `[Deny, Audit]` once. **Deny and Warn cannot be combined.** Confirm readback and dry-run: old RW is Forbidden; old volume-RO, target RW and unrelated claim remain accepted. Reconcile unknown reply without another mutation. All of this remains inside the original <=60s clock.
4. Perform final globally consistent four-DB/all-other-data checkpoint only after writer exclusion, then target init/start/verification. Keep the Deny fence through service restoration and later operation. Do not remove it to revive a stale old writer if target launch fails. Before target has any write, any deliberate return to old storage still requires separately reviewed exclusion and admission rollback; there is no automatic fallback here.
5. After accepted cutover, explicitly update current-delivery pointer/receipt/current claim to candidate, record retired old claim UID and capture new actual fullspecs. Preserve historical snapshots as evidence only. The admission fence prevents old ReplicaSets/new Pods from writing the old claim even if a privileged operator accidentally reapplies an old Deployment; it does not stop the stale Deployment spec change itself.

Root's original `936.801786s` planned-cutover failure remains. This candidate neither changes the <=60s threshold nor claims unplanned HA. The timed operation must retain the original start/end meaning and include final snapshot/transfer/validation, admission transition, startup and actual required API usability.

## Validation and limits

Seven Python tests cover manifest deltas, exact UID/spec refusal, public-record metadata and unarmed scope. `tests/policy_test.go` compiles/evaluates the **actual manifest CEL** with cel-go for nine positive/negative volumes plus four namespace values. It is not a substitute for API-server type-check/observed-generation and live dry-run prequalification. Three controller candidate full specs and both policy resource specs passed API server dry-run exactly, without creating or altering resources. No current Deny enforcement is claimed.

```sh
python3 -m unittest discover -s platform-staging/compute-checkpoint-authority/tests -p 'test_*.py' -v
cd platform-staging/compute-checkpoint-authority/tests
go test -mod=readonly -v ./...
```

Kubernetes documentation: [ValidatingAdmissionPolicy](https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/). It documents Warn/Audit prequalification and the separate Deny action. No mutation or policy application was performed while preparing this source.

## Live prequalification, 18 November 2026

The policy and Warn/Audit binding have now been installed. Actual policy UID is `40f89f68-da5b-452b-981a-28298ca61da7`; binding UID is `620b91f2-2267-4a0d-b2eb-fc9b54cf2abc`. Generation1 was observed without type-check warnings. Four server dry-runs passed: only old RW produced the expected warning. No Deny transition or production migration has occurred. See `docs/operations/evidence/upstream-sharing-20261116/controller-admission-warning-20261118.json`. The historical unarmed envelope remains unarmed for enforcement.

`probe_source_readonly.py` runs via stdin inside either existing Source Pod, with `PROBE_SOURCE=cps` or `cit`. It reads the existing `COMPUTE_POLICY_TOKEN` environment variable and `/trust/ca.crt`; it never prints or exports credentials. Four GET-only checks per Source verify exact inactive reservation, workspace/namespace/policy identity, the shared profile catalog and foreign-source workspace refusal. Its successful live baseline is in `controller-route-baseline-20261118.json`. This establishes authenticated backend usability, not frontend login, starting workloads, or the cutover timing gate. The exact prefixed policy identifier is intentional; changes require reviewed successor expectations.

Legacy lifecycle147 routes have a separately retained strict-TLS expired-certificate diagnostic. Their mounted settings scope them to two legacy qualification workspaces. They are not counted as successful normal API calls. Both legacy process custody journals remain preserved; no TLS bypass, certificate replacement, legacy retirement or journal deletion was performed.

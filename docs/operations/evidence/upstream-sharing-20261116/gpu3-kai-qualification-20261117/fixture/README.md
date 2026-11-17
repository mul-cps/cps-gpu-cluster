# GPU3 unqualified KAI admin candidate — offline preparation only

This isolated copy removes the circular requirement to promote GPU3 before observing stock KAI placement. It never adds/removes labels, taints, Node cordons, scheduler configuration or production policy. Canonical source files and the approved parent packet/selection are unchanged.

Root must explicitly release this stage AFTER hardware faults and coldboot checks. Selected GPU3 must be Ready, **uncordoned**, retain exactly `cps.unileoben.ac.at/maintenance=upstream-pilot:NoSchedule`, and have NO `cps.unileoben.ac.at/upstream-gpu-sharing` label. The sole qualified worker must be accepted GPU2 NodeUID3336cdd5-d245-436e-b57c-2f66c6dcaa41, Ready and not deleting. Unexpected qualified workers fail closed.

`--candidate-selection` is mandatory and selects this candidate-only envelope. The closed JSON schema is copied from the reviewed parent guard: exact GPU3 NodeUID7b3b5113-158d-4e0d-bd63-898a508fe806/IP10.21.0.40/two physical UUIDs, fresh postcoldboot bootID, driver/fractiond Pod names+UIDs+containerIDs, explicit release reference and exact authorized SSH destination/key. The template contains nulls; root supplies actual readbacks in a separate new selection file. This packet neither fills nor changes the parent selection.

The only Pod scheduling differences are hostname-only selector `kubernetes.io/hostname: k3s-wk-gpu3` and one exact Equal maintenance toleration. There is no broad Exists toleration and no nodeName/runtimeClass override. These are administrator-created fixtures. Production shared selectors still require qualified capacity and exclude GPU3; they are not edited. Root's uncordon allows nodeName-bound Longhorn infrastructure to start while the retained taint fences ordinary scheduling. Fixtures cannot select GPU2 merely because it remains qualified.

All canonical stock KAI15 roles, two ordering sequences, CUDA payload bytes, allocations, above-hard OOM2, 16GiB host leaves, progress intervals, scheduler BindRequest watch, CDI/physical identities, runtime outer6ce/inner0ca checks and UID/RV cleanup remain. Before CREATE and normal EXEC, guard rereads selected node, exact accepted peers and exact driver/fractiond UID/CID. During cleanup the original owned-Pod release path remains available without requiring eligibility to remain open; UID/RV deletion is never bypassed. Final identity/eligibility readback must pass. No automatic retries, force deletion or promotion are added.

## Offline verification

```
python3 -m unittest -v test_candidate.py kai_placement_safety_test.Safety
python3 -m py_compile kai_placement_run.py kai_placement_render.py candidate_guard.py test_candidate.py
```

Initial RED against unchanged canonical copies: selected-unqualified/exactpeer case refused; selected-qualified case incorrectly allowed for candidate mode; candidate option/guard absent. GREEN:11 tests including replacement/boot/fence/peer negatives, exact operand replacement, all15 envelope/payload/sequence comparisons, and subprocess render with failing kubectl/SSH sentinels. RED is retained in red.log. This proves offline behavior, not a KAI hardware receipt.

## Concrete commands (root supplies new postcoldboot identities/release)

Prepare with a new output directory; all CLI tuples must match the closed selection file:

```sh
python3 kai_placement_run.py \
  --candidate-selection /ABSOLUTE/ROOT-OWNED-KAI-SELECTION.json \
  --node k3s-wk-gpu3 --operator-selected-worker k3s-wk-gpu3 --node-ip 10.21.0.40 \
  --gpu-a GPU-0a9f2da8-59f5-1cb0-9ead-d9fce56b69e5 \
  --gpu-b GPU-e7a56fad-ce29-f7d7-380a-3b5ae62a0b2a \
  --expected-boot-id ACTUAL-POSTCOLDBOOT-UUID \
  --expected-module-srcversion 10301D70B8ED1758BC717E9 \
  --accepted-qualified-peer k3s-wk-gpu2=3336cdd5-d245-436e-b57c-2f66c6dcaa41 \
  --run-id kai-gpu3-candidate-UNIQUE --output /ABSOLUTE/NEW-OUTPUT
```

For actual authorized execution, use another NEW output directory and append:

```sh
--execute --parent-idle-release EXACT_SELECTION_RELEASE \
--ssh-target ubuntu@10.21.0.40 --ssh-key /home/bjoern/.ssh/id_ed25519
```

Do not execute concurrently with another GPU workload. Root owns temporary uncordon and all subsequent acceptance/promotion decisions. Require process exit0, summary PASS/cleanup PASS, actual final identity/idle proof and complete BR/reservation cleanup. Rendering or seeing a pre-cleanup PASS does not qualify the worker.

## Review boundaries

The tradeoff is an explicitly administrator-only scheduling envelope differing from the production qualified selector. It exercises the same KAI scheduler/admission/binder, GPU request/assignment and runtime accounting without granting tenant eligibility. A later production Source/workspace receipt is still required; this does not substitute for it. The copied guard is frozen locally, so future canonical fixes must be reviewed and copied deliberately. Diffs and source-hashes.json delimit all changes; no runtime/plugin/image patch is involved.

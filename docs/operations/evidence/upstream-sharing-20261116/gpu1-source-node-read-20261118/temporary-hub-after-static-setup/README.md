# Later temporary Hub Node GET setup

This follows the initial403 Hub results in the parent evidence directory. Root separately created a static get-only ClusterRole for the single resourceNameGPU1, bound to only the CPS/CIT Hub service accounts. The exact Root-owned Role and Binding UIDs are retained. No Source hook, permit, grant, operator credential or start was armed.

Actual mounted Pod-bound Hub tokens were then tested directly against the Kubernetes service using the mounted CA, hostname validation and no environment proxy. Both Hubs GETGPU1=200 with NodeUIDb13bebdd; GPU2/GPU3/GPU4 and LIST remain403. Tokens were never printed or minted. The SourceQA selected-worker inputs remain unfilled until Root's post-coldboot and KAI release; no earlier boot is frozen by these UID-only probes.

Root retains cleanup ownership: remove only these exact temporary Role/Binding UIDs after both future QA hooks are gone and normal Hub configs are restored, then verify actual HubGPU1GET is403 again. Permanent Gateway named-node GET remains separately owned. This later stage does not alter or overwrite the earlier before403 proof.

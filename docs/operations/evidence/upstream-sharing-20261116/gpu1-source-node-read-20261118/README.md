# GPU1 Gateway Node GET scope

Actual mounted Pod service-account tokens were tested against `https://kubernetes.default.svc` with their mounted CA, hostname verification and environment proxies disabled. No token was printed or minted. Before the change, Gateway could GET GPU2/GPU3, but GPU1 and node LIST returned403. Both Hubs returned403 for GPU1/GPU2/GPU3/LIST.

Root added one resourceName, GPU1, to the existing Helm/Fleet-owned Gateway observer ClusterRole. The binding and its single Gateway-controller SA subject were unchanged. Source commit36834c71 and a revision-only Fleet CAS preserved the remaining owner spec and paths. After convergence, the same actual caller GETs GPU1/GPU2/GPU3 returned200 with exact NodeUIDs, while GPU4 and LIST returned403. Role and binding UIDs were preserved.

Root's operator `kubectl auth --as` checks had reported broader permissions. Those results are retained as a misleading impersonation/SAR observation, not treated as native caller capability; their cause is not established here. The native mounted-token responses provide acceptance evidence. Temporary Hub GPU1 GET permission remains an unapplied draft; no Source operation, grant, credential or Hub permission change is part of this delivery.

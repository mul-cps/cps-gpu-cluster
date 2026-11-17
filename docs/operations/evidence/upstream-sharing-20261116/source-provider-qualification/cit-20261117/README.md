# Actual CIT Source-provider qualification — 2026-11-17

Supported Source APIs, authenticated by the existing genuinely logged-in
administrator `akadmin`, created the reviewed QA course/term/group/four canonical
members and CPU workspace. The two explicitly approved C/D APP aliases are
adminFalse with no auth_state/credentials/IdP claims; reviewed Source mappings
refer to the existing CPS canonical C/D people. Four existing QA people retain
5GiB/allowance1 each (pooled20); no new canonical people or grant budgets.
Original49 grant-record bytes were checked before/after every Source API call.

No product/runtime/image/policy code changed. Catalog2b2, notebook4a03,
Gateway3a90 and SourceRegistry Hubs0bbe/bf13 remained installed. Every GPU Pod
ran on actual GPU2 UID3336cdd5-d245-436e-b57c-2f66c6dcaa41, boot8874dcda-ced2-4aa4-b5cb-71a0871abdd5.

| Actual supported lifecycle | Result |
|---|---|
| CPU create/warm start/normalstop | Ready18.22s; SDK200; retained file; no GPU devices/libcuda/TorchCUDA |
| shared5 | Ready13.37s;4.5GiB fill,45s useful progress, above6GiB OOM2, raw context destroyed then PyTorch CUDA tensor equals CPU reference |
| shared10 | Ready13.01s;9.5GiB fill,45s useful progress, above11GiB OOM2, PyTorch/reference, files/SDK retained |
| shared20 | Ready13.39s;19.5GiB fill,45s useful progress, above21GiB OOM2, PyTorch/reference, files/SDK retained |
| normal memberA removal and CPU restart | Source200; Podgone/leaseinactive; CPU Ready19.95s, central3/Aabsent, HubgroupAabsent/Bpresent; retained file, noGPU/libcuda/TorchCUDA |
| CPU neutral-owner held memberB removal | Normal Source200 closed the owned kernel and2RTC sockets at08:39:49.710Z; no human member impersonation |
| two concurrent identical SourceSTART | Sent within0.0009s;200+typed400 lifecycle-unresolved; one actual PodUIDd9334d23 and active attempte175e331, no second successful start |
| complete STOP response loss | One request through one-shot127.0.0.1 proxy, exact working XSRF/Host/headers. Proxy consumed real upstream409pendingcleanup and forwarded ZERO HTTP response bytes. Caller RemoteDisconnected. No upstream200 claim |
| reconciliation before replay | Fresh GET SourceStopped, actual Podabsent, authoritative reservation inactive/attemptnull, THEN one normal STOP replay200 without new start |
| cleanup | Remaining C/D Source memberships removed200; final normalSTOP200; Source memberships0, Hubgroupusers0, Shares0, bothQA Podsabsent and authoritative reservationsinactive. Files/audit metadata retained |

Root independently captured real driver leaves at5120/10240/20480MiB soft=hard,
actual active memory/NVML and host16GiB during sustained fills. Those witnesses
remain in root/platform artifacts `cit-source-{5,10,20}-leaf.json`.

The real Source client token and cleanup token were revoked204, absent by raw
lookup and rejected by authentication; preexisting administrator token IDs and
all8 authority tables preserved. Supervisor stopped, issuer raw copies removed;
this adapter removed its Source wrapper and expired visitor copies. Root then
revoked exactly the five QA grants, preserving original49 bytes and re-fencedGPU2.
No future test is authorized by these artifacts.

Read `scope-and-failed-fixtures.json`: human QA visitors had preexisting403 due
to missing SSO auth_state, so removed/remaining HUMAN access is NOT qualified.
The initial GPU-owner observer timed out and the early raw caller-disconnect
fixture was rejected403 by XSRF before mutation; neither is a passing fault or
closure test. The successful CPU-owner closure and later actual reply-loss
case are separate witnesses. Full response loss recorded upstream409 with
pending cleanup, not a fabricated200 success.

**SQL correction:** `/data/reservations.sqlite` is current; prior zero queries
used the wrong unprefixed workspace keys. Do not use those counts as current
charge evidence. Root's independent09:00:02Z query found globalperson0/binding0
and both correct Source-prefixed keys0/0. This app closure relies on the
corresponding authoritative Gateway API plus actual Pod absence.

Real nonadministrator IdP/browser access and two-human collaboration remain
OPEN. These artifacts qualify the installed operator/Source controller,
workload, quota/custody reconciliation and neutral-owner lifecycle only.

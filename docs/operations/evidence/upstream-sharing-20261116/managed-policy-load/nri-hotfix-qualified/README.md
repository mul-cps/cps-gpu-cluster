# Installed NRI hotfix: GPU2 fault and lifecycle acceptance

**PASS on the actual installed derived runtime.** This evidence qualifies the
NRI fault/lifecycle cases below; it does not promote GPU2 or establish CPS/CIT
service acceptance. GPU2 remains cordoned, in maintenance, and unqualified.
The historical stock-runtime first-request failure remains in `../nri-candidate`.

| Check | Retained witness |
| --- | --- |
| First protected GPU Create while actual Fractioning process is stopped | `containerd-hang-window.log`: Create 19:51:21.754; deadline closes plugin 19:51:23.770; same request rejected by default validator 19:51:23.774; no container execution |
| CPU after plugin timeout | `cpu-during-stop.json`, CPU completed while fractiond state remained `T` |
| New protected GPU Create while plugin disconnected | `disconnected-rejection.json`, `hung-snapshots.json`: rejected before execution |
| Independently bounded STOP | `fractiond-hang-identity.json`: actual `/fractiond`, PID 6234/starttime 2731; pidfd/starttime guard; host timer CONT at 19:51:35.941; `timer-journal.txt` |
| Missing mandatory plugin | `missing-rejection.json`, `missing-cpu.log`: GPU rejected; CPU worked |
| CUDA recovery, both physical cards | `recovery-0.log`, `recovery-1.log`: 1 GiB success + fill/sync; 6 GiB typed CUDA OOM 2; 2 GiB success + fill/sync |
| Final-binary runtime restart | `restart-unit.txt`: completed successfully; `restart-owned-before.json` and `restart-owned-after.json`: identical GPU/CPU PodUID, containerID, restart counts |
| CUDA quota and identity survive restart | `survivor-accounting-{before,after}.json`: same PID, cgroup path/inode, containerID and misc.max; `survivor-after.log`: continued CUDA work and typed quota rejection |
| Fractioning reconnect | `fractiond-after-restart.log`: registers 19:54:16 and synchronizes running containers 19:54:17 |
| Existing artifact-download service continuity | `artifact-downloads-{before,after}.json`: unchanged UID/container identities |
| Cleanup | `owned-pods-final.json`: none; `restart-after-host.json`: no compute clients on either GPU; timer inactive; `node-final.json`: fences retained |

The installed outer SHA is
`6ce276301723a902da671058730611591c59b5f016b816f57f2d97b05c88fe2c`.
Both actual agent/containerd executable hashes before and after restart are
`0ca3be05fd3fcdd9682e68bbff5821ea15027773404a7e47517b822bcb57387a`.
The actual data directory is the regenerated archive identity
`2277a2c458beda093f8367b944c2fbb2e5f53a00f17776759721fb781b3874fa`.
See `before-runtime.json` and `restart-after-runtime.json`.

`actual-driver-pod.json` retains c3b image and driver PodUID
`dfd0cc7a-1e57-476f-a90c-50b4f09b70c4`. Host snapshots verify loaded UVM
srcversion `10301D70B8ED1758BC717E9`, both policy parameters `Y`, and source SHA
`5648dbfe43957eb257d9efb715906de0fb6caa43458752544221d90db6efdb18`.
No binary, driver, host policy, scheduler, grant, or node-fence changes were
made by these qualification fixtures. One explicit runtime restart was tested.

Two fixture bookkeeping incidents are retained without treating them as
runtime failures: the first read-only preflight used main-thread children
and missed the Go agent's other-thread child; corrected PPid enumeration
ran before any injection. After the successful STOP witnesses, the independent
timer had already fired and auto-collected, so a redundant `systemctl stop`
returned 5. The exact process had resumed, manual pidfd CONT succeeded, and
inactive/not-found timer state was verified. `initial-run-timer-bookkeeping-summary.json`
and `run.log` preserve that interruption. No STOP was repeated: recovery and
continuity ran separately after reconciling the retained successful witnesses.

All fixture Pods were removed using UID-preconditioned DeleteOptions. The
completed diagnostic restart unit remains an exited oneshot with no running
process or timer. The hardware window was returned to the root coordinator.

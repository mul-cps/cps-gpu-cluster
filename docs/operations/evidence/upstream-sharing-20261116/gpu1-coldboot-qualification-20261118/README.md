# GPU1 coldboot, NRI, CPU and storage qualification

**PASS for these scoped postcoldboot checks.** This packet does not establish KAI placement, Source workspace acceptance, GPU1 worker promotion, or full-platform acceptance. It records the controlled reboot and tests on 2026-11-18 UTC, with no new live action during publication.

GPU1 retained Node UID `b13bebdd-60c2-4bbd-8fce-a39312ec264d`; boot changed from `b82de564-00cd-4596-a6cf-b4c618e79583` to `cd940ce3-dfb4-420c-92c5-712afe89eb29`. Root's [preconditions](coldboot-preconditions.safe.json) included three healthy GPU peers, no selected user/GPU jobs and current remote Longhorn replicas. The [single reboot intent](coldboot-intent.safe.json) was recorded at 00:40:01 UTC.

## Cold startup and persistent runtime

[Runtime identities](cold-runtime-identities.safe.json) retain actual kernel `7.0.0-43-generic`, K3s outer SHA `6ce27630…`, running agent/containerd inner SHA `0ca3be05…`, archive `2277a2c4…`, driver image `c3b71557…`, UVM source `5648dbfe…`, loaded srcversion `10301D70B8ED1758BC717E9`, both managed-memory/HMM guard parameters `Y`, and `RmMemacctMode=1`. The AppArmor profile remains enforced with restriction `1`; root/scratch filesystem identities and fstab hashes persisted. Both apt timers are active, matching the original policy rather than a cold-start failure.

The [resolved startup cause](cold-startup-cause.safe.json) records stock NVIDIA toolkit 1.20.1 flushing configuration and sending containerd SIGHUP at 00:45:33.831. K3s consequently restarted automatically once through systemd, starting again at 00:45:42.624. **No uninterrupted-agent or zero-restart claim is made.** No manual warm restart or runtime repair was used.

The driver-ready File marker appeared at 00:45:28.479, before the first current-boot metricsd instance at 00:45:43.989 and NVML initialization at 00:45:44.051. No NVML initialization error was observed. Stock fractioning targets and all Prometheus targets were UP at the retained readback; this does not assert end-user metrics coverage.

## CPU confinement and disposable storage

The [CPU probe](cpu-probe.safe.json) ran as UID1000 on the selected node, under the enforced stacked profile, using immutable image `5030556e…`. Signals, ptrace attach/detach, kill/reap and mount denial passed; there were no NVIDIA devices. Mount denial is **not uniquely attributable to AppArmor**, as the probe also retains other confinement controls. [CPU cleanup](cpu-cleanup.safe.json) confirms both owned objects absent.

Storage was initially held before creation because no selected Longhorn instance manager was available under cordon. Root opened the controlled IM window while retaining maintenance and qualification fences. The [storage probe](storage-probe.safe.json) then wrote, fsynced and read back exactly 4,194,324 bytes; SHA `d87a6c61…`, exit0. It used the original payload, a new disposable 100Mi Longhorn PVC and no user data.

Root [reclosed the window](root-storage-window-reclosed.safe.json) at 01:02:45. [Normal cleanup](storage-cleanup.safe.json) used UID/resourceVersion preconditions and default grace, then verified Pod, PVC, original disposable PV and Longhorn volume absent. No force or finalizer changes were used. The [original 17 attached volumes](original-volumes-preserved.safe.json) retained exact UID/state/health/current-node metadata. [Combined completion](cpu-storage-complete.safe.json) supersedes the CPU receipt's historical storage-held field.

## Postcold NRI rejection and recovery

The [fault witnesses](nri-fault-witnesses.safe.json) bind the actual fractiond PID/starttime/CID and retained Pod UIDs. The first fresh GPU container during the stopped plugin, a disconnected mandatory plugin, and a missing mandatory plugin were rejected by the default validator with `CreateContainerError` and **no containerID**. CPU containers completed independently during the fault cases.

[Both physical cards](nri-two-card-recovery.safe.json) passed the same 5GiB-quota raw-driver sequence: 1GiB allocation/fill/sync/free succeeded; 6GiB returned typed CUDA OOM2; a subsequent 2GiB allocation/fill/sync/free succeeded. This is a postcold NRI/quota-recovery check, not a repetition or expansion of the broader CUDA API qualification suite.

[Completion](nri-complete.safe.json) records no remaining owned Pods, ConfigMaps or BindRequests. All seven [known owned cgroups](nri-cgroups-cleaned.safe.json) were absent. [Final runtime/physical readbacks](nri-final-runtime-physical.safe.json) retain the same boot, outer/inner/module/source/guard identities, both cards at 1MiB and no compute clients. Cordon, maintenance and qualification-absent fences remained in place at this gate.

## Corrected cordon history and provenance

The [resolved cordon receipt](cordon-cause-resolved.safe.json) supersedes the earlier unknown-actor interpretation. Both observed clears were Root's intended IM-window PATCHes. Kubernetes omitted the serialized `unschedulable:false`, causing a literal post-write equality assertion to fail after the mutation had succeeded. Matching patch timestamps, IM creation times and a server-dry-run reproduction close the cause. There is no external-actor claim or controller-remedy requirement; maintenance and qualification fences were retained throughout.

[Source provenance](source-provenance.safe.json) records verified source manifest/file hashes. Public files contain explicit safe receipts and selected structured metadata only: no raw private Pod/config specs, log bodies, credentials, certificates, archives or fixture copies. Scope remains cold startup, NRI fault/recovery, CPU confinement and disposable storage.

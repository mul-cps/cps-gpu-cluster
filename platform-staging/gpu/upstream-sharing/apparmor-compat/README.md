# GPU2 AppArmor stacked-peer compatibility

Applied on GPU2 only on 2026-11-16 at 18:09:14 UTC. Installed K3s
v1.34.9+k3s1 / containerd v2.2.5-k3s2 remain unchanged.

The installed containerd template was fetched from
https://github.com/k3s-io/containerd/blob/v2.2.5-k3s2/contrib/apparmor/template.go.
`prepare.py` renders its verified GPU2 inputs: ABI 3.0, global/base includes,
unconfined containerd daemon, no RootlessKit executable. The resulting baseline,
compiled on GPU2 with `apparmor_parser -S -K -c0`, is **byte-identical** to the
previously loaded kernel policy. SHA256:
`8fd644921ce685e50f6dc8f57db6adb3fa0433d3fae7fa39cfdd673bd951dd82`.

The only policy changes are the exact two rules merged upstream in
https://github.com/containerd/containerd/pull/14487, commit
`447ef198eae9bae73186140a16705625479c19dc`:

```
signal (send,receive) peer=cri-containerd.apparmor.d//&unconfined,
ptrace (trace,tracedby,read,readby) peer=cri-containerd.apparmor.d//&unconfined,
```

There is no wildcard peer, filesystem-rule change, unconfined container setting,
sysctl relaxation, service restart, runtime upgrade, or peer-node change.
The upstream releases endpoint's latest entries predate the merge; the latest
released 2.2.10 template also lacks these rules. Source and release metadata are
retained in `upstream.json`. The failure explanation is upstream issue
https://github.com/containerd/containerd/issues/14485.

`install_gpu2.py` checks host, versions, hardening sysctl, exact original binary
policy, parser dry run and absent destination before replacement. It is
deliberately a one-time guarded operation, not a general cluster installer.

Evidence is in
`docs/operations/evidence/upstream-sharing-20261116/apparmor-compat/`:

- Ordinary nonroot CPU Pod, all capabilities dropped, RuntimeDefault AppArmor
  and seccomp: RED SIGUSR1, SIGKILL and parent-child ptrace each errno13.
  Children have a natural bounded exit, so failure does not strand them.
- SAME existing Pod after replacement and a fresh Pod: GREEN signal delivery,
  ptrace attach/detach, SIGKILL and reaping. Both retain the stacked enforced label.
- Private host mount namespace, root capability positive control: unconfined
  tmpfs mount succeeds; the same mount under the container profile fails and
  leaves no mount. The original `deny mount` is unchanged.
- All preexisting Pod UIDs and container restart counts unchanged during the
  observation. Existing ingress controller became Ready (was not Ready) with
  restart count 71 unchanged; FRR remained Ready with unchanged restart counts.
- No container-profile signal/ptrace audit denials between apply and final
  journal snapshot at 18:10:45 UTC. Unrelated `who` profile file denials remain.
- Both CPU fixtures removed with exact UID/resourceVersion preconditions.
  GPU2 remains quarantined. This does not override the managed-memory sharing
  failure and does not establish GPU acceptance.

Persistence is the installed `/etc/apparmor.d/cri-containerd.apparmor.d` loaded
by enabled `apparmor.service`, with explicit `Requires=apparmor.service` and
`After=apparmor.service` in
`/etc/systemd/system/k3s-agent.service.d/30-apparmor-compat.conf`.
Only `systemctl daemon-reload` was run. A reboot was **not** performed; boot
persistence is configured and ordering inspected, not reboot-tested.
Containerd's `LoadDefaultProfile` skips generation when this profile already
exists (retained `containerd-v2.2.5-apparmor.go`). Revisit this pinned profile
when upgrading containerd/AppArmor so future upstream policy changes are not
masked by the preloaded profile.

Rollback, if explicitly needed, on GPU2:

```sh
sudo apparmor_parser -r -B /var/lib/cps-apparmor-compat/original.raw
sudo rm /etc/apparmor.d/cri-containerd.apparmor.d
sudo rm /etc/systemd/system/k3s-agent.service.d/30-apparmor-compat.conf
sudo systemctl daemon-reload
```

Rollback reinstates the exact original enforced policy, including the known
stacked-peer incompatibility. No service restart is required for replacement.

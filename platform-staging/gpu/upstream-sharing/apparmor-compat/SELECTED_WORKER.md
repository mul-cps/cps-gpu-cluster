# Selected-worker preparation

`install_selected_worker.py` prepares the same retained upstream two-rule fix
without editing the historical GPU2 installer, source profiles, or evidence.
Default operation is entirely local: no SSH, Kubernetes command, host policy
change, or credential issuance. The explicitly supplied SSH key path is
`/home/bjoern/.ssh/id_ed25519`; only its regular-file ownership/mode0600 metadata
is checked. Private key bytes are never read or hashed by this helper.

The selection JSON is an operator fixture, **not an authorization receipt**.
`parent_release` is a correlation ID and must match the explicit CLI argument.
Root/operator authorization and serial maintenance coordination remain external.
This preparation nominates no worker and grants no runtime/reservation authority.

Prepare these exact fields from reviewed observations (replace placeholders):

```json
{
  "node": "EXACT_SELECTED_WORKER",
  "node_uid": "EXACT_NODE_UID",
  "ip": "EXACT_INTERNAL_IPV4",
  "expected_boot": "EXACT_CURRENT_BOOT_UUID",
  "expected_kernel": "EXACT_UNAME_RELEASE",
  "expected_os_version": "26.04",
  "k3s_version": "v1.34.9+k3s1",
  "containerd_version": "v2.2.5-k3s2",
  "parent_release": "EXPLICIT_PARENT_CORRELATION_ID",
  "profile_sha256": "30e2fc1210fc99c4e7060ea6bf7f931f6d6c03fbdc499f5f0584fb5c01c92875"
}
```

`expected_os_version` is the host's exact Ubuntu `VERSION_ID`, not its marketing
point-release string. Supply the read-only selected Node JSON separately. It
must match name, UID, sole InternalIP, boot, kernel and runtime versions; be
cordoned; carry
`cps.unileoben.ac.at/maintenance=upstream-pilot:NoSchedule`; and have **no**
`cps.unileoben.ac.at/upstream-gpu-sharing` label.

```sh
python platform-staging/gpu/upstream-sharing/apparmor-compat/install_selected_worker.py \
  --selection /private/selected-worker.json \
  --node-json /private/selected-node-observation.json \
  --ssh-key /home/bjoern/.ssh/id_ed25519 \
  --parent-release EXPLICIT_PARENT_CORRELATION_ID \
  --output /private/new-apparmor-review-bundle.json
```

The new mode0600 bundle contains the exact input, unchanged profile bytes,
rendered remote Python and SSH argv for review. Existing output is not replaced.
No `--apply` has been executed during qualification.

A separately authorized future `--apply` first performs a fresh read-only GET
of **only** the selected Node and rechecks its identity and maintenance fence.
It then opens one strict-known-hosts, batch SSH connection to that selected IP,
using the explicit key, and passwordless `sudo -n`. It performs no cluster
writes, peer connections, service restarts, reboot, forced signals, sysctl
relaxation, or qualification-label changes.

The remote operation rejects a different host/boot/kernel/Ubuntu version,
different K3s/containerd, relaxed hardening sysctl, multiple loaded profiles,
unknown loaded raw policy, or changed source profile. It requires loaded raw
SHA256 `8fd644921ce685e50f6dc8f57db6adb3fa0433d3fae7fa39cfdd673bd951dd82`
and byte-exact equality to a fresh `apparmor_parser -S -K -c0` compilation of
retained `baseline.profile`. The baseline text SHA256 is
`21888f007c25c39922acc64267b277ae6f43255e7314fd2a52dcf675c8533994`.
Candidate syntax/compilation are checked before replacement; loaded candidate
bytes are compared to that compilation afterward.

The policy file, systemd ordering drop-in and `/var/lib/cps-apparmor-compat`
backup must all be absent. Symlink/unsafe writable parents are rejected. The
backup is create-once mode0700 with fsynced mode0600 original raw policy,
baseline source and operation metadata, written before replacement. Only the
new policy and `Requires/After=apparmor.service` drop-in are installed, followed
by `systemctl daemon-reload`.

On an exception, an attempted kernel replacement is rolled back to the exact
saved binary before removing only files created by this operation. A failed
rollback retains the backup/files and reports incomplete reconciliation. The
backup remains after any outcome. A lost reply, interrupted process or existing
backup requires reading actual state and reconciling; do not blindly retry.
This is a one-time maintenance helper, not a reconciler or acceptance decision.

Offline qualification:

```sh
python -m unittest discover -s tests/upstream-sharing -p test_selected_worker_apparmor.py -q
python -m pytest -q
python -m py_compile platform-staging/gpu/upstream-sharing/apparmor-compat/install_selected_worker.py
```

Sixteen focused tests cover the identity/fence/source guards, no-transport
preparation, stock/compiled mismatch, create-once private backup, partial file
write, partial kernel load, reload rollback and failed rollback retention.
Filesystem effects are real temporary files; the host command boundary is a
strict offline double. Rendered remote Python compiles. The local workstation
has no AppArmor parser, so no new kernel/parser or selected-host acceptance is
claimed. The retained profile bytes and historical GPU2 installer are unchanged.

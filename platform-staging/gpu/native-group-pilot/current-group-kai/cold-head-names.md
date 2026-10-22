# Distinct head names for a new authority domain

The staged helpers in `head_bootstrap.py` accept an optional keyword-only
`domain_uid`. For a reviewed cold recovery, use the actual successor Namespace
UID as a naming token and pass it to every stage: `pointer_candidates`,
`anchor_candidates`, `bind`, `runtime_candidates`, `bind_runtime` and
`readiness_settings`. Omitting it preserves all existing bootstrap names.

All four mutable pointer names receive the canonical UID suffix. This matters
for the gateway and Hubs because their namespaces remain in place while their
authority changes. Anchors, Node configuration and runtime binding maps remain
content addressed and bound to actual API UID/content readbacks. A mismatched
or omitted token at a later stage fails readback validation. No objects are
applied by these helpers.

The naming token is not authentication, retirement approval or evidence of
physical exclusion. The operator must independently verify its Namespace UID,
retirement boundary, fresh qualified epoch and Source registry transition.
The pure tests use SDK-validated fixtures at a nonzero Source generation; they
do not qualify live hardware or authorize creating an empty old authority.

`bind_runtime` retains its original one-time adoption scope. It still rejects
controllers that already contain head mounts; a cold handover of the existing
Hub/gateway mounts needs its own reviewed full-spec CAS composition. Ordinary
rotation and namespace/epoch guards are unchanged.

## Recovery preparation evidence

`cold-head-recovery-evidence-20261022.json` records the bounded checks. The
recovery capture, including its original historical-byte artifact and 401
indexed byte records, was age encrypted, copied to the existing TrueNAS backup
directory, retrieved, decrypted and checked byte-for-byte. All 40 archived
files match. No private identity key was copied. TrueNAS inherited open modes
on the new encrypted-file directory; explicit 0600/0700 modes were applied and
verified before acceptance. Independent disaster-key custody remains false.
The 29 absent historical retirement journals remain absent.

GPU2's successor custody directory is staged on its ext4 system disk under
`/var/lib/cps-native-gpu/domains/<successor-namespace-uid>/custody`, owned by
root with mode 0700. Existing release files under the parent were preserved.
This domain-specific path avoids reusing another domain's state root. The
directory is empty and inactive: no ledger, head, private journal or authority
was initialized. HostPath composition must pin this exact directory with
type Directory; never DirectoryOrCreate. No driver load or live SQL migration
is established by these preparation receipts.

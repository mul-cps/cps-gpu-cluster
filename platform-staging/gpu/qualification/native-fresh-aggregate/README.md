# Fresh same-parent accounting acceptance

Default inert. Root alone reviews the current actual manifest and executes.
The manifest/current147 observer is the existing `native-fresh-domain` contract;
no Source, production Node, custody migration or cap-setting operation is added.

`run_aggregate.py` adapts the reviewed historical
`cps-group-native-20261009/group-probes/run_group_acceptance.py:434–499`.
Two independent exec processes run in the SAME selected capped Pod: a touched
2048MiB holder (`aggregate-peer`) and the stepped `aggregate-oom` process.
The latter must reach typed OOM with1536–2816MiB held, retain pressure for eight
seconds, then successfully run the original64MiB recovery kernel. Both process
streams require stable distinct actual PIDs. A THIRD ordinary peer runs in the
other Pod and must continuously execute kernels across OOM and recovery.
An aggregate holder in the other Pod cannot qualify same-parent accounting.

The probe program is an exact byte copy of current reviewed `peer_probe.py`:
5120MiB cap/256MiB steps, UID1000/GID100, raw CUDA without LD_PRELOAD,
original typed OOM and kernel bytes, independent remote watchdogs unchanged.
The current reviewed host observer/API fullspec brackets, four independent Root
physical samples inside held pressure (>6GiB free, >30GiB total), unchanged
seal/journal/process proof and charge recovery remain mandatory. The runner
cleans all local kubectl transports; remote watchdogs bound surviving probes.
It does not delete/stop Pods or claim remote termination from a local kill.

CLI (hashes and manifest must be independently reviewed actual values):

```text
python -I -B run_aggregate.py --execute --manifest ABSOLUTE_MANIFEST \
 --manifest-sha256 SHA --output NEW_PRIVATE_DIRECTORY \
 --runner-sha256 SHA --probe-sha256 SHA --preflight-sha256 SHA \
 --direction a-to-b
```

`--preflight-sha256` pins the existing sibling
`native-fresh-domain/fresh_preflight.py`; the output directory must not exist.
Reverse `--direction b-to-a` swaps which Pod hosts the two aggregate processes.
Source/manifest pins are checked before transport dispatch. Transport argv are
trusted Root-reviewed vectors, not an untrusted command language. Measurements
remain `production_qualified:false`; passing this gate does not activate sharing.

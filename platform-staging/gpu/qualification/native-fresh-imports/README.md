# Fresh same-parent import measurements

Default-inert operator wrapper for the actual fresh147 QA cohort. It reuses the
independently reviewed actual manifest, observer and peer engine in
`../native-fresh-domain`; it does not import the historical Node/head context,
retirement allowlist or hardware results.

`same_pod_imports.py` is byte-identical to the reviewed helper
`d8cdbf06d93a0f46e0fc122f5f547ff121d0728b7d99b55f1ca8345c574e4f6c`.
The pure `bundle` and `assess` functions in `same_parent_engine.py` are unchanged
from original engine `1fcb76aae4ab13e34cdc3e6071560abd2bbb90720ef4c7b4ea54cb8a2cb6593c`;
tests bind their exact ASTs. No old preflight code is imported.

Root explicitly approved reuse of userspace binary
`0e19d4ec396dd64cabe364607fee151c001821cdcb2da5e5b181d7f902a76f69`.
The original CPU artifact receipt identifies canonical C source
`15119a459ad4611a001ee1e89fb97929efa693d8a1ec3136c1e7d0a9b7b45a86`,
Ubuntu13.3.0 compiler marker, x86-64 ELF requiring only libc, maximumGLIBC2.34,
and compatibility checks in Ubuntu24.04. The original historical build receipt
was not located and this wrapper does not assert a fresh rebuild. The current
canonical compilation recipe uses official CUDA13.4.92 `cuda.h`
`7a79d67ca888061b1dfbe4739b51ad64f85a2f3ad874947ce09b2c635b4c7072`
from package `71bf3d001f2560a4710bdaba9297fcd3f775a50e3b320ec1c5fcc880d458b0df`.
These are userspace artifact/source identities, not carried-over hardware evidence.

Run from Root's reviewed local environment, with its actual API configuration:

```text
python -I -B run_imports.py --execute
  --manifest ACTUAL_FRESH_MANIFEST --manifest-sha256 REVIEWED_RAW_SHA
  --binary APPROVED_LOCAL_NATIVE_IMPORTS --binary-sha256 0e19d4ec...
  --runner-sha256 REVIEWED_RUNNER_SHA
  --side a --mode vmm-direct --output NEW_PRIVATE_DIRECTORY
```

`--side` is `a` or `b`; modes are `vmm-direct`, `ipc`, and `vmm`. No binary
preinstallation into the Pod is needed. Exact authenticated binary/helper bytes
are streamed through isolated Python into fresh UID1000-owned0700 temporary
directories, then removed. The helper's original native result/error checks,
5120MiB cap,64MiB touch, typedCUDA OOM2, recovery, retained VMM backing touch,
same-parent process protocol and reverse-order child cleanup remain in force.

All sources/binary authenticate before dependency execution or API access.
Actual fresh host proof brackets each measurement, with a continuous115-second
peer and unchanged Pod/status, PID/CID/start, original protected seal/journal,
cap and recovered charge. Successful state is recorded only after fresh final
proof. Cancellation or late proof failure cannot produce accepted authority.

The original helper deadline is90 seconds; the streamed wrapper has its original
115-second watchdog. The local transport timeout is105 seconds. Local transport
exit or timeout never establishes remote/native cleanup. Root must observe the
actual participants, preserve protection on failures and finally stop the actual
Pods and run the existing full controller cleanup transaction. These tools never
delete a Pod, remove a cap or reset a journal.

A passing receipt is a bounded same-parent raw-CUDA measurement with peer
continuity. It keeps `production_qualified:false` and
`cross_parent_isolation_qualified:false`. It does not qualify cross-parent import
isolation, exporter-process death, arbitrary external-memory protocols, MPS,
restart-cleanup,10GiB operation or a complete six-gate qualification report.

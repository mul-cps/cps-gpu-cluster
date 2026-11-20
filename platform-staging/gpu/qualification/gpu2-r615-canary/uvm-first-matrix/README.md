The first actual trusted global UVM-guard matrix passed its bounded raw CUDA
and managed-creation checks. Torch at512 MiB was inconclusive with a native OOM;
the matrix Pod exited1 and Torch is not qualified by this receipt.

The exact original five main log records are preserved: raw, fresh managed,
fork-before-CUDA managed, Torch, and the final subprocess matrix. Main Pod UID
567b84be-5bd3-48bf-9ee1-0633a6676acd ran the cached CPS notebook digest
6b6a8d6a225df1b938fe98bcdad9e547aef249347392ce8f29adb3fedda512ae.
The peer UID1f02616c-6d0e-4cfd-ae34-a8bb31ee5f39 ran compute digest
b3802a7f70077ff56adbc060d1177409eeff76c8b3cf8ccf9f39047c1e6716bf.
Actual full Pod specs, image IDs, init/main status and events are retained. Each
spec hash matches its root manual cap-before-main receipt. Immutable ConfigMap
data SHA matches both Pods' source annotations; the actual source bytes are
preserved in `configmaps.json`.

Both normal UID1000/GID100 processes observed their own exact512 MiB soft/hard
parent limits. Actual guard/HMM/ATS/builtin settings wereY/Y/0/0 and CUDA
attributes88/100 were0/0. Raw64 MiB allocation/touch succeeded,256 MiB failed
with native CUDA OOM2,64 MiB recovery succeeded, and managed64 MiB creation
failed801. Fresh direct and fork-before-CUDA managed creation also failed801.
No inherited CUDA context or imported/shared managed mapping is qualified.

The peer log contains597 successful heartbeat records plus one final summary,
598 total records. Heartbeats span119.854 seconds, every CUDA result0. Every
main phase, including the inconclusive Torch phase, has successful bracketing
peer ticks within one second of both boundaries and no gap exceeding0.221s.
The collector verifies phase-local coverage rather than using distant startup
or shutdown successes. Three tests reject missing boundaries, failures and
distant heartbeats.

The root's complete116-sample physical-memory log covers all main phases. The
tested GPU ranged427–575 MiB used; the untouched second GPU stayed0 MiB used
and0% utilization during these samples. This is physical sampling supporting
the fixture receipt, not a full peer-duration physical trace.

Torch2.11/cu129 reported AcceleratorError OOM after attributes were read, with
no phase markers establishing the exact failing allocation. Its status remains
inconclusive and exit1. A new separately bounded Torch phase needs a new peer;
this record must not be reused as that phase's continuity evidence.

All live operations by this collector are read-only. Root controls fixture cap
cleanup/deletion, later tests and original UVM/driver restoration. Per-Pod policy,
hostile isolation, lifecycle automation and production activation remain
unqualified; dynamic sharing stays disabled. `report.json` binds every complete
source artifact by SHA256.

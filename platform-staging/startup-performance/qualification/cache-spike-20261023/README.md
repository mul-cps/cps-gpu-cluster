# Startup caching and preloading investigation — 23 October 2026

Images are already cached. A read-only in-Gateway benchmark compared full GETs
of a 216 KB immutable qualification object with cached bodies and a live UID/RV
metadata check. Median latency fell from 4.22 to 2.46 ms: a real but small gain,
not an explanation of 128/144-second startup. Nothing was installed or deployed.
Three actual qualification context reloads took 0.967 seconds; production prepare
performs roughly 30 context loads. Parsed immutable qualification/history reuse
may help, but current approval pointers, process ACKs, identity, grants, device
witnesses and reservations must remain live, including final fencing checks.

An existing workspace's full Source provisioning call took 14.4 seconds. NAS
status reads took 0.77–0.98 seconds, but omit verified ACL/export evidence.
A test-driven candidate correctly fell back to full provisioning and did not
pass the live fast-path assertion. Its production source changes were removed;
the prototype is private throwaway evidence, not a published or deployed speedup.
The existing NAS provision path already verifies an existing dataset without
implicitly repairing its permissions. Replacing it with shallow status would
weaken the boundary; complete live verification is required before optimization.

Next work: instrument the Source/storage/owner checks, reduce repeated immutable
qualification reconstruction, examine the 20–26-second enrollment publication
wait, and profile the 27–28-second notebook-to-ready interval. Pre-stage account,
workspace and runtime preparation where validation can remain fresh. Bound and
serialize competing lease admission before side effects. Measure complete warm
starts and representative bursts after each change; do not infer end-to-end
speed from these isolated microbenchmarks.

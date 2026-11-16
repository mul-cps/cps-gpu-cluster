# Candidate: opt-in managed-memory rejection on shared R620 nodes

Review candidate only. Publication does not mean loaded or qualified. No driver/operator
ownership, scheduling, CPU/storage policy, or allocation-store change is included.

The reproduced stock R620/misc contention failure is causal motivation: a first
20 GiB tenant with approximately 19.5 GiB managed residency was CPU OOM-killed at
its 16 GiB host-memory cap when a later 5 GiB tenant allocated about 36 GiB
managed memory and survived. Permitting borrowing while idle remains the policy,
but borrowing must not kill a protected peer. Raising host-memory limits does
not establish GPU isolation. NVIDIA's R620 documentation explicitly lists managed
allocations as tracked only by the system-memory controller:
https://docs.nvidia.com/deploy/mps/620/mpsv3-memory-partitioning.html#known-limitations

## Small policy change and compatibility boundary

`uvm-reject-managed-memory.patch` adds a default-false, read-only `0444` boolean
module parameter, `uvm_reject_managed_memory`. When enabled it rejects new managed
VA ranges with `NV_ERR_NOT_SUPPORTED` **after successful range-tree insertion**.
The existing error path removes the inserted range and frees its allocations;
the mmap caller retains VMA-wrapper cleanup ownership. The stock conversion
returns `ENOSYS` from mmap; the exact CUDA-facing error must be measured.

The placement preserves `NV_ERR_UVM_ADDRESS_IN_USE` on collisions. Stock mmap
then recognizes pre-existing semaphore pools and device P2P mappings. A blanket
mmap denial, or an early return before collision classification, would break
those ordinary CUDA paths. External RM allocations, VMM mappings, channel/context
allocations, semaphore pools and device P2P remain separate range types.

This is deliberately **node-wide**, including host processes and exclusive jobs
on an enabled node. Explicit managed memory and `__managed__` globals become
unsupported; applications may fail during startup. Default false preserves stock
behavior. No RM/UVM bridge, cgroup-name heuristic, library interception, device
allocation accounting change, scheduler change or userspace enforcement exists
in this patch. Ordinary device-memory idle borrowing remains unchanged.

The released `uvm_disable_hmm=1` option is a separate requirement to close
pageable malloc/new HMM migration. It does not reject explicit managed ranges by
itself. ATS is a different path: verify the actual x86/A100 qualification device
reports no pageable-memory access using host page tables. This policy is not a
universal coherent-memory/ATS solution.

## Actual stock image layout and reproducible build

The immutable base is recorded in `provenance.json`. OCI inspection showed the
effective source is **inside**
`/usr/local/repos/nvidia-dkms-open_620.70.06-1ubuntu1_amd64.deb`, not a preinstalled
`/usr/src` tree. Its package SHA and original source SHA are enforced by the
recipe. At runtime stock `nvidia-driver` installs `nvidia-open` from the local
APT repository, which installs this DKMS package and compiles its embedded source
for the selected host kernel. The Debian package's `dkms.conf` builds
`nvidia-uvm` from that source. Merely patching an extracted archive outside the
package would not affect runtime compilation.

`repack-dkms.sh` extracts the exact package, applies the patch with zero fuzz,
verifies the resulting source SHA, updates that one source entry in Debian
md5sums, rebuilds the same package/version and regenerates `Packages.gz` for the
trusted local repository. Control fields and maintainer scripts stay unchanged.
No package is installed during the candidate build. All base layers, NVIDIA
620.70.06 userspace libraries, firmware, other packages and driver entrypoint
remain inherited. Candidate records are under
`/usr/share/cps-managed-memory-policy/` inside the image.

Build from this directory against an existing BuildKit endpoint; neither command
pushes an image or loads a module:

```sh
buildctl --addr "$BUILDKIT_ADDR" build --frontend dockerfile.v0 \
  --local context=. --local dockerfile=. --opt target=candidate \
  --opt build-arg:POLICY_SOURCE_REVISION="$(git rev-parse HEAD)" \
  --output type=oci,dest=/tmp/managed-memory-policy-candidate.oci.tar \
  --metadata-file /tmp/managed-memory-policy-build.json

buildctl --addr "$BUILDKIT_ADDR" build --frontend dockerfile.v0 \
  --local context=. --local dockerfile=. --opt target=compile-check \
  --opt build-arg:POLICY_SOURCE_REVISION="$(git rev-parse HEAD)" \
  --opt build-arg:KERNEL_VERSION=7.0.0-43-generic
```

The optional compile-check stage installs Ubuntu headers **inside an isolated
build layer**, builds modules with four jobs, and checks the new parameter in
the resulting `.ko`. It never runs DKMS installation, `nvidia-driver`, or
modprobe. Its headers and modules are excluded from the deployable candidate.
Compile success is source/build evidence, not hardware acceptance.

## Candidate module configuration; no apply is included

`nvidia-uvm.conf` is the **GPU Operator `/drivers/nvidia-uvm.conf` input format**:
bare parameter assignments, not an `options nvidia-uvm ...` modprobe stanza.
After review, add it as the `nvidia-uvm.conf` key of the selected driver's
kernelModuleConfig ConfigMap, preserving its current `nvidia.conf` and misc
backend configuration. The stock entrypoint converts these parameters into a
modprobe configuration. For a normal host `/etc/modprobe.d/` file, the equivalent
syntax instead is:

```text
options nvidia_uvm uvm_reject_managed_memory=1 uvm_disable_hmm=1
```

That file is not installed in the image. Activation requires a reviewed,
quiescent worker module reload/reboot and observed `/sys/module/nvidia_uvm/parameters/`
values. A driver userspace-only restart can keep old modules loaded; changing
an image reference or ConfigMap is not proof of policy activation. Keep the
worker quarantined until exact loaded module provenance and behavior pass.

## Acceptance before publication/promotion

Root owns hardware fixtures and acceptance: opt-in off positive; enabled direct
managed allocation fails safely; no managed range survives failure; repeated
failures do not leak ranges/memory; HMM pageable access cannot migrate; ordinary
CUDA allocation/copy/kernel, async pool, VMM, IPC and required semaphore/P2P
paths work; approved notebook/framework starts work. Repeat the reproduced
contention sequence and require the protected tenant to survive and complete.
Check actual loaded module hashes and both module parameters. Do not weaken
host-memory, reservation, storage, or protected-peer gates to pass.

No peer maintenance or deployment change is authorized by this directory.

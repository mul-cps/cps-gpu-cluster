# Initial candidate build evidence — 2026-11-16

Candidate directory only was edited. At this initial snapshot no image push,
driver/module load, live configuration change, or peer maintenance occurred.
The final recipe additionally requires the committed policy source revision and
overrides inherited OCI source/revision labels, with explicit base digest and
patch/source SHA labels. Its final publication identity is recorded separately;
the local digest below identifies the initial compile-checked artifact.

## Artifact identities and source path

- Stock OCI manifest: `sha256:0fcbf7340155f8d6868e30b1b0fbf09b601d093a9316621902d5ac09ad7874a1`.
- Local candidate OCI manifest: `sha256:79dbb641dce1d8d2c5266c276d0a91a5122bcb49946d90bb34b02186565a6720`.
- Local OCI: `/tmp/cps-upstream-20261116/managed-memory-policy-candidate.oci.tar`.
- Build metadata: `/tmp/cps-upstream-20261116/managed-memory-policy-build.json`, SHA256 `5b93638e8e6a47df9eb5e44a146839cdf10883dd60df4bd8e80aeb2746e891da`.
- Patch SHA256: `b1b423626bdd5ff726a95939a4b3b27ff08437e5f93c8732f2edaa5565031257`.
- Original embedded DKMS package SHA256: `fae10115b4938a4cc016d0cece0acab03756f216a4dc49491052e68519362e28`.
- Derived embedded DKMS package SHA256: `8772f26c6beddb818c27c78e2d9a8b2524136471cb7108ec1c66576cc3c9f82e`.
- Original UVM source SHA256: `6ed2a2ed36f39654151d9df7e60e5812bc791517d7a1045cc841287b8f7dea91`.
- Patched UVM source SHA256: `5648dbfe43957eb257d9efb715906de0fb6caa43458752544221d90db6efdb18`.

The old `/tmp/cps-upstream-20261116/r620-dkms-source.tar` was useful for source
analysis but contains a proprietary RM object and is not the effective image
source package. The candidate was built from the **open DKMS package embedded
in the pinned stock image**, not that archive.

## Completed offline checks

1. Stock package SHA/package name/version checked before modification. Patch
   applied with `--fuzz=0`; patched source SHA matched. Shell syntax check passed.
2. Candidate OCI comparison: **all 12 base layer descriptors identical**. Only
   appended policy/build records, changed DKMS package, and regenerated
   `/usr/local/repos/Packages.gz` occur in derived layers. Entrypoint remains
   `nvidia-driver init`, working directory `/drivers`.
3. Extracted original and candidate Debian packages compared by relative path,
   file bytes, symlink targets and file modes. **Only**
   `usr/src/nvidia-620.70.06/nvidia-uvm/uvm_va_range.c` and `DEBIAN/md5sums`
   differ. All other **470** files/symlinks and modes identical, including control
   fields, package version, maintainer scripts and `dkms.conf`. Debian md5sums
   validated after update. NVIDIA libraries, firmware and stock entrypoint are
   inherited without modification.
4. Isolated BuildKit compile-check completed **exit 0** against Ubuntu
   `linux-headers-7.0.0-43-generic` version `7.0.0-43.43`. All NVIDIA modules
   linked. `modinfo -p nvidia-uvm.ko` reports the new boolean parameter.
   No `error:` lines. This is not a warning-free build: log contains 13,821
   `warning:` lines, largely objtool warnings on `nvidia.o`/`nvidia-modeset.o`,
   plus local package override-file notices. BTF generation skipped because
   vmlinux is unavailable. These warnings were retained, not suppressed by
   changing kernel/build gates. No stock compile comparison was performed, so
   their baseline status is not claimed.

Compile log: `/tmp/cps-upstream-20261116/managed-memory-policy-compile.log`,
SHA256 `311bed7d3f4967b4cedb5b99bb356f9e913f8bcf3eb04dd76292325ed9d0b286`.
Compilation used the existing BuildKit pool via a local port-forward; no new
cluster build Pod or deployment was created. Header installation happened only
inside the isolated compile stage, excluded from the candidate image.

## Actual installed module-config parser, verified read-only

Running stock Pod entrypoint SHA256 matches inspected source:
`2b4d20033aded507f67f66330e528a699fe0cee15f3182683fab88e918987c6b`.
Current ConfigMap `cps-r620-misc-config` mounts `nvidia.conf` at
`/drivers/nvidia.conf`. Its existing input is:

```text
options nvidia NVreg_RegistryDwords="RmMemacctMode=1"
```

The stock `_get_module_params` function reads `/drivers/<module>.conf` lines
as parameter strings; `_create_module_params_conf` prefixes the resulting
modprobe configuration. Consequently the actual current generated file is:

```text
options nvidia NVreg_CoherentGPUMemoryMode=driver options nvidia NVreg_RegistryDwords="RmMemacctMode=1"
```

Read-only `/proc/driver/nvidia/params` confirms `RegistryDwords: "RmMemacctMode=1"`
and `CoherentGPUMemoryMode: "driver"` on the stock running worker. This report
does not propose changing its existing nested `options nvidia` tokens.

Offline reproduction executed those exact stock function bodies, substituting
only the `/drivers` directory with a temporary fixture and using the current
nvidia input plus candidate UVM input. Assertions passed:

- Generated `nvidia.conf` remains byte-for-byte identical to the actual current
  output above, preserving misc selection.
- Generated `nvidia-uvm.conf` is exactly
  `options nvidia-uvm uvm_reject_managed_memory=1 uvm_disable_hmm=1`.

Thus the candidate `nvidia-uvm.conf` intentionally contains **bare assignments**;
add only that key to the existing kernelModuleConfig, preserving `nvidia.conf`.
Actual new-parameter loading remains untested and unperformed.

## Review and hardware boundary

Root supplied the failing stock protected-peer contention witness before this
candidate; this worker did not rerun live hardware fixtures. Source/package
integrity and compile evidence do not establish safe CUDA-facing rejection,
absence of runtime leaks, ordinary CUDA/VMM/IPC/P2P compatibility, or protection
under contention. Root owns those fixtures and promotion gates. No publication
or rollout approval is inferred from this build.

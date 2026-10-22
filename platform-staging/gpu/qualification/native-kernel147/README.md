# CPU-only kernel 147 reconstruction

This recipe reconstructs the qualified **source**, then compiles against captured
147 headers. It does not promise the old 134 binary hashes on a different kernel,
install anything, load a module, contact Kubernetes, or qualify GPU behavior.
`recipe.py` with no arguments is inert. Its two explicit operations only prepare
source or inspect ELF files; compilation is deliberately a separate reviewed step.

## Exact retained provenance

State base: `/home/bjoern/.local/state/`.

* Final core: `cps-group-native-20261009/driver-optional-stack-f430b26/candidate-nvidia.ko`,
  SHA256 `4fdcafcdf7f57b9de81f56e8e17db06a91e27680c6a711f3888fd0b76da46421`,
  srcversion `2F87172C8F45C13DCB1A7BA`. Sibling `compile-abi-receipt.json`,
  `source-provenance.json`, `source-after.sha256`, and `build-core.sh` bind source
  f430b26b092670c5149554c79ecd97df211f2634, integrated14cfbac.
* Final cumulative core patch is that directory's `readonly-cap-inventory.patch`,
  SHA256 `89c96c231286b60eb72421ec2a2f0f9d8dd6aa7d90ef68eadf735d1216f949ef`.
  It ALREADY includes the final optional-stack osapi change. Do not add old
  retained/session/object-export or inventory patches again.
* Pristine archive: `cps-group-native-20261009/r615-pristine-open-source.tar.gz`,
  SHA256 `45bcef6e82bef0dccdb40d5f0751c86af0fd5e0276b60d407d7b96eadd2ebfdf`.
* Qualified UVM: `cps-group-native-20261009/driver-readonly-inventory/approved-original-uvm.ko`,
  SHA256 `b2ae67722e9e21a70c319aeed2184f5b2d1f23b8e32dea00816cfd5cd2c3ee61`,
  srcversion `9353E234906B1910373B07A`.
  Its original build is `cps-gpu2-r615-canary-20261008/uvm-guard-build/`:
  `actual-compile-receipt.json`, `build_candidate-crc-fixed.py`, `guard.py`.
  Generator SHA256 `70e6719709c8f5e5eb33a02a7323473e48dede3e4c74021b8992ea8ee0605114`;
  original UVM source `cf8d21c77f7db22f11b1a9c80f4197644d736d145afc2ea01bf057f83faaf8af`,
  final `e49447593565bef4ff899ab65283169387a9992f941598a978bb939aca6a2871`.
  The archive's original UVM sources match that generator's pins. No old core
  binary or old Module.symvers is used in a new 147 build.

## Inputs and source preparation

Root captured both 147 common/generic headers as one archive (120678400 bytes),
SHA256 `2128308bcb44512cdd2a49e6922fe26323f87da5d4d0b3bb805c0939a96b9cd3`;
stock147 NVIDIA core/UVM archive (93388800 bytes), SHA256
`4ebda23a12fa4051ed75b2d5f1f720fae4feee6deb71c13dd9e30d0050a594ff`.
They are under `cps-full-project-20261013/gpu-recovery-20261022/kernel147-build-inputs/`.
Verify raw archive hashes before extraction into a NEW isolated build context;
retain both headers trees at their captured `/usr/src/` layout. Do not mount the
host's live `/lib/modules`, devices, driver container, or module-loading socket.

Run `recipe.py prepare-source` with explicit `--archive`, `--patch`, `--guard`,
`--source-after` paths above and a fresh `--output`. It checks all input hashes,
safe bounded archive members, zero-fuzz cumulative patch, every final core source
pin and exact UVM output hash. The emitted `source-proof.json` records source-only
status. Missing/changed inputs fail; no header/compiler/version guard is skipped.

## Reviewed build job (Root only; not launched by this preparation)

Use a separately pinned Ubuntu24.04 toolchain image with gcc-13/g++-13 **13.3.0**,
binutils, make, patch, python3, kmod and matching dependencies installed during
image construction. The original compiler was Ubuntu13.3.0-6ubuntu2~24.04.1.
Do not assume the official driver image has the runtime-APT tools baked in.
Record toolchain image digest, installed package versions, compiler executable
hashes, full source proof, both input archives and complete stdout/stderr.
No network/devices during the compile RUN; at most2CPUs,4GiB, `nice -n19`.

Before compiling, assert actual `gcc-13 -dumpfullversion` and `g++-13
-dumpfullversion` are13.3.0, actual target UTS_RELEASE is6.8.0-147-generic, target
`.config`/generated headers/Module.symvers exist, and the kernel recorded compiler
is compatible. A mismatch stops for review; never use IGNORE_CC_MISMATCH, forced
vermagic, a substituted134 Module.symvers, or skipped version checks.

Inside the fresh prepared tree, with headers at their captured locations:

```sh
nice -n19 make -j2 CC=gcc-13 CXX=g++-13 kernel-open/nvidia/nv-kernel.o_binary
nice -n19 make -C kernel-open -j2 NV_KERNEL_MODULES='nvidia nvidia-uvm' \
  KERNEL_UNAME=6.8.0-147-generic \
  SYSSRC=/usr/src/linux-headers-6.8.0-147-generic \
  SYSOUT=/usr/src/linux-headers-6.8.0-147-generic \
  CC=gcc-13 CXX=g++-13 modules
```

No install target, modprobe load, insmod, depmod, nvidia-smi or GPU probe follows.
Export candidate core/UVM, fresh generated Module.symvers, source proof, buildlogs
and exact header/compiler/source input receipts only.

## Mandatory offline ELF gate before any separately reviewed load

`recipe.py verify-build --headers <captured-generic-headers> --stock-core ...
--stock-uvm ... --core <candidate> --uvm <candidate>` uses only modinfo and
modprobe's **query-only** --show-exports/--show-modversions. It requires identical
stock/candidate147 vermagic/version, unchanged full NVIDIA core and UVM exports
(UVM may have an empty export map only when readelf confirms no export section),
all candidate imports resolved with exact CRC against actual147 kernel symvers
or the new core exports, unchanged stock UVM import set/CRCs, preserved stockcore
imports, and only the documented cgrp_dfl_root extra core dependency. Any extra
ABI difference is a STOP for independent inspection, never an allowlist expansion
in the build job. Retain actual stock raw hashes and complete compared symbol maps
alongside result. Successful offline ABI comparison is NOT permission to load,
restore old epochs, reconstruct missing journals, or publish readiness.

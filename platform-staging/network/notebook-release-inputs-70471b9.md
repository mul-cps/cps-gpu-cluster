# Notebook release input preparation

Status: input validation passed; tagged-source build and release qualification incomplete.

The [candidate lock](notebook-release-inputs-70471b9-lock.json) pins twelve previously reviewed immutable notebook image bases, the shared policy hash and 146 wheel SHA-256 checksums. The current `70471b9` compute wheel replaces the older wheel in the existing multi-ABI wheelhouse. Notebook release validation checked wheel metadata, package version consistency, compute version, prebuilt addon presence, RTC presence and complete variant coverage: 133 packages passed.

The [receipt](notebook-release-inputs-70471b9-report.json) hashes the exact lock and records source revisions. Wheels and requirements remain in private release evidence. No source tag was created, no release was published and no image or production configuration changed. The `0.1.0`/`v0.1.0` fields are intended release targets, not an assertion that either exists or is qualified.

The canonical builder in the notebook repository requires a clean checkout at the matching source tag. Actual offline dependency installation for every runtime ABI, image/provenance generation, full inventories, runtime qualification and compatibility/release gates remain required. The wheelhouse's structural validation is not proof of dependency resolution or execution. Do not treat these layered candidate bases as proof of common-source tagged builds. Preserve all independent GPU, identity, collaboration, admission and recovery gates.

## Offline resolver evidence

The [default-interpreter resolver receipt](notebook-offline-resolution-70471b9-report.json) records twelve successful pip `--dry-run --ignore-installed --no-index --require-hashes` requests against the pinned wheelhouse in disposable local containers with network disabled. The wheelhouse was read-only. Post-run image config IDs match candidate reports; logs are checksummed in private evidence.

The first non-root and unmapped-root passes failed before resolution because private inputs were unreadable. Explicit host-owner mapping and disabled container labeling fixed fixture access without widening directory permissions. All twelve corrected requests passed. These results cover the default interpreter, not secondary ROS/system kernels. Installation, pip-check after installation, source-tag builds, runtime and release qualification remain open.

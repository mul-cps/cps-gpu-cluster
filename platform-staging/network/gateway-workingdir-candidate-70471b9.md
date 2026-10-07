# Gateway working-directory fix candidate

Status: packaged and remotely verified; not deployed or release-qualified.

The candidate in the adjacent JSON contains the trusted notebook launcher working-directory fix from compute commit `70471b9793f21a87d74ac7a673f871dfa9620101`. Its wheel was built from a clean Git archive and force-installed on the previously verified 6bb6a57 gateway base. Pulling the published exact registry digest and running verification matched all 21 Python modules and five addon assets to wheel contents, found no broken dependencies, and confirmed UID 10001 and the installed working-directory fix.

The older fourteen-artifact 6bb6a57 compatibility inventory remains historical evidence. This new gateway is not a replacement compatibility matrix or an official release: the new wheel checksum differs, and coordinated release construction, the full current gateway HTTP/Argo/S3 notebook gate remains incomplete. Production continues using the existing gateway and image permissions. The underlying real Argo runtime evidence is in `argo-isolated-runtime-report.json`; that run used the current CPU runner with the corrected Pod working directory, rather than this new gateway image.

The exact gateway digest now has an OCI referrer containing SPDX 2.3 and the native Syft inventory: 185 packages and 23,952 files. The source image config ID and referrer subject were checked, then both published files were downloaded and their SHA-256 values matched the originals. Scanner/publisher binaries matched the previously reviewed tool artifacts. This is an inventory publication, not a vulnerability clearance, release signature or runtime promotion gate. Exact attachment and checksums are recorded in the adjacent JSON.

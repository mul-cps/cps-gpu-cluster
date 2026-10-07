# Gateway working-directory fix candidate

Status: packaged and remotely verified; not deployed or release-qualified.

The candidate in the adjacent JSON contains the trusted notebook launcher working-directory fix from compute commit `70471b9793f21a87d74ac7a673f871dfa9620101`. Its wheel was built from a clean Git archive and force-installed on the previously verified 6bb6a57 gateway base. Pulling the published exact registry digest and running verification matched all 21 Python modules and five addon assets to wheel contents, found no broken dependencies, and confirmed UID 10001 and the installed working-directory fix.

The older fourteen-artifact 6bb6a57 compatibility inventory remains historical evidence. This new gateway is not a replacement compatibility matrix or an official release: the new wheel checksum differs, and coordinated release construction, SBOM publication and the full current gateway HTTP/Argo/S3 notebook gate remain incomplete. Production continues using the existing gateway and image permissions. The underlying real Argo runtime evidence is in `argo-isolated-runtime-report.json`; that run used the current CPU runner with the corrected Pod working directory, rather than this new gateway image.

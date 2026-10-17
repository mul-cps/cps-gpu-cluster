# Dynamic approval head source qualification

Exact application revision: `1dafcfe5baa75c894b01c8521095f962a22d7567`.

The explicit SDK/Hub and addon Python commands passed 3,230 tests and 68 subtests, with six environment-specific skips. All six skipped scenarios were separately executed against this exact revision: three addon artifact checks and three root CPU gate checks in a rootless, network-disabled, read-only container with no GPU/CRI/authority mounts. These CPU checks do not prove hardware isolation.

Six installed node-only functional cases passed. All 71 installed SDK modules matched the final wheel; the node-only environment retained 30 distributions and passed `pip check`. SDK and Hub wheels rebuilt from sdists were byte-identical. Artifact digests are recorded in `result.json`.

CI run [39017427697](https://github.com/mul-cps/cps-compute/actions/runs/39017427697) completed successfully: build, installed SDK/Hub, and installed JupyterLab 4.5.7 and 4.6.4. This workflow does not publish container images. Published images, automatic delivery migration, live adoption and hardware qualification remain separate gates. No live configuration was changed by these checks.

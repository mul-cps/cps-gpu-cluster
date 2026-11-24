# JupyterHub notebook lifecycle monitoring

Public route Jobs check both Hubs every three minutes. Each check loads the
Hub health endpoint and login page, selects the correct trusted Dex
connector, and reads the initial challenge from the owning Authentik
provider. The CIT check also verifies that the challenge offers
Montanuni Login. These checks stop at the anonymous challenge and do
not submit credentials, create users, or start notebooks. The
Prometheus freshness alert tracks both routes.

The profile Jobs cover an ordinary CIT user, a CIT researcher, and a CPS power user. The ordinary CIT check requires the 2 and 5 GiB options. The researcher checks cover each Hub's dedicated 1- and 2-GPU TensorFlow and PyTorch choices. The Jobs stay suspended until their scoped identities and non-preempting launch path are qualified.

## Full notebook check

1. Verify the token belongs to the dedicated monitoring user and that the user's Hub groups match the profile being checked.
2. Start a named test server through the public Hub API. Verify Ready state and the requested profile options.
3. Open an actual Python notebook kernel over the public route. Check CPU capacity and the RAM limit, write and read a small buffer in RAM and a temporary file in the home directory, and check reported filesystem space. Test every assigned CUDA device and the selected framework. Shared profiles check the exact VRAM limit and reject an above-cap allocation. The designated dual-device CIT profiles check CUDA peer access.
4. Stop the kernel and the named test server and verify the server has no running or pending operation. The cleanup runs after a failed resource check as well. It retries transient stop API failures within the existing stop deadline. A subsequent run stops a leftover server with its own test name and reports that cleanup was needed. One successful result requires the resource checks and verified stop.

The home test measures writable space inside the notebook filesystem. Verify the PVC and storage quota separately before declaring a storage claim guarantee. CPU capacity and RAM are checked against the profile contract exposed to users. Record any mismatch between the display and the live limits.

## GPU visibility check

Use `--visibility-only` on a qualified notebook probe to check which physical GPU UUIDs the notebook sees. The kernel still checks CPU, RAM, writable storage, and the configured VRAM limit environment for shared profiles. It queries the NVIDIA device list without creating a CUDA context or running a framework. The receipt records `gpuCheck: visibility`. Use the full resource check to qualify CUDA, the requested framework, or enforcement of the VRAM cap.

The scheduler reserves the selected share while the notebook is running. A server-side dry run against current KAI admission accepted 1 MiB and 64 MiB requests and rejected 0 MiB. The dry runs created no Pods. A smaller probe-only profile still needs binding, device visibility, non-preempting placement, and release checks before scheduling. Keep the existing course profile checks for the user-facing 2 and 5 GiB contracts.

## Credentials and scope

| Probe | Required Secret reference |
| --- | --- |
| CIT shared | `cattle-monitoring-system/cit-hub-spawn-shared-identity` |
| CIT research | `cattle-monitoring-system/cit-hub-spawn-research-identity` |
| CPS power user | `cattle-monitoring-system/cps-hub-spawn-poweruser-identity` |

Each reference takes a dedicated test user's `username` and `token`. Scope the token to read the test user's identity and groups, start and stop its own named servers, and access its own notebook. Follow the normal sign-in path when registering the test user. Keep the token in the protected Secret. Test Jobs must use their configured role-specific identities. They never use a real class or researcher account.

Before enabling scheduled GPU starts, validate one successful run and one failed-run cleanup through the public route, verify that test starts cannot evict user workloads, and confirm that a test stopped by the scheduler or by Job termination cannot retain a reservation. The active route probes are a separate signal and continue during this qualification.

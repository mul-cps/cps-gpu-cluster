# GPU2 raw-driver enforcement witnesses

These are real-hardware probes, excluded from ordinary pytest discovery. They
require the exact qualified runtime candidate, an administrator-controlled
maintenance node and no active user work. Each Pod is pinned to GPU2 and its
first GPU; no KAI scheduler cutover is performed by these fixtures.

Create the respective ConfigMap before applying a Pod:

```sh
kubectl -n gpu-operator create configmap gpu2-raw-driver-probe \
  --from-file=probe.py=tests/upstream-sharing/hardware/raw_driver_probe.py
kubectl apply -f tests/upstream-sharing/hardware/raw-driver-pod.yaml
kubectl -n gpu-operator logs -f gpu2-raw-driver-5g
```

The managed variant uses ConfigMap `gpu2-managed-driver-probe`, file
`managed_driver_probe.py`, Pod YAML `managed-driver-pod.yaml` and Pod name
`gpu2-managed-driver-5g`. It holds the successful managed allocation for 60
seconds so the administrator can query physical GPU memory from outside the
container. A 6 GiB managed allocation with successful GPU prefetch/fill under
5 GiB is a failing witness; compare host-wide NVML usage with the container's
virtualized accounting before drawing a residency conclusion. The initial
candidate measured 6567 MiB on the physical GPU while its container saw 415 MiB.

The device annotation uses the qualified CDI names emitted by stock KAI's
NvFractions plugin when CDI is enabled. A bare UUID does not resolve through
the GPU Operator's management-only default CDI kind. That initial harness
configuration error was corrected without changing production runtime code.

Always retain logs and remove the probe Pods and ConfigMaps after the probe
exits. Neither a passing ordinary allocation case nor Fractioning Ready is
workspace acceptance. Managed/UVM enforcement failed on the initial candidate;
keep GPU2 fenced until the same witness is bounded or safely rejected at the
driver boundary and final-artifact acceptance passes.

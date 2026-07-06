#!/usr/bin/env bash
# Priority-scheduling / preemption flood test for KAI Scheduler on this cluster.
#
# Strategy:
#   1. Flood the `batch` queue (lowest priority, kai-batch-low=10, quota=0,
#      relies entirely on bursting into idle capacity) with enough
#      MPS-shared jobs to consume most of the cluster's real GPU memory
#      (8 physical GPUs x 40960 MiB = 327680 MiB total).
#   2. Once batch jobs have filled the cluster, submit a second wave of
#      higher-priority jobs across `phd-interactive` (kai-phd-interactive=50)
#      and `courses` (kai-course-high=90) queues.
#   3. Watch KAI's scheduler preempt/evict lower-priority batch pods to make
#      room for the higher-priority ones -- this is the actual mechanism the
#      whole queue/priority design exists to prove, not just assumed from
#      static config.
#
# What to look for while this runs (see the `watch` commands it prints):
#   - `kubectl get pods` transitioning batch-queue pods to Terminating/Evicted
#     shortly after the interactive/course wave is submitted.
#   - `kubectl logs -n kai-scheduler deploy/kai-scheduler-default` showing
#     `[preempt]` log lines picking victim pods from the `batch` queue.
#   - Interactive/course pods reaching Running while some batch pods remain
#     Pending/evicted -- proof the priority ordering actually took effect,
#     not just that everything happened to fit.
#
# This is a LOAD TEST against a live cluster -- it will consume real GPU
# capacity and disrupt anything else running on the `batch` queue at the
# time. Do not run against production traffic without coordinating first.
#
# Usage:
#   ./priority-scheduling-flood-test.sh submit-batch [N]       # default N=40
#   ./priority-scheduling-flood-test.sh submit-priority [N]    # default N=10
#   ./priority-scheduling-flood-test.sh watch
#   ./priority-scheduling-flood-test.sh cleanup

set -euo pipefail

NAMESPACE="default"
LABEL_KEY="flood-test"
LABEL_VALUE="priority-scheduling"

usage() {
  echo "Usage: $0 {submit-batch [N]|submit-priority [N]|watch|cleanup}"
  exit 1
}

# Each pod requests a modest MPS-shared GPU-memory tier and just sleeps,
# holding the allocation so it's a real scheduling-pressure test, not a
# quick in-and-out job. gpu-memory tier chosen (~8GB) so ~5 pods roughly
# saturate one physical A100 (40960 MiB), letting a few dozen pods realistically
# fill the cluster's 8 physical GPUs without needing an enormous count.
make_pod() {
  local name="$1" queue="$2" priority_class="$3" mem_mib="$4"
  cat <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: ${name}
  namespace: ${NAMESPACE}
  labels:
    kai.scheduler/queue: ${queue}
    ${LABEL_KEY}: ${LABEL_VALUE}
  annotations:
    gpu-memory: "${mem_mib}"
spec:
  schedulerName: kai-scheduler
  priorityClassName: ${priority_class}
  restartPolicy: Never
  containers:
    - name: holder
      image: nvcr.io/nvidia/cuda:12.6.0-base-ubuntu24.04
      command: ["sh", "-c", "nvidia-smi; sleep 1800"]
      env:
        - name: CUDA_MPS_PINNED_DEVICE_MEM_LIMIT
          value: "0=${mem_mib}M"
        - name: CUDA_MPS_PIPE_DIRECTORY
          value: "/mps/nvidia.com/gpu/pipe"
        - name: CUDA_MPS_LOG_DIRECTORY
          value: "/mps/nvidia.com/gpu/log"
      volumeMounts:
        - name: mps-pipe
          mountPath: /mps/nvidia.com/gpu/pipe
        - name: mps-log
          mountPath: /mps/nvidia.com/gpu/log
  volumes:
    - name: mps-pipe
      hostPath:
        path: /run/nvidia/mps/nvidia.com/gpu/pipe
        type: DirectoryOrCreate
    - name: mps-log
      hostPath:
        path: /run/nvidia/mps/nvidia.com/gpu/log
        type: DirectoryOrCreate
EOF
}

submit_batch() {
  local n="${1:-40}"
  echo "Submitting ${n} batch-queue pods (kai-batch-low, 8192 MiB each)..."
  for i in $(seq 1 "$n"); do
    make_pod "flood-batch-${i}" "batch" "kai-batch-low" "8192" | kubectl apply -f - >/dev/null
  done
  echo "Done. Watch with: kubectl get pods -l ${LABEL_KEY}=${LABEL_VALUE},kai.scheduler/queue=batch"
}

submit_priority() {
  local n="${1:-10}"
  echo "Submitting ${n} phd-interactive pods (kai-phd-interactive, 10240 MiB each)"
  echo "and ${n} courses pods (kai-course-high, 5120 MiB each) to trigger preemption..."
  for i in $(seq 1 "$n"); do
    make_pod "flood-interactive-${i}" "phd-interactive" "kai-phd-interactive" "10240" | kubectl apply -f - >/dev/null
    make_pod "flood-course-${i}" "courses" "kai-course-high" "5120" | kubectl apply -f - >/dev/null
  done
  echo "Done. Watch preemption with:"
  echo "  kubectl get pods -l ${LABEL_KEY}=${LABEL_VALUE} -w"
  echo "  kubectl logs -n kai-scheduler deploy/kai-scheduler-default -f | grep -i preempt"
}

watch_test() {
  echo "=== Pods by queue ==="
  kubectl get pods -l "${LABEL_KEY}=${LABEL_VALUE}" -o custom-columns='NAME:.metadata.name,QUEUE:.metadata.labels.kai\.scheduler/queue,STATUS:.status.phase,NODE:.spec.nodeName' 2>&1
  echo
  echo "=== Recent scheduler preemption/allocate decisions ==="
  kubectl logs -n kai-scheduler deploy/kai-scheduler-default --tail=200 2>&1 | grep -iE "preempt|allocate|reclaim" | tail -30
}

cleanup() {
  echo "Deleting all flood-test pods..."
  kubectl delete pods -l "${LABEL_KEY}=${LABEL_VALUE}" --wait=false
  echo "Done (deletion runs in background)."
}

case "${1:-}" in
  submit-batch) submit_batch "${2:-40}" ;;
  submit-priority) submit_priority "${2:-10}" ;;
  watch) watch_test ;;
  cleanup) cleanup ;;
  *) usage ;;
esac

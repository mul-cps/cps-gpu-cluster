# No userspace, firmware, driver version, entrypoint, or runtime owner change.
FROM ghcr.io/mul-cps/cps-nvidia-driver@sha256:0fcbf7340155f8d6868e30b1b0fbf09b601d093a9316621902d5ac09ad7874a1 AS candidate
ARG POLICY_SOURCE_REVISION
COPY uvm-reject-managed-memory.patch repack-dkms.sh provenance.json /policy/
RUN printf '%s\n' "$POLICY_SOURCE_REVISION" | grep -Eq '^[0-9a-f]{40}$' && \
    sh /policy/repack-dkms.sh && rm -rf /policy
LABEL cps.unileoben.ac.at/driver-policy="reject-managed-opt-in-v1"
LABEL org.opencontainers.image.source="https://github.com/mul-cps/cps-gpu-cluster" \
      org.opencontainers.image.revision="${POLICY_SOURCE_REVISION}" \
      org.opencontainers.image.base.name="ghcr.io/mul-cps/cps-nvidia-driver" \
      org.opencontainers.image.base.digest="sha256:0fcbf7340155f8d6868e30b1b0fbf09b601d093a9316621902d5ac09ad7874a1" \
      cps.unileoben.ac.at/driver-policy-patch-sha256="b1b423626bdd5ff726a95939a4b3b27ff08437e5f93c8732f2edaa5565031257" \
      cps.unileoben.ac.at/driver-policy-source-sha256="5648dbfe43957eb257d9efb715906de0fb6caa43458752544221d90db6efdb18"

# Optional isolated build check; never execute nvidia-driver, modprobe, or DKMS
# install. These headers/build outputs are excluded from the candidate target.
FROM candidate AS compile-check
ARG KERNEL_VERSION=7.0.0-43-generic
RUN apt-get update && apt-get install -y --no-install-recommends linux-headers-${KERNEL_VERSION}
RUN mkdir /tmp/compile && \
    dpkg-deb -x /usr/local/repos/nvidia-dkms-open_620.70.06-1ubuntu1_amd64.deb /tmp/compile && \
    make -C /tmp/compile/usr/src/nvidia-620.70.06 -j4 \
      KERNEL_UNAME=${KERNEL_VERSION} SYSSRC=/usr/src/linux-headers-${KERNEL_VERSION} \
      IGNORE_CC_MISMATCH=1 IGNORE_PREEMPT_RT_PRESENCE=1 IGNORE_XEN_PRESENCE=1 \
      CONFIG_X86_KERNEL_IBT= modules && \
    modinfo -p /tmp/compile/usr/src/nvidia-620.70.06/nvidia-uvm.ko | \
      grep '^uvm_reject_managed_memory:'

# Default builds remain the deployable candidate, never the header/build stage.
FROM candidate AS final

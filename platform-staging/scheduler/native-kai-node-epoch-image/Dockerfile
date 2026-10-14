# Node-only qualification derivative: no SDK/Hub/package replacement.
# Preserve every inherited runtime setting, including the original command.
FROM ghcr.io/mul-cps/cps-compute@sha256:5079458fe0fcb3c11231b21f1bbc1f4c12ad3ac578799932aa0bc9f46d5510c7
LABEL org.opencontainers.image.source="https://github.com/mul-cps/cps-gpu-cluster" \
      io.mul-cps.native-node.base="sha256:5079458fe0fcb3c11231b21f1bbc1f4c12ad3ac578799932aa0bc9f46d5510c7" \
      io.mul-cps.native-node.packet="76460b31ba3e5343510e0259da98dcb5443d9a15" \
      io.mul-cps.native-node.epoch-source="58cec1acebbcc920a4ef1e4cd83d3518297fd39d" \
      io.mul-cps.native-node.operator-default="disabled"
COPY bundle/ /opt/native/

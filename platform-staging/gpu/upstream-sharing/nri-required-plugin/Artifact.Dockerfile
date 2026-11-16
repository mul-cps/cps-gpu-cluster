FROM scratch
ARG SOURCE_REVISION
LABEL org.opencontainers.image.title="CPS K3s required-plugin artifact candidate" \
      org.opencontainers.image.description="Derived K3s outer binary; exact upstream NRI required-plugin backport; qualification pending" \
      org.opencontainers.image.source="https://github.com/mul-cps/cps-gpu-cluster" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.version="v1.34.9+k3s1-nri-required-v1" \
      ac.at.unileoben.cps.source-revision="${SOURCE_REVISION}" \
      ac.at.unileoben.cps.k3s-upstream-tag="v1.34.9+k3s1" \
      ac.at.unileoben.cps.k3s-upstream-commit="5f72184f2d188f75171bbd21953b1c16268e425f" \
      ac.at.unileoben.cps.nri-upstream-patch="9cb8bc1fee03ebd41d90319240c2493fb03411b9" \
      ac.at.unileoben.cps.outer-sha256="6ce276301723a902da671058730611591c59b5f016b816f57f2d97b05c88fe2c" \
      ac.at.unileoben.cps.inner-sha256="0ca3be05fd3fcdd9682e68bbff5821ea15027773404a7e47517b822bcb57387a" \
      ac.at.unileoben.cps.archive-sha256="2277a2c458beda093f8367b944c2fbb2e5f53a00f17776759721fb781b3874fa"
COPY k3s /k3s
COPY provenance.json /provenance.json

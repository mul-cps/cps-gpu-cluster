FROM ghcr.io/mul-cps/cps-jupyter-notebook@sha256:5427088986bc06ad0713875d1aa2f31439f0bd1fbe6099d4669570fcf3e85be4 AS qualified
USER root
COPY cps_compute_jupyterlab-0.1.0-py3-none-any.whl verify_installed.py wheel-proof.json timer-api-probe.py legacy_lab_ownership.py ownership_closure.py inventory.py /tmp/cps-addon-overlay/
RUN python -I -B /tmp/cps-addon-overlay/inventory.py base && python -I -B /tmp/cps-addon-overlay/verify_installed.py --inventory > /tmp/cps-addon-baseline.json && echo "9cbe6526150bd94f852855400cf286b8b810979f6cc5ead84ad1e394e05234f2  /tmp/cps-addon-overlay/cps_compute_jupyterlab-0.1.0-py3-none-any.whl" | sha256sum -c - && python -I -B /tmp/cps-addon-overlay/ownership_closure.py before && python -I -B /tmp/cps-addon-overlay/legacy_lab_ownership.py --execute --prefix /opt/conda --sdk-dist-info /opt/conda/lib/python3.13/site-packages/cps_compute-0.1.0.dist-info --metadata-sha256 ab4c5be5e7f14488af41f758ffbc93b1b70f0f751957680460da6b7504f2b00e --record-sha256 f8a064128f46830f821e0f686b2a51bb9338ca987c15691fec3be978ad71651d > /tmp/cps-preservation-evidence/ownership-audit.json && cat /tmp/cps-preservation-evidence/ownership-audit.json && python -m pip install --no-index --no-deps --no-cache-dir --force-reinstall /tmp/cps-addon-overlay/cps_compute_jupyterlab-0.1.0-py3-none-any.whl && python -I -B /tmp/cps-addon-overlay/ownership_closure.py after && python -m pip check && python -I -B /tmp/cps-addon-overlay/verify_installed.py --baseline /tmp/cps-addon-baseline.json --wheel-proof /tmp/cps-addon-overlay/wheel-proof.json && PYTHONDONTWRITEBYTECODE=1 python -I -B /tmp/cps-addon-overlay/timer-api-probe.py && python -I -B /tmp/cps-addon-overlay/inventory.py candidate && rm -rf /tmp/cps-addon-overlay /tmp/cps-addon-baseline.json /tmp/legacy-sdk-before.json
USER 1000
LABEL io.cps.jupyterlab.source-revision="e499c97a5616c67262c76323c68c3433508d93b2" io.cps.jupyterlab.wheel-sha256="9cbe6526150bd94f852855400cf286b8b810979f6cc5ead84ad1e394e05234f2"

FROM qualified AS runtime
USER root
RUN rm -rf /tmp/cps-preservation-evidence
USER 1000

FROM scratch AS evidence
COPY --from=qualified /tmp/cps-preservation-evidence/ /

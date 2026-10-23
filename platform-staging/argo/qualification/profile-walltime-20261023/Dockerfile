FROM ghcr.io/mul-cps/cps-compute@sha256:3c8030cc7dbf6c12a6d29374c4df16b490536c3e723bcc8a67e913c7a2287624
USER root
COPY cps_compute-0.1.0-py3-none-any.whl /tmp/cps_compute-0.1.0-py3-none-any.whl
RUN python -m pip install --no-deps --no-cache-dir --force-reinstall /tmp/cps_compute-0.1.0-py3-none-any.whl && rm /tmp/cps_compute-0.1.0-py3-none-any.whl
LABEL io.cps.compute.sdk-walltime-revision="e222f47"
USER 1000

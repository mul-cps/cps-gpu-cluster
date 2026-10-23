FROM ghcr.io/mul-cps/e2x-course-hub@sha256:661c71604e95b4913ab3cdb5154ce1e7908662809fa6fcbed9e64badfb5afe0d
USER root
COPY cps_compute-0.1.0-py3-none-any.whl /tmp/cps_compute-0.1.0-py3-none-any.whl
RUN python -m pip install --no-deps --no-cache-dir --force-reinstall /tmp/cps_compute-0.1.0-py3-none-any.whl && rm /tmp/cps_compute-0.1.0-py3-none-any.whl
LABEL io.cps.compute.sdk-archive-revision="ea97d603be591d622773100a0daf49eb6b249cc3"
USER 1000

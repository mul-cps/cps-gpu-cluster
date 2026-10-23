FROM ghcr.io/mul-cps/e2x-course-hub@sha256:7350b1f5e9e4c09f347aa43ff4cadfa7d5ef1d90c7e02a755970699b5794acc9
USER root
COPY e2x_course_hub-0.1.1-py3-none-any.whl /tmp/e2x_course_hub-0.1.1-py3-none-any.whl
RUN python -m pip install --no-deps --no-cache-dir --force-reinstall /tmp/e2x_course_hub-0.1.1-py3-none-any.whl && rm /tmp/e2x_course_hub-0.1.1-py3-none-any.whl
LABEL io.cps.admin.external-shutdown-revision="b1753e42499b21a06940902ce04fca5536669ed8"
USER 1000

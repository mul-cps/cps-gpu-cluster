FROM ghcr.io/mul-cps/e2x-course-hub@sha256:c176e348978fcce7bae53a4e38721279e2b25a96b53bf25e13a6f4b4722b9281
USER root
COPY e2x_course_hub-0.1.1-py3-none-any.whl /tmp/e2x_course_hub-0.1.1-py3-none-any.whl
RUN python -m pip install --no-deps --no-cache-dir --force-reinstall /tmp/e2x_course_hub-0.1.1-py3-none-any.whl && rm /tmp/e2x_course_hub-0.1.1-py3-none-any.whl
LABEL io.cps.admin.start-confirmation-revision="2e0b76fe6711dd334186542af2bf07e75df3033c"

USER 1000

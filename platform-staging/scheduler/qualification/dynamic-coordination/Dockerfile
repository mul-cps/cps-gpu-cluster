# Supply a reviewed Python image digest; this task builds/publishes no image.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY platform-staging/scheduler/qualification/dynamic-admission/quota_policy.py /opt/dynamic-admission/quota_policy.py
COPY platform-staging/scheduler/qualification/dynamic-coordination/fence.py platform-staging/scheduler/qualification/dynamic-coordination/service.py platform-staging/scheduler/qualification/dynamic-coordination/sealer.py /opt/dynamic-coordination/
USER 65532:65532
ENTRYPOINT ["python", "/opt/dynamic-coordination/service.py"]

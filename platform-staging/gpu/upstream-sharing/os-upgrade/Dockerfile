# Supply an immutable Ubuntu 24.04 base image reference at build time.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY kube_preflight.py /kube_preflight.py
COPY host_upgrade.py /host_upgrade.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod 0555 /host_upgrade.py /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

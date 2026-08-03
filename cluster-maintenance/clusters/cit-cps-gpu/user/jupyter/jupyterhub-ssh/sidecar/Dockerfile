# cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/Dockerfile
FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends openssh-server bash && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /run/sshd /etc/ssh/sidecar_host_keys /etc/ssh/sidecar_authorized_keys && \
    useradd -m -u 1000 -s /bin/bash jovyan && \
    passwd -d jovyan && \
    chown -R 1000:1000 /run/sshd /etc/ssh/sidecar_host_keys /etc/ssh/sidecar_authorized_keys

COPY sshd_config /etc/ssh/sshd_config.sidecar
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 2200
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

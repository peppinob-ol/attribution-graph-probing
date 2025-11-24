FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        openssh-server \
        git \
        ca-certificates \
        python3-venv && \
    rm -rf /var/lib/apt/lists/*

# sshd runtime directory (needed on Ubuntu images)
RUN mkdir -p /var/run/sshd

# Persistent volume mount point (set by RunPod template)
ENV APP_ROOT=/workspace/graphs/giuseppe
WORKDIR ${APP_ROOT}

# Copy entrypoint script (lives in repo)
COPY docker/runpod/entrypoint.sh /usr/local/bin/runpod-entrypoint.sh
RUN chmod +x /usr/local/bin/runpod-entrypoint.sh

EXPOSE 22

CMD ["/usr/local/bin/runpod-entrypoint.sh"]


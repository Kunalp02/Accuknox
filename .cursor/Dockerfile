FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        python3 \
        python3-pip \
        python3-venv \
        docker.io \
        docker-compose-v2 \
        fuse-overlayfs \
        iptables \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --break-system-packages uv

USER ubuntu
WORKDIR /workspace

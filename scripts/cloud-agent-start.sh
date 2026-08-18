#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

start_docker() {
  if docker info &>/dev/null; then
    return 0
  fi

  if command -v sudo &>/dev/null; then
    sudo dockerd --iptables=false --storage-driver=fuse-overlayfs >/tmp/dockerd.log 2>&1 &
  else
    dockerd --iptables=false --storage-driver=fuse-overlayfs >/tmp/dockerd.log 2>&1 &
  fi

  for _ in $(seq 1 60); do
    if docker info &>/dev/null; then
      break
    fi
    sleep 1
  done

  if ! docker info &>/dev/null; then
    echo "Docker daemon failed to start" >&2
    tail -50 /tmp/dockerd.log >&2 || true
    exit 1
  fi

  if command -v sudo &>/dev/null; then
    sudo chmod 666 /var/run/docker.sock 2>/dev/null || true
  fi
}

start_docker

cd "$ROOT"
docker compose -f infra/docker-compose.yml up -d

for _ in $(seq 1 60); do
  if docker compose -f infra/docker-compose.yml exec -T postgres pg_isready -U orchestrator &>/dev/null; then
    exit 0
  fi
  sleep 1
done

echo "Postgres did not become ready in time" >&2
exit 1

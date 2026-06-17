#!/usr/bin/env bash
# Start vault-memory Neo4j (graph + vector embeddings).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}/docker"

ensure_volume() {
  local vol="$1"
  if ! docker volume inspect "${vol}" >/dev/null 2>&1; then
    docker volume create "${vol}" >/dev/null
    echo "Created Docker volume ${vol}"
  fi
}

ensure_docker_daemon() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  if ! command -v dockerd >/dev/null 2>&1; then
    echo "Docker not installed. See https://docs.docker.com/get-docker/"
    return 1
  fi
  echo "Starting dockerd (cloud/restricted VM flags)..."
  sudo dockerd --iptables=false --storage-driver=vfs >/tmp/vault-memory-dockerd.log 2>&1 &
  for _ in $(seq 1 30); do
    docker info >/dev/null 2>&1 && return 0
    sleep 1
  done
  echo "dockerd failed — see /tmp/vault-memory-dockerd.log"
  return 1
}

ensure_docker_daemon
ensure_volume vault-memory-neo4j-data
docker compose -f docker-compose.yml up -d

echo "Neo4j: bolt://127.0.0.1:${NEO4J_BOLT_PORT:-7687} (graph + vectors)"

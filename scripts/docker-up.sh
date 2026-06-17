#!/usr/bin/env bash
# Start vault-memory databases (unified or separate mode from config).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-unified}"
cd "${ROOT}/docker"

if [[ -f "${HOME}/.vault-memory/config.yaml" ]]; then
  MODE=$(python3 -c "import yaml;print(yaml.safe_load(open('${HOME}/.vault-memory/config.yaml')).get('docker',{}).get('mode','unified'))" 2>/dev/null || echo unified)
fi

ensure_volume() {
  local vol="$1"
  if ! docker volume inspect "${vol}" >/dev/null 2>&1; then
    docker volume create "${vol}" >/dev/null
    echo "Created Docker volume ${vol}"
  fi
}

if [[ "${MODE}" == "separate" ]]; then
  ensure_volume vault-memory-neo4j-data
  docker compose -f docker-compose.separate.yml --profile graph up -d
else
  ensure_volume vault-memory-neo4j-data
  docker compose -f docker-compose.yml up -d
fi

echo "Neo4j: bolt://127.0.0.1:${NEO4J_BOLT_PORT:-7687} (graph + vectors)"
echo "Note: Qdrant removed in v0.2+ — Neo4j-only stack"
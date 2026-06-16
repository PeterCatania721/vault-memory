#!/usr/bin/env bash
# Start vault-memory databases (unified or separate mode from config).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-unified}"
cd "${ROOT}/docker"

if [[ -f "${HOME}/.vault-memory/config.yaml" ]]; then
  MODE=$(python3 -c "import yaml;print(yaml.safe_load(open('${HOME}/.vault-memory/config.yaml')).get('docker',{}).get('mode','unified'))" 2>/dev/null || echo unified)
fi

if [[ "${MODE}" == "separate" ]]; then
  docker compose -f docker-compose.separate.yml --profile vector up -d
  docker compose -f docker-compose.separate.yml --profile graph up -d
else
  docker compose --profile unified up -d
fi

echo "Qdrant: http://127.0.0.1:${QDRANT_PORT:-6333}"
echo "Neo4j:  bolt://127.0.0.1:${NEO4J_BOLT_PORT:-7687}"
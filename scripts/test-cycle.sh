#!/usr/bin/env bash
# Elon algorithm: test → fix → repeat until green (max 5 rounds).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MAX_ROUNDS="${MAX_ROUNDS:-5}"
ROUND=1

cd "${ROOT}/mcp-server"
uv sync --all-extras

while [[ "${ROUND}" -le "${MAX_ROUNDS}" ]]; do
  echo "=== vault-memory test round ${ROUND}/${MAX_ROUNDS} ==="
  if uv run pytest -q ../tests tests; then
    echo "=== ALL TESTS PASSED (round ${ROUND}) ==="
    exit 0
  fi
  echo "=== Tests failed — fix and re-run (round ${ROUND}) ==="
  ROUND=$((ROUND + 1))
  sleep 1
done

echo "=== FAILED after ${MAX_ROUNDS} rounds ==="
exit 1
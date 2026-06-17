#!/usr/bin/env bash
# Elon algorithm: test → fix → repeat until green (max 5 rounds).
# Layers: unit → environment → integration (when Docker/services available).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MAX_ROUNDS="${MAX_ROUNDS:-5}"
ROUND=1

cd "${ROOT}/mcp-server"
uv sync --all-extras

_run_pytest() {
  local label="$1"
  shift
  echo "--- ${label} ---"
  uv run pytest -q "${ROOT}/tests" "$@"
}

while [[ "${ROUND}" -le "${MAX_ROUNDS}" ]]; do
  echo "=== vault-memory test round ${ROUND}/${MAX_ROUNDS} ==="

  if _run_pytest "unit + environment" -m "not integration" \
    && _run_pytest "integration" -m "integration"; then
    echo "=== ALL TESTS PASSED (round ${ROUND}) ==="
    exit 0
  fi

  echo "=== Tests failed — fix and re-run (round ${ROUND}) ==="
  ROUND=$((ROUND + 1))
  sleep 1
done

echo "=== FAILED after ${MAX_ROUNDS} rounds ==="
exit 1
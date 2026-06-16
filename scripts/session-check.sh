#!/usr/bin/env bash
# SessionStart hook — warn if vault-memory backends are unreachable.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="${VAULT_MEMORY_CONFIG:-${HOME}/.vault-memory/config.yaml}"

if [[ ! -f "${CONFIG}" ]]; then
  echo "[vault-memory] No config at ${CONFIG}. Run /vault-memory-setup or scripts/install.sh"
  exit 0
fi

cd "${ROOT}/mcp-server"
if command -v uv >/dev/null 2>&1; then
  uv run python - <<'PY' 2>/dev/null || true
import json, os, sys
sys.path.insert(0, "src")
os.environ.setdefault("VAULT_MEMORY_CONFIG", os.path.expanduser("~/.vault-memory/config.yaml"))
from vault_memory_mcp.sync import VaultSync
from vault_memory_mcp.config import load_config
h = VaultSync(load_config()).health()
issues = []
if not h.get("vault_exists"):
    issues.append("vault path missing")
if h.get("vector", {}).get("ok") is False:
    issues.append("qdrant unreachable")
if h.get("graph", {}).get("ok") is False:
    issues.append("neo4j unreachable")
if issues:
    print("[vault-memory] Session check:", ", ".join(issues))
    print("[vault-memory] Fix: skills/vault-memory-setup or docker compose -f docker/ up -d")
PY
fi
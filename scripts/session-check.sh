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
  VAULT_MEMORY_ROOT="${ROOT}" uv run python - <<'PY' 2>/dev/null || true
import json, os, sys
sys.path.insert(0, "src")
os.environ.setdefault("VAULT_MEMORY_CONFIG", os.path.expanduser("~/.vault-memory/config.yaml"))
from pathlib import Path
from vault_memory_mcp.resilience import ensure_config_and_vault
from vault_memory_mcp.sync import VaultSync
from vault_memory_mcp.curator import VaultCurator

root = Path(os.environ["VAULT_MEMORY_ROOT"])
cfg, mode, warnings = ensure_config_and_vault(repo_root_path=root, allow_fixture=False)
sync = VaultSync(cfg)
try:
    h = sync.health()
    issues = list(warnings)
    if mode == "missing":
        issues.append("vault path missing — run scripts/install.sh")
    elif not h.get("vault_exists"):
        issues.append("vault path missing")
    if h.get("graph", {}).get("ok") is False:
        issues.append("neo4j unreachable")
    if issues:
        print("[vault-memory] Session check:", ", ".join(issues))
        print("[vault-memory] Fix: bash scripts/install.sh && bash scripts/docker-up.sh")
    elif mode == "bootstrapped":
        print("[vault-memory] Bootstrapped vault at", h.get("vault"))
    if h.get("vault_exists") and mode != "missing":
        curator = VaultCurator(cfg, state_dir=sync.state_dir, graph=sync.graph)
        curator.maybe_run(dry_run=False)
finally:
    sync.close()
PY
fi

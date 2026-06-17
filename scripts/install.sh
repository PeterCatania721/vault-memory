#!/usr/bin/env bash
# Install vault-memory plugin dependencies (reproducible).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="${HOME}/.vault-memory"
CONFIG_FILE="${CONFIG_DIR}/config.yaml"
DEFAULT_VAULT="${CONFIG_DIR}/vault"

echo "==> vault-memory install"

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

if [[ ! -f "${CONFIG_FILE}" ]]; then
  mkdir -p "${CONFIG_DIR}"
  cp "${ROOT}/config/vault-memory.example.yaml" "${CONFIG_FILE}"
  echo "Created ${CONFIG_FILE}"
fi

# Bootstrap a usable vault path when missing (cloud / fresh install).
export VAULT_MEMORY_ROOT="${ROOT}"
cd "${ROOT}/mcp-server"
uv run python - <<'PY'
from pathlib import Path
import os
import yaml

root = Path(os.environ["VAULT_MEMORY_ROOT"])
config_file = Path.home() / ".vault-memory" / "config.yaml"
default_vault = Path.home() / ".vault-memory" / "vault"
data = yaml.safe_load(config_file.read_text()) or {}
vault_raw = (data.get("vault") or {}).get("path", "")
vault_path = Path(vault_raw or str(default_vault)).expanduser()

if not vault_path.exists():
    import sys
    sys.path.insert(0, str(root / "mcp-server" / "src"))
    from vault_memory_mcp.resilience import bootstrap_vault_dir, patch_config_vault_path
    from vault_memory_mcp.config import load_config

    target = default_vault if not vault_raw else vault_path
    bootstrap_vault_dir(target)
    cfg = load_config(config_file)
    patch_config_vault_path(cfg, target)
    print(f"Bootstrapped vault at {target}")
PY

uv sync --all-extras

echo "==> MCP server ready: uv run --directory ${ROOT}/mcp-server vault-memory-mcp"
echo "==> Vault: ${DEFAULT_VAULT} (edit ${CONFIG_FILE} to point at Obsidian)"
echo "==> Install plugin:"
echo "    grok plugin install ${ROOT} --trust"
echo "    # Claude Code: /plugin → Add from path → ${ROOT}"

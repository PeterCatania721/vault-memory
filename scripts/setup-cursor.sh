#!/usr/bin/env bash
# Install vault-memory for Cursor IDE (global MCP + optional local plugin symlink).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CURSOR_PLUGINS="${HOME}/.cursor/plugins/local"
CURSOR_GLOBAL_MCP="${HOME}/.cursor/mcp.json"
UV_BIN="$(command -v uv)"

echo "==> vault-memory Cursor setup"

bash "${ROOT}/scripts/install.sh"
bash "${ROOT}/scripts/docker-up.sh"

mkdir -p "${CURSOR_PLUGINS}" "${HOME}/.cursor"
TARGET="${CURSOR_PLUGINS}/vault-memory"
if [[ -L "${TARGET}" ]]; then
  rm "${TARGET}"
elif [[ -e "${TARGET}" ]]; then
  echo "Exists (not a symlink): ${TARGET} — skip plugin symlink"
  TARGET=""
fi
if [[ -n "${TARGET}" ]]; then
  ln -sf "${ROOT}" "${TARGET}"
  echo "Linked plugin: ${TARGET} -> ${ROOT}"
fi

# Global MCP — active in every Cursor workspace on this machine
cat > "${CURSOR_GLOBAL_MCP}" <<EOF
{
  "mcpServers": {
    "vault-memory": {
      "command": "${UV_BIN}",
      "args": [
        "run",
        "--directory",
        "${ROOT}/mcp-server",
        "vault-memory-mcp"
      ],
      "env": {
        "VAULT_MEMORY_CONFIG": "${HOME}/.vault-memory/config.yaml",
        "PATH": "${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
EOF
echo "Wrote global MCP config: ${CURSOR_GLOBAL_MCP}"

echo ""
echo "Project MCP also available: ${ROOT}/.cursor/mcp.json"
echo "1. Restart Cursor (or reload window)"
echo "2. Settings → Tools & MCP → enable vault-memory"
echo "3. In Agent chat: health_check → sync_vault force=true"

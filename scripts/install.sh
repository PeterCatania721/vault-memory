#!/usr/bin/env bash
# Install vault-memory plugin dependencies (reproducible).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="${HOME}/.vault-memory"
CONFIG_FILE="${CONFIG_DIR}/config.yaml"

echo "==> vault-memory install"

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

if [[ ! -f "${CONFIG_FILE}" ]]; then
  mkdir -p "${CONFIG_DIR}"
  cp "${ROOT}/config/vault-memory.example.yaml" "${CONFIG_FILE}"
  echo "Created ${CONFIG_FILE} — edit vault.path before first sync."
fi

cd "${ROOT}/mcp-server"
uv sync --all-extras

echo "==> MCP server ready: uv run --directory ${ROOT}/mcp-server vault-memory-mcp"
echo "==> Install plugin:"
echo "    grok plugin install ${ROOT} --trust"
echo "    # Claude Code: /plugin → Add from path → ${ROOT}"
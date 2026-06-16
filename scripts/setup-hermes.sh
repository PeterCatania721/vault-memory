#!/usr/bin/env bash
# Register vault-memory MCP in Hermes Agent (~/.hermes/config.yaml).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HERMES_CONFIG="${HOME}/.hermes/config.yaml"

cat <<EOF

Add to ${HERMES_CONFIG} under mcp_servers:

  vault_memory:
    command: uv
    args:
      - run
      - --directory
      - ${ROOT}/mcp-server
      - vault-memory-mcp
    env:
      VAULT_MEMORY_CONFIG: ${HOME}/.vault-memory/config.yaml

Then: hermes mcp test vault_memory

Skills: symlink or tap MySkills, or copy skills/ into ~/.hermes/skills/vault-memory/

EOF
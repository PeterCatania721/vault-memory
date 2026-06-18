#!/usr/bin/env bash
# Install vault-memory for Cursor IDE (MCP + optional local plugin symlink).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CURSOR_PLUGINS="${HOME}/.cursor/plugins/local"
CURSOR_SKILLS="${HOME}/.cursor/skills"

echo "==> vault-memory Cursor setup"

bash "${ROOT}/scripts/install.sh"
bash "${ROOT}/scripts/docker-up.sh"

mkdir -p "${CURSOR_PLUGINS}"
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

mkdir -p "${CURSOR_SKILLS}"
for skill in "${ROOT}"/skills/*/; do
  name="$(basename "${skill}")"
  target="${CURSOR_SKILLS}/${name}"
  if [[ -L "${target}" ]]; then
    rm "${target}"
  elif [[ -e "${target}" ]]; then
    echo "Skill exists (not a symlink): ${target} — skip"
    continue
  fi
  ln -sf "${skill%/}" "${target}"
  echo "Linked skill: ${target} -> ${skill%/}"
done

echo ""
echo "Cursor MCP: ${ROOT}/.cursor/mcp.json (uses \${workspaceFolder})"
echo "1. Open this folder in Cursor: ${ROOT}"
echo "2. Restart Cursor (or reload window)"
echo "3. Settings → Tools & MCP → enable vault-memory"
echo "4. In Agent chat: health_check → sync_vault force=true"
echo ""
echo "Global MCP (all projects): copy .cursor/mcp.json to ~/.cursor/mcp.json"
echo "  and replace \${workspaceFolder} with: ${ROOT}"

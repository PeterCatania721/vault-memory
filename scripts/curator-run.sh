#!/usr/bin/env bash
# Elon algorithm: curator dry-run → review → live run (max 3 rounds in test mode).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FORCE="${FORCE:-false}"
DRY="${DRY:-false}"

cd "${ROOT}/mcp-server"
uv sync --all-extras

uv run python - <<PY
import json, os, sys
sys.path.insert(0, "src")
os.environ.setdefault("VAULT_MEMORY_CONFIG", os.path.expanduser("~/.vault-memory/config.yaml"))
from vault_memory_mcp.config import load_config
from vault_memory_mcp.curator import VaultCurator
from vault_memory_mcp.sync import VaultSync

cfg = load_config()
sync = VaultSync(cfg)
curator = VaultCurator(cfg, state_dir=sync.state_dir, graph=sync.graph)
dry = "${DRY}" == "true"
force = "${FORCE}" == "true"
if force or dry:
    result = curator.run(dry_run=dry)
else:
    result = curator.maybe_run(dry_run=False)
    if result is None:
        print(json.dumps({"skipped": True, "status": curator.status()}, indent=2))
        sys.exit(0)
print(json.dumps(result.to_dict(), indent=2))
PY
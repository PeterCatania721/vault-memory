# vault-memory status

**Version:** 0.1.1  
**Status:** Stable — tested and installed  
**Last verified:** 2026-06-16

## Test results

| Suite | Result |
|-------|--------|
| Unit tests (6) | Pass |
| Integration (Docker: Qdrant + Neo4j) | Pass |
| `grok plugin validate` | Pass |
| Grok Build install | Installed (`vault-memory`) |

## Agent support

| Agent | Status | Install |
|-------|--------|---------|
| Grok Build | Verified | `grok plugin install PeterCatania721/vault-memory --trust` |
| Claude Code | Ready | `/plugin` → local or GitHub path |
| Hermes Agent | Ready | `bash scripts/setup-hermes.sh` |

## Components

- MCP server: 10 tools (health, config, vault, vector, graph, sync)
- Skills: `vault-memory-setup`, `vault-memory-sync`, `vault-memory-query`
- Hooks: SessionStart health check
- Docker: Qdrant v1.12.5 + Neo4j 5.26.0 (unified or separate)

## Known requirements

- `uv` for MCP server
- Docker for vector/graph backends (or existing Qdrant/Neo4j instances)
- Obsidian vault path in `~/.vault-memory/config.yaml`
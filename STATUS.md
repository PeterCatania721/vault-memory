# vault-memory status

**Version:** 0.1.2  
**Status:** Stable — tested and installed  
**Last verified:** 2026-06-16

## Test results

| Suite | Result |
|-------|--------|
| Unit + environment tests (63) | Pass |
| Integration (Docker: Qdrant + Neo4j) | Pass |
| Triple memory correction | 3/3 pass |
| Elon 5-step audit | Pass |
| `scripts/test-cycle.sh` | Pass |

## Agent support

| Agent | Status | Install |
|-------|--------|---------|
| Grok Build | Verified | `grok plugin install PeterCatania721/vault-memory --trust` |
| Claude Code | Ready | `/plugin` → local or GitHub path |
| Hermes Agent | Ready | `bash scripts/setup-hermes.sh` → `Projects/vault-memory/mcp-server` (18 tools) |

## Components

- MCP server: **18 tools** (health, config, vault, vector, graph, sync, curator, correction)
- Skills: `vault-memory-setup`, `vault-memory-sync`, `vault-memory-query`, `vault-memory-curator`
- Hooks: SessionStart health check
- Docker: Qdrant v1.12.5 + Neo4j 5.26.0 (unified or separate)
- Curator: Elon-style archive/compress with pin/protect rules

## MCP tools

| Category | Tools |
|----------|-------|
| Core | `health_check`, `get_config`, `update_config`, `sync_vault` |
| Read/search | `list_vault_notes`, `read_vault_note`, `search_vault_keyword`, `search_vault_semantic` |
| Graph | `graph_neighbors`, `graph_query` |
| Curator | `curator_status`, `run_curator`, `curator_pin`, `curator_unpin`, `curator_restore` |
| Correction | `mark_vault_note_invalid`, `set_vault_note_expiry`, `delete_vault_note` |

## Known requirements

- `uv` for MCP server
- Docker for vector/graph backends (or existing Qdrant/Neo4j instances)
- Obsidian vault path in `~/.vault-memory/config.yaml`
- Run `sync_vault force=true` after graph drift (Neo4j should match vault note count)
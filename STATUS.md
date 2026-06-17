# vault-memory status

**Version:** 0.2.4  
**Status:** Stable — Elon-simplified, cloud-tested  
**Last verified:** 2026-06-17 (cloud VM + Neo4j 5.26 Docker)

## Test results

| Suite | Result |
|-------|--------|
| Unit + environment tests (87) | Pass |
| Integration (Docker: Neo4j) | Pass (9) |
| **Total** | **96 pass** |

## MCP tools: 25

| Category | Tools |
|----------|-------|
| Core | `health_check`, `get_config`, `update_config`, `sync_vault` |
| Read/search | `list_vault_notes`, `read_vault_note`, `search_vault_keyword`, `search_vault_semantic`, `search_vault_hybrid` |
| Agent | `add_agent_memory`, `query_agent_guidance` |
| Provenance | `add_research_memory`, `upsert_note_provenance`, `provenance_trail`, `query_stale_facts` |
| Graph | `graph_neighbors`, `graph_query` |
| Curator | `curator_status`, `run_curator`, `curator_pin`, `curator_unpin`, `curator_restore` |
| Correction | `mark_vault_note_invalid`, `set_vault_note_expiry`, `delete_vault_note` |

## Two-tier memory (agentic)

| Layer | Store | Use |
|-------|-------|-----|
| Concrete | Neo4j `:TestRun` | command, cwd, exit_code, expected, actual |
| Abstract | Obsidian `Memory/Agent/` | solutions, anti-patterns, lessons |

## Removed in v0.2.4

- `search_vault_graphrag` → use `search_vault_hybrid`
- Qdrant migration script → `scripts/archive/`
- `docker-compose.separate.yml` → use `docker/docker-compose.yml` only
- `:Verification` vector index (unused)

## Cloud Docker

```bash
bash scripts/docker-up.sh   # auto-starts dockerd on restricted VMs
```

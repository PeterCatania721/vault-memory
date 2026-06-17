# vault-memory status

**Version:** 0.2.3  
**Status:** Stable — agentic memory layers, cloud-tested with Docker Neo4j  
**Last verified:** 2026-06-17 (cloud VM + Neo4j 5.26 Docker)

## Test results

| Suite | Result |
|-------|--------|
| Unit + environment tests (72) | Pass |
| Integration (Docker: Neo4j) | Pass (9) |
| Agent memory graph chain | Pass |
| Provenance graph chain | Pass |
| `scripts/test-cycle.sh` | Pass |
| **Total** | **81 pass** |

## Agent support

| Agent | Status | Install |
|-------|--------|---------|
| Grok Build | Verified | `grok plugin install PeterCatania721/vault-memory --trust` |
| Claude Code | Ready | `/plugin` → local or GitHub path |
| Hermes Agent | Ready | `bash scripts/setup-hermes.sh` → `Projects/vault-memory/mcp-server` (26 tools) |

## Components

- MCP server: **26 tools** (health, config, vault, hybrid search, agent guidance, provenance, graph, sync, curator, correction)
- Skills: `vault-memory-setup`, `vault-memory-sync`, `vault-memory-query`, `vault-memory-curator`
- Hooks: SessionStart health check
- Docker: **Neo4j 5.26.0 only** (1 container)
- Agent memory: `Memory/Agent/{Solutions,Anti-Patterns,Lessons}/` + concrete `:TestRun` in Neo4j
- Curator: rule-based archive + Elon-style compress; protects agent memory paths
- Provenance: Fact/Source/TestRun/Version/System nodes in Neo4j

## Two-tier memory (agentic)

| Layer | Store | Use |
|-------|-------|-----|
| Concrete | Neo4j `:TestRun` | command, cwd, exit_code, expected, actual — recreation |
| Abstract | Obsidian `Memory/Agent/` | solutions, anti-patterns, lessons — planning |

## MCP tools

| Category | Tools |
|----------|-------|
| Core | `health_check`, `get_config`, `update_config`, `sync_vault` |
| Read/search | `list_vault_notes`, `read_vault_note`, `search_vault_keyword`, `search_vault_semantic`, `search_vault_hybrid`, `search_vault_graphrag` |
| Agent | `add_agent_memory`, `query_agent_guidance` |
| Provenance | `add_research_memory`, `upsert_note_provenance`, `provenance_trail`, `query_stale_facts` |
| Graph | `graph_neighbors`, `graph_query` |
| Curator | `curator_status`, `run_curator`, `curator_pin`, `curator_unpin`, `curator_restore` |
| Correction | `mark_vault_note_invalid`, `set_vault_note_expiry`, `delete_vault_note` |

## Known requirements

- `uv` for MCP server
- Docker for Neo4j (or existing Neo4j instance at `graph.uri`)
- Obsidian vault path in `~/.vault-memory/config.yaml`
- `vector.provider: neo4j` in config (default in v0.2+)
- Run `sync_vault force=true` after graph drift
- Restart Grok/Hermes MCP after upgrade to load new tool descriptors

## Cloud Docker note

On restricted cloud VMs, start Docker with:

```bash
sudo dockerd --iptables=false --storage-driver=vfs &
bash scripts/docker-up.sh
```

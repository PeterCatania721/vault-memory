# vault-memory

[![Status](https://img.shields.io/badge/status-stable%20(v0.2.1)-green)](STATUS.md)
[![Tests](https://img.shields.io/badge/tests-70%2F70%20passing-brightgreen)](STATUS.md)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Cross-agent plugin for **Obsidian + Neo4j** memory (graph + vector embeddings + provenance). Works with **Grok Build**, **Claude Code**, and **Hermes Agent**.

Built from patterns engineers use successfully: markdown vault as source of truth, local embeddings, single Docker database, MCP stdio, incremental sync.

> **Current status:** v0.2.1 — Neo4j-only, provenance GraphRAG, 24 MCP tools, [full details in STATUS.md](STATUS.md).

## Architecture

```
Obsidian vault (.md) — source of truth + YAML provenance on Memory/ notes
       │
       ├─► Keyword search (filesystem)
       └─► Neo4j (single store)
              ├─► :Note + LINKS_TO (wikilinks)
              ├─► :Chunk + vector index (semantic search)
              ├─► :Verification + embeddings (test evidence)
              └─► :Fact → :Source → :TestRun (provenance graph)
                     │
                     ▼
              vault-memory MCP (stdio)
                     │
           Grok / Claude Code / Hermes
```

### Why Neo4j-only (v0.2+)

v0.1.x used **Qdrant + Neo4j** (2 Docker containers, dual sync/prune). v0.2+ consolidates vectors and graph in Neo4j for simpler ops and native GraphRAG (`search_vault_hybrid`). Qdrant is no longer required. See [RELEASE-NOTES.md](RELEASE-NOTES.md).

## Quick start

```bash
git clone https://github.com/PeterCatania721/vault-memory.git
cd vault-memory
bash scripts/install.sh
bash scripts/docker-up.sh
# Edit ~/.vault-memory/config.yaml → set vault.path, vector.provider: neo4j
grok plugin install . --trust   # or Claude /plugin local path
```

## MCP tools (highlights)

| Tool | Purpose |
|------|---------|
| `health_check` | Vault + Neo4j status |
| `search_vault_hybrid` | **Default** — semantic + graph + provenance |
| `search_vault_semantic` | Neo4j vector search on chunks |
| `provenance_trail` / `query_stale_facts` | Audit sources and stale facts |
| `add_research_memory` | Write provenance-structured Memory/ note |
| `graph_neighbors` / `graph_query` | Wikilink graph + Cypher |
| `sync_vault` | Index / reindex |
| `run_curator` | Rule-based archive (spoil + verified_in) |

Full list in [STATUS.md](STATUS.md).

## Docker

**One container** — Neo4j 5.26 (graph + vector indexes):

```bash
docker compose -f docker/docker-compose.yml --profile unified up -d
```

Legacy Qdrant is not used. If an old `qdrant` container is still running, stop and remove it.

## Pinned versions

| Component | Version |
|-----------|---------|
| Neo4j | 5.26.0-community |
| neo4j (Python) | 5.26.0 |
| sentence-transformers | 3.3.1 |
| vault-memory-mcp | 0.2.1 |

## Tests (Elon loop)

```bash
bash scripts/test-cycle.sh          # unit tests, retry until green
pytest -m integration                 # needs Docker (Neo4j only)
```

## Skills

- `vault-memory-setup` — install, Docker, config
- `vault-memory-sync` — index vault
- `vault-memory-query` — hybrid search + graph
- `vault-memory-curator` — rule-based maintenance

## License

MIT
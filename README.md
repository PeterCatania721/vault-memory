# vault-memory

[![Status](https://img.shields.io/badge/status-stable%20(v0.1.2)-green)](STATUS.md)
[![Tests](https://img.shields.io/badge/tests-63%2F63%20passing-brightgreen)](STATUS.md)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Cross-agent plugin for **Obsidian + Qdrant + Neo4j** memory. Works with **Grok Build**, **Claude Code**, and **Hermes Agent**.

Built from patterns engineers use successfully: markdown vault as source of truth, local embeddings, Docker-pinned databases, MCP stdio, incremental sync.

> **Current status:** v0.1.2 — 18 MCP tools, curator + correction, [full details in STATUS.md](STATUS.md).

## Architecture

```
Obsidian vault (.md)
       │
       ├─► Keyword search (filesystem)
       ├─► Qdrant (semantic chunks + embeddings)
       └─► Neo4j (Note nodes, LINKS_TO from [[wikilinks]])
              │
              ▼
        vault-memory MCP (stdio)
              │
    Grok / Claude Code / Hermes
```

## Quick start

```bash
git clone https://github.com/PeterCatania721/vault-memory.git
cd vault-memory
bash scripts/install.sh
bash scripts/docker-up.sh
# Edit ~/.vault-memory/config.yaml → set vault.path
grok plugin install . --trust   # or Claude /plugin local path
```

## MCP tools

| Tool | Purpose |
|------|---------|
| `health_check` | Vault + DB status |
| `get_config` / `update_config` | AI-driven configuration |
| `list_vault_notes` / `read_vault_note` | Direct vault access |
| `search_vault_keyword` | FTS-style search |
| `search_vault_semantic` | Qdrant vector search |
| `graph_neighbors` / `graph_query` | Neo4j wikilink graph |
| `sync_vault` | Index / reindex |

## Docker

**Unified** (default): both DBs in one compose file.

```bash
docker compose -f docker/docker-compose.yml --profile unified up -d
```

**Separate**: one container per DB (easier independent updates).

```bash
docker compose -f docker/docker-compose.separate.yml --profile vector up -d
docker compose -f docker/docker-compose.separate.yml --profile graph up -d
```

Set `docker.mode: unified|separate` in config.

## Pinned versions

| Component | Version |
|-----------|---------|
| Qdrant | v1.12.5 |
| Neo4j | 5.26.0-community |
| qdrant-client | 1.12.1 |
| neo4j (Python) | 5.26.0 |
| sentence-transformers | 3.3.1 |

## Tests (Elon loop)

```bash
bash scripts/test-cycle.sh          # unit tests, retry until green
pytest -m integration             # needs Docker
```

## Skills

- `vault-memory-setup` — install, Docker, config
- `vault-memory-sync` — index vault
- `vault-memory-query` — search + graph

## License

MIT
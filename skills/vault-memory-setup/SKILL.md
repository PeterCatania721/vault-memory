---
name: vault-memory-setup
description: >
  Install and configure vault-memory (Obsidian + Neo4j graph/vector). Use when setting up
  the plugin, starting Docker, editing ~/.vault-memory/config.yaml, or runs
  /vault-memory-setup. Software 3.0 — read config with get_config, update with update_config.
---

# vault-memory Setup

Stack: **Obsidian markdown vault** (source of truth) → **Neo4j** (wikilinks + chunk embeddings + provenance graph) → **MCP stdio** (Grok, Claude Code, Hermes).

**v0.2+:** One Docker container (Neo4j). Qdrant is not used.

## Quick install

```bash
cd /path/to/vault-memory
bash scripts/install.sh
bash scripts/docker-up.sh
```

Edit `~/.vault-memory/config.yaml`:

```yaml
vault:
  path: ~/Documents/Obsidian Vault
vector:
  enabled: true
  provider: neo4j
graph:
  enabled: true
  uri: bolt://127.0.0.1:7687
```

## Grok Build

```bash
grok plugin install /path/to/vault-memory --trust
```

Trust activates MCP + hooks. Open `/mcps` and confirm `vault-memory` is connected.

## Claude Code

`/plugin` → Add plugin → local path `/path/to/vault-memory` → trust MCP.

## Hermes Agent

```bash
bash scripts/setup-hermes.sh
hermes mcp test vault_memory
```

## Docker

```bash
docker compose -f docker/docker-compose.yml --profile unified up -d
```

Only Neo4j starts. Remove legacy Qdrant if still present: `docker rm -f qdrant`.

## Verify

Call MCP `health_check`. Expect: vault path OK, `store: neo4j`, graph + vector OK.

Then `sync_vault force=true` once to index notes.
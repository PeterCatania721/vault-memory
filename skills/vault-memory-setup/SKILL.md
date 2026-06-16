---
name: vault-memory-setup
description: >
  Install and configure vault-memory (Obsidian + Qdrant + Neo4j). Use when setting up
  the plugin, starting Docker databases, editing ~/.vault-memory/config.yaml, or runs
  /vault-memory-setup. Software 3.0 — read config with get_config, update with update_config.
---

# vault-memory Setup

Battle-tested stack: **Obsidian markdown vault** (source of truth) → **Qdrant** (semantic search) → **Neo4j** (wikilink graph) → **MCP stdio** (Grok, Claude Code, Hermes).

## Quick install

```bash
cd /path/to/vault-memory
bash scripts/install.sh
bash scripts/docker-up.sh
```

Edit `~/.vault-memory/config.yaml` — set `vault.path` to your Obsidian vault.

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

## Docker modes

| Mode | Command |
|------|---------|
| **unified** (default) | `docker compose -f docker/docker-compose.yml --profile unified up -d` |
| **separate** | `bash scripts/docker-up.sh separate` |

Set `docker.mode` in config; AI can change via `update_config` MCP tool.

## Verify

Call MCP tool `health_check`. All three should be healthy: vault path, qdrant, neo4j.

Then call `sync_vault` once to index notes.